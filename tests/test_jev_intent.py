"""Jev's reply becomes a bounded, structured intent."""
import pytest

from jevsh.jev_intent import (
    CONFIRM_THRESHOLD,
    IntentError,
    JevIntent,
    clarification,
    from_response,
    to_command,
)
from jevsh.jev_router import build_intent
from jevsh.models import ActionType
from jevsh.shell.repl import dispatch


def reply(choice, confidence=1.0):
    return {"answers": {"decision": {"type": "choice", "choice": choice,
                                     "confidence": confidence}}}


def test_every_supported_choice_becomes_an_intent():
    for choice, action in [
        ("mkdir", ActionType.MKDIR), ("touch", ActionType.TOUCH),
        ("ls", ActionType.LS), ("pwd", ActionType.PWD),
        ("delete", ActionType.DELETE),
    ]:
        intent = from_response(reply(choice), "whatever")
        assert intent.action is action


def test_confidence_is_carried_through():
    assert from_response(reply("mkdir", 0.83), "x").confidence == 0.83


def test_raw_input_is_kept():
    assert from_response(reply("pwd"), "show my directory").raw_input == "show my directory"


def test_only_the_users_words_are_sent(jev):
    sent = jev(choice="mkdir")
    build_intent("ai create a folder called projects")

    # The prefix is stripped and nothing else is added.
    assert sent == ["create a folder called projects"]


def test_target_comes_from_the_deterministic_extractor(jev):
    jev(choice="mkdir")
    intent = build_intent("create a folder called projects")

    assert intent.target == "projects"


def test_high_confidence_is_actionable():
    assert JevIntent(ActionType.MKDIR, 1.0, "x").is_confident
    assert JevIntent(ActionType.MKDIR, CONFIRM_THRESHOLD, "x").is_confident


def test_low_confidence_is_not():
    # Measured: genuinely ambiguous requests landed at 0.73 and 0.66.
    assert not JevIntent(ActionType.TOUCH, 0.73, "x").is_confident
    assert not JevIntent(ActionType.LS, 0.66).is_confident


def test_ambiguous_input_asks_instead_of_guessing(jev, session, tmp_path, capfd):
    jev(choice="touch", confidence=0.73)
    before = set(tmp_path.iterdir())

    status = dispatch("create something for my project", session)
    out = capfd.readouterr().out

    assert status != 0
    assert "couldn't determine" in out
    assert "1. create a directory" in out
    assert set(tmp_path.iterdir()) == before, "nothing may be created"


def test_clarification_lists_the_options():
    text = clarification(JevIntent(ActionType.TOUCH, 0.5))

    for option in ("create a directory", "create a file", "list files"):
        assert option in text


def test_missing_target_refuses_without_inventing_one(session):
    for action in (ActionType.MKDIR, ActionType.TOUCH, ActionType.DELETE):
        with pytest.raises(IntentError, match="need the path"):
            to_command(JevIntent(action, 1.0, target=None), session)


def test_missing_target_message_reaches_the_user(jev, session, tmp_path, capfd):
    jev(choice="delete")

    # The extractor finds no path here, so the shell must ask rather than guess.
    status = dispatch("delete it", session)

    assert status != 0
    assert "need the path" in capfd.readouterr().out


def test_a_vague_phrase_that_does_extract_is_not_invented(jev, session):
    # "delete the old project" yields "old" -- a real token from the input, not
    # a path the shell made up. The target always comes from the user's words.
    jev(choice="delete")
    intent = build_intent("delete the old project")

    assert intent.target == "old"
    assert intent.target in "delete the old project"


def test_intents_without_a_target_still_work(session):
    assert to_command(JevIntent(ActionType.PWD, 1.0), session).argv == ["pwd"]
    assert to_command(JevIntent(ActionType.LS, 1.0), session).argv == ["ls"]


def test_pwd_ignores_a_stray_extracted_target(session):
    # "show my current directory" extracts "my", which pwd must not display.
    intent = JevIntent(ActionType.PWD, 1.0, target="my")

    assert intent.shown_target is None
    assert to_command(intent, session).argv == ["pwd"]
