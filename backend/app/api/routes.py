"""API routes for shelfie."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.config import settings
from app.jobs.manager import job_manager
from app.jobs.processor import process_job, process_manual_entries
from app.models.schemas import JobCreateResponse, JobProgress, ManualSubmitRequest

router = APIRouter(prefix="/api")


@router.post("/jobs", response_model=JobCreateResponse)
async def create_job(
    background_tasks: BackgroundTasks,
    photos: list[UploadFile] = File(...),
) -> JobCreateResponse:
    if not photos:
        raise HTTPException(status_code=400, detail="At least one photo is required")
    if len(photos) > settings.max_photos:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.max_photos} photos allowed",
        )

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    progress = job_manager.create(total_photos=len(photos))
    job_dir = settings.upload_dir / progress.job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    photo_paths: list[Path] = []
    for index, photo in enumerate(photos):
        suffix = Path(photo.filename or f"photo_{index}.jpg").suffix or ".jpg"
        dest = job_dir / f"{index:02d}{suffix}"
        content = await photo.read()
        dest.write_bytes(content)
        photo_paths.append(dest)

    background_tasks.add_task(process_job, progress.job_id, photo_paths)
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
