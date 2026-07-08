"""New Scan API: mobile/desktop uploads and ScanSnap folder watching (Phase 3)."""

from __future__ import annotations

import socket
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Document, Setting
from ..services.ingest import upload, watch
from ..services.pdf import ingest

router = APIRouter(prefix="/api/scan", tags=["scan"])


def _scan_path(session: Session) -> str:
    row = session.query(Setting).filter(Setting.key == "scansnap_path").first()
    return row.value if row else ""


def _lan_ip() -> str:
    """Best-effort LAN IP for this host — used to build a URL a phone on the
    same WiFi can open. Doesn't actually send any traffic (UDP connect just
    picks the outbound interface)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


@router.get("/lan-url")
def lan_url(session: Session = Depends(get_session)) -> dict:
    row = session.query(Setting).filter(Setting.key == "port").first()
    port = row.value if row and row.value else "8765"
    ip = _lan_ip()
    return {"url": f"http://{ip}:{port}", "ip": ip, "port": port}


@router.get("/status")
def status(session: Session = Depends(get_session)) -> dict:
    path = _scan_path(session)
    return {
        "scan_path": path,
        "path_exists": bool(path) and Path(path).expanduser().exists(),
        "watch": watch.status(),
        "recent": [
            {"filename": d.filename, "status": d.status, "source": d.source}
            for d in session.query(Document).order_by(Document.id.desc()).limit(8).all()
        ],
    }


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...), session: Session = Depends(get_session)
) -> dict:
    """Accept a photo or PDF (e.g. from a phone), normalize, and ingest it."""
    folder = _scan_path(session)
    if not folder:
        return {"error": "No scan folder configured."}
    data = await file.read()
    saved = upload.save_upload(data, file.filename or "upload", folder)
    businesses = ingest._businesses_payload(session)
    result = ingest.ingest_path(session, saved, source="mobile", businesses=businesses)
    session.commit()
    return {"saved_as": saved.name, "result": result}


def _set_watch_enabled(session: Session, enabled: bool) -> None:
    row = session.query(Setting).filter(Setting.key == "watch_enabled").first()
    value = "1" if enabled else "0"
    if row is None:
        session.add(Setting(key="watch_enabled", value=value))
    else:
        row.value = value
    session.commit()


@router.post("/watch/start")
def watch_start(session: Session = Depends(get_session)) -> dict:
    _set_watch_enabled(session, True)
    return watch.start(_scan_path(session))


@router.post("/watch/stop")
def watch_stop(session: Session = Depends(get_session)) -> dict:
    _set_watch_enabled(session, False)
    return watch.stop()
