"""Expansion must never execute anything.

Command substitution is out of scope for this stage, and the danger is not that
it is missing but that it might work by accident. These tests pin it shut.
"""
from jevsh.shell.repl import dispatch


def test_dollar_paren_does_not_execute(session, tmp_path, capfd):
    # The §15 requirement, stated exactly.
    assert dispatch("echo $(touch forbidden)", session) == 0

    assert not (tmp_path / "forbidden").exists()
    assert "$(touch" in capfd.readouterr().out


def test_backticks_do_not_execute(session, tmp_path, capfd):
    dispatch("echo `touch also_forbidden`", session)

    assert not (tmp_path / "also_forbidden").exists()
    assert "`touch" in capfd.readouterr().out


def test_arithmetic_expansion_is_literal(session, capfd):
    dispatch("echo $((1+2))", session)
    out = capfd.readouterr().out.strip()

    assert out != "3"
    assert "$((1" in out


def test_parameter_default_syntax_is_literal(session, capfd):
    dispatch("echo ${NOPE:-fallback}", session)

    # Advanced parameter expansion is out of scope, and ${NOPE:-fallback} is not
    # a bare name, so the whole thing survives as text.
    assert capfd.readouterr().out.strip() == "${NOPE:-fallback}"


def test_substitution_inside_double_quotes_does_not_execute(session, tmp_path):
    dispatch('echo "$(touch quoted_forbidden)"', session)

    assert not (tmp_path / "quoted_forbidden").exists()


def test_substitution_as_a_redirect_target_does_not_execute(session, tmp_path):
    dispatch("echo hi > $(touch target_forbidden)", session)

    assert not (tmp_path / "target_forbidden").exists()


def test_substitution_in_a_variable_value_does_not_execute(session, tmp_path, capfd):
    dispatch('export EVIL="$(touch var_forbidden)"', session)
    dispatch("echo $EVIL", session)

    assert not (tmp_path / "var_forbidden").exists()
    capfd.readouterr()


def test_expanded_value_is_not_reparsed_for_operators(session, tmp_path, capfd):
    # If expansion were re-parsed, this would run touch via a second command.
    dispatch('export EVIL="; touch reparse_forbidden"', session)
    dispatch("echo $EVIL", session)

    assert not (tmp_path / "reparse_forbidden").exists()
    assert ";" in capfd.readouterr().out


def test_expanded_value_is_not_reparsed_for_pipes(session, tmp_path, capfd):
    dispatch('export EVIL="| touch pipe_forbidden"', session)
    dispatch("echo $EVIL", session)

    assert not (tmp_path / "pipe_forbidden").exists()
    capfd.readouterr()


def test_glob_cannot_execute(session, tmp_path, capfd):
    (tmp_path / "$(touch glob_forbidden)").write_text("")
    dispatch("echo *", session)

    assert not (tmp_path / "glob_forbidden").exists()
    capfd.readouterr()


def test_no_shell_is_ever_invoked(session, capfd):
    # /bin/sh would expand $(...) itself. If the executor ever passed a raw
    # string to a shell, this would print the cwd instead of the literal text.
    dispatch("echo $(pwd)", session)

    assert "$(pwd)" in capfd.readouterr().out
