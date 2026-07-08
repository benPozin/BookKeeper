"""Automation API: enable/disable the daily job, run it now, see status (Phase 6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import scheduler
from ..db import get_session

router = APIRouter(prefix="/api/automation", tags=["automation"])


@router.get("/status")
def status(session: Session = Depends(get_session)) -> dict:
    return scheduler.status(session)


class EnableRequest(BaseModel):
    hour: int = 2
    minute: int = 0


@router.post("/enable")
def enable(req: EnableRequest, session: Session = Depends(get_session)) -> dict:
    return scheduler.enable(session, req.hour, req.minute)


@router.post("/disable")
def disable(session: Session = Depends(get_session)) -> dict:
    return scheduler.disable(session)


@router.post("/run-now")
def run_now() -> dict:
    return scheduler.run_now()
