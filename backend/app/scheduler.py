"""Phase 6 — daily automation via APScheduler.

A background scheduler runs a daily job: scan Gmail (if connected), ingest the
ScanSnap folder, and record a summary. Enable/time persist in Settings so it
survives restarts. `run_now` executes the job in a thread (the Gmail scan can
take minutes) and stores results when done.

The in-app scheduler runs while BookKeeper is running. To keep it always on,
launch BookKeeper at login on the Windows host (see README / Automation page).
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_sched: BackgroundScheduler | None = None
JOB_ID = "bookkeeper-daily"
_run_lock = threading.Lock()


def _set(session, key, value):
    from .models import Setting

    row = session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value
    session.commit()


def _get(session, key, default=""):
    from .models import Setting

    row = session.get(Setting, key)
    return row.value if row and row.value != "" else default


def daily_job() -> dict:
    """The work performed each day (also used by run-now).

    Guarded by ``_run_lock`` so a manual "Run now" click can't overlap with
    the scheduled cron firing (or a double-click of Run now with itself) —
    without this, two concurrent Gmail scans / folder scans would double-hit
    the Gmail API quota and interleave their status writes.
    """
    if not _run_lock.acquire(blocking=False):
        logger.info("daily_job skipped: a run is already in progress")
        return {"skipped": "already running"}

    from .db import SessionLocal
    from .services.gmail import client, scan as gscan
    from .services.pdf import ingest

    try:
        session = SessionLocal()
        summary = {"started": datetime.now().isoformat(timespec="seconds")}
        try:
            if client.mode() == "real" and client.is_connected():
                try:
                    g = gscan.run_scan(session)
                    summary["gmail"] = {"new": g["new_emails"], "total": g["total_emails"],
                                        "incremental": g.get("incremental", False)}
                except Exception as e:
                    logger.exception("Gmail scan failed")
                    summary["gmail"] = {"error": str(e)}

                # Pull PDF/image attachments from matched emails into Documents.
                if _get(session, "attachments_enabled", "1") == "1":
                    try:
                        from .services.gmail import attachments

                        a = attachments.fetch_new(session)
                        summary["attachments"] = {
                            "saved": a.get("saved", 0),
                            "duplicates": a.get("duplicates", 0),
                            "errors": a.get("errors", 0),
                        }
                    except Exception as e:
                        logger.exception("Attachment fetch failed")
                        summary["attachments"] = {"error": str(e)}
                else:
                    summary["attachments"] = {"skipped": "disabled"}
            else:
                summary["gmail"] = {"skipped": "not connected"}

            try:
                d = ingest.scan_folder(session, source="scansnap")
                summary["documents"] = d.get("summary", {}) | {"scanned": d.get("scanned", 0)}
            except Exception as e:
                logger.exception("Folder scan failed")
                summary["documents"] = {"error": str(e)}

            # AI review of any new/unreviewed documents (only if enabled + key present)
            try:
                from .services.ai import reviewer

                if reviewer.is_enabled(session):
                    ai_res = reviewer.review_new(session, limit=100)
                    summary["ai"] = {"reviewed": ai_res.get("reviewed", 0),
                                     "errors": ai_res.get("errors", 0)}
                else:
                    summary["ai"] = {"skipped": "disabled"}
            except Exception as e:
                logger.exception("AI review failed")
                summary["ai"] = {"error": str(e)}

            try:
                from .services import backup

                backup.backup_now("daily")
            except Exception as e:
                logger.exception("Daily backup failed")
                summary["backup"] = {"error": str(e)}

            summary["finished"] = datetime.now().isoformat(timespec="seconds")
            _set(session, "automation_last_run", summary["finished"])
            _set(session, "automation_last_summary", json.dumps(summary))
        finally:
            session.close()
        return summary
    finally:
        _run_lock.release()


def _ensure_started():
    global _sched
    if _sched is None:
        _sched = BackgroundScheduler(daemon=True)
        _sched.start()
    return _sched


def schedule(hour: int, minute: int) -> None:
    sched = _ensure_started()
    if sched.get_job(JOB_ID):
        sched.remove_job(JOB_ID)
    sched.add_job(
        daily_job, CronTrigger(hour=hour, minute=minute), id=JOB_ID,
        replace_existing=True, max_instances=1, coalesce=True,
    )


def enable(session, hour: int, minute: int) -> dict:
    _set(session, "automation_enabled", "1")
    _set(session, "automation_hour", str(hour))
    _set(session, "automation_minute", str(minute))
    schedule(hour, minute)
    return status(session)


def disable(session) -> dict:
    _set(session, "automation_enabled", "0")
    sched = _ensure_started()
    if sched.get_job(JOB_ID):
        sched.remove_job(JOB_ID)
    return status(session)


def run_now() -> dict:
    if _run_lock.locked():
        return {"started": False, "error": "A run is already in progress."}
    threading.Thread(target=daily_job, daemon=True).start()
    return {"started": True}


def init_from_settings() -> None:
    """Called at app startup — re-arm the job if it was enabled."""
    from .db import SessionLocal

    session = SessionLocal()
    try:
        if _get(session, "automation_enabled", "0") == "1":
            schedule(int(_get(session, "automation_hour", "2")),
                     int(_get(session, "automation_minute", "0")))
    finally:
        session.close()


def status(session) -> dict:
    enabled = _get(session, "automation_enabled", "0") == "1"
    last = _get(session, "automation_last_summary", "")
    sched = _ensure_started()
    job = sched.get_job(JOB_ID)
    return {
        "enabled": enabled,
        "hour": int(_get(session, "automation_hour", "2")),
        "minute": int(_get(session, "automation_minute", "0")),
        "next_run": str(job.next_run_time) if job else None,
        "last_run": _get(session, "automation_last_run", None) or None,
        "last_summary": json.loads(last) if last else None,
    }
