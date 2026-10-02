"""Operators must not launder a command: pipes, chains, background, redirection."""
from pathlib import Path

from jevsh.safety import SafetyLevel, evaluate_all

ALLOW, CONFIRM, BLOCK = SafetyLevel.ALLOW, SafetyLevel.CONFIRM, SafetyLevel.BLOCK
HOME = str(Path.home())


def test_safe_pipelines_stay_allowed(level):
    assert level("echo hello | grep hello") is ALLOW
    assert level("cat file.txt | grep hello") is ALLOW
    assert level("ps aux | grep python | head") is ALLOW


def test_danger_in_the_second_stage_is_caught(level):
    assert level("echo data | rm file.txt") is CONFIRM
    assert level(f"echo data | rm -rf {HOME}") is BLOCK


def test_danger_in_the_middle_of_a_long_pipeline(level):
    assert level(f"echo a | cat | rm -rf {HOME} | cat") is BLOCK


def test_chaining_is_inspected(level):
    assert level("mkdir test && cd test") is ALLOW
    assert level("mkdir test && rm important.txt") is CONFIRM
    assert level(f"echo safe ; rm -rf /") is BLOCK
    assert level(f"echo safe && rm -rf {HOME}") is BLOCK
    assert level(f"echo safe || rm -rf {HOME}") is BLOCK


def test_a_safe_command_cannot_shield_a_dangerous_one(level):
    # Before, after, and on both sides.
    assert level("rm -rf / ; echo safe") is BLOCK
    assert level("echo safe ; rm -rf / ; echo also_safe") is BLOCK


def test_background_does_not_bypass_policy(level):
    assert level("python server.py &") is ALLOW
    assert level("rm file &") is CONFIRM
    assert level(f"rm -rf {HOME}/important &") is CONFIRM
    assert level("rm -rf / &") is BLOCK


def test_redirection_is_evaluated_as_a_write(level):
    assert level("echo hello > file.txt") is ALLOW
    assert level("echo hello >> file.txt") is ALLOW
    assert level("cat < file.txt") is ALLOW
    assert level("echo malicious > /etc/something") is BLOCK
    assert level(f"echo malicious > {HOME}") is BLOCK


def test_redirection_does_not_hide_the_command(level):
    assert level("rm important.txt > output.txt") is CONFIRM
    assert level(f"rm -rf {HOME} > output.txt") is BLOCK


def test_every_command_in_the_tree_is_reported(session):
    from jevsh.shell.parser import parse

    tree = parse("a | b && c || d ; e", env=session.environment, cwd=session.cwd)
    findings = evaluate_all(tree, session)

    assert len(findings) == 5


def test_the_worst_finding_decides(session):
    from jevsh.shell.parser import parse

    line = f"echo ok ; rm notes.txt ; rm -rf {HOME}"
    tree = parse(line, env=session.environment, cwd=session.cwd)
    levels = [f.level for f in evaluate_all(tree, session)]

    assert ALLOW in levels and CONFIRM in levels and BLOCK in levels


def test_blocked_line_does_not_run_its_safe_commands(session, tmp_path, capfd):
    from jevsh.shell.repl import dispatch

    dispatch(f"echo safe > marker.txt ; rm -rf {HOME}", session)

    assert not (tmp_path / "marker.txt").exists()
    assert "blocked" in capfd.readouterr().out.lower()
