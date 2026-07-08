"""Application configuration: paths and default settings.

Defaults live here in code. User overrides are persisted in the ``Setting``
table (see ``models.py``) and read/written through the settings API. All
filesystem paths use ``pathlib`` so the same code runs on macOS (dev) and
Windows (the ``shimo`` host where BookKeeper actually runs).
"""

from __future__ import annotations

from pathlib import Path

# Repo root = .../BookKeeper  (this file is backend/app/config.py)
REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = REPO_ROOT / "data"
TEMPLATES_DIR = REPO_ROOT / "templates"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

DB_PATH = DATA_DIR / "bookkeeper.db"

# Default ScanSnap output folder on the Windows host. Editable in Settings.
DEFAULT_SCANSNAP_PATH = (
    r"C:\Users\shimo\AppData\Roaming\PFU\ScanSnap Home\ScanSnap Home"
)

# Default root where BookKeeper builds the accountant-ready folder structure.
DEFAULT_OUTPUT_ROOT = str(REPO_ROOT / "output")

# Default settings surfaced and editable on the Settings page. These keys are
# the source of truth for what the app considers configurable.
DEFAULT_SETTINGS: dict[str, str] = {
    "scansnap_path": DEFAULT_SCANSNAP_PATH,
    "output_root": DEFAULT_OUTPUT_ROOT,
    "port": "8765",
    # Whether the ScanSnap folder watcher should auto-start with the app.
    # Set to "0" only when the user has explicitly clicked Stop watching.
    "watch_enabled": "1",
    # Gmail labels (confirmed with user in Phase 1).
    "gmail_business_label": "Business",
    "gmail_label_consulting": "Business/Consulting",
    "gmail_label_rental": "Business/Rental",
    "gmail_label_real_estate": "Business/Real Estate",
    "gmail_label_home": "Business/Home",
    "gmail_scan_account": "shimon.pozin@gmail.com",
    # First-scan year range (daily scans focus on the current year). Inclusive.
    "scan_year_start": "2022",
    "scan_year_end": "2026",
    # Fiscal year config. "calendar" or a corporate fiscal year end like "06-30".
    "fiscal_year_mode": "calendar",
    "fiscal_year_end": "12-31",
    # AI review (Google Gemini free tier only — Claude/Anthropic is
    # deliberately not supported in this app).
    # The key can also come from the GEMINI_API_KEY / GOOGLE_API_KEY env vars.
    "gemini_api_key": "",
    # Blank = the default Gemini model (gemini-2.5-flash).
    "ai_model": "",
    "ai_enabled": "0",
    # Download PDF/image attachments from matched business emails during scans.
    "attachments_enabled": "1",
    # Optional PIN protecting the app on the local network. Blank = no PIN.
    "app_pin": "",
    # Debug mode: enables testing tools that create FAKE data (sample PDFs,
    # mock Gmail scans). Keep "0" on the real machine — real data only.
    "debug_mode": "0",
}

# Human-friendly metadata for rendering the Settings form on the frontend.
SETTINGS_FIELDS = [
    {"key": "scansnap_path", "label": "ScanSnap folder path", "type": "text",
     "help": "Where ScanSnap Home saves scanned PDFs (Windows host)."},
    {"key": "output_root", "label": "Output root folder", "type": "text",
     "help": "Where BookKeeper builds the accountant-ready folder structure."},
    {"key": "port", "label": "Server port", "type": "text",
     "help": "Port the local web app listens on."},
    {"key": "gmail_scan_account", "label": "Gmail account", "type": "text",
     "help": "Mailbox scanned daily."},
    {"key": "gmail_business_label", "label": "Business label", "type": "text",
     "help": "Top-level Gmail label for business email."},
    {"key": "gmail_label_consulting", "label": "Consulting (SPAL) label", "type": "text"},
    {"key": "gmail_label_rental", "label": "Rental label", "type": "text"},
    {"key": "gmail_label_real_estate", "label": "Real Estate label", "type": "text"},
    {"key": "gmail_label_home", "label": "Home office label", "type": "text",
     "help": "Parent label for the home office (e.g. Business/Home)."},
    {"key": "scan_year_start", "label": "Scan from year", "type": "text",
     "help": "Earliest tax year to pull on a full scan."},
    {"key": "scan_year_end", "label": "Scan to year", "type": "text",
     "help": "Latest tax year to pull on a full scan."},
    {"key": "fiscal_year_mode", "label": "Fiscal year mode", "type": "select",
     "options": ["calendar", "fiscal"],
     "help": "Confirm with your accountant: 'calendar' files by calendar year; "
             "'fiscal' uses the corporate year-end below."},
    {"key": "fiscal_year_end", "label": "Fiscal year end (MM-DD)", "type": "text",
     "help": "Used when fiscal year mode is 'fiscal', e.g. 06-30."},
    {"key": "attachments_enabled", "label": "Fetch email attachments", "type": "select",
     "options": ["1", "0"],
     "help": "1 = download PDF/image attachments from matched business emails into Documents."},
    {"key": "app_pin", "label": "App PIN (optional)", "type": "password",
     "help": "4+ characters. Anyone on your WiFi must enter this to open BookKeeper. "
             "Blank = no PIN."},
    {"key": "debug_mode", "label": "Debug mode", "type": "select",
     "options": ["0", "1"],
     "help": "1 shows testing tools that create FAKE data (sample PDFs, mock "
             "Gmail scans). Keep 0 on the real PC."},
    {"key": "gemini_api_key", "label": "Gemini API key (free, optional)", "type": "password",
     "help": "Free key from aistudio.google.com/apikey. Or set the GEMINI_API_KEY env var."},
    {"key": "ai_model", "label": "AI model (optional)", "type": "text",
     "help": "Leave blank for the default (gemini-2.5-flash)."},
]


def ensure_dirs() -> None:
    """Create runtime directories if missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
