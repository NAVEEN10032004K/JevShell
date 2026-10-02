"""Pipelines: data flow, exit status, no deadlocks."""
from jevsh.shell.repl import dispatch


def test_single_stage_pipe(session, capfd):
    assert dispatch("echo hello | grep hello", session) == 0
    assert capfd.readouterr().out.strip() == "hello"


def test_no_match_gives_grep_exit_one(session, capfd):
    assert dispatch("echo hello | grep missing", session) == 1
    assert capfd.readouterr().out.strip() == ""


def test_head_truncates_without_hanging(session, capfd):
    # If the parent did not close its copy of the upstream pipe, printf would
    # never see SIGPIPE and this would block forever.
    assert dispatch('printf "a\\nb\\nc\\n" | head -2', session) == 0
    assert capfd.readouterr().out == "a\nb\n"


def test_three_stage_pipeline(session, capfd):
    status = dispatch('printf "a\\nb\\nc\\nd\\n" | grep -v d | head -2', session)

    assert status == 0
    assert capfd.readouterr().out == "a\nb\n"


def test_long_pipeline(session, capfd):
    assert dispatch("echo x | cat | cat | cat | cat", session) == 0
    assert capfd.readouterr().out.strip() == "x"


def test_status_comes_from_the_last_stage(session, capfd):
    assert dispatch("echo x | false", session) == 1
    assert dispatch("false | echo x", session) == 0
    capfd.readouterr()


def test_large_payload_does_not_deadlock(session, capfd):
    # 200k of data through a pipe: would hang if the executor read in-process
    # instead of letting the two children talk directly.
    assert dispatch('python3 -c "print(\\"x\\" * 200000)" | wc -c', session) == 0
    assert int(capfd.readouterr().out.strip()) == 200001


def test_missing_command_in_a_pipeline(session, capfd):
    assert dispatch("echo x | no_such_command_xyz", session) == 127
    assert "command not found: no_such_command_xyz" in capfd.readouterr().out


def test_pipeline_runs_in_session_cwd(session, tmp_path, capfd):
    (tmp_path / "work").mkdir()
    session.change_directory("work")

    assert dispatch("pwd | cat", session) == 0
    assert capfd.readouterr().out.strip() == str(tmp_path / "work")


def test_stderr_is_not_piped_into_the_next_stage(session, capfd):
    # Only stdout flows down the pipe; stderr goes straight to the terminal.
    dispatch('python3 -c "import sys; print(\\"OUT\\"); sys.stderr.write(\\"ERR\\")" | cat', session)
    captured = capfd.readouterr()

    assert "OUT" in captured.out
    assert "ERR" not in captured.out
    assert "ERR" in captured.err
