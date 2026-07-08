"""Optional PIN gate for the API.

Single-user app on a home LAN: the app binds to 0.0.0.0 so the phone can
upload scans, which also means anyone on the same WiFi could open your tax
documents. Setting an ``app_pin`` in Settings closes that: every /api request
must carry a token that only the PIN unlocks. This is guest-on-the-WiFi
protection, not internet-grade auth — never port-forward this app.

The token is an HMAC of the PIN under a per-install random secret, so it
survives restarts (the phone stays logged in) and changing the PIN instantly
invalidates every device.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Setting

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _pin(session: Session) -> str:
    row = session.get(Setting, "app_pin")
    return row.value if row else ""


def _secret(session: Session) -> str:
    """A per-install random secret, created on first use."""
    row = session.get(Setting, "auth_secret")
    if row is not None and row.value:
        return row.value
    value = secrets.token_hex(32)
    if row is None:
        session.add(Setting(key="auth_secret", value=value))
    else:
        row.value = value
    session.commit()
    return value


def expected_token(session: Session) -> str | None:
    """The token clients must present, or None when no PIN is set."""
    pin = _pin(session)
    if not pin:
        return None
    return hmac.new(
        _secret(session).encode(), f"pin:{pin}".encode(), hashlib.sha256
    ).hexdigest()


class LoginRequest(BaseModel):
    pin: str


@router.get("/status")
def status(session: Session = Depends(get_session)) -> dict:
    return {"pin_required": bool(_pin(session))}


@router.post("/login")
def login(req: LoginRequest, session: Session = Depends(get_session)) -> dict:
    pin = _pin(session)
    if not pin:
        return {"pin_required": False, "token": ""}
    time.sleep(0.3)  # makes guessing a short PIN over WiFi impractically slow
    if hmac.compare_digest(req.pin.encode(), pin.encode()):
        return {"pin_required": True, "token": expected_token(session)}
    raise HTTPException(status_code=401, detail="Wrong PIN")
