"""Jev being unavailable must never take the shell down."""
import json

import pytest
import requests

from jevsh.jev import JevError
from jevsh.shell.repl import dispatch

NL = "create a folder called projects"


def assert_degrades(session, capfd, tmp_path):
    """One message, non-zero status, nothing created, shell still usable."""
    before = set(tmp_path.iterdir())
    status = dispatch(NL, session)
    out = capfd.readouterr().out

    assert status != 0
    assert "Jev is unavailable" in out
    assert set(tmp_path.iterdir()) == before

    # And the shell carries on.
    assert dispatch("pwd", session) == 0
    capfd.readouterr()


def test_missing_api_key(jev, session, capfd, tmp_path):
    jev(raises=JevError("No API key found."))
    assert_degrades(session, capfd, tmp_path)


def test_timeout(jev, session, capfd, tmp_path):
    jev(raises=requests.Timeout("timed out"))
    assert_degrades(session, capfd, tmp_path)


def test_connection_failure(jev, session, capfd, tmp_path):
    jev(raises=requests.ConnectionError("no route to host"))
    assert_degrades(session, capfd, tmp_path)


def test_http_error(jev, session, capfd, tmp_path):
    jev(raises=JevError("Jev API error 500: upstream failure"))
    assert_degrades(session, capfd, tmp_path)


def test_rate_limited(jev, session, capfd, tmp_path):
    jev(raises=JevError("Jev API error 429: too many requests"))
    assert_degrades(session, capfd, tmp_path)


def test_service_unavailable(jev, session, capfd, tmp_path):
    jev(raises=JevError("Jev API error 529: overloaded"))
    assert_degrades(session, capfd, tmp_path)


def test_malformed_json(jev, session, capfd, tmp_path):
    jev(raises=json.JSONDecodeError("Expecting value", "", 0))
    assert_degrades(session, capfd, tmp_path)


def test_response_missing_the_answer(monkeypatch, session, capfd, tmp_path):
    import jevsh.jev_router as router

    monkeypatch.setattr(router, "ask_jev", lambda text: {"model": "jev-1.13.0"})
    assert_degrades(session, capfd, tmp_path)


def test_response_missing_the_choice(monkeypatch, session, capfd, tmp_path):
    import jevsh.jev_router as router

    monkeypatch.setattr(
        router, "ask_jev", lambda text: {"answers": {"decision": {"type": "choice"}}}
    )
    assert_degrades(session, capfd, tmp_path)


def test_choice_outside_the_schema(jev, session, capfd, tmp_path):
    # The enum lookup rejects anything not in the five supported operations.
    jev(choice="reboot_the_planet")
    assert_degrades(session, capfd, tmp_path)


def test_confidence_of_the_wrong_type(monkeypatch, session, capfd, tmp_path):
    import jevsh.jev_router as router

    monkeypatch.setattr(
        router, "ask_jev",
        lambda text: {"answers": {"decision": {"choice": "mkdir",
                                               "confidence": "very sure"}}},
    )
    assert_degrades(session, capfd, tmp_path)


def test_the_error_text_is_never_shown(jev, session, capfd, tmp_path):
    # An exception message could carry a URL or a key, so none of it is printed.
    jev(raises=JevError("Bearer sk-secret-abc123 rejected by https://api.example"))

    dispatch(NL, session)
    out = capfd.readouterr().out

    assert "sk-secret-abc123" not in out
    assert "api.example" not in out
    assert "Jev is unavailable" in out


def test_shell_works_without_any_key(session, tmp_path, monkeypatch, capfd):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("JEV_API", raising=False)

    for line in ("pwd", "echo hello", "mkdir made", "ls"):
        assert dispatch(line, session) == 0

    assert (tmp_path / "made").is_dir()
    capfd.readouterr()


def test_a_missing_key_says_how_to_fix_it(jev, session, capfd, tmp_path, monkeypatch):
    """With no key configured the message names the variable to set (section 9)."""
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("JEV_API", raising=False)
    jev(raises=JevError("No API key found."))

    dispatch(NL, session)
    out = capfd.readouterr().out

    assert "Jev is unavailable" in out
    assert "TYPESAFE_API_KEY" in out


def test_with_a_key_present_the_message_stays_generic(jev, session, capfd, monkeypatch):
    # A configured key that failed is a different problem from a missing one.
    monkeypatch.setenv("TYPESAFE_API_KEY", "configured-but-rejected")
    jev(raises=JevError("Jev API error 500"))

    dispatch(NL, session)
    out = capfd.readouterr().out

    assert "Jev is unavailable" in out
    assert "configured-but-rejected" not in out


def test_jev_can_be_switched_off_entirely(session, capfd, monkeypatch):
    """JEVSH_JEV_ENABLED=0 routes everything to the shell, with no network call.

    The autouse guard fails on any real API call, so reaching the shell at all
    proves nothing was sent.
    """
    monkeypatch.setenv("JEVSH_JEV_ENABLED", "0")

    status = dispatch("create a folder called projects", session)

    assert status != 0
    assert "command not found: create" in capfd.readouterr().out
