"""Aliases: definition, expansion, cycle detection."""
import pytest

from jevsh.shell.aliases import AliasError, expand
from jevsh.shell.parser import parse, tokenize
from jevsh.shell.repl import dispatch

SPLIT = tokenize


def test_define_and_use(session, capfd):
    assert dispatch('alias greet="echo hello"', session) == 0
    assert session.aliases["greet"] == "echo hello"

    assert dispatch("greet", session) == 0
    assert capfd.readouterr().out.strip() == "hello"


def test_alias_arguments_are_appended(session, capfd):
    dispatch('alias say="echo"', session)
    dispatch("say one two", session)

    assert capfd.readouterr().out.strip() == "one two"


def test_alias_with_flags(session, tmp_path, capfd):
    (tmp_path / "f.txt").write_text("x")
    dispatch('alias ll="ls -a"', session)

    assert dispatch("ll", session) == 0
    assert "f.txt" in capfd.readouterr().out


def test_listing_aliases(session, capfd):
    dispatch('alias b="echo b"', session)
    dispatch('alias a="echo a"', session)
    capfd.readouterr()

    dispatch("alias", session)
    lines = capfd.readouterr().out.splitlines()

    assert lines == ["alias a='echo a'", "alias b='echo b'"]


def test_query_a_single_alias(session, capfd):
    dispatch('alias ll="ls -l"', session)
    capfd.readouterr()

    assert dispatch("alias ll", session) == 0
    assert capfd.readouterr().out.strip() == "alias ll='ls -l'"


def test_query_unknown_alias_fails(session, capfd):
    assert dispatch("alias nope", session) == 1
    assert "not found" in capfd.readouterr().out


def test_unalias_removes(session, capfd):
    dispatch('alias ll="echo hello"', session)
    assert dispatch("unalias ll", session) == 0
    assert "ll" not in session.aliases

    # Now it is just a missing command again.
    assert dispatch("ll", session) == 127
    capfd.readouterr()


def test_unalias_unknown_fails(session, capfd):
    assert dispatch("unalias nope", session) == 1
    assert "not found" in capfd.readouterr().out


def test_alias_only_expands_in_command_position(session, capfd):
    dispatch('alias ll="SHOULD_NOT_APPEAR"', session)
    dispatch("echo ll", session)

    assert capfd.readouterr().out.strip() == "ll"


def test_chained_aliases_expand(session, capfd):
    dispatch('alias a="b"', session)
    dispatch('alias b="echo deep"', session)

    assert dispatch("a", session) == 0
    assert capfd.readouterr().out.strip() == "deep"


def test_cycle_is_reported_not_infinite():
    aliases = {"a": "b", "b": "a"}

    with pytest.raises(AliasError, match="cyclic"):
        expand(["a"], aliases, SPLIT)


def test_three_way_cycle_is_reported():
    aliases = {"a": "b", "b": "c", "c": "a"}

    with pytest.raises(AliasError, match="cyclic"):
        expand(["a"], aliases, SPLIT)


def test_self_reference_expands_once(session):
    # alias ls="ls -l" must not recurse; one expansion then stop.
    assert expand(["ls"], {"ls": "ls -l"}, SPLIT) == ["ls", "-l"]


def test_cycle_in_the_repl_is_a_message_not_a_crash(session, capfd):
    dispatch('alias a="b"', session)
    dispatch('alias b="a"', session)
    capfd.readouterr()

    assert dispatch("a", session) == 2
    assert "cyclic" in capfd.readouterr().out


def test_aliases_expand_at_parse_time(session):
    # The IR must hold the real command, so the policy layer sees it.
    tree = parse("del x", env=session.environment, aliases={"del": "rm -rf"})
    argv = tree.items[0].node.pipelines[0].commands[0].argv

    assert argv == ["rm", "-rf", "x"]


def test_aliases_are_session_local(session):
    from jevsh.shell import ShellSession

    dispatch('alias ll="echo hi"', session)

    assert ShellSession().aliases == {}
