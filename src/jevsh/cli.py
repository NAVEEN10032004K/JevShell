import argparse
import sys

from . import __version__, config

from .jev_router import handle_natural_language
from .safety import evaluate
from .shell import ShellSession, run_repl
from .shell.aliases import AliasError
from .shell.parser import ParseError, parse

# Aliased: .executor.execute runs a Jev Action, this one runs a shell command
# tree. Importing both under one name silently broke the Jev path.
from .shell.executor import execute as execute_shell


EPILOG = """\
examples:
  jevsh                                 start the interactive shell
  jevsh -c "ls | grep .py"              run one shell command and exit
  jevsh --dry-run -c "rm notes.txt"     show the safety decision, run nothing
  jevsh "create a folder called src"    ask Jev, then run it through safety

interactive builtins:
  cd  pwd  history  clear  alias  unalias  export  unset  jobs  exit  quit
  ai <request>                          send a request to Jev explicitly

environment:
  TYPESAFE_API_KEY      enables natural-language commands
  JEVSH_JEV_ENABLED=0   disable Jev; everything runs as a shell command
  JEVSH_LOG_LEVEL=DEBUG diagnostics on stderr (never secrets)
  NO_COLOR              disable colored output

exit codes:
  0 success                 1 command failed        2 invalid input
  77 refused by policy      126 not executable      127 command not found
  130 interrupted
"""


def main():
    parser = argparse.ArgumentParser(
        prog="jevsh",
        description="JevShell -- a Unix shell with a deterministic safety policy "
                    "and optional natural-language commands.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"jevsh {__version__}",
    )

    parser.add_argument(
        "command",
        nargs="*",
        help="Natural-language command. Omit to start the interactive shell.",
    )

    parser.add_argument(
        "-c",
        "--command",
        dest="shell_command",
        metavar="CMD",
        help="Run one shell command non-interactively, then exit.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the safety decision for a command without running it.",
    )

    args = parser.parse_args()
    config.configure_logging()

    if args.shell_command:
        return run_once(args.shell_command, dry_run=args.dry_run)

    user_input = " ".join(args.command)

    # No arguments means the interactive shell. A natural-language argument keeps
    # the original one-shot Jev behaviour.
    if not user_input:
        if args.dry_run:
            parser.error("--dry-run needs a command; pass -c \"...\"")

        return run_repl(ShellSession())

    # One pipeline for natural language, whether it arrives here or in the REPL:
    # Jev's intent becomes a shell command, which the Stage 3 safety engine and
    # the shell executor handle exactly as if it had been typed.
    session = ShellSession()

    return handle_natural_language(user_input, session)


def run_once(line: str, dry_run: bool = False) -> int:
    """Run (or merely judge) one shell command outside the REPL.

    The session keeps its default confirmer, which denies, so a CONFIRM command
    reports and exits rather than hanging on a prompt nobody can answer.
    """
    session = ShellSession()

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
        return 0

    if dry_run:
        result = evaluate(tree, session)

        print("Command:")
        print(f"    {line}")
        print()
        print("Safety:")
        print(f"    {result.level.name}")
        print()
        print("Reason:")
        print(f"    {result.reason}")
        print()
        print("Execution:")
        print("    skipped (dry run)")

        return 0

    return execute_shell(tree, session, line)


if __name__ == "__main__":
    sys.exit(main() or 0)