"""Background jobs and the jobs builtin."""
import time

from jevsh.shell.jobs import refresh
from jevsh.shell.repl import dispatch


def test_background_returns_before_the_child_finishes(session, capfd):
    started = time.time()
    status = dispatch("sleep 2 &", session)
    elapsed = time.time() - started

    assert status == 0
    assert elapsed < 1.0, "the REPL waited for the background child"
    assert len(session.jobs) == 1
    capfd.readouterr()

    session.jobs[0].process.kill()
    session.jobs[0].process.wait()


def test_background_announces_id_and_pid(session, capfd):
    dispatch("sleep 1 &", session)
    out = capfd.readouterr().out.strip()

    assert out.startswith("[1] ")
    assert out.split()[1].isdigit()

    session.jobs[0].process.kill()
    session.jobs[0].process.wait()


def test_job_ids_increment(session, capfd):
    dispatch("sleep 1 &", session)
    dispatch("sleep 1 &", session)

    assert [job.id for job in session.jobs] == [1, 2]
    capfd.readouterr()

    for job in session.jobs:
        job.process.kill()
        job.process.wait()


def test_jobs_lists_running_then_done(session, capfd):
    dispatch("sleep 0.3 &", session)
    capfd.readouterr()

    dispatch("jobs", session)
    assert "Running" in capfd.readouterr().out

    session.jobs[0].process.wait()
    dispatch("jobs", session)
    assert "Done" in capfd.readouterr().out


def test_finished_jobs_are_forgotten_after_reporting(session, capfd):
    dispatch("true &", session)
    session.jobs[0].process.wait()

    dispatch("jobs", session)       # reports Done
    dispatch("jobs", session)       # and then the table is empty

    assert session.jobs == []
    capfd.readouterr()


def test_refresh_reaps_so_no_zombie_remains(session, capfd):
    dispatch("true &", session)
    process = session.jobs[0].process
    process.wait()

    refresh(session)

    assert session.jobs[0].status == "Done"
    assert process.returncode == 0
    capfd.readouterr()


def test_background_command_keeps_its_text(session, capfd):
    dispatch("sleep 1 &", session)

    assert "sleep 1" in session.jobs[0].command
    capfd.readouterr()

    session.jobs[0].process.kill()
    session.jobs[0].process.wait()


def test_missing_background_command_reports(session, capfd):
    assert dispatch("no_such_background_cmd &", session) == 127
    assert "command not found" in capfd.readouterr().out
    assert session.jobs == []
