"""Upload and media processing API endpoints.

Owned by: feature/ocr-whisper
Implements the 4 PRD-contracted routes for media ingestion, status polling, and retry.
"""

import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Request,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_active_user_optional,
    get_db,
    get_ocr,
    get_request_id,
    get_speech,
    get_storage,
)
from app.core.config import settings
from app.core.exceptions import NotFoundException, ValidationException
from app.db.models.enums import AIJobType, InputKind
from app.db.models.user import User
from app.db.models.visit import Visit
from app.db.session import SessionLocal
from app.integrations.ocr import OCRProvider
from app.integrations.speech import SpeechProvider
from app.integrations.storage import StorageProvider
from app.schemas.common import ApiResponse, Meta
from app.schemas.media import (
    AudioUploadResponse,
    DocumentUploadResponse,
    JobStatusResponse,
)
from app.services import job_service, upload_service
from app.services.audit_service import AuditService

router = APIRouter(tags=["Uploads & Media Processing"])


# -------------------------------------------------------------------
# POST /visits/{visit_id}/audio
# -------------------------------------------------------------------
@router.post(
    "/visits/{visit_id}/audio",
    response_model=ApiResponse[AudioUploadResponse],
    status_code=202,
    summary="Upload audio recording for transcription",
)
async def upload_audio(
    visit_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Form(default="en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_optional),
    speech: SpeechProvider = Depends(get_speech),
    storage: StorageProvider = Depends(get_storage),
):
    """Upload audio blob and enqueue transcription job.

    Returns immediately with job_id. Client polls GET /inputs/{input_id} for status.
    """
    request_id = get_request_id(request)

    # 1. Validate visit exists and has consent
    visit = db.get(Visit, visit_id)
    if not visit:
        raise NotFoundException(f"Visit {visit_id} not found")
    upload_service.check_consent(visit)

    # 2. Read and validate file
    file_bytes = await file.read()
    content_type = file.content_type or "audio/webm"
    upload_service.validate_audio_file(content_type, len(file_bytes))

    # 3. Upload to storage
    original_filename = file.filename or "recording.webm"
    object_key = upload_service.build_object_key(
        visit.clinic_id, visit.id, InputKind.AUDIO, original_filename
    )
    await storage.upload(file_bytes, object_key, content_type)

    # 4. Create VisitInput record
    visit_input = upload_service.create_visit_input(
        db,
        visit,
        InputKind.AUDIO,
        object_key,
        language=language,
        original_filename=original_filename,
    )

    # 5. Enqueue transcription job
    provider = settings.WHISPER_PROVIDER_MODE
    idempotency_key = f"transcribe-{visit.id}-{visit_input.id}"
    job = job_service.enqueue_job(
        db,
        visit.id,
        AIJobType.TRANSCRIPTION,
        provider,
        visit_input.id,
        idempotency_key=idempotency_key,
    )

    # 6. Audit
    audit = AuditService(db)
    audit.record_event(
        action="MEDIA_UPLOADED",
        entity_type="visit_input",
        entity_id=str(visit_input.id),
        request_id=request_id,
        actor_id=current_user.id if current_user else None,
        actor_role=current_user.role.value if current_user else "patient_kiosk",
        payload={
            "kind": "AUDIO",
            "language": language,
            "object_key": object_key,
            "size_bytes": len(file_bytes),
            "job_id": str(job.id),
        },
    )

    db.commit()

    # 7. Schedule background processing
    background_tasks.add_task(
        job_service.execute_transcription_job,
        job.id,
        SessionLocal,
        speech,
        storage,
    )

    return ApiResponse(
        success=True,
        data=AudioUploadResponse(
            input_id=visit_input.id,
            job_id=job.id,
            status=job.status.value,
            language=language,
            provider=provider,
            web_speech_fallback=settings.WEB_SPEECH_FALLBACK,
        ),
        meta=Meta(request_id=request_id),
    )


# -------------------------------------------------------------------
# POST /visits/{visit_id}/uploads
# -------------------------------------------------------------------
@router.post(
    "/visits/{visit_id}/uploads",
    response_model=ApiResponse[DocumentUploadResponse],
    status_code=202,
    summary="Upload document (PDF/image) for OCR extraction",
)
async def upload_document(
    visit_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_optional),
    ocr: OCRProvider = Depends(get_ocr),
    storage: StorageProvider = Depends(get_storage),
):
    """Upload document and enqueue OCR job.

    Returns immediately with job_id. Client polls GET /inputs/{input_id} for status.
    """
    request_id = get_request_id(request)

    # 1. Validate visit
    visit = db.get(Visit, visit_id)
    if not visit:
        raise NotFoundException(f"Visit {visit_id} not found")
    upload_service.check_consent(visit)

    # 2. Read and validate file
    file_bytes = await file.read()
    content_type = file.content_type or "application/octet-stream"
    upload_service.validate_document_file(content_type, len(file_bytes))

    # 3. Determine InputKind
    kind = InputKind.PDF if content_type == "application/pdf" else InputKind.IMAGE

    # 4. Upload to storage
    original_filename = file.filename or "document"
    object_key = upload_service.build_object_key(
        visit.clinic_id, visit.id, kind, original_filename
    )
    await storage.upload(file_bytes, object_key, content_type)

    # 5. Create VisitInput record
    visit_input = upload_service.create_visit_input(
        db,
        visit,
        kind,
        object_key,
        original_filename=original_filename,
    )

    # 6. Enqueue OCR job
    provider = settings.OCR_PROVIDER_MODE
    idempotency_key = f"ocr-{visit.id}-{visit_input.id}"
    job = job_service.enqueue_job(
        db,
        visit.id,
        AIJobType.OCR,
        provider,
        visit_input.id,
        idempotency_key=idempotency_key,
    )

    # 7. Audit
    audit = AuditService(db)
    audit.record_event(
        action="MEDIA_UPLOADED",
        entity_type="visit_input",
        entity_id=str(visit_input.id),
        request_id=request_id,
        actor_id=current_user.id if current_user else None,
        actor_role=current_user.role.value if current_user else "patient_kiosk",
        payload={
            "kind": kind.value,
            "object_key": object_key,
            "size_bytes": len(file_bytes),
            "job_id": str(job.id),
            "display_name": original_filename,
        },
    )

    db.commit()

    # 8. Schedule background processing
    background_tasks.add_task(
        job_service.execute_ocr_job,
        job.id,
        SessionLocal,
        ocr,
        storage,
    )

    return ApiResponse(
        success=True,
        data=DocumentUploadResponse(
            input_id=visit_input.id,
            job_id=job.id,
            status=job.status.value,
            kind=kind,
            display_name=original_filename,
            provider=provider,
        ),
        meta=Meta(request_id=request_id),
    )


