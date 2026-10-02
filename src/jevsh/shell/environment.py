"""Variable expansion and the export/unset builtins.

Only $NAME and ${NAME} are recognized. That is deliberate and is what makes
command substitution inert: `$(touch x)` has no NAME after the `$`, so it falls
through as literal text and no command is ever run from an expansion.
"""
import re

# Carried over from Stage 1. Anything fancier -- $(...), ${VAR:-default},
# $((...)) -- is explicitly out of scope, so it stays literal.
VARIABLE = re.compile(r"\$(\w+)|\$\{(\w+)\}")


def substitute(text: str, env: dict[str, str]) -> str:
    """Replace $NAME / ${NAME} from env. Unset names become empty, as in sh."""
    return VARIABLE.sub(
        lambda match: env.get(match.group(1) or match.group(2), ""),
        text,
    )


def apply_tilde(text: str, env: dict[str, str]) -> str:
    """Expand a leading ~ to $HOME. `~user` is not supported and stays literal."""
    home = env.get("HOME")

    if home and text.startswith("~") and (len(text) == 1 or text[1] == "/"):
        return home + text[1:]

    return text


def builtin_export(args: list[str], session) -> int:
    if not args:
        for name in sorted(session.environment):
            print(f"export {name}={session.environment[name]}")
        return 0

    for arg in args:
        name, separator, value = arg.partition("=")

        if not name or not name.replace("_", "").isalnum() or name[0].isdigit():
            print(f"jevsh: export: `{arg}': not a valid identifier")
            return 1

        if separator:
            session.environment[name] = value
        elif name not in session.environment:
            # Marking an unset name for export has no effect for us; make that
            # visible rather than silently doing nothing.
            session.environment[name] = ""

    return 0


def builtin_unset(args: list[str], session) -> int:
    for name in args:
        session.environment.pop(name, None)

    return 0
