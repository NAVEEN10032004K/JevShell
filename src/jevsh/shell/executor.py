"""Walk a command tree and run it.

Never uses shell=True. Every process is an explicit Popen with its own stdin,
stdout, cwd and env. stderr is deliberately left inherited so it stays separate
from the data flowing through a pipeline.

A foreground child shares this process's group, which is what makes Ctrl+C work:
the terminal signals the whole group, the child dies, and the REPL merely sees
KeyboardInterrupt. Background children are the one exception and get their own
session so a Ctrl+C aimed at the foreground does not take them down.

Note this is the *shell* executor. jevsh/executor.py dispatches Jev Actions.
"""
import contextlib
import subprocess
import sys

from .. import ui
from ..safety import SafetyLevel, evaluate
from . import jobs as jobs_module
from .ast import AndOr, Pipeline, Sequence, SequenceItem, SimpleCommand

NOT_FOUND = 127
NOT_EXECUTABLE = 126
INTERRUPTED = 130
REDIRECTION_ERROR = 1
# Distinct from an ordinary failure, so a caller can tell "the policy refused
# this" from "the command ran and failed". 77 is sysexits' EX_NOPERM.
BLOCKED = 77
CANCELLED = 1


class RedirectionError(Exception):
    """A redirection target could not be opened."""


def open_redirections(command: SimpleCommand, session):
    """Open this command's redirection targets. Caller closes what comes back."""
    opened = []
    stdin = stdout = None

    try:
        for redirection in command.redirections:
            path = session.resolve(redirection.target)

            try:
                if redirection.operator == "<":
                    handle = open(path, "r")
                    stdin = handle
                else:
                    handle = open(path, "a" if redirection.operator == ">>" else "w")
                    stdout = handle
            except FileNotFoundError:
                raise RedirectionError(f"jevsh: {redirection.target}: No such file or directory")
            except IsADirectoryError:
                raise RedirectionError(f"jevsh: {redirection.target}: Is a directory")
            except PermissionError:
                raise RedirectionError(f"jevsh: {redirection.target}: Permission denied")
            except OSError as error:
                raise RedirectionError(f"jevsh: {redirection.target}: {error.strerror}")

            opened.append(handle)

    except RedirectionError:
        for handle in opened:
            handle.close()
        raise

    return stdin, stdout, opened


def run_external(argv, session, stdin=None, stdout=None) -> int:
    """Run one external command to completion and return its real exit code."""
    if not argv:
        return 0

    command = argv[0]
    sys.stdout.flush()

    try:
        process = subprocess.Popen(
            argv, cwd=session.cwd, env=session.environment, stdin=stdin, stdout=stdout
        )
    except FileNotFoundError:
        print(f"jevsh: command not found: {command}")
        return NOT_FOUND
    except PermissionError:
        print(f"jevsh: permission denied: {command}")
        return NOT_EXECUTABLE
    except NotADirectoryError:
        print(f"jevsh: not a directory: {command}")
        return NOT_FOUND
    except OSError as error:
        print(f"jevsh: {command}: {error.strerror}")
        return 1

    try:
        return process.wait()
    except KeyboardInterrupt:
        # The child already received the same SIGINT from the terminal; reap it
        # so it does not linger, then report without dying.
        process.wait()
        print()
        return INTERRUPTED


def run_builtin(builtin, command: SimpleCommand, session) -> int:
    """Run a builtin in this process, honouring its output redirection."""
    try:
        _, stdout, opened = open_redirections(command, session)
    except RedirectionError as error:
        print(error)
        return REDIRECTION_ERROR

    try:
        if stdout is None:
            return builtin(command.argv[1:], session)

        with contextlib.redirect_stdout(stdout):
            return builtin(command.argv[1:], session)
    finally:
        for handle in opened:
            handle.close()


def run_pipeline(pipeline: Pipeline, session) -> int:
    """Run a pipeline, returning the last command's status."""
    from .builtins import BUILTINS

    commands = pipeline.commands

    if len(commands) == 1:
        command = commands[0]

        if not command.argv:
            # A bare redirection such as `> file` still creates the file.
            try:
                _, _, opened = open_redirections(command, session)
            except RedirectionError as error:
                print(error)
                return REDIRECTION_ERROR
            for handle in opened:
                handle.close()
            return 0

        builtin = BUILTINS.get(command.argv[0])

        if builtin is not None:
            return run_builtin(builtin, command, session)

        try:
            stdin, stdout, opened = open_redirections(command, session)
        except RedirectionError as error:
            print(error)
            return REDIRECTION_ERROR

        try:
            return run_external(command.argv, session, stdin=stdin, stdout=stdout)
        finally:
            for handle in opened:
                handle.close()

    return run_multi_stage(commands, session)


