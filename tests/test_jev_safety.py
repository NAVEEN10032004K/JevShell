"""Every Jev-driven action goes through the Stage 3 safety engine."""
from pathlib import Path

from jevsh.jev_intent import JevIntent, to_command
from jevsh.models import ActionType
from jevsh.safety import SafetyLevel, evaluate
from jevsh.shell.ast import AndOr, Pipeline, Sequence, SequenceItem
from jevsh.shell.repl import dispatch


def level_of(action, target, session):
    command = to_command(JevIntent(action, 1.0, target), session)
    tree = Sequence([SequenceItem(AndOr([Pipeline([command])], []))])
    return evaluate(tree, session).level


def test_creating_is_allowed(session):
    assert level_of(ActionType.MKDIR, "projects", session) is SafetyLevel.ALLOW
    assert level_of(ActionType.TOUCH, "notes.txt", session) is SafetyLevel.ALLOW


def test_reading_is_allowed(session):
    assert level_of(ActionType.LS, None, session) is SafetyLevel.ALLOW
    assert level_of(ActionType.PWD, None, session) is SafetyLevel.ALLOW


def test_deleting_requires_confirmation(session):
    assert level_of(ActionType.DELETE, "test.txt", session) is SafetyLevel.CONFIRM


def test_deleting_home_is_blocked(session):
    assert level_of(ActionType.DELETE, str(Path.home()), session) is SafetyLevel.BLOCK


def test_deleting_root_is_blocked(session):
    assert level_of(ActionType.DELETE, "/", session) is SafetyLevel.BLOCK


def test_deleting_a_system_path_is_blocked(session):
    assert level_of(ActionType.DELETE, "/etc", session) is SafetyLevel.BLOCK


def test_confidence_cannot_override_a_block(session):
    # Even a perfectly confident intent is refused.
    command = to_command(JevIntent(ActionType.DELETE, 1.0, str(Path.home())), session)
    tree = Sequence([SequenceItem(AndOr([Pipeline([command])], []))])

    assert evaluate(tree, session).level is SafetyLevel.BLOCK


def test_delete_uses_the_same_confirmation_prompt(jev, session, tmp_path, capfd):
    jev(choice="delete")
    (tmp_path / "notes.txt").write_text("x")
    seen = []
    session.confirm = lambda result: seen.append(result) or False

    dispatch("delete notes.txt", session)

    assert len(seen) == 1, "the shell's own confirmation must be used"
    assert (tmp_path / "notes.txt").exists()
    capfd.readouterr()


def test_declining_a_jev_delete_keeps_the_file(jev, session, tmp_path, capfd):
    jev(choice="delete")
    (tmp_path / "notes.txt").write_text("x")
    session.confirm = lambda result: False

    assert dispatch("delete notes.txt", session) != 0
    assert (tmp_path / "notes.txt").exists()
    capfd.readouterr()


def test_approving_a_jev_delete_removes_the_file(jev, session, tmp_path, capfd):
    jev(choice="delete")
    (tmp_path / "notes.txt").write_text("x")
    session.confirm = lambda result: True

    assert dispatch("delete notes.txt", session) == 0
    assert not (tmp_path / "notes.txt").exists()
    capfd.readouterr()


def test_blocked_jev_request_is_never_offered_a_prompt(jev, session, capfd):
    jev(choice="delete")
    asked = []
    session.confirm = lambda result: asked.append(result) or True

    status = dispatch("delete everything in my home directory", session)
    out = capfd.readouterr().out

    assert status != 0
    assert asked == [], "a blocked request must not be confirmable"
    assert "blocked" in out.lower()
    assert Path.home().exists()


def test_jev_mkdir_actually_creates_through_the_shell(jev, session, tmp_path, capfd):
    jev(choice="mkdir")

    assert dispatch("create a folder called projects", session) == 0
    assert (tmp_path / "projects").is_dir()
    capfd.readouterr()
