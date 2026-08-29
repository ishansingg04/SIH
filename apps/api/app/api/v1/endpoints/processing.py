"""Operator-facing worker observability and manual job processing endpoints.

Owned by: feature/ocr-whisper
Provides SYSTEM_OPERATOR and CLINIC_ADMIN access to view pending jobs
and manually trigger processing for debugging.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_db,
    get_ocr,
    get_request_id,
    get_speech,
    get_storage,
    require_roles,
)
from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.db.models.ai_job import AIJob
from app.db.models.enums import AIJobStatus, AIJobType, UserRole
from app.db.models.user import User
from app.db.session import SessionLocal
from app.integrations.ocr import OCRProvider
from app.integrations.speech import SpeechProvider
from app.integrations.storage import StorageProvider
from app.schemas.common import ApiResponse, Meta
from app.schemas.media import WorkerJobItem, WorkerJobListResponse
from app.services import job_service

router = APIRouter(
    prefix="/worker",
    tags=["Worker & Observability"],
)


@router.get(
    "/jobs",
    response_model=ApiResponse[WorkerJobListResponse],
    summary="List pending and retrying jobs (operator view)",
)
def list_pending_jobs(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles([UserRole.SYSTEM_OPERATOR, UserRole.CLINIC_ADMIN])
    ),
):
    """List all jobs in PENDING or RETRYING state for operator monitoring."""
    request_id = get_request_id(request)

    stmt = (
        select(AIJob)
        .where(AIJob.status.in_([AIJobStatus.PENDING, AIJobStatus.RETRYING]))
        .order_by(AIJob.created_at.asc())
        .limit(100)
    )
    jobs = db.scalars(stmt).all()

    job_items = [WorkerJobItem.model_validate(j) for j in jobs]

    return ApiResponse(
        success=True,
        data=WorkerJobListResponse(jobs=job_items, total=len(job_items)),
        meta=Meta(request_id=request_id),
    )


@router.post(
    "/jobs/{job_id}/process",
    response_model=ApiResponse[WorkerJobItem],
    summary="Manually trigger processing for a specific job (debug)",
)
async def trigger_job_processing(
    job_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles([UserRole.SYSTEM_OPERATOR, UserRole.CLINIC_ADMIN])
    ),
    speech: SpeechProvider = Depends(get_speech),
    ocr: OCRProvider = Depends(get_ocr),
    storage: StorageProvider = Depends(get_storage),
):
    """Manually trigger background processing for a PENDING/RETRYING job.

    Useful for debugging or re-processing stuck jobs.
    """
    request_id = get_request_id(request)

    job = db.get(AIJob, job_id)
    if not job:
        raise NotFoundException(f"Job {job_id} not found")

    if job.status not in (AIJobStatus.PENDING, AIJobStatus.RETRYING):
        from app.core.exceptions import ConflictException

        raise ConflictException(
            f"Job is in '{job.status.value}' state. "
            f"Only PENDING or RETRYING jobs can be manually processed."
        )

    # Schedule background processing
    if job.type == AIJobType.TRANSCRIPTION:
        background_tasks.add_task(
            job_service.execute_transcription_job,
            job.id,
            SessionLocal,
            speech,
            storage,
        )
    elif job.type == AIJobType.OCR:
        background_tasks.add_task(
            job_service.execute_ocr_job,
            job.id,
            SessionLocal,
            ocr,
            storage,
        )

    return ApiResponse(
        success=True,
        data=WorkerJobItem.model_validate(job),
        meta=Meta(request_id=request_id),
    )
