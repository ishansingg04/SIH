import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from app.api.dependencies import (
    get_current_active_user_optional,
    get_current_user,
    get_db,
    get_request_id,
    require_roles,
)
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.schemas.common import ApiResponse, Meta
from app.schemas.summary import (
    PatientHistoryResponse,
    SummaryDetailResponse,
    SummaryGenerateRequest,
    SummaryRead,
    SummaryReviewRequest,
)
from app.services.history_service import HistoryService
from app.services.summary_service import SummaryService

from sqlalchemy import select
from app.db.models.patient import Patient
from app.db.models.visit import Visit

router = APIRouter(tags=["AI Clinical Summary & Patient History"])


@router.get("/summaries/demo/active-context")
def get_demo_active_context(
    request: Request,
    db: Session = Depends(get_db),
):
    """Convenience endpoint for testing console to fetch active seed visit, patient and inputs."""
    request_id = get_request_id(request)
    visit = db.scalars(select(Visit).order_by(Visit.created_at.desc())).first()
    patient = db.scalars(select(Patient).order_by(Patient.created_at.asc())).first()

    evidence_items = []
    if visit:
        for inp in visit.inputs:
            evidence_items.append({
                "kind": inp.kind.value,
                "text": inp.text,
                "provenance": inp.provenance,
            })

    return ApiResponse(
        success=True,
        data={
            "visit_id": str(visit.id) if visit else None,
            "patient_id": str(patient.id) if patient else (str(visit.patient_id) if visit else None),
            "patient_name": patient.name if patient else "Asha Devi",
            "token": visit.token if visit else "A12",
            "intake_pathway": visit.intake_pathway.value if visit else "AYUSH",
            "service_date": visit.service_date.isoformat() if visit else None,
            "ayush_intake": {
                "prakriti": visit.prakriti if visit else None,
                "vikriti": visit.vikriti if visit else None,
                "agni": visit.agni if visit else None,
                "koshtha": visit.koshtha if visit else None,
                "sattva": visit.sattva if visit else None,
                "ayush_notes": visit.ayush_notes if visit else None,
            } if visit else {},
            "evidence": evidence_items,
        },
        meta=Meta(request_id=request_id),
        error=None,
    )


@router.post("/visits/{visit_id}/summary", response_model=ApiResponse[SummaryRead])
async def generate_or_get_visit_summary(
    visit_id: uuid.UUID,
    request: Request,
    payload: SummaryGenerateRequest = SummaryGenerateRequest(),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """Generate a structured, evidence-linked clinical AI summary for a visit or retrieve cached draft."""
    request_id = get_request_id(request)
    service = SummaryService(db)

    summary = await service.generate_summary(
        visit_id=visit_id,
        force_refresh=payload.force_refresh,
        actor_id=current_user.id if current_user else None,
        request_id=request_id,
    )

    return ApiResponse(
        success=True,
        data=SummaryRead.model_validate(summary),
        meta=Meta(request_id=request_id),
        error=None,
    )


@router.get("/visits/{visit_id}/summary", response_model=ApiResponse[SummaryDetailResponse])
def get_visit_summary(
    visit_id: uuid.UUID,
    request: Request,
    version: Optional[int] = Query(default=None, description="Optional specific version number"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """Retrieve the latest or specific version of the clinical AI summary for a visit."""
    request_id = get_request_id(request)
    service = SummaryService(db)

    summary = service.get_summary_by_visit(visit_id=visit_id, version=version)

    # Flatten structured facts and flags for UI convenience
    payload = summary.payload_json or {}
    facts = []
    if "patient_reported" in payload and isinstance(payload["patient_reported"], dict):
        for k, v in payload["patient_reported"].items():
            facts.append({"key": f"patient_{k}", "value": v, "category": "patient_reported"})
    if "document_extracted" in payload and isinstance(payload["document_extracted"], dict):
        for k, v in payload["document_extracted"].items():
            facts.append({"key": f"doc_{k}", "value": v, "category": "document_extracted"})
    if "ayush_assessment" in payload and isinstance(payload["ayush_assessment"], dict):
        for k, v in payload["ayush_assessment"].items():
            facts.append({"key": f"ayush_{k}", "value": v, "category": "ayush_assessment"})

    flags = payload.get("red_flags_for_doctor_review", [])

    detail = SummaryDetailResponse(
        status="READY",
        version=summary.version,
        summary_id=summary.id,
        visit_id=summary.visit_id,
        review_status=summary.review_status,
        confidence=summary.confidence,
        payload=payload,
        facts=facts,
        flags=flags,
        reviewed_by=summary.reviewed_by,
        doctor_notes=summary.doctor_notes,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
    )

    return ApiResponse(
        success=True,
        data=detail,
        meta=Meta(request_id=request_id),
        error=None,
    )


@router.post("/summaries/{summary_id}/review", response_model=ApiResponse[SummaryRead])
def review_clinical_summary(
    summary_id: uuid.UUID,
    payload: SummaryReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR, UserRole.CLINIC_ADMIN])),
):
    """Doctor review endpoint: approve, reject, or edit an AI-generated clinical summary."""
    request_id = get_request_id(request)
    service = SummaryService(db)

    reviewed_summary = service.review_summary(
        summary_id=summary_id,
        decision=payload.decision,
        edits=payload.edits,
        doctor_notes=payload.doctor_notes,
        doctor_id=current_user.id,
        request_id=request_id,
    )

    return ApiResponse(
        success=True,
        data=SummaryRead.model_validate(reviewed_summary),
        meta=Meta(request_id=request_id),
        error=None,
    )


@router.get("/patients/{patient_id}/history", response_model=ApiResponse[PatientHistoryResponse])
def get_patient_clinical_history(
    patient_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR, UserRole.CLINIC_ADMIN, UserRole.RECEPTIONIST])),
):
    """Retrieve chronological longitudinal patient clinical history across prior encounters."""
    request_id = get_request_id(request)
    service = HistoryService(db)

    history = service.get_patient_history(patient_id=patient_id)

    return ApiResponse(
        success=True,
        data=history,
        meta=Meta(request_id=request_id),
        error=None,
    )
