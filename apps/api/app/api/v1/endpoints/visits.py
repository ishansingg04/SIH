import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.dependencies import (
    get_current_active_user_optional,
    get_db,
    get_request_id,
)
from app.core.exceptions import NotFoundException
from app.db.models.clinic import Clinic
from app.db.models.enums import IntakePathway, VisitStatus
from app.db.models.patient import Patient
from app.db.models.queue import QueueEntry
from app.db.models.user import User
from app.db.models.visit import Visit
from app.schemas.common import ApiResponse, Meta
from app.schemas.visit import VisitCreate, VisitRead
from app.services.audit_service import AuditService

router = APIRouter(prefix="/visits", tags=["Visits & AYUSH Intake Foundation"])


def generate_clinic_token(clinic: Clinic, db: Session) -> str:
    """Generate clinic-scoped daily sequential token (e.g., A12)."""
    today = datetime.now(timezone.utc).date()
    prefix = clinic.queue_policy.get("prefix", "A") if clinic.queue_policy else "A"

    stmt = (
        select(func.count(Visit.id))
        .where(Visit.clinic_id == clinic.id)
        .where(Visit.service_date == today)
    )
    count = db.scalar(stmt) or 0
    return f"{prefix}{count + 1:02d}"


@router.post("", response_model=ApiResponse[VisitRead])
def create_visit(
    request: Request,
    payload: VisitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_optional),
):
    """Create a new clinical visit, issuing token and recording AYUSH/Allopathic intake."""
    request_id = get_request_id(request)

    clinic = db.get(Clinic, payload.clinic_id)
    if not clinic:
        raise NotFoundException("Clinic not found")

    patient = db.get(Patient, payload.patient_id)
    if not patient:
        raise NotFoundException("Patient not found")

    token = generate_clinic_token(clinic, db)
    now = datetime.now(timezone.utc)

    # Build visit instance with AYUSH Dashavidha Pariksha structured payload if present
    visit = Visit(
        patient_id=payload.patient_id,
        clinic_id=payload.clinic_id,
        status=VisitStatus.WAITING,
        intake_pathway=payload.intake_pathway,
        token=token,
        service_date=now.date(),
        consent_at=now if payload.consent_given else None,
        consent_language=payload.consent_language,
        created_by=current_user.id if current_user else None,
        prakriti=payload.prakriti.model_dump() if payload.prakriti else None,
        vikriti=payload.vikriti.model_dump() if payload.vikriti else None,
        agni=payload.agni.model_dump() if payload.agni else None,
        koshtha=payload.koshtha.model_dump() if payload.koshtha else None,
        sattva=payload.sattva.model_dump() if payload.sattva else None,
        ayush_notes=payload.ayush_notes,
    )
    db.add(visit)
    db.flush()

    # Calculate queue position
    waiting_stmt = (
        select(func.count(QueueEntry.id))
        .where(QueueEntry.clinic_id == payload.clinic_id)
        .where(QueueEntry.state == VisitStatus.WAITING)
    )
    waiting_count = db.scalar(waiting_stmt) or 0

    queue_entry = QueueEntry(
        visit_id=visit.id,
        clinic_id=payload.clinic_id,
        position=waiting_count + 1,
        state=VisitStatus.WAITING,
    )
    db.add(queue_entry)
    db.flush()

    # Audit logging
    audit_service = AuditService(db)
    audit_service.record_event(
        action="VISIT_CREATED",
        entity_type="visit",
        entity_id=str(visit.id),
        request_id=request_id,
        actor_id=current_user.id if current_user else None,
        actor_role=current_user.role.value if current_user else "patient_kiosk",
        payload={
            "token": token,
            "intake_pathway": payload.intake_pathway.value,
            "clinic_id": str(payload.clinic_id),
            "patient_id": str(payload.patient_id),
        },
    )

    db.commit()
    db.refresh(visit)

    return ApiResponse(
        success=True,
        data=VisitRead.model_validate(visit),
        meta=Meta(request_id=request_id),
        error=None,
    )


@router.get("/{visit_id}", response_model=ApiResponse[VisitRead])
def get_visit_details(
    visit_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    """Retrieve visit details including AYUSH Dashavidha Pariksha findings."""
    request_id = get_request_id(request)
    visit = db.get(Visit, visit_id)
    if not visit:
        raise NotFoundException(f"Visit with ID {visit_id} not found")

    return ApiResponse(
        success=True,
        data=VisitRead.model_validate(visit),
        meta=Meta(request_id=request_id),
        error=None,
    )
