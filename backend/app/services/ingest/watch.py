"""Background watcher for the ScanSnap output folder.

When the ScanSnap ix1600 saves a new PDF, the watcher auto-ingests it through
the same pipeline as a manual scan. A single worker thread drains a queue of
paths, deduped so the same file can't be ingested twice concurrently from
overlapping on_created/on_moved events (de-duplication by content hash also
makes repeated events harmless, but this avoids the wasted work and the log
noise of racing threads). Auto-starts at app startup so a reboot doesn't
silently turn auto-ingest off until someone remembers to click Start.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_state = {"observer": None, "folder": None, "started_at": None, "ingested": 0, "last": None}
_lock = threading.Lock()
_queue: "queue.Queue[str]" = queue.Queue()
_queued: set[str] = set()
_worker: threading.Thread | None = None


def _wait_stable(path: Path, checks: int = 3, interval: float = 0.5, max_wait: float = 10.0) -> bool:
    """Wait until the file's size stops changing across consecutive polls.

    ScanSnap writes PDFs incrementally, so a naive "size > 0" check can hash
    and ingest a half-written file, producing a junk unmatched/corrupt row.
    Returns False if the file never appears or never stabilizes in time.
    """
    deadline = time.monotonic() + max_wait
    last_size = -1
    stable_count = 0
    while time.monotonic() < deadline:
        try:
            size = path.stat().st_size if path.exists() else -1
        except OSError:
            size = -1
        if size > 0 and size == last_size:
            stable_count += 1
            if stable_count >= checks:
                return True
        else:
            stable_count = 0
        last_size = size
        time.sleep(interval)
    return False


def _ingest_one(path_str: str) -> None:
    from ...db import SessionLocal
    from ..pdf import ingest

    p = Path(path_str)
    if p.suffix.lower() != ".pdf":
        return
    if not _wait_stable(p):
        logger.warning("Gave up waiting for %s to finish writing", p)
        _state["last"] = {"file": p.name, "status": "error", "error": "File never finished writing"}
        return

    session = SessionLocal()
    try:
        businesses = ingest._businesses_payload(session)
        try:
            r = ingest.ingest_path(session, p, source="scansnap", businesses=businesses)
        except PermissionError:
            # ScanSnap (and some network drives) can briefly hold an exclusive
            # lock right after the write completes — one retry covers it.
            time.sleep(1.0)
            r = ingest.ingest_path(session, p, source="scansnap", businesses=businesses)
        session.commit()
        _state["ingested"] += 1
        _state["last"] = r
    except Exception as e:
        logger.exception("Failed to ingest %s", p)
        _state["last"] = {"file": p.name, "status": "error", "error": str(e)}
    finally:
        session.close()


def _worker_loop() -> None:
    while True:
        path_str = _queue.get()
        try:
            _ingest_one(path_str)
        finally:
            _queued.discard(path_str)
            _queue.task_done()


def _enqueue(path_str: str) -> None:
    if path_str in _queued:
        return
    _queued.add(path_str)
    _queue.put(path_str)


def _ensure_worker() -> None:
    global _worker
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_worker_loop, daemon=True)
        _worker.start()


def start(folder: str) -> dict:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    with _lock:
        if _state["observer"] is not None:
            return status()
        root = Path(folder).expanduser()
        if not root.exists():
            return {"running": False, "error": f"Folder not found: {folder}"}

        _ensure_worker()

        class Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    _enqueue(event.src_path)

            def on_moved(self, event):
                if not event.is_directory:
                    _enqueue(event.dest_path)

        obs = Observer()
        obs.schedule(Handler(), str(root), recursive=True)
        obs.daemon = True
        obs.start()
        _state.update(observer=obs, folder=str(root), started_at=time.time(), ingested=0, last=None)
        logger.info("Started watching %s", root)
        return status()


def stop() -> dict:
    with _lock:
        obs = _state["observer"]
        if obs is not None:
            obs.stop()
            _state["observer"] = None
            logger.info("Stopped watching %s", _state["folder"])
        return status()


def status() -> dict:
    return {
        "running": _state["observer"] is not None,
        "folder": _state["folder"],
        "ingested_this_session": _state["ingested"],
        "last": _state["last"],
    }


def autostart_if_enabled() -> None:
    """Called at app startup — re-arm the watcher unless the user explicitly
    stopped it, so a reboot doesn't silently disable auto-ingest."""
    from ...db import SessionLocal
    from ...models import Setting

    session = SessionLocal()
    try:
        row = session.query(Setting).filter(Setting.key == "scansnap_path").first()
        folder = row.value if row else ""
        if not folder or not Path(folder).expanduser().exists():
            return
        enabled_row = session.query(Setting).filter(Setting.key == "watch_enabled").first()
        if enabled_row is not None and enabled_row.value == "0":
            return
        start(folder)
    finally:
        session.close()
