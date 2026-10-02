"""Commands the shell must run itself.

`cd` is the reason this module exists. A subprocess cannot change its parent's
directory, so `cd` has to mutate the ShellSession directly. The rest are here
because they read session state the outside world cannot see.

Every builtin takes (args, session) and returns an exit code, so the REPL can
treat builtins and external commands identically.
"""
from .aliases import builtin_alias, builtin_unalias
from .environment import builtin_export, builtin_unset
from .jobs import builtin_jobs
from .session import ShellSession


class ExitShell(Exception):
    """Raised by exit/quit to unwind the REPL with a status."""

    def __init__(self, code: int = 0):
        super().__init__(code)
        self.code = code


def builtin_cd(args: list[str], session: ShellSession) -> int:
    if len(args) > 1:
        print("jevsh: cd: too many arguments")
        return 1

    target = args[0] if args else None
    error = session.change_directory(target)

    if error:
        print(error)
        return 1

    # bash echoes the destination for `cd -`; it is otherwise invisible.
    if target == "-":
        print(session.cwd)

    return 0


def builtin_pwd(args: list[str], session: ShellSession) -> int:
    # The session, not os.getcwd() -- they are intentionally different.
    print(session.cwd)
    return 0


def builtin_exit(args: list[str], session: ShellSession) -> int:
    if not args:
        raise ExitShell(session.last_exit_code)

    try:
        raise ExitShell(int(args[0]))
    except ValueError:
        print(f"jevsh: exit: {args[0]}: numeric argument required")
        return 2


def builtin_clear(args: list[str], session: ShellSession) -> int:
    # Erase the screen and home the cursor. No subprocess needed.
    print("\033[2J\033[H", end="")
    return 0


def builtin_history(args: list[str], session: ShellSession) -> int:
    entries = list(enumerate(session.history, start=1))

    if args:
        try:
            count = int(args[0])
        except ValueError:
            print(f"jevsh: history: {args[0]}: numeric argument required")
            return 1

        entries = entries[-count:] if count > 0 else []

    width = len(str(len(session.history)))

    for number, line in entries:
        print(f"{number:>{width}}  {line}")

    return 0


# One dispatch table, so "is this a builtin" stays a single lookup. The logic
# for the Stage 2 entries lives in its own module; only the wiring is here.
BUILTINS = {
    "cd": builtin_cd,
    "pwd": builtin_pwd,
    "exit": builtin_exit,
    "quit": builtin_exit,
    "clear": builtin_clear,
    "history": builtin_history,
    "alias": builtin_alias,
    "unalias": builtin_unalias,
    "export": builtin_export,
    "unset": builtin_unset,
    "jobs": builtin_jobs,
}
