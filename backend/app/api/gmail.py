"""Gmail API router: status, OAuth connect/disconnect, scan, history, discovery."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_session
from ..models import Business, Email, Year
from ..services import jobs
from ..services.gmail import attachments, client, scan

router = APIRouter(prefix="/api/gmail", tags=["gmail"])


@router.get("/status")
def status(session: Session = Depends(get_session)) -> dict:
    from ..debug import is_debug

    st = client.status()
    st["debug"] = is_debug(session)
    st["counts"] = {
        "emails": session.query(Email).count(),
        "businesses": session.query(Business).count(),
        "years": session.query(Year.label).distinct().count(),
    }
    return st


@router.post("/connect")
def connect() -> dict:
    """Run the OAuth consent flow (opens the system browser on the host)."""
    try:
        return client.run_oauth_flow()
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # surface google/library errors to the UI
        raise HTTPException(status_code=500, detail=f"OAuth failed: {e}")


@router.post("/disconnect")
def disconnect() -> dict:
    return client.disconnect()


@router.get("/labels")
def labels() -> dict:
    try:
        return {"labels": client.list_labels()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot list labels: {e}")


@router.post("/scan")
def run_scan(full: bool = Query(False), session: Session = Depends(get_session)) -> dict:
    return scan.run_scan(session, full=full)


@router.post("/scan-async")
def run_scan_async(full: bool = Query(False)) -> dict:
    """Same as /scan but returns immediately with a job id to poll. The
    default incremental scan is fast; ``full=true`` re-walks every label."""

    def work(progress):
        progress(0, 1, "Scanning Gmail…")
        job_session = SessionLocal()
        try:
            result = scan.run_scan(job_session, full=full)
            progress(1, 1, "Done")
            return result
        finally:
            job_session.close()

    return {"job_id": jobs.start("gmail-scan", work)}


@router.get("/attachments/status")
def attachments_status(session: Session = Depends(get_session)) -> dict:
    return {
        "pending_emails": attachments.pending_count(session),
        "connected": client.mode() == "real" and client.is_connected(),
    }


@router.post("/attachments-async")
def fetch_attachments_async() -> dict:
    """Download attachments from matched business emails as a background job."""

    def work(progress):
        job_session = SessionLocal()
        try:
            return attachments.fetch_new(job_session, on_progress=progress)
        finally:
            job_session.close()

    return {"job_id": jobs.start("gmail-attachments", work)}


@router.get("/emails")
def emails(
    session: Session = Depends(get_session),
    category: Optional[str] = Query(None),
    business_id: Optional[int] = Query(None),
    year: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    q = (
        session.query(Email, Business.name, Year.label)
        .outerjoin(Business, Email.business_id == Business.id)
        .outerjoin(Year, Email.year_id == Year.id)
    )
    if category:
        q = q.filter(Email.category == category)
    if business_id:
        q = q.filter(Email.business_id == business_id)
    if year:
        q = q.filter(Year.label == year)

    total = q.count()
    q = q.order_by(Email.date.desc()).offset(offset).limit(limit)

    items = []
    for email, biz_name, yr_label in q.all():
        items.append({
            "id": email.id,
            "category": email.category,
            "kind": email.kind,
            "business": biz_name,
            "year": yr_label,
            "subject": email.subject,
            "sender": email.sender,
            "date": email.date,
            "snippet": email.snippet,
            "has_attachments": email.has_attachments,
        })
    return {
        "emails": items,
        "count": len(items),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/businesses")
def businesses(session: Session = Depends(get_session)) -> dict:
    out = []
    for b in session.query(Business).order_by(Business.type, Business.name).all():
        years = (
            session.query(Year.label)
            .filter(Year.business_id == b.id)
            .distinct()
            .all()
        )
        email_count = session.query(Email).filter(Email.business_id == b.id).count()
        out.append({
            "id": b.id,
            "name": b.name,
            "type": b.type,
            "years": sorted({y[0] for y in years}),
            "email_count": email_count,
        })
    return {"businesses": out}


class MergeRequest(BaseModel):
    src_id: int
    dst_id: int


@router.post("/businesses/merge")
def merge(req: MergeRequest, session: Session = Depends(get_session)) -> dict:
    try:
        return scan.merge_business(session, req.src_id, req.dst_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
