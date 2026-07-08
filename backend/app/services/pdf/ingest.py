"""Scan a folder of PDFs → extract → match → de-duplicate → persist Documents."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...models import Business, Document, Setting, Year
from . import core, extract, matcher


def _businesses_payload(session: Session) -> list[dict]:
    out = []
    for b in session.query(Business).all():
        years = [
            y[0] for y in session.query(Year.label).filter(Year.business_id == b.id).distinct()
        ]
        out.append({"id": b.id, "name": b.name, "type": b.type, "years": years})
    return out


def _resolve_year(session: Session, business_id: int | None, label: str | None) -> int | None:
    if not business_id or not label:
        return None
    yr = (
        session.query(Year)
        .filter(Year.business_id == business_id, Year.label == label)
        .first()
    )
    if yr is None:
        yr = Year(business_id=business_id, label=label)
        session.add(yr)
        session.flush()
    return yr.id


def ingest_path(
    session: Session, path: Path, source: str, businesses: list[dict]
) -> dict:
    """Ingest a single PDF. Returns a status dict (incl. 'duplicate')."""
    content_hash = core.file_hash(path)
    existing = (
        session.query(Document).filter(Document.content_hash == content_hash).first()
    )
    if existing:
        return {"file": path.name, "status": "duplicate", "of_id": existing.id}

    text, method, extract_error = core.extract_text(path)
    m = matcher.match_document(text, path.name, businesses)
    fields = extract.extract_fields(text, path.name)

    if extract_error:
        status = "extraction_failed"
        reason = f"{extract_error} — assign this document manually."
    elif m["confidence"] == "none":
        status = "unmatched"
        reason = m["reason"]
    elif m["confidence"] == "high":
        status = "matched"
        reason = m["reason"]
    else:
        status = "needs_review"
        reason = m["reason"]

    year_id = _resolve_year(session, m["business_id"], m["year"])
    doc = Document(
        business_id=m["business_id"],
        year_id=year_id,
        source=source,
        filename=path.name,
        original_path=str(path),
        content_hash=content_hash,
        folder_bucket=m["bucket"],
        confidence=m["confidence"],
        match_reason=reason + (f" [{method}]" if method != "text" else ""),
        status=status,
        vendor=fields["vendor"],
        doc_date=fields["doc_date"],
        amount=fields["amount"],
    )
    session.add(doc)
    try:
        session.flush()
    except IntegrityError:
        # Two ingest paths raced past the check above (e.g. the watcher firing
        # on_created and on_moved for the same file). The unique index on
        # content_hash caught it — treat it as the duplicate it is.
        session.rollback()
        existing = (
            session.query(Document).filter(Document.content_hash == content_hash).first()
        )
        return {"file": path.name, "status": "duplicate", "of_id": existing.id if existing else None}
    return {"file": path.name, "status": status, "confidence": m["confidence"], "id": doc.id}


def scan_folder(
    session: Session, folder: str | None = None, source: str = "scansnap", on_progress=None
) -> dict:
    """Scan all PDFs in the configured (or given) folder.

    ``on_progress``, if given, is called as ``on_progress(done, total, filename)``
    after each file so a caller can report live progress on what would
    otherwise be a multi-second-to-multi-minute blocking call.
    """
    if folder is None:
        row = session.query(Setting).filter(Setting.key == "scansnap_path").first()
        folder = row.value if row else ""
    root = Path(folder).expanduser() if folder else None

    if not root or not root.exists():
        return {"error": f"Folder not found: {folder}", "scanned": 0}

    businesses = _businesses_payload(session)
    pdfs = sorted(root.rglob("*.pdf")) + sorted(root.rglob("*.PDF"))
    total = len(pdfs)

    results = {"matched": 0, "needs_review": 0, "unmatched": 0, "duplicate": 0, "extraction_failed": 0}
    items = []
    for i, pdf in enumerate(pdfs):
        if on_progress:
            on_progress(i, total, pdf.name)
        r = ingest_path(session, pdf, source, businesses)
        results[r["status"]] = results.get(r["status"], 0) + 1
        items.append(r)
    if on_progress:
        on_progress(total, total, "Done")
    session.commit()

    return {
        "folder": str(root),
        "scanned": len(pdfs),
        "summary": results,
        "items": items[:200],
        "total_documents": session.query(Document).count(),
    }
