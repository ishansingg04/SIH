from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, get_db, get_request_id, require_roles
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.schemas.common import ApiResponse, Meta
from app.schemas.patient import PatientRead, PatientUpdate
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["Patient Profile"])


@router.get("/me", response_model=ApiResponse[PatientRead])
def get_my_profile(
    request: Request,
    current_user: User = Depends(require_roles([UserRole.PATIENT])),
    db: Session = Depends(get_db),
):
    """Get the authenticated patient's profile."""
    request_id = get_request_id(request)
    patient_service = PatientService(db)
    
    patient = patient_service.get_my_profile(current_user)
    
    return ApiResponse(
        success=True,
        data=PatientRead.model_validate(patient),
        meta=Meta(request_id=request_id),
        error=None,
    )


@router.patch("/me", response_model=ApiResponse[PatientRead])
def update_my_profile(
    request: Request,
    payload: PatientUpdate,
    current_user: User = Depends(require_roles([UserRole.PATIENT])),
    db: Session = Depends(get_db),
):
    """Update safe profile fields for the authenticated patient."""
    request_id = get_request_id(request)
    patient_service = PatientService(db)
    
    patient = patient_service.update_my_profile(current_user, payload)
    
    return ApiResponse(
        success=True,
        data=PatientRead.model_validate(patient),
        meta=Meta(request_id=request_id),
        error=None,
    )
