"""Ordinary shell features must not be usable as a bypass.

Not a malware detector: the goal is that aliases, variables and absolute paths
cannot trivially route around the policy.
"""
from pathlib import Path

from jevsh.safety import SafetyLevel
from jevsh.shell.repl import dispatch

ALLOW, CONFIRM, BLOCK = SafetyLevel.ALLOW, SafetyLevel.CONFIRM, SafetyLevel.BLOCK
HOME = str(Path.home())


def test_variable_holding_the_command_name(session, level):
    session.environment["RM"] = "rm"

    assert level("$RM -rf /") is BLOCK
    assert level("${RM} -rf /") is BLOCK


def test_variable_holding_the_target_path(session, level):
    session.environment["TARGET"] = "/"

    assert level("rm -rf $TARGET") is BLOCK


def test_variable_holding_the_flags(session, level):
    session.environment["FLAGS"] = "-rf"

    assert level("rm $FLAGS /") is BLOCK


def test_alias_hiding_a_destructive_command(session, level):
    session.aliases["destroy"] = "rm -rf"

    assert level("destroy /") is BLOCK
    assert level(f"destroy {HOME}") is BLOCK
    assert level("destroy build/") is CONFIRM


def test_harmless_alias_stays_harmless(session, level):
    session.aliases["ll"] = "ls -lah"

    assert level("ll") is ALLOW


def test_alias_chain_is_followed(session, level):
    session.aliases["a"] = "b"
    session.aliases["b"] = "rm -rf"

    assert level("a /") is BLOCK


def test_alias_cycle_is_refused_before_execution(session, capfd):
    session.aliases["a"] = "b"
    session.aliases["b"] = "a"

    assert dispatch("a /", session) == 2
    assert "cyclic" in capfd.readouterr().out


def test_absolute_executable_path(level):
    assert level("/bin/rm -rf /") is BLOCK


def test_relative_executable_path(level):
    assert level("../../bin/rm -rf /") is BLOCK


def test_flag_reordering(level):
    for line in ("rm -rf /", "rm -fr /", "rm -r -f /", "rm -f -r /", "rm -vrf /"):
        assert level(line) is BLOCK, line


def test_trailing_slash_and_dot_forms(level):
    for line in ("rm -rf /", "rm -rf //", "rm -rf /.", "rm -rf /../"):
        assert level(line) is BLOCK, line


def test_command_substitution_cannot_be_used_at_all(session, tmp_path, capfd):
    # Stage 2 never executes it; this pins that it is still inert under Stage 3.
    dispatch("echo $(touch bypass_marker)", session)

    assert not (tmp_path / "bypass_marker").exists()
    capfd.readouterr()


def test_quoting_does_not_hide_the_target(session, level):
    assert level('rm -rf "/"') is BLOCK
    assert level("rm -rf '/'") is BLOCK


def test_everything_still_blocked_through_an_operator(session, level):
    session.aliases["destroy"] = "rm -rf"
    session.environment["RM"] = "rm"

    assert level("echo ok | destroy /") is BLOCK
    assert level("echo ok ; $RM -rf /") is BLOCK
    assert level("echo ok && destroy /") is BLOCK
    assert level("destroy / &") is BLOCK
