"""Build the accountant-ready folder structure for a year and route docs into it.

Layout (under <output_root>/<year>/):
  6a Car Expenses, 6b Car Lease, 6c Insurance, 6d Property Tax, 6e Mortgages,
  6f Real Estate/Supporting Docs, 6g Rental Expenses/Supporting Docs,
  6h T-Forms, 6i Utilities/{Gas,Hydro,Internet,Cellular}

Matched documents are COPIED (originals stay in the scan folder) into their
bucket; the user's Excel templates (with supporting-doc sheets) are placed in
6a/6f/6g. Idempotent and fully audited via RoutingLog. Supports dry-run.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from ...config import REPO_ROOT
from ...models import Business, Document, RoutingLog, Setting, Year
from ..templates import builder as templates_builder

logger = logging.getLogger(__name__)

# internal bucket code -> folder name (plain names, no codes on disk or in UI)
BUCKETS = {
    "6a": "Car Expenses", "6b": "Car Lease", "6c": "Insurance",
    "6d": "Property Tax", "6e": "Mortgages", "6f": "Real Estate",
    "6g": "Rental Expenses", "6h": "T-Forms", "6i": "Utilities",
}
SUPPORTING = {"6f", "6g"}  # buckets that get a "Supporting Docs" subfolder
UTILITY_SUBDIRS = ["Gas", "Hydro", "Internet", "Cellular"]

# where each Phase-4 template lands
TEMPLATE_BUCKET = {
    "Cars": "6a", "Home Office Expenses FY25": "6g", "Rental Expenses FY25": "6g",
    "RealEstateExpenses": "6f", "RealEstateFees": "6f",
}


def _output_root(session: Session) -> Path:
    row = session.query(Setting).filter(Setting.key == "output_root").first()
    val = row.value if row and row.value else str(REPO_ROOT / "output")
    return Path(val).expanduser()


def _utility_subdir(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ("hydro", "electric")):
        return "Hydro"
    if any(k in n for k in ("gas", "enbridge")):
        return "Gas"
    if any(k in n for k in ("internet", "bell", "rogers", "teksavvy", "wifi")):
        return "Internet"
    if any(k in n for k in ("cell", "wireless", "mobile", "phone")):
        return "Cellular"
    return ""


def _doc_target(year_dir: Path, doc: Document) -> Path:
    folder = BUCKETS.get(doc.folder_bucket)
    if not folder:
        return year_dir / "Other (unsorted)" / doc.filename
    base = year_dir / folder
    if doc.folder_bucket in SUPPORTING:
        base = base / "Supporting Docs"
    elif doc.folder_bucket == "6i":
        sub = _utility_subdir(doc.filename)
        if sub:
            base = base / sub
    return base / doc.filename


def plan(session: Session, year: str) -> dict:
    """Compute the routing plan for a year without touching disk."""
    year_dir = _output_root(session) / year
    docs = (
        session.query(Document)
        .join(Year, Document.year_id == Year.id)
        .filter(Year.label == year, Document.status.in_(("matched", "filed")))
        .all()
    )
    moves = []
    for d in docs:
        biz = session.get(Business, d.business_id) if d.business_id else None
        target = _doc_target(year_dir, d)
        moves.append({
            "file": d.filename, "business": biz.name if biz else "",
            "bucket": BUCKETS.get(d.folder_bucket, "Unsorted"),
            "to": str(target.relative_to(year_dir)),
        })
    template_files = [
        {"file": f"{name} - {year}.xlsx", "bucket": bucket}
        for name, bucket in TEMPLATE_BUCKET.items()
        if (templates_builder.TEMPLATES_DIR / f"{name}.xlsx").exists()
    ]
    return {
        "year": year, "year_dir": str(year_dir),
        "folders": list(BUCKETS.values()),
        "doc_count": len(moves), "moves": moves, "templates": template_files,
    }


def apply(session: Session, year: str) -> dict:
    """Create the tree, copy docs + place templates, log routing, mark filed."""
    year_dir = _output_root(session) / year

    # 1) scaffold the full tree
    for folder in BUCKETS.values():
        (year_dir / folder).mkdir(parents=True, exist_ok=True)
    for b in SUPPORTING:
        (year_dir / BUCKETS[b] / "Supporting Docs").mkdir(parents=True, exist_ok=True)
    for sub in UTILITY_SUBDIRS:
        (year_dir / BUCKETS["6i"] / sub).mkdir(parents=True, exist_ok=True)

    # 2) copy matched documents into their buckets
    docs = (
        session.query(Document)
        .join(Year, Document.year_id == Year.id)
        .filter(Year.label == year, Document.status.in_(("matched", "filed")))
        .all()
    )
    copied = 0
    skipped: list[dict] = []
    for d in docs:
        src = Path(d.original_path)
        if not src.exists():
            skipped.append({"file": d.filename, "error": "Original file no longer exists"})
            continue
        target = _doc_target(year_dir, d)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, target)
        except OSError as e:
            # A locked/open file, a too-long Windows path, or a permissions
            # issue shouldn't abort the whole build — file what we can and
            # report the rest so the user knows exactly what to fix.
            logger.exception("Could not copy %s to %s", src, target)
            skipped.append({"file": d.filename, "error": str(e)})
            continue
        session.add(RoutingLog(document_id=d.id, from_path=str(src),
                               to_path=str(target), action="copied"))
        d.routed_path = str(target)
        d.status = "filed"
        copied += 1

    # 3) place the year's templates into their buckets
    tmpl_out = templates_builder.build_for_year(session, year, year_dir / "_templates_tmp")
    placed = []
    for m in tmpl_out["templates"]:
        if m.get("status") != "built":
            continue
        name_no_year = m["file"].rsplit(" - ", 1)[0]
        bucket = TEMPLATE_BUCKET.get(name_no_year, "")
        src = year_dir / "_templates_tmp" / m["file"]
        dest = (year_dir / BUCKETS.get(bucket, "Other (unsorted)")) / m["file"]
        if src.exists():
            try:
                shutil.copy(src, dest)
                placed.append({"file": m["file"], "bucket": bucket})
            except OSError as e:
                logger.exception("Could not place template %s at %s", src, dest)
                skipped.append({"file": m["file"], "error": str(e)})
    # clean temp
    shutil.rmtree(year_dir / "_templates_tmp", ignore_errors=True)

    session.commit()
    return {
        "year": year, "year_dir": str(year_dir),
        "documents_filed": copied, "templates_placed": len(placed),
        "templates": placed,
        "skipped": skipped,
    }


def unfile(session: Session, year: str) -> dict:
    """Reverse a previous apply() for a year: delete the copied files (per
    RoutingLog), reset those documents back to 'matched', and drop the
    RoutingLog entries. Safe because apply() only ever copies — the
    originals in the scan folder are never touched, so nothing is lost.
    """
    docs = (
        session.query(Document)
        .join(Year, Document.year_id == Year.id)
        .filter(Year.label == year, Document.status == "filed")
        .all()
    )
    files_removed = 0
    for d in docs:
        logs = session.query(RoutingLog).filter(RoutingLog.document_id == d.id).all()
        for log in logs:
            path = Path(log.to_path)
            if path.exists():
                try:
                    path.unlink()
                    files_removed += 1
                except OSError:
                    logger.exception("Could not remove %s while un-filing %s", path, year)
            session.delete(log)
        d.status = "matched"
        d.routed_path = ""
    session.commit()
    return {"year": year, "documents_reset": len(docs), "files_removed": files_removed}
