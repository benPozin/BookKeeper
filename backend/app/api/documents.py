"""Documents API: scan folder, list/review matches, confirm/correct (Phase 2)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import REPO_ROOT
from ..db import SessionLocal, get_session
from ..debug import is_debug
from ..models import Business, Document, Setting, Year
from ..services import jobs
from ..services.pdf import core, extract, ingest, sample

router = APIRouter(prefix="/api/documents", tags=["documents"])

BUCKETS = {
    "6a": "Car Expenses", "6b": "Car Lease", "6c": "Insurance",
    "6d": "Property Tax", "6e": "Mortgages", "6f": "Real Estate",
    "6g": "Rental Expenses", "6h": "T-Forms", "6i": "Utilities",
}


def _scan_path(session: Session) -> str:
    row = session.query(Setting).filter(Setting.key == "scansnap_path").first()
    return row.value if row else ""


@router.get("/status")
def status(session: Session = Depends(get_session)) -> dict:
    path = _scan_path(session)
    counts = {}
    for st in ("matched", "needs_review", "unmatched", "filed", "extraction_failed"):
        counts[st] = session.query(Document).filter(Document.status == st).count()
    counts["total"] = session.query(Document).count()
    return {
        "scan_path": path,
        "path_exists": bool(path) and Path(path).expanduser().exists(),
        "counts": counts,
        "buckets": BUCKETS,
        "debug": is_debug(session),
    }


@router.post("/scan")
def scan(session: Session = Depends(get_session)) -> dict:
    return ingest.scan_folder(session, source="scansnap")


@router.post("/scan-async")
def scan_async() -> dict:
    """Same as /scan but returns immediately with a job id to poll — a full
    folder scan can take a while and the button shouldn't freeze."""

    def work(progress):
        job_session = SessionLocal()
        try:
            return ingest.scan_folder(job_session, source="scansnap", on_progress=progress)
        finally:
            job_session.close()

    return {"job_id": jobs.start("documents-scan", work)}


@router.post("/generate-samples")
def generate_samples(session: Session = Depends(get_session)) -> dict:
    """Dev helper: create sample PDFs and point the scan path at them."""
    if not is_debug(session):
        raise HTTPException(
            status_code=403,
            detail="Sample data is a debug-mode tool. Enable Debug mode in "
                   "Settings if you really want fake documents on this machine.",
        )
    sample_dir = str(REPO_ROOT / "data" / "sample_scans")
    res = sample.generate_samples(sample_dir)
    row = session.query(Setting).filter(Setting.key == "scansnap_path").first()
    if row:
        row.value = sample_dir
        session.commit()
    return {"generated": res["count"], "dir": sample_dir}


@router.post("/extract-fields-async")
def extract_fields_async() -> dict:
    """Backfill vendor/date/amount on documents ingested before field
    extraction existed. Re-reads each file's text, so it runs as a job."""

    def work(progress):
        job_session = SessionLocal()
        try:
            docs = (
                job_session.query(Document)
                .filter(Document.amount.is_(None), Document.vendor == "")
                .all()
            )
            total = len(docs)
            updated = skipped = 0
            for i, doc in enumerate(docs):
                progress(i, total, doc.filename)
                path = Path(doc.routed_path or doc.original_path)
                if not path.exists():
                    skipped += 1
                    continue
                text, _method, _err = core.extract_text(path)
                fields = extract.extract_fields(text, doc.filename)
                if fields["vendor"] or fields["doc_date"] or fields["amount"] is not None:
                    doc.vendor = fields["vendor"]
                    doc.doc_date = fields["doc_date"]
                    doc.amount = fields["amount"]
                    job_session.commit()
                    updated += 1
            progress(total, total, "Done")
            return {"scanned": total, "updated": updated, "skipped_missing_files": skipped}
        finally:
            job_session.close()

    return {"job_id": jobs.start("extract-fields", work)}


