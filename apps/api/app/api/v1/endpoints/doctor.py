import uuid
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, get_request_id, require_roles
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.schemas.common import ApiResponse, Meta
from app.schemas.doctor import (
    DoctorWorkspaceResponse,
    SummaryReviewRequest,
    SummaryReviewResponse,
)
from app.schemas.queue import VisitCompleteRequest, VisitCompleteResponse
from app.services.queue_service import QueueService

router = APIRouter(prefix="/doctor", tags=["Doctor Workspace & Clinical Review"])
visits_doctor_router = APIRouter(prefix="/visits", tags=["Doctor Clinical Completion"])


@router.get("/workspace/{visit_id}", response_model=ApiResponse[DoctorWorkspaceResponse])
def get_doctor_workspace(
    visit_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR, UserRole.CLINIC_ADMIN])),
):
    """Retrieve full patient workspace context including AYUSH findings, AI summary, and raw inputs."""
    request_id = get_request_id(request)
    service = QueueService(db)
    result = service.get_doctor_workspace(visit_id)

    return ApiResponse(
        success=True,
        data=result,
        meta=Meta(request_id=request_id),
    )


@visits_doctor_router.post("/{visit_id}/complete", response_model=ApiResponse[VisitCompleteResponse])
def complete_visit(
    visit_id: uuid.UUID,
    payload: VisitCompleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR, UserRole.CLINIC_ADMIN])),
):
    """Complete a clinical visit with mandatory clinical disposition and notes."""
    request_id = get_request_id(request)
    service = QueueService(db)
    result = service.complete_visit(
        visit_id=visit_id,
        disposition=payload.disposition,
        note=payload.note,
        doctor=current_user,
        request_id=request_id,
    )

    return ApiResponse(
        success=True,
        data=result,
        meta=Meta(request_id=request_id),
    )


@visits_doctor_router.post("/{visit_id}/summary/review", response_model=ApiResponse[SummaryReviewResponse])
def review_ai_summary(
    visit_id: uuid.UUID,
    payload: SummaryReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR, UserRole.CLINIC_ADMIN])),
):
    """Review and confirm/reject AI-generated clinical summary."""
    request_id = get_request_id(request)
    service = QueueService(db)
    result = service.review_summary(
        visit_id=visit_id,
        review_status=payload.review_status,
        doctor_notes=payload.doctor_notes,
        doctor=current_user,
        request_id=request_id,
    )

    return ApiResponse(
        success=True,
        data=result,
        meta=Meta(request_id=request_id),
    )