# -------------------------------------------------------------------
# GET /inputs/{input_id}
# -------------------------------------------------------------------
@router.get(
    "/inputs/{input_id}",
    response_model=ApiResponse[JobStatusResponse],
    summary="Poll processing status for an uploaded input",
)
async def get_input_status(
    input_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
):
    """Retrieve current processing status, progress, and result preview."""
    request_id = get_request_id(request)

    # Fetch job and input
    job, visit_input = job_service.get_job_with_input(db, input_id)

    # Generate presigned URL for source file if available
    source_url = None
    if visit_input.object_key:
        try:
            source_url = await storage.get_presigned_url(visit_input.object_key)
        except Exception:
            source_url = None

    # Build result preview
    result_preview = None
    if visit_input.text:
        result_preview = visit_input.text[:200]

    return ApiResponse(
        success=True,
        data=JobStatusResponse(
            job_id=job.id,
            input_id=visit_input.id,
            visit_id=job.visit_id,
            type=job.type,
            status=job.status,
            progress=job_service.compute_progress(job.status),
            attempts=job.attempts,
            max_retries=settings.MAX_JOB_RETRIES,
            error_code=job.error_code,
            result_preview=result_preview,
            source_url=source_url,
            created_at=job.created_at,
            updated_at=job.updated_at,
        ),
        meta=Meta(request_id=request_id),
    )


# -------------------------------------------------------------------
# POST /inputs/{input_id}/retry
# -------------------------------------------------------------------
@router.post(
    "/inputs/{input_id}/retry",
    response_model=ApiResponse[JobStatusResponse],
    summary="Retry a failed processing job",
)
async def retry_input_processing(
    input_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_optional),
    speech: SpeechProvider = Depends(get_speech),
    ocr: OCRProvider = Depends(get_ocr),
    storage: StorageProvider = Depends(get_storage),
):
    """Retry a failed job. Returns 409 if job is terminal or not in FAILED state."""
    request_id = get_request_id(request)

    # Retry (raises ConflictException if not retriable)
    job = job_service.retry_job(db, input_id)
    visit_input = db.get(VisitInput, input_id)

    # Audit retry event
    audit = AuditService(db)
    audit.record_event(
        action="JOB_RETRIED",
        entity_type="ai_job",
        entity_id=str(job.id),
        request_id=request_id,
        actor_id=current_user.id if current_user else None,
        actor_role=current_user.role.value if current_user else "patient_kiosk",
        payload={
            "input_id": str(input_id),
            "attempt": job.attempts,
        },
    )

    db.commit()

    # Re-schedule background processing
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
        data=JobStatusResponse(
            job_id=job.id,
            input_id=input_id,
            visit_id=job.visit_id,
            type=job.type,
            status=job.status,
            progress=job_service.compute_progress(job.status),
            attempts=job.attempts,
            max_retries=settings.MAX_JOB_RETRIES,
            error_code=job.error_code,
            result_preview=visit_input.text[:200] if visit_input and visit_input.text else None,
            source_url=None,
            created_at=job.created_at,
            updated_at=job.updated_at,
        ),
        meta=Meta(request_id=request_id),
    )
