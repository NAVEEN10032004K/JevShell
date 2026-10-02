"""--dry-run reports a decision and executes nothing."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_cli(*args, cwd=None):
    """Invoke the CLI in a child process.

    pytest's pythonpath applies to this process only, so the child is given src/
    explicitly. That keeps these tests working from a bare checkout, whether or
    not the package happens to be installed.
    """
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")

    return subprocess.run(
        [sys.executable, "-m", "jevsh", *args],
        cwd=cwd or ROOT, capture_output=True, text=True, timeout=30,
        env=environment,
    )


def test_dry_run_reports_without_executing(tmp_path):
    victim = tmp_path / "important.txt"
    victim.write_text("precious")

    result = run_cli("--dry-run", "-c", f"rm {victim}")

    assert result.returncode == 0
    assert "CONFIRM" in result.stdout
    assert "skipped (dry run)" in result.stdout
    assert victim.exists(), "dry run must not execute"


def test_dry_run_shows_the_command_and_reason(tmp_path):
    result = run_cli("--dry-run", "-c", "rm notes.txt")

    assert "Command:" in result.stdout
    assert "rm notes.txt" in result.stdout
    assert "Safety:" in result.stdout
    assert "Reason:" in result.stdout


def test_dry_run_reports_allow(tmp_path):
    result = run_cli("--dry-run", "-c", "echo hello")

    assert "ALLOW" in result.stdout
    assert "skipped (dry run)" in result.stdout


def test_dry_run_reports_block_without_executing():
    result = run_cli("--dry-run", "-c", "rm -rf /")

    assert "BLOCK" in result.stdout
    assert "skipped (dry run)" in result.stdout
    assert Path("/").exists()


def test_non_interactive_confirm_skips_and_does_not_hang(tmp_path):
    victim = tmp_path / "important.txt"
    victim.write_text("precious")

    result = run_cli("-c", f"rm {victim}")

    assert result.returncode != 0
    assert "CONFIRM" in result.stdout
    assert "confirmation required in interactive mode" in result.stdout
    assert victim.exists(), "a confirmation-required command must not run silently"


def test_non_interactive_allow_executes(tmp_path):
    target = tmp_path / "made.txt"

    result = run_cli("-c", f"touch {target}")

    assert result.returncode == 0
    assert target.exists()


def test_non_interactive_block_is_refused():
    result = run_cli("-c", "rm -rf /")

    assert result.returncode != 0
    assert "blocked" in result.stdout.lower()


def test_dry_run_without_a_command_is_an_error():
    result = run_cli("--dry-run")

    assert result.returncode != 0
    assert "--dry-run needs a command" in result.stderr


def test_bare_argv_routes_to_jev_not_the_shell(monkeypatch):
    """Stage 1's contract: a natural-language argument is not a shell command.

    Routing is checked without touching the network, by standing in for the API
    call. A live request here could really create directories.
    """
    import jevsh.cli as cli
    import jevsh.jev_router as router

    seen = {}

    def fake_ask_jev(text):
        seen["jev"] = text
        return {
            "answers": {
                "decision": {
                    "type": "choice", "choice": "pwd",
                    "confidence": 1.0, "probabilities": {"pwd": 1.0},
                }
            }
        }

    monkeypatch.setattr(router, "ask_jev", fake_ask_jev)
    monkeypatch.setattr(sys, "argv", ["jevsh", "create", "a", "folder", "called", "demo"])

    cli.main()

    # Only the user's own words reached Jev.
    assert seen["jev"] == "create a folder called demo"


def test_shell_flag_does_not_route_to_jev(monkeypatch):
    import jevsh.cli as cli
    import jevsh.jev_router as router

    def must_not_be_called(text):
        raise AssertionError("-c must not reach the Jev path")

    monkeypatch.setattr(router, "ask_jev", must_not_be_called)
    monkeypatch.setattr(sys, "argv", ["jevsh", "-c", "echo hi"])

    assert cli.main() == 0
