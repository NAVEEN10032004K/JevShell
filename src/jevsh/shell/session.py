"""The state that has to outlive a single command.

A real shell remembers where it is. That is the whole reason this class exists:
`cd` cannot work in a process that exits after every command. One ShellSession
is created when the REPL starts and threaded through every command after that.

`os.chdir` is deliberately never called. The session's cwd is passed to each
subprocess instead, which keeps the host Python process's own cwd untouched and
stops tests from leaking directory changes into one another.
"""
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


# Assignments whose value should never be kept. Matches the name, not the value,
# so there is nothing secret in this pattern itself.
SECRET_ASSIGNMENT = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*\s*=",
    re.IGNORECASE,
)


def deny_without_a_terminal(result) -> bool:
    """The default answer to a CONFIRM, for any non-interactive caller.

    Denying by default is the whole point: a script, a pipe or a test must never
    silently run a command that would have asked a human first. The REPL replaces
    this with a real prompt.
    """
    print(f"Safety: {result.level.value.upper()}")
    print("Execution skipped: confirmation required in interactive mode.")

    return False


@dataclass
class ShellSession:
    cwd: Path = field(default_factory=Path.cwd)
    environment: dict[str, str] = field(default_factory=lambda: dict(os.environ))
    history: list[str] = field(default_factory=list)
    previous_cwd: Path | None = None
    last_exit_code: int = 0
    aliases: dict[str, str] = field(default_factory=dict)
    jobs: list = field(default_factory=list)
    next_job_id: int = 1
    confirm: Callable = deny_without_a_terminal

    def home(self) -> Path:
        """Home per the session's own environment, so tests can point it elsewhere."""
        return Path(self.environment.get("HOME") or Path.home())

    def resolve(self, target: str) -> Path:
        """Turn a user-supplied path into an absolute one, relative to this session."""
        path = Path(target).expanduser()

        if not path.is_absolute():
            path = self.cwd / path

        # normpath collapses ".." textually, which is what a shell shows the user.
        # resolve() would follow symlinks and report the physical path instead.
        return Path(os.path.normpath(path))

    def record(self, line: str) -> None:
        """Append to history, unless the line looks like it carries a secret.

        A pasted `export TYPESAFE_API_KEY=...` would otherwise sit in the
        history buffer for the rest of the session.
        """
        if SECRET_ASSIGNMENT.search(line):
            return

        self.history.append(line)

    def change_directory(self, target: str | None = None) -> str | None:
        """Move the session. Returns an error message, or None on success.

        Every failure is a message rather than an exception: a bad `cd` must not
        take the shell down with it.
        """
        if target is None or target == "~":
            destination = self.home()

        elif target == "-":
            if self.previous_cwd is None:
                return "jevsh: cd: OLDPWD not set"

            destination = self.previous_cwd

        else:
            destination = self.resolve(target)

        try:
            if not destination.exists():
                return f"jevsh: cd: {target or destination}: No such file or directory"

            if not destination.is_dir():
                return f"jevsh: cd: {target or destination}: Not a directory"

            # Permission to enter a directory is execute, not read. Listing it is
            # the cheapest honest check, and it is what the next command will need.
            os.listdir(destination)

        except PermissionError:
            return f"jevsh: cd: {target or destination}: Permission denied"
        except (NotADirectoryError, FileNotFoundError):
            return f"jevsh: cd: {target or destination}: No such file or directory"
        except OSError as error:
            return f"jevsh: cd: {target or destination}: {error.strerror}"

        self.previous_cwd = self.cwd
        self.cwd = destination
        self.environment["PWD"] = str(destination)

        return None
