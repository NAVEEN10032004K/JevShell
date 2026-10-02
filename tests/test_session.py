import os
from pathlib import Path

from jevsh.shell import ShellSession


def test_inherits_environment_by_default():
    assert ShellSession().environment.get("PATH") == os.environ.get("PATH")


def test_cwd_persists_across_calls(session, tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)

    assert session.change_directory("a") is None
    assert session.cwd == tmp_path / "a"

    # The point of the whole class: the second cd starts from the first one.
    assert session.change_directory("b") is None
    assert session.cwd == tmp_path / "a" / "b"


def test_cd_never_moves_the_host_process(session, tmp_path):
    before = Path.cwd()
    (tmp_path / "elsewhere").mkdir()

    session.change_directory("elsewhere")

    assert Path.cwd() == before


def test_cd_updates_pwd_in_session_env(session, tmp_path):
    (tmp_path / "x").mkdir()
    session.change_directory("x")

    assert session.environment["PWD"] == str(tmp_path / "x")
    # The real process environment is untouched.
    assert os.environ.get("PWD") != str(tmp_path / "x")


def test_history_accumulates_in_order(session):
    for line in ("pwd", "ls", "cd projects"):
        session.record(line)

    assert session.history == ["pwd", "ls", "cd projects"]


def test_resolve_normalises_without_following_symlinks(session, tmp_path):
    assert session.resolve("a/../b") == tmp_path / "b"
    assert session.resolve("/absolute/path") == Path("/absolute/path")
