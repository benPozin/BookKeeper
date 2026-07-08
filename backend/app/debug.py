"""Debug-mode flag.

Debug mode unlocks tools that fabricate data — sample PDFs and mock Gmail
scans — which must never mix with the real books on the production machine.
Off by default; the dev machine flips it on in Settings.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Setting


def is_debug(session: Session) -> bool:
    row = session.get(Setting, "debug_mode")
    return bool(row and row.value == "1")
