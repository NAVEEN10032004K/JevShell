"""Shared fixtures.

pyproject sets `pythonpath = ["src"]`, so `import jevsh` resolves to the package
under src/ -- the same name it carries once installed. One import path means a
test that patches a module is patching the module the code actually uses.
"""
import pytest

from jevsh.shell import ShellSession


@pytest.fixture
def session(tmp_path):
    """A session rooted in a temp dir, with HOME pointed there too.

    HOME is overridden so `cd ~` and `~/x` expansion are exercised without ever
    touching the real home directory.
    """
    home = tmp_path / "home"
    home.mkdir()

    return ShellSession(cwd=tmp_path, environment={"HOME": str(home), "PATH": "/usr/bin:/bin"})


@pytest.fixture
def approving(session):
    """A session whose CONFIRM prompts are answered yes."""
    session.confirm = lambda result: True
    return session


@pytest.fixture
def declining(session):
    """A session whose CONFIRM prompts are answered no."""
    session.confirm = lambda result: False
    return session


@pytest.fixture
def level(session):
    """Evaluate a command line and return just its SafetyLevel."""
    from jevsh.safety import evaluate
    from jevsh.shell.parser import parse

    def evaluate_line(line, in_session=None):
        target = in_session or session
        tree = parse(
            line,
            env=target.environment,
            cwd=target.cwd,
            aliases=target.aliases,
        )
        return evaluate(tree, target).level

    return evaluate_line


@pytest.fixture(autouse=True)
def no_real_api(monkeypatch):
    """Nothing in the suite may call the real Jev API.

    Autouse, so a test that accidentally routes to Jev fails loudly instead of
    quietly spending money and depending on the network. Tests that want a reply
    override this through the `jev` fixture.
    """
    import jevsh.jev_router as router

    def forbidden(_text):
        raise AssertionError("test reached the real Jev API")

    monkeypatch.setattr(router, "ask_jev", forbidden)


@pytest.fixture
def jev(monkeypatch):
    """Install a canned Jev reply and record what was sent."""
    import jevsh.jev_router as router

    sent = []

    def install(choice="pwd", confidence=1.0, probabilities=None, raises=None):
        def fake_ask_jev(text):
            sent.append(text)

            if raises is not None:
                raise raises

            return {
                "model": "jev-1.13.0",
                "answers": {
                    "decision": {
                        "type": "choice",
                        "choice": choice,
                        "confidence": confidence,
                        "probabilities": probabilities or {choice: confidence},
                    }
                },
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }

        monkeypatch.setattr(router, "ask_jev", fake_ask_jev)
        return sent

    install.sent = sent
    return install
