"""Which paths are off limits, and how to resolve a path before judging it.

String comparison is not enough. `.`, `..`, `~`, a relative path and a symlink
can all name the same directory, so every path is canonicalized before any
destructive decision is made.
"""
import os
import tempfile
from pathlib import Path


def _resolved(*candidates: str) -> frozenset[Path]:
    """Resolve each candidate, dropping any that does not exist.

    Resolving at build time matters on macOS, where /etc, /var and /tmp are all
    symlinks into /private. Comparing an unresolved /var against a resolved
    /private/var/... would never match.
    """
    found = set()

    for candidate in candidates:
        path = Path(candidate)

        if path.exists():
            found.add(path.resolve())

    return frozenset(found)


# Platform-aware, so this is not a Unix-only policy. Note /private is absent on
# purpose: it is the parent of /private/tmp and /private/var/folders, so
# protecting it would take the system temp directory with it.
if os.name == "nt":
    SYSTEM_PATHS = _resolved(
        r"C:\Windows", r"C:\Program Files", r"C:\Program Files (x86)", r"C:\ProgramData"
    )
else:
    SYSTEM_PATHS = _resolved(
        "/etc", "/bin", "/sbin", "/usr", "/var", "/lib", "/lib64",
        "/boot", "/dev", "/proc", "/sys", "/System", "/Library",
    )

# Temp space exists to be written to and deleted, so it is exempt even though it
# lives under /var on macOS. Without this, every pytest tmp_path would be
# blocked, since pytest puts them in /private/var/folders/...
TEMP_PATHS = _resolved(tempfile.gettempdir(), "/tmp", "/var/tmp")


def canonicalize(path, cwd=None, env=None) -> Path:
    """Absolute, symlink-resolved form of a user-supplied path.

    Relative paths resolve against the *session* cwd, never os.getcwd(), because
    jevsh never chdir()s the host process.

    Nonexistent paths are fine: resolve() is non-strict. Be aware it collapses
    `..` textually through missing directories, so a path through a nonexistent
    parent can land somewhere unexpected. That errs toward refusing, which is
    the safe direction here.
    """
    text = str(path)

    if text.startswith("~"):
        home = (env or {}).get("HOME")
        if home and (len(text) == 1 or text[1] == "/"):
            text = home + text[1:]
        else:
            text = os.path.expanduser(text)

    candidate = Path(text)

    if not candidate.is_absolute() and cwd is not None:
        candidate = Path(cwd) / candidate

    try:
        return candidate.expanduser().resolve()
    except (OSError, RuntimeError):
        # Unresolvable (a symlink loop, say). Hand back something absolute so
        # the caller still has a path to refuse.
        return Path(os.path.abspath(text))


def home_directory(env=None) -> Path:
    """Home per the session environment, falling back to the real one."""
    home = (env or {}).get("HOME")

    try:
        return Path(home).resolve() if home else Path.home().resolve()
    except (OSError, RuntimeError):
        return Path.home()


def is_protected(path, env=None) -> bool:
    """True for the filesystem root, a home directory, or any parent of one.

    Both the session's HOME and the real one are checked. A session must be able
    to protect the home it actually uses, and must not be able to unprotect the
    real one by pointing HOME somewhere else.
    """
    target = Path(path)

    if target == Path(target.anchor):
        return True

    homes = {home_directory(env)}

    try:
        homes.add(Path.home().resolve())
    except (OSError, RuntimeError):
        pass

    for home in homes:
        if target == home:
            return True

        # A directory that contains a home takes that home down with it.
        try:
            home.relative_to(target)
            return True
        except ValueError:
            continue

    return False


def is_temp(path) -> bool:
    target = Path(path)

    return any(target == temp or temp in target.parents for temp in TEMP_PATHS)


def is_system(path) -> bool:
    """True inside a critical system location, unless it is temp space.

    Temp is checked first because /var/folders sits under the protected /var.
    """
    target = Path(path)

    if is_temp(target):
        return False

    return any(target == system or system in target.parents for system in SYSTEM_PATHS)


def is_protected_path(path) -> bool:
    """Backwards-compatible predicate used by the Jev layer since Stage 2."""
    return is_protected(canonicalize(path))
