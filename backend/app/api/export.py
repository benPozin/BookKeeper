"""Export API: summarize, build, and download the accountant zip (Phase 7)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..services.export import builder

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/years")
def years(session: Session = Depends(get_session)) -> dict:
    return {"years": builder.available_years(session)}


@router.get("/summary")
def summary(year: str, session: Session = Depends(get_session)) -> dict:
    return builder.summarize(session, year)


@router.get("/tree")
def tree(year: str, session: Session = Depends(get_session)) -> dict:
    """The package as a nested folder/file structure, for the visual view."""
    return builder.package_tree(session, year)


class RevealRequest(BaseModel):
    year: str
    target: str = "folder"  # folder | zip


@router.post("/reveal")
def reveal(req: RevealRequest, session: Session = Depends(get_session)) -> dict:
    """Open Finder/Explorer on the host at the built package."""
    res = builder.reveal(session, req.year, req.target)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


class BuildRequest(BaseModel):
    year: str


@router.post("/build")
def build(req: BuildRequest, session: Session = Depends(get_session)) -> dict:
    return builder.build_package(session, req.year)


@router.get("/download/{year}")
def download(year: str, session: Session = Depends(get_session)):
    res = builder.build_package(session, year)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    path = Path(res["zip_path"])
    return FileResponse(path, filename=path.name, media_type="application/zip")
