"""Poll the status of a background job started by another endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..services import jobs

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job(job_id: str) -> dict:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job
