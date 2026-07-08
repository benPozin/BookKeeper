"""Diagnostics: a single page of "is everything actually working" for a
non-technical user to check (or screenshot for help) when something seems off.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_session
from ..logging_setup import tail
from ..models import Document, Setting
from ..services import backup
from ..services.ai import reviewer as ai_reviewer
from ..services.gmail import client as gmail_client
from ..services.ingest import watch

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


def _setting(session: Session, key: str, default: str = "") -> str:
    row = session.query(Setting).filter(Setting.key == key).first()
    return row.value if row and row.value else default


def _ocr_available() -> bool:
    from ..services.pdf import core

    return core.ocr_available()


@router.get("")
def diagnostics(session: Session = Depends(get_session)) -> dict:
    scansnap_path = _setting(session, "scansnap_path")
    output_root = _setting(session, "output_root")
    last_summary_raw = _setting(session, "automation_last_summary")

    return {
        # 'win32' on the real Windows host, 'darwin' on the dev Mac — lets the
        # in-app setup guide know which machine it is looking at.
        "platform": sys.platform,
        "paths": {
            "scansnap_path": {
                "value": scansnap_path,
                "exists": bool(scansnap_path) and Path(scansnap_path).expanduser().exists(),
            },
            "output_root": {
                "value": output_root,
                "exists": bool(output_root) and Path(output_root).expanduser().exists(),
            },
        },
        "watcher": watch.status(),
        "gmail": gmail_client.status(),
        "ocr_available": _ocr_available(),
        "ai": {
            "configured": ai_reviewer.is_configured(session),
            "enabled": ai_reviewer.is_enabled(session),
            "provider": "gemini",
        },
        "documents": {
            "extraction_failed": session.query(Document)
            .filter(Document.status == "extraction_failed")
            .count(),
            "needs_review": session.query(Document)
            .filter(Document.status == "needs_review")
            .count(),
        },
        "last_automation_run": json.loads(last_summary_raw) if last_summary_raw else None,
        "backups": backup.list_backups()[:5],
        "log_tail": tail(200),
    }
