"""&& || ; -- short-circuit semantics and exit status."""
from jevsh.shell.repl import dispatch


def test_and_runs_on_success(session, capfd):
    assert dispatch("true && echo yes", session) == 0
    assert capfd.readouterr().out.strip() == "yes"


def test_and_skips_on_failure(session, capfd):
    assert dispatch("false && echo no", session) == 1
    assert capfd.readouterr().out.strip() == ""


def test_or_skips_on_success(session, capfd):
    assert dispatch("true || echo no", session) == 0
    assert capfd.readouterr().out.strip() == ""


def test_or_runs_on_failure(session, capfd):
    assert dispatch("false || echo yes", session) == 0
    assert capfd.readouterr().out.strip() == "yes"


def test_semicolon_runs_both_regardless(session, capfd):
    assert dispatch("echo one ; echo two", session) == 0
    assert capfd.readouterr().out == "one\ntwo\n"


def test_semicolon_runs_second_after_a_failure(session, capfd):
    assert dispatch("false ; echo still", session) == 0
    assert capfd.readouterr().out.strip() == "still"


def test_chain_is_left_associative(session, capfd):
    # false fails, so && is skipped; the || then sees the failure and runs.
    assert dispatch("false && echo a || echo b", session) == 0
    assert capfd.readouterr().out.strip() == "b"


def test_success_chain_carries_through(session, capfd):
    assert dispatch("true || echo a && echo b", session) == 0
    assert capfd.readouterr().out.strip() == "b"


def test_chaining_with_builtins(session, tmp_path, capfd):
    assert dispatch("mkdir project && cd project", session) == 0
    assert session.cwd == tmp_path / "project"
    capfd.readouterr()


def test_failed_builtin_triggers_or(session, capfd):
    assert dispatch('cd missing || echo failed', session) == 0
    assert "failed" in capfd.readouterr().out


def test_pipeline_status_drives_the_chain(session, capfd):
    assert dispatch("echo x | grep missing || echo nomatch", session) == 0
    assert capfd.readouterr().out.strip() == "nomatch"


def test_last_exit_code_is_recorded(session, capfd):
    dispatch("false", session)
    assert session.last_exit_code == 1

    dispatch("true", session)
    assert session.last_exit_code == 0
    capfd.readouterr()
