"""Rotating file logging for the whole backend.

Configured once at startup (see ``main.py``). Every module gets a logger via
the normal ``logging.getLogger(__name__)`` and inherits the root handlers
below — nothing else needs to be wired up per module.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import DATA_DIR

LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "bookkeeper.log"

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)

    _configured = True


def tail(lines: int = 200) -> list[str]:
    """Last N lines of the log file, for the diagnostics endpoint."""
    if not LOG_FILE.exists():
        return []
    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        return [line.rstrip("\n") for line in f.readlines()[-lines:]]
