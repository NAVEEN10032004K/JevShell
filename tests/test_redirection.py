"""Redirection: > >> <, and the error cases that must not crash the shell."""
import os

import pytest

from jevsh.shell.repl import dispatch


def test_output_redirection_creates_the_file(session, tmp_path):
    assert dispatch("echo hello > out.txt", session) == 0
    assert (tmp_path / "out.txt").read_text() == "hello\n"


def test_output_redirection_truncates(session, tmp_path):
    (tmp_path / "out.txt").write_text("stale content that must go\n")

    assert dispatch("echo fresh > out.txt", session) == 0
    assert (tmp_path / "out.txt").read_text() == "fresh\n"


def test_append_redirection(session, tmp_path):
    dispatch("echo hello > out.txt", session)
    assert dispatch("echo world >> out.txt", session) == 0
    assert (tmp_path / "out.txt").read_text() == "hello\nworld\n"


def test_append_creates_when_absent(session, tmp_path):
    assert dispatch("echo first >> new.txt", session) == 0
    assert (tmp_path / "new.txt").read_text() == "first\n"


def test_input_redirection(session, tmp_path, capfd):
    (tmp_path / "in.txt").write_text("from the file\n")

    assert dispatch("cat < in.txt", session) == 0
    assert capfd.readouterr().out == "from the file\n"


def test_redirection_resolves_against_session_cwd(session, tmp_path):
    (tmp_path / "sub").mkdir()
    session.change_directory("sub")

    dispatch("echo nested > out.txt", session)

    assert (tmp_path / "sub" / "out.txt").exists()
    assert not (tmp_path / "out.txt").exists()


def test_redirection_target_expands_variables(session, tmp_path):
    session.environment["OUTFILE"] = "expanded.txt"

    assert dispatch("echo hi > $OUTFILE", session) == 0
    assert (tmp_path / "expanded.txt").read_text() == "hi\n"


def test_missing_input_file_reports_and_does_not_crash(session, capfd):
    assert dispatch("cat < nope.txt", session) != 0
    assert "No such file or directory" in capfd.readouterr().out


def test_directory_as_input_reports_and_does_not_crash(session, tmp_path, capfd):
    (tmp_path / "adir").mkdir()

    assert dispatch("cat < adir", session) != 0
    assert "Is a directory" in capfd.readouterr().out


def test_directory_as_output_target_reports(session, tmp_path, capfd):
    (tmp_path / "adir").mkdir()

    assert dispatch("echo hi > adir", session) != 0
    assert "Is a directory" in capfd.readouterr().out


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_unwritable_target_reports(session, tmp_path, capfd):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)

    try:
        assert dispatch("echo hi > locked/out.txt", session) != 0
        assert "Permission denied" in capfd.readouterr().out
    finally:
        locked.chmod(0o755)


def test_builtin_output_can_be_redirected(session, tmp_path):
    # pwd is a builtin, so this proves in-process redirection works.
    (tmp_path / "work").mkdir()
    session.change_directory("work")

    assert dispatch("pwd > where.txt", session) == 0
    assert (tmp_path / "work" / "where.txt").read_text().strip() == str(tmp_path / "work")


def test_builtin_history_can_be_redirected(session, tmp_path):
    session.record("pwd")
    session.record("ls")

    assert dispatch("history > log.txt", session) == 0
    contents = (tmp_path / "log.txt").read_text()

    assert "pwd" in contents and "ls" in contents


def test_redirection_combined_with_a_pipeline(session, tmp_path):
    assert dispatch('printf "b\\na\\n" | sort > sorted.txt', session) == 0
    assert (tmp_path / "sorted.txt").read_text() == "a\nb\n"


def test_bare_redirection_creates_an_empty_file(session, tmp_path):
    assert dispatch("> created.txt", session) == 0
    assert (tmp_path / "created.txt").exists()
    assert (tmp_path / "created.txt").read_text() == ""
