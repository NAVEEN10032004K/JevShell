"""Path canonicalization: dots, tildes, symlinks, missing paths, system dirs."""
import os
from pathlib import Path

import pytest

from jevsh.safety import SafetyLevel, canonicalize, is_protected, is_system, is_temp
from jevsh.shell import ShellSession

ALLOW, CONFIRM, BLOCK = SafetyLevel.ALLOW, SafetyLevel.CONFIRM, SafetyLevel.BLOCK
HOME = Path.home()


def test_dot_resolves_onto_the_current_directory(level):
    # Standing in home, `rm -rf .` is `rm -rf ~`.
    at_home = ShellSession(cwd=HOME, environment={"HOME": str(HOME)})

    assert level("rm -rf .", at_home) is BLOCK
    assert level("rm -rf ./", at_home) is BLOCK


def test_dotdot_resolves_upward(level):
    at_home = ShellSession(cwd=HOME, environment={"HOME": str(HOME)})

    # One level above home is a parent of home, so still protected.
    assert level("rm -rf ..", at_home) is BLOCK


def test_traversal_back_to_root_is_blocked(level):
    at_home = ShellSession(cwd=HOME, environment={"HOME": str(HOME)})

    assert level("rm -rf ~/../..", at_home) is BLOCK


def test_tilde_expands_to_the_session_home(level):
    assert level("rm -rf ~") is BLOCK


def test_symlink_to_home_is_blocked(session, tmp_path, level):
    link = tmp_path / "shortcut"

    try:
        link.symlink_to(HOME)
    except OSError:
        pytest.skip("symlinks unavailable")

    # The link name is innocent; what it points at is not.
    assert level("rm -rf shortcut") is BLOCK


def test_symlink_to_an_ordinary_directory_is_not_blocked(session, tmp_path, level):
    target = tmp_path / "ordinary"
    target.mkdir()
    (tmp_path / "link").symlink_to(target)

    assert level("rm -rf link") is CONFIRM


def test_nonexistent_paths_evaluate_without_raising(level):
    assert level("rm -rf no_such_directory_xyz") is CONFIRM
    assert level("rm /a/b/c/d/e/f/does/not/exist") is CONFIRM


def test_canonicalize_handles_a_missing_path():
    result = canonicalize("also/missing", cwd="/tmp")

    assert result.is_absolute()


def test_canonicalize_uses_the_given_cwd_not_the_process_cwd(tmp_path):
    assert canonicalize("file.txt", cwd=tmp_path) == (tmp_path / "file.txt").resolve()


def test_system_paths_are_blocked(level):
    for line in (
        "rm /etc/passwd", "rm -rf /usr/local/lib", "echo x > /etc/hosts",
        "rm /bin/ls", "chmod 777 /etc",
    ):
        assert level(line) is BLOCK, line


def test_temp_is_exempt_from_the_system_rule(level):
    # /var/folders is under the protected /var, but temp space must stay usable
    # or every test that writes to tmp_path would be refused.
    assert level("rm /tmp/scratch.txt") is CONFIRM
    assert level("echo hi > /tmp/scratch.txt") is ALLOW


def test_tmp_path_itself_is_usable(session, tmp_path, level):
    assert is_temp(tmp_path.resolve())
    assert level("rm notes.txt") is CONFIRM
    assert level("echo hi > notes.txt") is ALLOW


def test_predicates_agree_with_the_rules():
    assert is_protected(Path("/"))
    assert is_protected(HOME)
    assert is_protected(HOME.parent)
    assert not is_protected(HOME / "Documents")

    if os.name != "nt":
        assert is_system(Path("/etc").resolve())
        assert not is_system(Path("/tmp").resolve())


def test_private_is_not_protected_wholesale():
    # Protecting /private would take /private/tmp and /private/var/folders with
    # it, which is where the system temp directory lives on macOS.
    if os.name != "nt":
        assert not is_system(Path("/private/tmp"))