def run_multi_stage(commands, session) -> int:
    """Build the whole Popen chain, then wait.

    A builtin in a pipeline is not special-cased: the external binary is used, so
    `pwd | cat` works through /bin/pwd while `history | grep` is not found.
    """
    processes = []
    files = []
    previous_stdout = None
    sys.stdout.flush()

    try:
        for index, command in enumerate(commands):
            last = index == len(commands) - 1

            try:
                stdin, stdout, opened = open_redirections(command, session)
            except RedirectionError as error:
                print(error)
                return REDIRECTION_ERROR

            files.extend(opened)

            # An explicit redirection wins over the pipe, matching a real shell.
            if stdin is None:
                stdin = previous_stdout
            if stdout is None and not last:
                stdout = subprocess.PIPE

            try:
                process = subprocess.Popen(
                    command.argv,
                    cwd=session.cwd,
                    env=session.environment,
                    stdin=stdin,
                    stdout=stdout,
                )
            except FileNotFoundError:
                print(f"jevsh: command not found: {command.argv[0]}")
                return NOT_FOUND
            except PermissionError:
                print(f"jevsh: permission denied: {command.argv[0]}")
                return NOT_EXECUTABLE
            except OSError as error:
                print(f"jevsh: {command.argv[0]}: {error.strerror}")
                return 1

            processes.append(process)

            # Close our copy of the upstream read end, or the upstream command
            # never sees SIGPIPE when a later stage exits early and `head` hangs.
            if previous_stdout is not None:
                previous_stdout.close()

            previous_stdout = process.stdout

        try:
            for process in processes:
                process.wait()
        except KeyboardInterrupt:
            for process in processes:
                process.wait()
            print()
            return INTERRUPTED

        return processes[-1].returncode

    finally:
        for handle in files:
            handle.close()


def start_background(item: SequenceItem, session, line: str) -> int:
    """Spawn the first command of a background item and return immediately."""
    commands = [c for p in item.node.pipelines for c in p.commands]

    if not commands or not commands[0].argv:
        return 0

    command = commands[0]

    try:
        stdin, stdout, opened = open_redirections(command, session)
    except RedirectionError as error:
        print(error)
        return REDIRECTION_ERROR

    sys.stdout.flush()

    try:
        process = subprocess.Popen(
            command.argv,
            cwd=session.cwd,
            env=session.environment,
            stdin=stdin,
            stdout=stdout,
            # Its own session, so Ctrl+C at the prompt does not kill it. This is
            # the only job-control concession in this stage.
            start_new_session=True,
        )
    except FileNotFoundError:
        print(f"jevsh: command not found: {command.argv[0]}")
        return NOT_FOUND
    except OSError as error:
        print(f"jevsh: {command.argv[0]}: {error.strerror}")
        return 1
    finally:
        for handle in opened:
            handle.close()

    job = jobs_module.register(session, process, line or " ".join(command.argv))
    print(f"[{job.id}] {job.pid}")

    return 0


def run_andor(node: AndOr, session) -> int:
    """Run pipelines joined by && / ||, honouring short-circuit semantics."""
    status = run_pipeline(node.pipelines[0], session)

    for operator, pipeline in zip(node.operators, node.pipelines[1:]):
        if operator == "&&" and status != 0:
            continue
        if operator == "||" and status == 0:
            continue

        status = run_pipeline(pipeline, session)

    return status


def authorize(node, session):
    """Run the safety engine and, for CONFIRM, ask.

    Returns True to proceed, or the exit code to report. Nothing executes before
    this. A BLOCK is never offered a prompt; no answer would make it run.
    """
    result = evaluate(node, session)

    if result.level is SafetyLevel.BLOCK:
        print(ui.blocked(result.reason))
        return BLOCKED

    if result.level is SafetyLevel.CONFIRM and not session.confirm(result):
        return CANCELLED

    return True


def execute(node, session, line: str = "") -> int:
    """Run a parsed node, once the safety engine has authorized it."""
    authorization = authorize(node, session)

    if authorization is not True:
        return authorization

    if isinstance(node, Sequence):
        status = session.last_exit_code

        for item in node.items:
            if item.background:
                status = start_background(item, session, line)
            else:
                status = run_andor(item.node, session)

            session.last_exit_code = status

        return status

    if isinstance(node, SequenceItem):
        return run_andor(node.node, session)

    if isinstance(node, AndOr):
        return run_andor(node, session)

    if isinstance(node, Pipeline):
        return run_pipeline(node, session)

    if isinstance(node, SimpleCommand):
        return run_pipeline(Pipeline([node]), session)

    raise TypeError(f"cannot execute {type(node).__name__}")
