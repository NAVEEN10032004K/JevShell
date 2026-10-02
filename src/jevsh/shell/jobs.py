"""Background job tracking.

Deliberately limited: no fg, bg, SIGTSTP or terminal ownership. Just enough to
start something with `&` and ask about it later with `jobs`.
"""
from dataclasses import dataclass


@dataclass
class Job:
    id: int
    process: object
    command: str
    status: str = "Running"

    @property
    def pid(self) -> int:
        return self.process.pid


def register(session, process, command: str) -> Job:
    job = Job(id=session.next_job_id, process=process, command=command)
    session.next_job_id += 1
    session.jobs.append(job)

    return job


def refresh(session) -> None:
    """Poll each job so finished ones are reaped rather than left as zombies."""
    for job in session.jobs:
        if job.status == "Running" and job.process.poll() is not None:
            job.status = "Done"


def builtin_jobs(args: list[str], session) -> int:
    refresh(session)

    for job in session.jobs:
        print(f"[{job.id}] {job.status:<8} {job.command}")

    # A finished job is reported once and then forgotten, as bash does. Without
    # this the table would grow for the life of the session.
    session.jobs = [job for job in session.jobs if job.status == "Running"]

    return 0
