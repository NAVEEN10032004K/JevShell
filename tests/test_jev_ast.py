"""Jev intent produces the same IR a typed command would."""
from jevsh.jev_intent import JevIntent, to_command
from jevsh.models import ActionType
from jevsh.shell.parser import parse


def typed(line, session):
    tree = parse(line, env=session.environment, cwd=session.cwd)
    return tree.items[0].node.pipelines[0].commands[0].argv


def from_intent(action, target, session):
    return to_command(JevIntent(action, 1.0, target), session).argv


def test_mkdir_matches_the_typed_command(session):
    assert from_intent(ActionType.MKDIR, "projects", session) == typed("mkdir projects", session)


def test_touch_matches(session):
    assert from_intent(ActionType.TOUCH, "notes.txt", session) == typed("touch notes.txt", session)


def test_pwd_matches(session):
    assert from_intent(ActionType.PWD, None, session) == typed("pwd", session)


def test_ls_matches(session):
    assert from_intent(ActionType.LS, None, session) == typed("ls", session)
    assert from_intent(ActionType.LS, "src", session) == typed("ls src", session)


def test_delete_of_a_file_matches_rm(session, tmp_path):
    (tmp_path / "notes.txt").write_text("x")

    assert from_intent(ActionType.DELETE, "notes.txt", session) == typed("rm notes.txt", session)


def test_delete_of_a_directory_adds_recursion(session, tmp_path):
    (tmp_path / "project").mkdir()

    assert from_intent(ActionType.DELETE, "project", session) == ["rm", "-r", "project"]


def test_delete_of_a_missing_path_is_not_recursive(session):
    assert from_intent(ActionType.DELETE, "nothing_here", session) == ["rm", "nothing_here"]


def test_recursion_is_decided_by_the_filesystem_not_the_model(session, tmp_path):
    # Same intent, same confidence; only the target's nature differs.
    (tmp_path / "adir").mkdir()
    (tmp_path / "afile").write_text("")

    assert "-r" in from_intent(ActionType.DELETE, "adir", session)
    assert "-r" not in from_intent(ActionType.DELETE, "afile", session)


def test_the_command_carries_no_shell_string(session):
    command = to_command(JevIntent(ActionType.MKDIR, 1.0, "x"), session)

    # argv entries, never a single string to be re-parsed by a shell.
    assert command.argv == ["mkdir", "x"]
    assert all(" " not in part for part in command.argv)
    assert command.redirections == []
