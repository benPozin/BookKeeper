"""Build an accountant-ready zip of a year's folder tree, with a manifest.

Walks <output_root>/<year>, summarizes each 6x bucket (file counts, empty
buckets flagged), writes a MANIFEST.txt into the archive, and zips it all to
<output_root>/BookKeeper_<year>.zip — ready to email to the accountant.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from ...config import REPO_ROOT
from ...models import Business, Document, Setting, Year

EXPECTED_BUCKETS = [
    "Car Expenses", "Car Lease", "Insurance", "Property Tax", "Mortgages",
    "Real Estate", "Rental Expenses", "T-Forms", "Utilities",
]


def _output_root(session: Session) -> Path:
    row = session.query(Setting).filter(Setting.key == "output_root").first()
    val = row.value if row and row.value else str(REPO_ROOT / "output")
    return Path(val).expanduser()


def available_years(session: Session) -> list[str]:
    root = _output_root(session)
    if not root.exists():
        return []
    return sorted(
        (p.name for p in root.iterdir() if p.is_dir() and p.name.isdigit()),
        reverse=True,
    )


def summarize(session: Session, year: str) -> dict:
    year_dir = _output_root(session) / year
    if not year_dir.exists():
        return {"error": f"No built folder for {year}. Run the Organizer first."}

    buckets = []
    total_files = 0
    for name in EXPECTED_BUCKETS:
        folder = year_dir / name
        files = [f for f in folder.rglob("*") if f.is_file()] if folder.exists() else []
        total_files += len(files)
        buckets.append({"bucket": name, "files": len(files), "empty": len(files) == 0})

    # Documents for this year that never made it into the built tree — the
    # package would otherwise ship silently incomplete.
    pending = (
        session.query(Document)
        .join(Year, Document.year_id == Year.id)
        .filter(
            Year.label == year,
            Document.status.in_(("needs_review", "unmatched", "extraction_failed")),
        )
        .count()
    )
    return {
        "year": year, "year_dir": str(year_dir),
        "buckets": buckets, "total_files": total_files,
        "empty_buckets": [b["bucket"] for b in buckets if b["empty"]],
        "pending_documents": pending,
    }


def _manifest_text(summary: dict, stamp: str) -> str:
    lines = [
        "BookKeeper — Accountant Package",
        f"Tax year: {summary['year']}",
        f"Generated: {stamp}",
        f"Total files: {summary['total_files']}",
        "",
        "Folder contents:",
    ]
    for b in summary["buckets"]:
        flag = "  (empty)" if b["empty"] else ""
        lines.append(f"  {b['bucket']}: {b['files']} file(s){flag}")
    if summary["empty_buckets"]:
        lines += ["", "Note — empty buckets (no documents filed): "
                  + ", ".join(summary["empty_buckets"])]
    return "\n".join(lines) + "\n"


def build_package(session: Session, year: str, stamp: str | None = None) -> dict:
    summary = summarize(session, year)
    if "error" in summary:
        return summary
    year_dir = Path(summary["year_dir"])
    stamp = stamp or datetime.now().isoformat(timespec="seconds")
    manifest = _manifest_text(summary, stamp)

    zip_path = _output_root(session) / f"BookKeeper_{year}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"BookKeeper_{year}/MANIFEST.txt", manifest)
        for f in year_dir.rglob("*"):
            if f.is_file() and not _hidden(f.relative_to(year_dir)):
                zf.write(f, f"BookKeeper_{year}/{f.relative_to(year_dir)}")

    return {
        **summary,
        "zip_path": str(zip_path),
        "zip_name": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "manifest": manifest,
    }


# --- package tree + reveal ------------------------------------------------------
def _hidden(rel: Path) -> bool:
    """Staging/system entries (any path part starting with '_' or '.') stay out
    of the package, the tree view, and the zip."""
    return any(part.startswith(("_", ".")) for part in rel.parts)


SOURCE_LABEL = {"email": "from email", "scansnap": "scanned", "mobile": "phone upload"}


def _describe(f: Path, doc: dict | None) -> str:
    """One human line saying what a packaged file IS."""
    if f.name == "MANIFEST.txt":
        return "Package manifest — a table of contents for your accountant"
    if f.suffix.lower() in (".xlsx", ".xlsm"):
        return "Excel expense template (your formulas + a Supporting Docs sheet)"
    if doc:
        bits = [b for b in (doc["vendor"], doc["doc_date"]) if b]
        label = " · ".join(bits) if bits else (doc["business"] or "Document")
        kind = doc["kind"] if doc["kind"] in ("income", "expense") else "document"
        src = SOURCE_LABEL.get(doc["source"], doc["source"] or "")
        return f"{label} — {kind}" + (f", {src}" if src else "")
    if f.suffix.lower() == ".pdf":
        return "Scanned document"
    return "File"


def _doc_map(session: Session, year_dir: Path) -> dict[str, dict]:
    """routed_path -> document facts, for every doc filed under this year."""
    rows = (
        session.query(Document, Business.name)
        .outerjoin(Business, Document.business_id == Business.id)
        .filter(Document.routed_path != "")
        .all()
    )
    prefix = str(year_dir)
    out = {}
    for d, biz_name in rows:
        if d.routed_path.startswith(prefix):
            out[d.routed_path] = {
                "vendor": d.vendor or "", "doc_date": d.doc_date or "",
                "amount": d.amount, "kind": d.kind or "", "source": d.source or "",
                "business": biz_name or "",
            }
    return out


def walk_tree(d: Path, docmap: dict[str, dict], rel_base: Path | None = None) -> list[dict]:
    """Nested folder/file entries for the package view (hidden parts skipped)."""
    base = rel_base or d
    entries: list[dict] = []
    for p in sorted(d.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        if _hidden(p.relative_to(base)):
            continue
        if p.is_dir():
            children = walk_tree(p, docmap, base)
            entries.append({
                "type": "folder", "name": p.name, "children": children,
                "files": sum(c["files"] if c["type"] == "folder" else 1 for c in children),
                "size": sum(c["size"] for c in children),
            })
        else:
            doc = docmap.get(str(p))
            suffix = p.suffix.lower()
            entry = {
                "type": "file", "name": p.name, "size": p.stat().st_size,
                "kind": "excel" if suffix in (".xlsx", ".xlsm")
                        else "pdf" if suffix == ".pdf" else "text",
                "desc": _describe(p, doc),
            }
            if doc:
                entry["amount"] = doc["amount"]
                entry["business"] = doc["business"]
            entries.append(entry)
    return entries


def package_tree(session: Session, year: str) -> dict:
    """Everything the Export page needs to SHOW the package before/after zipping."""
    year_dir = _output_root(session) / year
    if not year_dir.exists():
        return {"error": f"No built folder for {year}. Run the Organizer first."}
    tree = walk_tree(year_dir, _doc_map(session, year_dir))

    def _count(entries):
        return sum(c["files"] if c["type"] == "folder" else 1 for c in entries)

    def _size(entries):
        return sum(c["size"] for c in entries)

    zip_path = _output_root(session) / f"BookKeeper_{year}.zip"
    zip_info = {"exists": zip_path.exists(), "name": zip_path.name, "path": str(zip_path)}
    if zip_path.exists():
        st = zip_path.stat()
        zip_info["size"] = st.st_size
        zip_info["built_at"] = datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
    return {
        "year": year, "root": str(year_dir), "platform": sys.platform,
        "tree": tree, "total_files": _count(tree), "total_size": _size(tree),
        "zip": zip_info,
    }


def reveal(session: Session, year: str, target: str = "folder") -> dict:
    """Open the OS file manager at the year folder, or with the zip selected.

    macOS: ``open`` / ``open -R``; Windows: ``os.startfile`` / ``explorer
    /select,``; elsewhere ``xdg-open``. Paths are pinned inside output_root.
    """
    if not re.fullmatch(r"(19|20)\d\d", year):
        return {"error": f"Not a year: {year!r}"}
    root = _output_root(session).resolve()
    path = (root / (f"BookKeeper_{year}.zip" if target == "zip" else year)).resolve()
    if not path.is_relative_to(root):
        return {"error": "Path escapes the output folder."}
    if not path.exists():
        return {"error": f"Nothing at {path} yet — build it first."}

    select_file = target == "zip"
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)] if select_file else ["open", str(path)])
    elif sys.platform.startswith("win"):
        if select_file:
            subprocess.Popen(["explorer", f"/select,{path}"])
        else:
            os.startfile(str(path))  # noqa: S606 — local single-user app
    else:
        subprocess.Popen(["xdg-open", str(path)])
    return {"opened": str(path), "selected": select_file}
