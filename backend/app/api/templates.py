"""Templates API: list the real templates and build working copies (Phase 4)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import REPO_ROOT
from ..db import get_session
from ..models import Year
from ..services.templates import builder

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("")
def list_templates(session: Session = Depends(get_session)) -> dict:
    years = sorted({y[0] for y in session.query(Year.label).distinct()}, reverse=True)
    return {"templates": builder.list_templates(), "years": years}


class BuildRequest(BaseModel):
    year: str


@router.post("/build")
def build(req: BuildRequest, session: Session = Depends(get_session)) -> dict:
    out_dir = REPO_ROOT / "output" / req.year / "_templates"
    return builder.build_for_year(session, req.year, out_dir)
