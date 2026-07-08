"""Organizer API: preview (dry-run) and apply the 6a-6i folder build (Phase 5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Year
from ..services.organizer import builder

router = APIRouter(prefix="/api/organizer", tags=["organizer"])


@router.get("/years")
def years(session: Session = Depends(get_session)) -> dict:
    return {"years": sorted({y[0] for y in session.query(Year.label).distinct()}, reverse=True)}


@router.get("/plan")
def plan(year: str, session: Session = Depends(get_session)) -> dict:
    return builder.plan(session, year)


class ApplyRequest(BaseModel):
    year: str


@router.post("/apply")
def apply(req: ApplyRequest, session: Session = Depends(get_session)) -> dict:
    return builder.apply(session, req.year)


class UnfileRequest(BaseModel):
    year: str


@router.post("/unfile")
def unfile(req: UnfileRequest, session: Session = Depends(get_session)) -> dict:
    return builder.unfile(session, req.year)
