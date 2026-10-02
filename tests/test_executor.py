import subprocess
import sys

from jevsh.shell.executor import INTERRUPTED, NOT_EXECUTABLE, NOT_FOUND, run_external
from jevsh.shell.repl import dispatch


def test_zero_exit_code(session):
    assert run_external(["true"], session) == 0


def test_nonzero_exit_code_is_returned(session):
    assert run_external(["false"], session) == 1


def test_arbitrary_exit_code(session):
    assert run_external(["sh", "-c", "exit 7"], session) == 7


def test_command_runs_in_session_cwd(session, tmp_path, capfd):
    target = tmp_path / "work"
    target.mkdir()
    session.change_directory("work")

    assert run_external(["pwd"], session) == 0
    assert capfd.readouterr().out.strip() == str(target)


def test_command_not_found(session, capfd):
    assert run_external(["abcdef_no_such_command"], session) == NOT_FOUND
    assert "jevsh: command not found: abcdef_no_such_command" in capfd.readouterr().out


def test_non_executable_file(session, tmp_path, capfd):
    script = tmp_path / "not_executable.sh"
    script.write_text("echo hi\n")
    script.chmod(0o644)

    assert run_external([str(script)], session) == NOT_EXECUTABLE
    assert "permission denied" in capfd.readouterr().out


def test_empty_argv_is_a_noop(session):
    assert run_external([], session) == 0


def test_keyboard_interrupt_returns_130_without_propagating(session, monkeypatch, capfd):
    class FakeProcess:
        def __init__(self):
            self.waits = 0

        def wait(self):
            self.waits += 1
            # First wait is the one the user interrupts; the second reaps the child.
            if self.waits == 1:
                raise KeyboardInterrupt
            return INTERRUPTED

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: FakeProcess())

    assert run_external(["sleep", "30"], session) == INTERRUPTED


def test_external_command_through_dispatch(session, capfd):
    assert dispatch("echo hello", session) == 0
    assert capfd.readouterr().out.strip() == "hello"


def test_quoted_argument_reaches_the_command_intact(session, capfd):
    assert dispatch('echo "hello world"', session) == 0
    assert capfd.readouterr().out.strip() == "hello world"


def test_variable_expansion_reaches_the_command(session, capfd):
    session.environment["GREETING"] = "hi there"

    assert dispatch("echo $GREETING", session) == 0
    assert capfd.readouterr().out.strip() == "hi there"


def test_syntax_error_is_reported_not_raised(session, capfd):
    assert dispatch('echo "unclosed', session) == 2
    assert "syntax error" in capfd.readouterr().out


def test_nonzero_status_is_recorded_not_fatal(session):
    # dispatch returns the code; the REPL stores it and carries on.
    assert dispatch("false", session) == 1
    assert dispatch("true", session) == 0


def test_python_runs_from_the_session_directory(session, tmp_path, capfd):
    work = tmp_path / "scripts"
    work.mkdir()
    (work / "where.py").write_text("import os; print(os.getcwd())\n")
    session.change_directory("scripts")

    assert run_external([sys.executable, "where.py"], session) == 0
    assert capfd.readouterr().out.strip() == str(work)
