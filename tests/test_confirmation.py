"""The confirmation flow, and what happens when nobody can answer."""
from pathlib import Path

from jevsh.shell.repl import ask_to_confirm, dispatch
from jevsh.shell.session import deny_without_a_terminal

HOME = str(Path.home())


def test_confirm_runs_when_approved(approving, tmp_path):
    (tmp_path / "doomed.txt").write_text("x")

    assert dispatch("rm doomed.txt", approving) == 0
    assert not (tmp_path / "doomed.txt").exists()


def test_confirm_cancels_when_declined(declining, tmp_path):
    (tmp_path / "keep.txt").write_text("x")

    assert dispatch("rm keep.txt", declining) != 0
    assert (tmp_path / "keep.txt").exists()


def test_allow_never_asks(session, tmp_path):
    asked = []
    session.confirm = lambda result: asked.append(result) or True

    dispatch("echo hi > notes.txt", session)

    assert asked == []
    assert (tmp_path / "notes.txt").exists()


def test_block_is_never_offered_a_prompt(session, capfd):
    asked = []
    session.confirm = lambda result: asked.append(result) or True

    status = dispatch(f"rm -rf {HOME}", session)

    assert status != 0
    assert asked == [], "a blocked command must not be confirmable"
    assert "blocked" in capfd.readouterr().out.lower()


def test_the_prompt_sees_the_reason(session, tmp_path):
    (tmp_path / "f.txt").write_text("x")
    seen = []

    session.confirm = lambda result: seen.append(result) or False
    dispatch("rm f.txt", session)

    assert len(seen) == 1
    assert seen[0].reason
    assert "rm f.txt" in seen[0].describe()


def test_only_an_explicit_yes_proceeds(monkeypatch, capfd):
    class Result:
        reason = "Deletes a file."
        def describe(self):
            return "rm x"

    for answer, expected in [
        ("y", True), ("Y", True), ("yes", True), ("YES", True), (" y ", True),
        ("n", False), ("N", False), ("no", False),
        ("", False), ("   ", False), ("maybe", False), ("yep", False), ("1", False),
    ]:
        monkeypatch.setattr("builtins.input", lambda _prompt, a=answer: a)
        assert ask_to_confirm(Result()) is expected, repr(answer)

    capfd.readouterr()


def test_empty_input_is_not_approval(monkeypatch, capfd):
    class Result:
        reason = "Deletes a file."
        def describe(self):
            return "rm x"

    monkeypatch.setattr("builtins.input", lambda _prompt: "")

    assert ask_to_confirm(Result()) is False
    capfd.readouterr()


def test_interrupting_the_prompt_cancels(monkeypatch, capfd):
    class Result:
        reason = "Deletes a file."
        def describe(self):
            return "rm x"

    for failure in (EOFError, KeyboardInterrupt):
        def raiser(_prompt, exc=failure):
            raise exc

        monkeypatch.setattr("builtins.input", raiser)
        assert ask_to_confirm(Result()) is False

    capfd.readouterr()


def test_default_session_denies_and_explains(session, tmp_path, capfd):
    # A fresh ShellSession has no human attached, so it must refuse rather than
    # hang on a prompt or silently execute.
    from jevsh.shell import ShellSession

    fresh = ShellSession(cwd=tmp_path, environment={"HOME": str(tmp_path / "home")})
    (tmp_path / "f.txt").write_text("x")

    assert dispatch("rm f.txt", fresh) != 0
    assert (tmp_path / "f.txt").exists()

    out = capfd.readouterr().out
    assert "CONFIRM" in out
    assert "confirmation required in interactive mode" in out


def test_the_denier_returns_false(capfd):
    class Result:
        class level:
            value = "confirm"

    assert deny_without_a_terminal(Result()) is False
    capfd.readouterr()
