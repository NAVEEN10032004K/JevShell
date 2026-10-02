import os

import pytest


def test_cd_relative(session, tmp_path):
    (tmp_path / "projects").mkdir()

    assert session.change_directory("projects") is None
    assert session.cwd == tmp_path / "projects"


def test_cd_absolute(session, tmp_path):
    target = tmp_path / "abs"
    target.mkdir()

    assert session.change_directory(str(target)) is None
    assert session.cwd == target


def test_cd_dot_stays_put(session, tmp_path):
    assert session.change_directory(".") is None
    assert session.cwd == tmp_path


def test_cd_dotdot_goes_up(session, tmp_path):
    (tmp_path / "deep").mkdir()
    session.change_directory("deep")

    assert session.change_directory("..") is None
    assert session.cwd == tmp_path


def test_cd_bare_and_tilde_go_home(session):
    home = session.home()

    assert session.change_directory() is None
    assert session.cwd == home

    session.change_directory(str(home.parent))
    assert session.change_directory("~") is None
    assert session.cwd == home


def test_cd_dash_toggles(session, tmp_path):
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()

    session.change_directory("one")
    session.change_directory(str(tmp_path / "two"))

    assert session.change_directory("-") is None
    assert session.cwd == tmp_path / "one"

    # Toggling again returns to where we just were.
    assert session.change_directory("-") is None
    assert session.cwd == tmp_path / "two"


def test_cd_dash_without_history_errors(session):
    error = session.change_directory("-")

    assert error is not None
    assert "OLDPWD" in error


def test_cd_nonexistent_errors_and_does_not_move(session, tmp_path):
    error = session.change_directory("not_there")

    assert error is not None
    assert "No such file or directory" in error
    assert session.cwd == tmp_path


def test_cd_into_a_file_errors(session, tmp_path):
    (tmp_path / "file.txt").write_text("not a directory")

    error = session.change_directory("file.txt")

    assert error is not None
    assert "Not a directory" in error
    assert session.cwd == tmp_path


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_cd_without_permission_errors(session, tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o000)

    try:
        error = session.change_directory("locked")

        assert error is not None
        assert "Permission denied" in error
        assert session.cwd == tmp_path
    finally:
        locked.chmod(0o755)
