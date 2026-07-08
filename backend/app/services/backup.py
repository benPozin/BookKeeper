"""Automatic backups of the SQLite database and the Gmail token.

Keeps the most recent copies in ``data/backups/``. A snapshot is always taken
before any schema migration runs (see ``db.init_db``), so a bad ``ALTER
TABLE`` can never destroy the only copy of the user's data, and the daily
automation job takes one too so backups exist even if the app runs for weeks
without a schema change.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from ..config import DATA_DIR, DB_PATH

BACKUP_DIR = DATA_DIR / "backups"
KEEP = 14


def backup_now(reason: str = "daily") -> Path | None:
    """Copy the DB (and Gmail token, if present) into ``data/backups/``.

    Returns the DB backup path, or ``None`` if there is no database yet
    (first run before anything has been created).
    """
    if not DB_PATH.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    dest = BACKUP_DIR / f"bookkeeper-{stamp}-{reason}.db"
    shutil.copy2(DB_PATH, dest)

    token = DATA_DIR / "gmail_token.json"
    if token.exists():
        shutil.copy2(token, BACKUP_DIR / f"gmail_token-{stamp}-{reason}.json")

    _rotate()
    return dest


def _rotate(keep: int = KEEP) -> None:
    """Keep only the most recent ``keep`` backups of each kind."""
    for pattern in ("bookkeeper-*.db", "gmail_token-*.json"):
        files = sorted(
            BACKUP_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True
        )
        for old in files[keep:]:
            old.unlink(missing_ok=True)


def list_backups() -> list[dict]:
    """Backups on disk, most recent first — used by the diagnostics endpoint."""
    if not BACKUP_DIR.exists():
        return []
    files = sorted(
        BACKUP_DIR.glob("bookkeeper-*.db"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    return [
        {"name": f.name, "size": f.stat().st_size, "mtime": f.stat().st_mtime}
        for f in files
    ]
