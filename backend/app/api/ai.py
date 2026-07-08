"""AI review API: status, run review, daily overview, enable/disable (Gemini)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_session
from ..models import Document, Setting
from ..services import jobs
from ..services.ai import reviewer

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/status")
def status(session: Session = Depends(get_session)) -> dict:
    return {
        "configured": reviewer.is_configured(session),
        "enabled": reviewer.is_enabled(session),
        "provider": "gemini",
        "model": reviewer.get_model(session),
        "key_source": reviewer.key_source(session),
        "reviewed": session.query(Document).filter(Document.ai_reviewed.is_(True)).count(),
        "total": session.query(Document).count(),
        "pending": session.query(Document).filter(Document.ai_reviewed.is_(False)).count(),
    }


@router.post("/review")
def review(session: Session = Depends(get_session)) -> dict:
    return reviewer.review_new(session)


@router.post("/review-async")
def review_async() -> dict:
    """Same as /review but returns immediately with a job id to poll — reviewing
    a batch of documents against an LLM can take a while."""

    def work(progress):
        job_session = SessionLocal()
        try:
            return reviewer.review_new(job_session, on_progress=progress)
        finally:
            job_session.close()

    return {"job_id": jobs.start("ai-review", work)}


@router.get("/overview")
def overview(session: Session = Depends(get_session)) -> dict:
    return reviewer.daily_overview(session)


class EnableRequest(BaseModel):
    enabled: bool


@router.post("/enable")
def enable(req: EnableRequest, session: Session = Depends(get_session)) -> dict:
    row = session.get(Setting, "ai_enabled")
    if row is None:
        session.add(Setting(key="ai_enabled", value="1" if req.enabled else "0"))
    else:
        row.value = "1" if req.enabled else "0"
    session.commit()
    return status(session)
