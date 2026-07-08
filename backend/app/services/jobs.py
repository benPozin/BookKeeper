"""In-memory background job registry.

A tiny job runner for long operations (Gmail scan, folder scan, AI review)
that would otherwise block a request for minutes with no feedback. Jobs run
in a daemon thread; the frontend polls ``GET /api/jobs/{id}`` for progress.
State lives in memory only — jobs don't survive a restart, which is fine
since nothing here needs to resume across process boundaries, and volume is
low (one user, at most a couple of jobs a day).
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Callable

logger = logging.getLogger(__name__)

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def start(kind: str, fn: Callable[[Callable[[int, int, str], None]], dict]) -> str:
    """Start a job in a background thread.

    ``fn`` receives a ``progress(done, total, message)`` callback it can call
    as often as it likes; it should return the same result dict the
    equivalent synchronous endpoint used to return.
    """
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {
            "id": job_id, "kind": kind, "state": "running",
            "done": 0, "total": 0, "message": "Starting…", "result": None, "error": None,
        }

    def progress(done: int, total: int, message: str = "") -> None:
        with _lock:
            job = _jobs.get(job_id)
            if job:
                job.update(done=done, total=total, message=message)

    def run() -> None:
        try:
            result = fn(progress)
            with _lock:
                _jobs[job_id].update(state="done", result=result, message="Done")
        except Exception as e:
            logger.exception("Job %s (%s) failed", job_id, kind)
            with _lock:
                _jobs[job_id].update(state="error", error=str(e), message=f"Failed: {e}")

    threading.Thread(target=run, daemon=True).start()
    return job_id


def get(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None
