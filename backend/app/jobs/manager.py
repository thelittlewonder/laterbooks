"""In-memory job state for progress polling."""

from __future__ import annotations

import uuid
from threading import Lock

from app.models.schemas import JobProgress, JobStatus, ProcessingStep


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobProgress] = {}
        self._lock = Lock()

    def create(self, total_photos: int) -> JobProgress:
        job_id = str(uuid.uuid4())
        progress = JobProgress(
            job_id=job_id,
            status=JobStatus.PENDING,
            total_photos=total_photos,
            message="Waiting to start",
        )
        with self._lock:
            self._jobs[job_id] = progress
        return progress

    def get(self, job_id: str) -> JobProgress | None:
        with self._lock:
            return self._jobs.get(job_id)

    def ensure(self, job_id: str, total_photos: int = 0) -> JobProgress:
        """Return an existing job or recreate one with the given id.

        Render's free tier drops in-memory state on spin-down, so a manual
        submit can arrive after the original job is gone. Recreating lets the
        corrected titles still be processed instead of hard-failing.
        """
        with self._lock:
            existing = self._jobs.get(job_id)
            if existing is not None:
                return existing
            progress = JobProgress(
                job_id=job_id,
                status=JobStatus.PENDING,
                total_photos=total_photos,
                message="Resuming manual review",
            )
            self._jobs[job_id] = progress
            return progress

    def update(self, job_id: str, **fields: object) -> JobProgress | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            updated = job.model_copy(update=fields)
            self._jobs[job_id] = updated
            return updated

    def set_step(self, job_id: str, step: ProcessingStep, message: str | None = None) -> None:
        fields: dict[str, object] = {
            "status": JobStatus.PROCESSING,
            "current_step": step,
        }
        if message is not None:
            fields["message"] = message
        self.update(job_id, **fields)


job_manager = JobManager()
