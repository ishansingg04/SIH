"""AI Job orchestration service.

Owned by: feature/ocr-whisper
Manages the job state machine (PENDING → RUNNING → COMPLETED/RETRYING/FAILED),
enqueuing, background execution, status polling, and retry logic.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    ConflictException,
    DependencyUnavailableException,
    NotFoundException,
)
from app.core.logging import logger
from app.db.models.ai_job import AIJob
from app.db.models.enums import AIJobStatus, AIJobType, InputStatus
from app.db.models.input import VisitInput
from app.integrations.ocr import OCRProvider
from app.integrations.speech import SpeechProvider
from app.integrations.storage import StorageProvider
from app.services.upload_service import update_input_status


# -------------------------------------------------------------------
# Progress mapping for client polling
# -------------------------------------------------------------------
PROGRESS_MAP = {
    AIJobStatus.PENDING: 0,
    AIJobStatus.RUNNING: 50,
    AIJobStatus.RETRYING: 30,
    AIJobStatus.COMPLETED: 100,
    AIJobStatus.FAILED: 100,
}


# -------------------------------------------------------------------
# Enqueue
# -------------------------------------------------------------------
def enqueue_job(
    db: Session,
    visit_id: uuid.UUID,
    job_type: AIJobType,
    provider: str,
    input_id: uuid.UUID,
    idempotency_key: Optional[str] = None,
) -> AIJob:
    """Create a new AI job in PENDING state.

    Raises ConflictException if a job with the same idempotency_key already exists.
    """
    # Idempotency guard
    if idempotency_key:
        existing = db.scalars(
            select(AIJob).where(AIJob.idempotency_key == idempotency_key)
        ).first()
        if existing:
            raise ConflictException(
                f"Job with idempotency key '{idempotency_key}' already exists "
                f"(job_id={existing.id}, status={existing.status.value})"
            )

    job = AIJob(
        visit_id=visit_id,
        type=job_type,
        status=AIJobStatus.PENDING,
        provider=provider,
        attempts=0,
        idempotency_key=idempotency_key,
        payload_in={"input_id": str(input_id)},
    )
    db.add(job)
    db.flush()

    logger.info(
        f"Enqueued {job_type.value} job {job.id} for visit {visit_id} "
        f"(provider={provider}, input={input_id})"
    )
    return job


# -------------------------------------------------------------------
# Background execution tasks
# -------------------------------------------------------------------
async def execute_transcription_job(
    job_id: uuid.UUID,
    session_factory,
    speech: SpeechProvider,
    storage: StorageProvider,
) -> None:
    """Background task: run transcription for an audio VisitInput.

    State machine: PENDING → RUNNING → COMPLETED | RETRYING | FAILED
    """
    with session_factory() as db:
        try:
            job = db.get(AIJob, job_id)
            if not job:
                logger.error(f"Transcription job {job_id} not found")
                return

            # Transition to RUNNING
            job.status = AIJobStatus.RUNNING
            job.attempts += 1
            db.flush()

            # Load linked VisitInput
            input_id = uuid.UUID(job.payload_in["input_id"])
            visit_input = db.get(VisitInput, input_id)
            if not visit_input or not visit_input.object_key:
                job.status = AIJobStatus.FAILED
                job.error_code = "INPUT_NOT_FOUND"
                db.commit()
                return

            # Update input status to PROCESSING
            visit_input.status = InputStatus.PROCESSING
            db.flush()

            # Fetch audio bytes from storage
            audio_bytes = await _fetch_object_bytes(storage, visit_input.object_key)

            # Determine language from provenance
            language = visit_input.provenance.get("language", "en")
            filename = visit_input.provenance.get(
                "original_filename", "audio.webm"
            )

            # Call speech provider
            result = await speech.transcribe(
                audio_bytes=audio_bytes,
                language=language,
                filename=filename,
            )

            # Save result
            job.payload_out = {
                "text": result.text,
                "language": result.language,
                "provider": result.provider,
                "is_fallback": result.is_fallback,
                "segments": [s.model_dump() for s in result.segments],
                "metadata": result.metadata,
            }
            job.status = AIJobStatus.COMPLETED
            job.error_code = None

            # Update VisitInput with extracted text
            update_input_status(
                db,
                input_id,
                InputStatus.COMPLETED,
                text=result.text,
                confidence=result.segments[0].confidence
                if result.segments
                else 0.9,
            )

            db.commit()
            logger.info(
                f"Transcription job {job_id} completed successfully "
                f"({len(result.text)} chars)"
            )

        except DependencyUnavailableException as exc:
            _handle_provider_failure(db, job, str(exc), "PROVIDER_UNAVAILABLE")

        except Exception as exc:
            logger.error(f"Transcription job {job_id} unexpected error: {exc}")
            _handle_provider_failure(db, job, str(exc), "INTERNAL_ERROR")


async def execute_ocr_job(
    job_id: uuid.UUID,
    session_factory,
    ocr: OCRProvider,
    storage: StorageProvider,
) -> None:
    """Background task: run OCR extraction for a document VisitInput.

    State machine: PENDING → RUNNING → COMPLETED | RETRYING | FAILED
    """
    with session_factory() as db:
        try:
            job = db.get(AIJob, job_id)
            if not job:
                logger.error(f"OCR job {job_id} not found")
                return

            # Transition to RUNNING
            job.status = AIJobStatus.RUNNING
            job.attempts += 1
            db.flush()

            # Load linked VisitInput
            input_id = uuid.UUID(job.payload_in["input_id"])
            visit_input = db.get(VisitInput, input_id)
            if not visit_input or not visit_input.object_key:
                job.status = AIJobStatus.FAILED
                job.error_code = "INPUT_NOT_FOUND"
                db.commit()
                return

            # Update input status to PROCESSING
            visit_input.status = InputStatus.PROCESSING
            db.flush()

            # Fetch document bytes from storage
            doc_bytes = await _fetch_object_bytes(storage, visit_input.object_key)

            # Determine content type and filename
            filename = visit_input.provenance.get(
                "original_filename", "document.jpg"
            )
            content_type = _guess_content_type(filename)

            # Call OCR provider
            result = await ocr.extract(
                file_bytes=doc_bytes,
                content_type=content_type,
                filename=filename,
            )

            # Save result
            job.payload_out = {
                "raw_text": result.raw_text,
                "items": [item.model_dump() for item in result.items],
                "page_count": result.page_count,
                "confidence": result.confidence,
                "provider": result.provider,
                "metadata": result.metadata,
            }
            job.status = AIJobStatus.COMPLETED
            job.error_code = None

            # Update VisitInput with extracted text
            update_input_status(
                db,
                input_id,
                InputStatus.COMPLETED,
                text=result.raw_text,
                confidence=result.confidence,
            )

            db.commit()
            logger.info(
                f"OCR job {job_id} completed successfully "
                f"({len(result.raw_text)} chars, {len(result.items)} items)"
            )

        except DependencyUnavailableException as exc:
            _handle_provider_failure(db, job, str(exc), "PROVIDER_UNAVAILABLE")

        except Exception as exc:
            logger.error(f"OCR job {job_id} unexpected error: {exc}")
            _handle_provider_failure(db, job, str(exc), "INTERNAL_ERROR")


# -------------------------------------------------------------------
# Status and retry
# -------------------------------------------------------------------
def get_job_with_input(
    db: Session,
    input_id: uuid.UUID,
) -> tuple[AIJob, VisitInput]:
    """Fetch the AI job linked to a VisitInput for status polling."""
    visit_input = db.get(VisitInput, input_id)
    if not visit_input or visit_input.is_deleted:
        raise NotFoundException(f"Input {input_id} not found")

    # Query by visit_id, then filter by input_id in Python.
    # This avoids JSON path operators that differ between SQLite and Postgres.
    input_id_str = str(input_id)
    stmt = (
        select(AIJob)
        .where(AIJob.visit_id == visit_input.visit_id)
        .order_by(AIJob.created_at.desc())
    )
    all_jobs = db.scalars(stmt).all()

    job = None
    for j in all_jobs:
        if j.payload_in and j.payload_in.get("input_id") == input_id_str:
            job = j
            break

    if not job:
        raise NotFoundException(f"No processing job found for input {input_id}")

    return job, visit_input


def compute_progress(status: AIJobStatus) -> int:
    """Compute progress percentage from job status."""
    return PROGRESS_MAP.get(status, 0)


def retry_job(db: Session, input_id: uuid.UUID) -> AIJob:
    """Retry a failed job.

    - If FAILED and attempts < MAX_RETRIES: resets to PENDING
    - If terminal (attempts >= MAX_RETRIES): raises ConflictException (409)
    - If not FAILED: raises ConflictException (409)
    """
    job, visit_input = get_job_with_input(db, input_id)

    if job.status != AIJobStatus.FAILED:
        raise ConflictException(
            f"Cannot retry job in '{job.status.value}' state. "
            f"Only FAILED jobs can be retried."
        )

    max_retries = settings.MAX_JOB_RETRIES
    if job.attempts >= max_retries:
        raise ConflictException(
            f"Job has exhausted all {max_retries} retry attempts. "
            f"This failure is terminal."
        )

    # Reset to PENDING for re-processing
    job.status = AIJobStatus.PENDING
    job.error_code = None

    # Reset input status
    visit_input.status = InputStatus.PENDING
    db.flush()

    logger.info(
        f"Job {job.id} reset for retry (attempt {job.attempts}/{max_retries})"
    )
    return job


# -------------------------------------------------------------------
# Internal helpers
# -------------------------------------------------------------------
def _handle_provider_failure(
    db: Session,
    job: AIJob,
    error_message: str,
    error_code: str,
) -> None:
    """Handle provider failure with retry/terminal logic."""
    max_retries = settings.MAX_JOB_RETRIES

    if job.attempts < max_retries:
        job.status = AIJobStatus.RETRYING
        job.error_code = error_code
        logger.warning(
            f"Job {job.id} failed (attempt {job.attempts}/{max_retries}), "
            f"marking for retry: {error_message}"
        )
    else:
        job.status = AIJobStatus.FAILED
        job.error_code = error_code
        logger.error(
            f"Job {job.id} terminally failed after {job.attempts} attempts: "
            f"{error_message}"
        )

        # Update linked VisitInput to FAILED
        try:
            input_id = uuid.UUID(job.payload_in["input_id"])
            visit_input = db.get(VisitInput, input_id)
            if visit_input:
                visit_input.status = InputStatus.FAILED
        except (KeyError, ValueError):
            pass

    db.commit()


async def _fetch_object_bytes(
    storage: StorageProvider,
    object_key: str,
) -> bytes:
    """Fetch object bytes from storage.

    For LocalStorageAdapter: reads from filesystem.
    For S3StorageAdapter: fetches via presigned URL.
    """
    from app.integrations.storage import LocalStorageAdapter

    if isinstance(storage, LocalStorageAdapter):
        file_path = storage.base_dir / object_key
        if not file_path.exists():
            raise DependencyUnavailableException(
                f"Object not found in local storage: {object_key}"
            )
        return file_path.read_bytes()

    # For S3-compatible storage: get presigned URL and download
    import httpx

    url = await storage.get_presigned_url(object_key)
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def _guess_content_type(filename: str) -> str:
    """Guess content type from filename extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    type_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "pdf": "application/pdf",
    }
    return type_map.get(ext, "image/jpeg")
