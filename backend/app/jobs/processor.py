"""Background photo processing pipeline."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.goodreads.automation import GoodreadsAutomation
from app.jobs.manager import job_manager
from app.models.schemas import (
    BookResult,
    JobStatus,
    ProcessingStep,
    UnknownBook,
)
from app.ocr.detector import extract_titles

logger = logging.getLogger(__name__)


async def process_job(job_id: str, photo_paths: list[Path]) -> None:
    goodreads = GoodreadsAutomation()

    try:
        job_manager.update(
            job_id,
            status=JobStatus.PROCESSING,
            current_photo=0,
            message="Starting Goodreads session",
        )
        await goodreads.start()

        books_found = 0
        books_on_shelf = 0
        books_added = 0
        unknown_books: list[UnknownBook] = []
        results: list[BookResult] = []

        for index, photo_path in enumerate(photo_paths):
            photo_num = index + 1
            job_manager.update(
                job_id,
                current_photo=photo_num,
                current_step=ProcessingStep.OCR,
                message=f"Reading photo {photo_num} of {len(photo_paths)}",
            )

            titles = await asyncio.to_thread(extract_titles, photo_path)
            if not titles:
                unknown_books.append(
                    UnknownBook(
                        title="",
                        photo_index=index,
                        photo_filename=photo_path.name,
                    )
                )
                job_manager.update(
                    job_id,
                    unknown_books=unknown_books,
                    message=f"No text detected in photo {photo_num}",
                )
            else:
                books_found += len(titles)
                job_manager.update(job_id, books_found=books_found)

                for title in titles:
                    job_manager.update(
                        job_id,
                        current_step=ProcessingStep.CHECKING,
                        current_title=title,
                        message=f"Checking Goodreads for “{title}”",
                    )

                    result = await goodreads.check_and_add(title)

                    if result.status == "on_shelf":
                        books_on_shelf += 1
                    elif result.status == "added":
                        books_added += 1
                    elif result.status == "unknown":
                        unknown_books.append(
                            UnknownBook(
                                title=title,
                                photo_index=index,
                                photo_filename=photo_path.name,
                            )
                        )

                    results.append(
                        BookResult(
                            title=result.title,
                            status=result.status,
                            message=result.message,
                            photo_index=index,
                        )
                    )

                    job_manager.update(
                        job_id,
                        books_on_shelf=books_on_shelf,
                        books_added=books_added,
                        unknown_books=unknown_books,
                        results=results,
                    )

            job_manager.update(
                job_id,
                current_step=ProcessingStep.CLEANUP,
                message=f"Removing photo {photo_num}",
            )
            photo_path.unlink(missing_ok=True)

        if photo_paths:
            job_dir = photo_paths[0].parent
            if job_dir.exists():
                job_dir.rmdir()

        job_manager.update(
            job_id,
            status=JobStatus.COMPLETED,
            current_step=ProcessingStep.IDLE,
            current_title=None,
            message="Done",
        )

    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        job_manager.update(
            job_id,
            status=JobStatus.FAILED,
            error=str(exc),
            message="Processing failed",
        )
        for photo_path in photo_paths:
            photo_path.unlink(missing_ok=True)
        if photo_paths:
            job_dir = photo_paths[0].parent
            if job_dir.exists():
                job_dir.rmdir()
    finally:
        await goodreads.close()


async def process_manual_entries(
    job_id: str,
    entries: list[tuple[str, int]],
) -> None:
    """Process manually corrected book titles."""
    goodreads = GoodreadsAutomation()
    job = job_manager.get(job_id)
    if job is None:
        return

    try:
        await goodreads.start()
        books_added = job.books_added
        books_on_shelf = job.books_on_shelf
        results = list(job.results)
        unknown_books = list(job.unknown_books)

        for corrected_title, photo_index in entries:
            job_manager.update(
                job_id,
                current_step=ProcessingStep.ADDING,
                current_title=corrected_title,
                message=f"Adding “{corrected_title}”",
            )

            result = await goodreads.check_and_add(corrected_title)

            if result.status == "on_shelf":
                books_on_shelf += 1
            elif result.status == "added":
                books_added += 1

            results.append(
                BookResult(
                    title=result.title,
                    status=result.status,
                    message=result.message,
                    photo_index=photo_index,
                )
            )

            unknown_books = [
                book
                for book in unknown_books
                if not (
                    book.photo_index == photo_index
                    and (book.title == corrected_title or book.title == "")
                )
            ]

            job_manager.update(
                job_id,
                books_added=books_added,
                books_on_shelf=books_on_shelf,
                results=results,
                unknown_books=unknown_books,
            )

        job_manager.update(
            job_id,
            status=JobStatus.COMPLETED,
            current_step=ProcessingStep.IDLE,
            message="Manual entries processed",
        )

    except Exception as exc:
        logger.exception("Manual processing failed for job %s", job_id)
        job_manager.update(
            job_id,
            status=JobStatus.FAILED,
            error=str(exc),
            message="Manual processing failed",
        )
    finally:
        await goodreads.close()
