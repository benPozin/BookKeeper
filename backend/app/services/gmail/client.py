"""Gmail credentials, OAuth flow, and connection status.

Google libraries are imported lazily so the app (and mock mode) run fine even
if they aren't installed yet.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ...config import DATA_DIR

logger = logging.getLogger(__name__)

# Read-only access is all BookKeeper needs.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# The user drops their downloaded OAuth client here; token is written here after consent.
CREDENTIALS_PATH = DATA_DIR / "gmail_credentials.json"
TOKEN_PATH = DATA_DIR / "gmail_token.json"


def has_credentials() -> bool:
    return CREDENTIALS_PATH.exists()


def has_token() -> bool:
    return TOKEN_PATH.exists()


def mode() -> str:
    """'real' once a credentials.json is present, else 'mock'."""
    return "real" if has_credentials() else "mock"


def _load_creds():
    """Return valid google Credentials, refreshing if needed, or None."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    if not TOKEN_PATH.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    return creds if creds and creds.valid else None


def is_connected() -> bool:
    """True when a usable token exists (real mode, consent completed)."""
    if not has_credentials() or not has_token():
        return False
    try:
        return _load_creds() is not None
    except Exception:
        logger.exception("Failed to load/refresh Gmail credentials")
        return False


def status() -> dict:
    m = mode()
    return {
        "mode": m,
        "connected": is_connected() if m == "real" else False,
        "has_credentials": has_credentials(),
        "has_token": has_token(),
        "credentials_path": str(CREDENTIALS_PATH),
        "scopes": SCOPES,
    }


def run_oauth_flow() -> dict:
    """Run the installed-app OAuth flow (opens the system browser for consent).

    Intended for the local single-user app: backend and browser are on the same
    machine, so a transient local-server redirect works. Writes the token file.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not has_credentials():
        raise FileNotFoundError(
            f"No OAuth client found at {CREDENTIALS_PATH}. Download a Desktop-app "
            "OAuth client from Google Cloud and save it there."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    TOKEN_PATH.write_text(creds.to_json())
    return status()


def disconnect() -> dict:
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
    return status()


def build_service():
    """Build the Gmail API client from stored creds (real mode only)."""
    from googleapiclient.discovery import build

    creds = _load_creds()
    if creds is None:
        raise RuntimeError("Gmail not connected — complete OAuth consent first.")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def list_labels() -> list[dict]:
    """Return the account's labels (real mode), for category→label mapping."""
    service = build_service()
    resp = service.users().labels().list(userId="me").execute()
    return [
        {"id": l["id"], "name": l["name"]}
        for l in resp.get("labels", [])
        if l.get("type") != "system" or l["name"].lower() in ("inbox",)
    ]
