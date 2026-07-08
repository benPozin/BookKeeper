"""Settings API: read and persist app configuration (Phase 0, fully wired)."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import DEFAULT_SETTINGS, SETTINGS_FIELDS
from ..db import get_session
from ..models import Setting

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    values: dict[str, str]


def _current(session: Session) -> dict[str, str]:
    rows = {s.key: s.value for s in session.query(Setting).all()}
    # Fall back to code defaults for any missing keys.
    return {**DEFAULT_SETTINGS, **rows}


def _validate(key: str, value: str) -> str | None:
    """Return a plain-language warning if a value looks wrong, else None.

    These are warnings, not hard failures — the value is still saved, so a
    user mid-edit (e.g. clearing a field before retyping it) never gets
    blocked, but a wrong port/year/path is caught at the moment they can
    still fix it instead of failing silently during an automation run days
    later.
    """
    if not value:
        return None
    if key == "port":
        if not value.isdigit() or not (1024 <= int(value) <= 65535):
            return "Should be a number between 1024 and 65535."
    elif key in ("scan_year_start", "scan_year_end"):
        if not re.fullmatch(r"\d{4}", value):
            return "Should be a 4-digit year, e.g. 2024."
    elif key == "fiscal_year_mode":
        if value not in ("calendar", "fiscal"):
            return "Should be 'calendar' or 'fiscal'."
    elif key == "fiscal_year_end":
        if not re.fullmatch(r"\d{2}-\d{2}", value):
            return "Should be MM-DD, e.g. 06-30."
    elif key == "app_pin":
        if len(value) < 4:
            return "PIN should be at least 4 characters."
    elif key in ("scansnap_path", "output_root"):
        if not Path(value).expanduser().exists():
            return "This folder does not exist on this computer."
    return None


@router.get("")
def get_settings(session: Session = Depends(get_session)) -> dict:
    values = _current(session)
    # Annotate path fields with whether they currently exist on this host,
    # so the UI can warn when a configured folder is missing.
    path_status = {}
    for key in ("scansnap_path", "output_root"):
        p = values.get(key, "")
        path_status[key] = bool(p) and Path(p).expanduser().exists()
    return {"fields": SETTINGS_FIELDS, "values": values, "path_status": path_status}


@router.put("")
def update_settings(
    payload: SettingsUpdate, session: Session = Depends(get_session)
) -> dict:
    warnings: dict[str, str] = {}
    for key, value in payload.values.items():
        row = session.get(Setting, key)
        if row is None:
            row = Setting(key=key, value=value)
            session.add(row)
        else:
            row.value = value
        msg = _validate(key, value)
        if msg:
            warnings[key] = msg
    session.commit()

    current = _current(session)
    try:
        if int(current["scan_year_start"]) > int(current["scan_year_end"]):
            warnings["scan_year_start"] = "Scan-from year is after scan-to year."
    except (ValueError, KeyError):
        pass

    result = get_settings(session)
    result["warnings"] = warnings
    return result
