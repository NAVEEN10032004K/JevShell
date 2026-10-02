"""export / unset, and what a child process actually receives."""
import sys

from jevsh.shell.repl import dispatch


def test_export_sets_a_variable(session, capfd):
    assert dispatch("export PROJECT=jevsh", session) == 0
    assert session.environment["PROJECT"] == "jevsh"

    dispatch("echo $PROJECT", session)
    assert capfd.readouterr().out.strip() == "jevsh"


def test_export_value_with_spaces(session, capfd):
    dispatch('export GREETING="hello world"', session)

    assert session.environment["GREETING"] == "hello world"
    dispatch('echo "$GREETING"', session)
    assert capfd.readouterr().out.strip() == "hello world"


def test_exported_variable_reaches_a_child(session, capfd):
    dispatch("export NAME=Naveen", session)
    dispatch(f'{sys.executable} -c "import os; print(os.environ[\\"NAME\\"])"', session)

    assert capfd.readouterr().out.strip() == "Naveen"


def test_export_affects_only_later_commands(session, capfd):
    dispatch("export LATER=yes", session)
    dispatch("unset LATER", session)
    dispatch(
        f'{sys.executable} -c "import os; print(os.environ.get(\\"LATER\\", \\"absent\\"))"',
        session,
    )

    assert capfd.readouterr().out.strip() == "absent"


def test_unset_removes(session, capfd):
    dispatch("export GONE=1", session)
    assert dispatch("unset GONE", session) == 0
    assert "GONE" not in session.environment

    dispatch("echo $GONE", session)
    assert capfd.readouterr().out.strip() == ""


def test_unset_unknown_is_not_an_error(session):
    assert dispatch("unset NEVER_EXISTED", session) == 0


def test_export_rejects_an_invalid_name(session, capfd):
    assert dispatch("export 9bad=x", session) == 1
    assert "not a valid identifier" in capfd.readouterr().out


def test_export_with_no_arguments_lists(session, capfd):
    dispatch("export LISTED=1", session)
    capfd.readouterr()

    assert dispatch("export", session) == 0
    assert "export LISTED=1" in capfd.readouterr().out


def test_quoting_decides_expansion(session, capfd):
    dispatch("export N=naveen", session)
    capfd.readouterr()

    dispatch("echo $N", session)
    assert capfd.readouterr().out.strip() == "naveen"

    dispatch('echo "$N"', session)
    assert capfd.readouterr().out.strip() == "naveen"

    dispatch("echo '$N'", session)
    assert capfd.readouterr().out.strip() == "$N"


def test_unset_variable_expands_to_empty(session, capfd):
    dispatch("echo [$NOT_SET_ANYWHERE]", session)

    assert capfd.readouterr().out.strip() == "[]"


def test_braced_form(session, capfd):
    dispatch("export N=x", session)
    capfd.readouterr()

    dispatch("echo ${N}y", session)
    assert capfd.readouterr().out.strip() == "xy"


def test_session_env_is_not_the_process_env(session):
    import os

    dispatch("export ONLY_IN_SESSION=1", session)

    assert "ONLY_IN_SESSION" not in os.environ
