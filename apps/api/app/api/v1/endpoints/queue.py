import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, get_request_id, require_roles
from app.core.exceptions import ValidationException
from app.db.models.enums import UserRole, VisitStatus
from app.db.models.user import User
from app.schemas.common import ApiResponse, Meta
from app.schemas.queue import (
    ClaimResponse,
    QueueEntryRead,
    QueueListResponse,
    QueueSummary,
    VisitActionRequest,
)
from app.services.queue_service import QueueService

router = APIRouter(prefix="/queue", tags=["Doctor Queue & Triage"])


@router.get("/today", response_model=ApiResponse[QueueListResponse])
def get_today_queue(
    request: Request,
    clinic_id: Optional[uuid.UUID] = Query(None, description="Clinic ID (defaults to staff user's clinic)"),
    state: Optional[VisitStatus] = Query(None, description="Filter queue entries by state"),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles([UserRole.DOCTOR, UserRole.RECEPTIONIST, UserRole.CLINIC_ADMIN, UserRole.SYSTEM_OPERATOR])
    ),
):
    """Retrieve today's active waiting queue in strict FIFO ordering."""
    request_id = get_request_id(request)
    target_clinic_id = clinic_id or current_user.clinic_id
    if not target_clinic_id:
        raise ValidationException("Clinic ID must be provided or associated with the user account")

    service = QueueService(db)
    result = service.get_today_queue(target_clinic_id, state_filter=state)

    return ApiResponse(
        success=True,
        data=result,
        meta=Meta(request_id=request_id),
    )


@router.get("/summary", response_model=ApiResponse[QueueSummary])
def get_queue_summary(
    request: Request,
    clinic_id: Optional[uuid.UUID] = Query(None, description="Clinic ID (defaults to staff user's clinic)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles([UserRole.DOCTOR, UserRole.RECEPTIONIST, UserRole.CLINIC_ADMIN, UserRole.SYSTEM_OPERATOR])
    ),
):
    """Retrieve real-time queue aggregations for today."""
    request_id = get_request_id(request)
    target_clinic_id = clinic_id or current_user.clinic_id
    if not target_clinic_id:
        raise ValidationException("Clinic ID must be provided or associated with the user account")

    service = QueueService(db)
    result = service.get_queue_summary(target_clinic_id)

    return ApiResponse(
        success=True,
        data=result,
        meta=Meta(request_id=request_id),
    )


@router.post("/claim-next", response_model=ApiResponse[ClaimResponse])
def claim_next_patient(
    request: Request,
    clinic_id: Optional[uuid.UUID] = Query(None, description="Clinic ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR, UserRole.CLINIC_ADMIN])),
):
    """Claim and call the next eligible patient in FIFO sequence."""
    request_id = get_request_id(request)
    target_clinic_id = clinic_id or current_user.clinic_id
    if not target_clinic_id:
        raise ValidationException("Clinic ID must be provided or associated with the doctor account")

    service = QueueService(db)
    result = service.claim_next(target_clinic_id, current_user, request_id=request_id)

    return ApiResponse(
        success=True,
        data=result,
        meta=Meta(request_id=request_id),
    )


@router.post("/{entry_id}/in-progress", response_model=ApiResponse[QueueEntryRead])
def mark_visit_in_progress(
    entry_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR, UserRole.CLINIC_ADMIN])),
):
    """Transition a called patient visit to IN_PROGRESS state."""
    request_id = get_request_id(request)
    service = QueueService(db)
    result = service.set_in_progress(entry_id, current_user, request_id=request_id)

    return ApiResponse(
        success=True,
        data=result,
        meta=Meta(request_id=request_id),
    )


@router.post("/{entry_id}/no-show", response_model=ApiResponse[QueueEntryRead])
def mark_patient_no_show(
    entry_id: uuid.UUID,
    request: Request,
    payload: Optional[VisitActionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR, UserRole.RECEPTIONIST, UserRole.CLINIC_ADMIN])),
):
    """Mark a queued patient as NO_SHOW if they do not respond to calls."""
    request_id = get_request_id(request)
    service = QueueService(db)
    reason = payload.reason if payload else None
    result = service.no_show_visit(entry_id, reason, current_user, request_id=request_id)

    return ApiResponse(
        success=True,
        data=result,
        meta=Meta(request_id=request_id),
    )


@router.post("/{entry_id}/cancel", response_model=ApiResponse[QueueEntryRead])
def cancel_queue_entry(
    entry_id: uuid.UUID,
    request: Request,
    payload: Optional[VisitActionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR, UserRole.RECEPTIONIST, UserRole.CLINIC_ADMIN])),
):
    """Cancel a queue entry and linked visit."""
    request_id = get_request_id(request)
    service = QueueService(db)
    reason = payload.reason if payload else None
    result = service.cancel_visit(entry_id, reason, current_user, request_id=request_id)

    return ApiResponse(
        success=True,
        data=result,
        meta=Meta(request_id=request_id),
    )
