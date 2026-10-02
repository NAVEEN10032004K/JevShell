"""Filename globbing, and the quoting that suppresses it."""
import pytest


@pytest.fixture
def files(session, tmp_path):
    for name in ("a.py", "b.py", "c.txt", "file1.txt", "file2.txt"):
        (tmp_path / name).write_text("")
    return tmp_path


from jevsh.shell.parser import parse  # noqa: E402
from jevsh.shell.repl import dispatch  # noqa: E402


def argv_of(line, session):
    tree = parse(line, env=session.environment, cwd=session.cwd)
    return tree.items[0].node.pipelines[0].commands[0].argv


def test_star_matches_and_sorts(files, session):
    assert argv_of("ls *.py", session) == ["ls", "a.py", "b.py"]


def test_question_mark_matches_one_character(files, session):
    assert argv_of("ls file?.txt", session) == ["ls", "file1.txt", "file2.txt"]


def test_bracket_class(files, session):
    assert argv_of("ls file[12].txt", session) == ["ls", "file1.txt", "file2.txt"]


def test_no_match_leaves_the_pattern_literal(files, session):
    # nullglob is off, as in bash.
    assert argv_of("ls *.nomatch", session) == ["ls", "*.nomatch"]


def test_single_quotes_suppress_globbing(files, session):
    assert argv_of("echo '*.py'", session) == ["echo", "*.py"]


def test_double_quotes_suppress_globbing(files, session):
    assert argv_of('echo "*.py"', session) == ["echo", "*.py"]


def test_backslash_suppresses_globbing(files, session):
    assert argv_of(r"echo \*.py", session) == ["echo", "*.py"]


def test_glob_resolves_against_session_cwd_not_process_cwd(files, session, tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "only_here.py").write_text("")
    session.change_directory("nested")

    assert argv_of("ls *.py", session) == ["ls", "only_here.py"]


def test_glob_in_a_subdirectory_path(files, session, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.py").write_text("")

    assert argv_of("ls sub/*.py", session) == ["ls", "sub/deep.py"]


def test_dotfiles_are_not_matched(files, session, tmp_path):
    (tmp_path / ".hidden.py").write_text("")

    assert argv_of("ls *.py", session) == ["ls", "a.py", "b.py"]


def test_glob_reaches_the_command(files, session, capfd):
    assert dispatch("echo *.py", session) == 0
    assert capfd.readouterr().out.strip() == "a.py b.py"


def test_quoted_glob_reaches_the_command_literally(files, session, capfd):
    dispatch("echo '*.py'", session)

    assert capfd.readouterr().out.strip() == "*.py"


def test_redirection_target_is_not_globbed(files, session, tmp_path):
    # A pattern as a redirect target is taken literally rather than expanded.
    dispatch("echo hi > out*.txt", session)

    assert (tmp_path / "out*.txt").exists()
