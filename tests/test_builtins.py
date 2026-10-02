import pytest

from jevsh.shell.builtins import BUILTINS, ExitShell, builtin_exit, builtin_history
from jevsh.shell.repl import dispatch


def test_pwd_reports_session_not_process(session, tmp_path, capsys):
    (tmp_path / "test").mkdir()
    dispatch("cd test", session)
    dispatch("pwd", session)

    assert capsys.readouterr().out.strip() == str(tmp_path / "test")


def test_cd_then_pwd_through_dispatch(session, tmp_path, capsys):
    (tmp_path / "test").mkdir()

    assert dispatch("cd test", session) == 0
    assert session.cwd == tmp_path / "test"

    dispatch("pwd", session)
    assert capsys.readouterr().out.strip() == str(tmp_path / "test")


def test_cd_dash_prints_destination(session, tmp_path, capsys):
    (tmp_path / "one").mkdir()
    dispatch("cd one", session)
    capsys.readouterr()

    dispatch("cd -", session)
    assert capsys.readouterr().out.strip() == str(tmp_path)


def test_cd_failure_returns_one_without_raising(session, capsys):
    assert dispatch("cd /definitely/not/here", session) == 1
    assert "No such file or directory" in capsys.readouterr().out


def test_cd_too_many_arguments(session, capsys):
    assert dispatch("cd a b", session) == 1
    assert "too many arguments" in capsys.readouterr().out


def test_history_numbers_from_one(session, capsys):
    for line in ("pwd", "ls", "cd projects", "history"):
        session.record(line)

    builtin_history([], session)
    lines = capsys.readouterr().out.splitlines()

    assert lines == ["1  pwd", "2  ls", "3  cd projects", "4  history"]


def test_history_includes_itself_via_repl_recording(session, capsys):
    # The REPL records before dispatching, so `history` must list itself.
    for line in ("pwd", "history"):
        session.record(line)
        dispatch(line, session)

    assert "2  history" in capsys.readouterr().out


def test_history_with_count_shows_the_tail(session, capsys):
    for index in range(1, 16):
        session.record(f"command{index}")

    builtin_history(["10"], session)
    lines = capsys.readouterr().out.splitlines()

    assert len(lines) == 10
    assert lines[0].strip().startswith("6 ")
    assert lines[-1].strip() == "15  command15"


def test_history_rejects_non_numeric(session, capsys):
    assert builtin_history(["abc"], session) == 1
    assert "numeric argument required" in capsys.readouterr().out


def test_exit_and_quit_raise_with_a_code(session):
    for name in ("exit", "quit"):
        with pytest.raises(ExitShell) as raised:
            BUILTINS[name]([], session)
        assert raised.value.code == 0

    with pytest.raises(ExitShell) as raised:
        builtin_exit(["0"], session)
    assert raised.value.code == 0

    with pytest.raises(ExitShell) as raised:
        builtin_exit(["3"], session)
    assert raised.value.code == 3


def test_bare_exit_reports_last_status(session):
    session.last_exit_code = 7

    with pytest.raises(ExitShell) as raised:
        builtin_exit([], session)

    assert raised.value.code == 7


def test_exit_with_bad_argument_does_not_exit(session, capsys):
    assert builtin_exit(["abc"], session) == 2
    assert "numeric argument required" in capsys.readouterr().out


def test_clear_emits_an_escape_sequence(session, capsys):
    assert dispatch("clear", session) == 0
    assert "\033[2J" in capsys.readouterr().out
