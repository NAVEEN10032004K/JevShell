"""The interactive loop.

Deliberately knows nothing about Jev. The AI layer becomes an optional thing
layered on top of this later; today an unrecognized command is just a shell
error, exactly as it would be in sh.
"""
from .. import config, ui
from .aliases import AliasError
from .builtins import ExitShell
from .executor import execute
from .parser import ParseError, parse
from .session import ShellSession
from ..  import __version__

BANNER = "JevShell"

try:
    # Gives arrow-key line editing and in-line history for free. No completer is
    # registered, so tab completion stays out of this stage.
    import readline  # noqa: F401
except ImportError:
    pass


def ask_to_confirm(result) -> bool:
    """Prompt a human about a CONFIRM result.

    Only an explicit yes proceeds. Empty input, anything else, and Ctrl+C or
    Ctrl+D at the prompt all cancel.
    """
    print(ui.confirmation(result))

    try:
        answer = input("Continue? [y/N]: ")
    except (EOFError, KeyboardInterrupt):
        print()
        print("Cancelled.")
        return False

    if answer.strip().lower() in {"y", "yes"}:
        return True

    print("Cancelled.")
    return False


def format_prompt(session: ShellSession) -> str:
    """`jevsh ~/path>`, built from session state alone -- never a syscall or a
    network call, so the prompt costs nothing to draw."""
    cwd = str(session.cwd)
    home = str(session.home())

    if cwd == home:
        display = "~"
    elif cwd.startswith(home + "/"):
        display = "~" + cwd[len(home):]
    else:
        display = cwd

    return f"jevsh {display}> "


def dispatch(line: str, session: ShellSession) -> int:
    """Run one line, as a shell command or as a natural-language request.

    Routing is deterministic and offline, so an ordinary shell command never
    costs a network round trip.
    """
    from ..jev_router import InputType, handle_natural_language, route_input

    if route_input(line, session) is InputType.NATURAL_LANGUAGE:
        return handle_natural_language(line, session)

    try:
        tree = parse(
            line,
            env=session.environment,
            cwd=session.cwd,
            aliases=session.aliases,
        )
    except (ParseError, AliasError) as error:
        print(error)
        return 2

    if not tree.items:
        return session.last_exit_code

    return execute(tree, session, line)


def run_repl(session: ShellSession | None = None) -> int:
    session = session or ShellSession()

    # There is a human here, so CONFIRM can actually ask one.
    session.confirm = ask_to_confirm

    config.configure_logging()

    print(f"{BANNER} {__version__}")
    print()

    while True:
        try:
            line = input(format_prompt(session))

        except KeyboardInterrupt:
            # Ctrl+C at the prompt abandons the line, it does not quit.
            print()
            continue

        except EOFError:
            # Ctrl+D on an empty prompt is a clean exit.
            print()
            return session.last_exit_code

        if not line.strip():
            continue

        # Recorded before running so `history` includes itself, per the spec.
        session.record(line)

        try:
            session.last_exit_code = dispatch(line, session)
        except ExitShell as exit_request:
            return exit_request.code
        except KeyboardInterrupt:
            # Ctrl+C raised inside a command rather than at the prompt: a Jev
            # request is the usual case, since a blocking HTTP call has no
            # interrupt handling of its own. Abandon it and carry on.
            print()
            session.last_exit_code = 130

    return session.last_exit_code
