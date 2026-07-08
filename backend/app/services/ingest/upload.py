"""Save an uploaded file into the scan folder, converting images to PDF.

Phone uploads are usually photos (JPEG/PNG/HEIC); ScanSnap and desktop uploads
are PDFs. Everything is normalized to a PDF in the scan folder so the existing
extract → match → dedup pipeline handles it uniformly.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".heic"}


def _safe_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
    return name or "upload"


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    i = 2
    while True:
        cand = path.with_name(f"{stem}_{i}{suffix}")
        if not cand.exists():
            return cand
        i += 1


def save_upload(data: bytes, filename: str, scan_folder: str) -> Path:
    """Persist bytes into scan_folder as a PDF. Returns the saved path."""
    folder = Path(scan_folder).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    name = _safe_name(filename)
    ext = Path(name).suffix.lower()

    if ext == ".pdf":
        return _write(folder / name, data)

    if ext in IMAGE_EXTS:
        from PIL import Image  # Pillow ships with pdfplumber

        img = Image.open(io.BytesIO(data))
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        out = _unique(folder / (Path(name).stem + ".pdf"))
        img.save(str(out), "PDF", resolution=200.0)
        return out

    # Unknown type — store as-is (won't extract text, becomes needs_review).
    return _write(folder / name, data)


def _write(path: Path, data: bytes) -> Path:
    path = _unique(path)
    path.write_bytes(data)
    return path
