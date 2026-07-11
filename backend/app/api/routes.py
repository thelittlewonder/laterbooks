"""API routes for laterbooks."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.config import settings
from app.jobs.manager import job_manager
from app.jobs.processor import process_job, process_manual_entries
from app.models.schemas import (
    JobCreateRequest,
    JobCreateResponse,
    JobProgress,
    ManualSubmitRequest,
    PhotoSubmission,
)

router = APIRouter(prefix="/api")


@router.post("/jobs", response_model=JobCreateResponse)
async def create_job(
    body: JobCreateRequest,
    background_tasks: BackgroundTasks,
) -> JobCreateResponse:
    if not body.photos:
        raise HTTPException(status_code=400, detail="At least one photo is required")
    if len(body.photos) > settings.max_photos:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.max_photos} photos allowed",
        )

    photos = sorted(body.photos, key=lambda photo: photo.photo_index)
    progress = job_manager.create(total_photos=len(photos))
    background_tasks.add_task(process_job, progress.job_id, photos)
    return JobCreateResponse(job_id=progress.job_id)


@router.get("/jobs/{job_id}", response_model=JobProgress)
async def get_job(job_id: str) -> JobProgress:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/manual", response_model=JobProgress)
async def submit_manual(
    job_id: str,
    body: ManualSubmitRequest,
    background_tasks: BackgroundTasks,
) -> JobProgress:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not body.entries:
        raise HTTPException(status_code=400, detail="No entries provided")

    entries = [(entry.corrected_title, entry.photo_index) for entry in body.entries]
    background_tasks.add_task(process_manual_entries, job_id, entries)
    return job
