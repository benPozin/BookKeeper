"""Low-level PDF helpers: content hashing and text extraction.

Text extraction uses pdfplumber. If a PDF is image-only (a scan with no text
layer) and OCR tooling is available, it falls back to OCR. Extraction
failures (corrupt file, locked file, OCR raising) are distinguished from the
ordinary "no text found" case so the caller can flag the document instead of
silently filing it next to documents that were read fine but just didn't
match anything.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _tesseract_cmd() -> str | None:
    """Locate the tesseract binary: PATH first, then the default Windows dirs."""
    import shutil

    cmd = shutil.which("tesseract")
    if cmd:
        return cmd
    for cand in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if Path(cand).exists():
            return cand
    return None


def ocr_available() -> bool:
    """True when both pytesseract and the tesseract binary are usable."""
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return _tesseract_cmd() is not None


def file_hash(path: Path) -> str:
    """SHA-256 of the file bytes — used to drop exact duplicate scans."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_text(path: Path) -> tuple[str, str, str | None]:
    """Return (text, method, error).

    ``method`` is one of ``text``/``ocr``/``none``. ``error`` is ``None`` on a
    normal outcome (text found, or an image-only scan with no OCR installed)
    and a short human-readable message when extraction itself raised.
    """
    pdfplumber_error: str | None = None
    try:
        import pdfplumber

        parts = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages[:15]:  # cap pages for speed
                parts.append(page.extract_text() or "")
        text = "\n".join(parts).strip()
        if text:
            return text, "text", None
    except Exception as e:
        pdfplumber_error = str(e)
        logger.exception("pdfplumber failed to read %s", path)

    # OCR fallback for image-only scans. Pages are rasterized by pdfplumber's
    # built-in renderer (pypdfium2 — a plain pip wheel, works on Windows too),
    # so the only system dependency is the tesseract binary itself.
    try:
        import pytesseract  # type: ignore

        cmd = _tesseract_cmd()
        if cmd is None:
            raise ImportError("tesseract binary not found")
        pytesseract.pytesseract.tesseract_cmd = cmd

        import pdfplumber

        parts = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages[:5]:  # cap pages for speed
                image = page.to_image(resolution=200).original
                parts.append(pytesseract.image_to_string(image))
        text = "\n".join(parts).strip()
        if text:
            return text, "ocr", None
    except ImportError:
        pass  # OCR tooling not installed — not an error, just unavailable.
    except Exception as e:
        logger.exception("OCR failed on %s", path)
        return "", "none", f"OCR failed: {e}"

    if pdfplumber_error:
        return "", "none", f"Could not read this PDF ({pdfplumber_error})"
    return "", "none", None
