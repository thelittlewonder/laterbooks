from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStep(str, Enum):
    IDLE = "idle"
    OCR = "ocr"
    CHECKING = "checking"
    ADDING = "adding"
    CLEANUP = "cleanup"


class BookResult(BaseModel):
    title: str
    status: Literal["on_shelf", "added", "unknown", "failed"]
    message: str | None = None
    photo_index: int


class UnknownBook(BaseModel):
    title: str
    photo_index: int


class JobProgress(BaseModel):
    job_id: str
    status: JobStatus
    current_photo: int = 0
    total_photos: int = 0
    current_step: ProcessingStep = ProcessingStep.IDLE
    current_title: str | None = None
    books_found: int = 0
    books_on_shelf: int = 0
    books_added: int = 0
    unknown_books: list[UnknownBook] = Field(default_factory=list)
    results: list[BookResult] = Field(default_factory=list)
    error: str | None = None
    message: str | None = None


class ManualEntry(BaseModel):
    original_title: str
    corrected_title: str
    photo_index: int


class ManualSubmitRequest(BaseModel):
    entries: list[ManualEntry]


class JobCreateResponse(BaseModel):
    job_id: str
