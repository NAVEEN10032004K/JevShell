"""The three tiers, over the command examples the spec names."""
from jevsh.safety import SafetyLevel, evaluate, evaluate_command
from jevsh.safety.commands import Category, classify
from jevsh.shell.ast import Pipeline, SimpleCommand

ALLOW, CONFIRM, BLOCK = SafetyLevel.ALLOW, SafetyLevel.CONFIRM, SafetyLevel.BLOCK


def test_safe_commands_are_allowed(level):
    for line in (
        "pwd", "ls", "ls -lah", "echo hello", "cat file.txt",
        "python --version", "git status", "mkdir test", "touch test.txt",
        "head -2 notes.txt", "grep pattern file", "wc -l file", "find . -name x",
    ):
        assert level(line) is ALLOW, line


def test_modifying_commands_need_confirmation(level):
    for line in (
        "rm file.txt", "rmdir empty_dir", "mv file1 file2", "cp file1 file2",
        "chmod 755 script.sh", "chown me file", "kill 1234", "shred secret",
    ):
        assert level(line) is CONFIRM, line


def test_builtins_are_allowed(level):
    for line in (
        "cd test", "pwd", "history", "clear", "export NAME=x", "unset NAME",
        "alias ll=ls", "unalias ll", "jobs",
    ):
        assert level(line) is ALLOW, line


def test_unknown_commands_are_allowed_not_blocked(level):
    # Blocking everything unrecognized would make the shell useless.
    for line in ("some-unknown-tool", "npm install", "cargo build", "./configure"):
        assert level(line) is ALLOW, line


def test_aliases_in_the_allow_case_stay_allowed(session, level):
    session.aliases["ll"] = "ls -lah"

    assert level("ll") is ALLOW


def test_reading_is_allowed_even_from_a_protected_path(level):
    # Reading /etc is fine; only writing and deleting are restricted.
    assert level("cat /etc/hosts") is ALLOW
    assert level("ls /usr/bin") is ALLOW


def test_categories_are_assigned_sensibly():
    assert classify(["ls"]) is Category.READ_ONLY
    assert classify(["mkdir", "x"]) is Category.FILESYSTEM_WRITE
    assert classify(["rm", "x"]) is Category.FILESYSTEM_DELETE
    assert classify(["kill", "1"]) is Category.PROCESS_CONTROL
    assert classify(["chmod", "755", "x"]) is Category.SYSTEM_CONFIGURATION
    assert classify(["curl", "url"]) is Category.NETWORK
    assert classify(["totally-made-up"]) is Category.UNKNOWN


def test_result_carries_a_reason_and_the_command(session):
    result = evaluate_command(SimpleCommand(argv=["rm", "notes.txt"]), session)

    assert result.level is CONFIRM
    assert result.reason
    assert result.command == "rm notes.txt"


def test_empty_command_is_allowed(session):
    assert evaluate(Pipeline([SimpleCommand()]), session).level is ALLOW


def test_levels_order_by_severity():
    assert ALLOW.severity < CONFIRM.severity < BLOCK.severity


def test_legacy_names_are_the_same_members():
    # The Jev layer has used SAFE and BLOCKED since Stage 1.
    assert SafetyLevel.SAFE is ALLOW
    assert SafetyLevel.BLOCKED is BLOCK