@router.get("")
def list_documents(
    session: Session = Depends(get_session),
    status: Optional[str] = Query(None),
    business_id: Optional[int] = Query(None),
    confidence: Optional[str] = Query(None),
) -> dict:
    q = (
        session.query(Document, Business.name, Year.label)
        .outerjoin(Business, Document.business_id == Business.id)
        .outerjoin(Year, Document.year_id == Year.id)
    )
    if status:
        q = q.filter(Document.status == status)
    if business_id:
        q = q.filter(Document.business_id == business_id)
    if confidence:
        q = q.filter(Document.confidence == confidence)
    q = q.order_by(Document.status, Document.filename)

    items = [{
        "id": d.id, "filename": d.filename, "status": d.status,
        "confidence": d.confidence, "business": bname, "business_id": d.business_id,
        "year": ylabel, "bucket": d.folder_bucket,
        "bucket_name": BUCKETS.get(d.folder_bucket, ""),
        "reason": d.match_reason, "source": d.source,
        "summary": d.summary, "ai_reviewed": d.ai_reviewed,
        "vendor": d.vendor, "doc_date": d.doc_date, "amount": d.amount,
    } for d, bname, ylabel in q.all()]
    return {"documents": items, "count": len(items)}


@router.get("/{doc_id}/file")
def get_file(doc_id: int, session: Session = Depends(get_session)):
    doc = session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    path = Path(doc.routed_path or doc.original_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="file not found on disk")
    return FileResponse(path, media_type="application/pdf", filename=doc.filename)


class BulkRequest(BaseModel):
    ids: list[int]
    business_id: Optional[int] = None
    year: Optional[str] = None
    bucket: Optional[str] = None
    status: Optional[str] = None


@router.put("/bulk")
def bulk_update(req: BulkRequest, session: Session = Depends(get_session)) -> dict:
    # Registered before /{doc_id} — FastAPI matches path routes in
    # registration order, so this must come first or "/bulk" gets swallowed
    # as doc_id="bulk" by the route below.
    docs = session.query(Document).filter(Document.id.in_(req.ids)).all()
    updated = 0
    for doc in docs:
        if req.business_id is not None:
            doc.business_id = req.business_id
            doc.year_id = ingest._resolve_year(session, req.business_id, req.year)
        if req.bucket is not None:
            doc.folder_bucket = req.bucket
        if req.status is not None:
            doc.status = req.status
            if req.status == "matched":
                doc.confidence = "high"
        updated += 1
    session.commit()
    return {"updated": updated}


class ConfirmRequest(BaseModel):
    business_id: Optional[int] = None
    year: Optional[str] = None
    bucket: Optional[str] = None
    status: str = "matched"


@router.put("/{doc_id}")
def confirm(doc_id: int, req: ConfirmRequest, session: Session = Depends(get_session)) -> dict:
    doc = session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    if req.business_id is not None:
        doc.business_id = req.business_id
        doc.year_id = ingest._resolve_year(session, req.business_id, req.year)
    if req.bucket is not None:
        doc.folder_bucket = req.bucket
    doc.status = req.status
    if req.status == "matched":
        doc.confidence = "high"  # human-confirmed
    session.commit()
    return {"ok": True, "id": doc.id, "status": doc.status}


@router.get("/review-queue")
def review_queue(session: Session = Depends(get_session)) -> dict:
    """The next document waiting on a human decision, one at a time, plus how
    many are left — powers a focused approve/fix screen instead of a table."""
    pending_statuses = ("needs_review", "unmatched", "extraction_failed")
    q = (
        session.query(Document, Business.name, Year.label)
        .outerjoin(Business, Document.business_id == Business.id)
        .outerjoin(Year, Document.year_id == Year.id)
        .filter(Document.status.in_(pending_statuses))
        .order_by(Document.id)
    )
    total = q.count()
    row = q.first()
    if row is None:
        return {"remaining": 0, "document": None}
    d, bname, ylabel = row
    known_years = sorted({y[0] for y in session.query(Year.label).distinct()}, reverse=True)
    return {
        "remaining": total,
        "known_years": known_years,
        "document": {
            "id": d.id, "filename": d.filename, "status": d.status,
            "confidence": d.confidence, "business_id": d.business_id, "business": bname,
            "year": ylabel, "bucket": d.folder_bucket, "bucket_name": BUCKETS.get(d.folder_bucket, ""),
            "reason": d.match_reason, "summary": d.summary,
        },
    }


