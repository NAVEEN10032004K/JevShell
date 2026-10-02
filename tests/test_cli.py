"""The command-line surface: version, help, and exit codes."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from jevsh import __version__

ROOT = Path(__file__).resolve().parent.parent


def run(*args, cwd=None):
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")

    return subprocess.run(
        [sys.executable, "-m", "jevsh", *args],
        cwd=cwd or ROOT, capture_output=True, text=True, timeout=30, env=environment,
    )


def test_version_flag():
    result = run("--version")

    assert result.returncode == 0
    assert __version__ in result.stdout


def test_version_has_one_source_of_truth():
    # pyproject reads __version__ from the package, so there is nothing to drift.
    pyproject = (ROOT / "pyproject.toml").read_text()

    assert 'version = { attr = "jevsh.__version__" }' in pyproject
    assert f'version = "{__version__}"' not in pyproject


def test_help_lists_the_essentials():
    result = run("--help")
    out = result.stdout

    assert result.returncode == 0
    for expected in ("jevsh", "--dry-run", "ai <request>", "TYPESAFE_API_KEY", "exit codes"):
        assert expected in out, expected


def test_help_documents_the_builtins():
    out = run("--help").stdout

    for builtin in ("cd", "pwd", "history", "clear", "alias", "export", "jobs", "exit"):
        assert builtin in out, builtin


@pytest.mark.parametrize(
    "command,expected",
    [
        ("pwd", 0),
        ("false", 1),
        ("rm -rf /", 77),
        ("definitely_not_a_command", 127),
        ('echo "unclosed', 2),
    ],
)
def test_exit_codes_are_meaningful(command, expected):
    # A caller must be able to tell "refused by policy" from "the command failed".
    assert run("-c", command).returncode == expected


def test_a_failing_command_keeps_its_own_code():
    assert run("-c", "sh -c 'exit 7'").returncode == 7


def test_dry_run_never_executes(tmp_path):
    victim = tmp_path / "keep.txt"
    victim.write_text("x")

    result = run("--dry-run", "-c", f"rm {victim}")

    assert result.returncode == 0
    assert victim.exists()
    assert "skipped (dry run)" in result.stdout


def test_the_module_entry_point_works():
    assert run("--version").returncode == 0
