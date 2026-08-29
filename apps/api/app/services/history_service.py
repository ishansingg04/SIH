import uuid
from typing import Any, Dict, List, Set
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import NotFoundException
from app.db.models.patient import Patient
from app.db.models.summary import Summary
from app.db.models.visit import Visit
from app.schemas.summary import PatientHistoryResponse
from app.services.base_service import BaseService


class HistoryService(BaseService):
    """Service for assembling patient longitudinal clinical history across visits."""

    def __init__(self, db: Session):
        super().__init__(db)

    def get_patient_history(self, patient_id: uuid.UUID) -> PatientHistoryResponse:
        """Assembles longitudinal clinical history preserving visit boundaries and deduplicating medications."""
        patient = self.db.get(Patient, patient_id)
        if not patient:
            raise NotFoundException(f"Patient with ID {patient_id} not found")

        # 1. Fetch all visits for this patient ordered chronologically (most recent first)
        stmt = (
            select(Visit)
            .where(Visit.patient_id == patient_id)
            .order_by(Visit.service_date.desc(), Visit.created_at.desc())
        )
        visits = list(self.db.scalars(stmt).all())

        visit_entries: List[Dict[str, Any]] = []
        medications_set: Set[str] = set()
        medications_list: List[Dict[str, Any]] = []
        conditions_set: Set[str] = set()
        conditions_list: List[Dict[str, Any]] = []
        ayush_history: List[Dict[str, Any]] = []
        continuity_labels: List[Dict[str, Any]] = []

        for v in visits:
            # Find latest summary for this visit
            summary_stmt = (
                select(Summary)
                .where(Summary.visit_id == v.id)
                .order_by(Summary.version.desc())
                .limit(1)
            )
            latest_summary = self.db.scalars(summary_stmt).first()
            summary_payload = latest_summary.payload_json if latest_summary else {}

            chief_complaint = (
                summary_payload.get("chief_complaint", {}).get("value")
                if isinstance(summary_payload.get("chief_complaint"), dict)
                else summary_payload.get("patient_reported", {}).get("chief_complaint", "General consultation")
            )

            # Record visit boundary
            visit_entries.append({
                "visit_id": str(v.id),
                "service_date": v.service_date.isoformat(),
                "intake_pathway": v.intake_pathway.value,
                "token": v.token,
                "status": v.status.value,
                "chief_complaint": chief_complaint,
                "summary_version": latest_summary.version if latest_summary else None,
                "summary_review_status": latest_summary.review_status.value if latest_summary else None,
            })

            # Extract medications from documents/summaries
            doc_facts = summary_payload.get("document_extracted", {})
            prescriptions = doc_facts.get("prior_prescriptions", [])
            for med in prescriptions:
                norm_med = str(med).strip()
                if norm_med and norm_med not in medications_set:
                    medications_set.add(norm_med)
                    medications_list.append({
                        "name": norm_med,
                        "first_recorded_visit_id": str(v.id),
                        "first_recorded_date": v.service_date.isoformat(),
                        "source": "document_extracted",
                    })

            # Extract conditions/symptoms
            pat_facts = summary_payload.get("patient_reported", {})
            symptoms = pat_facts.get("symptoms", [])
            for sym in symptoms:
                norm_sym = str(sym).strip()
                if norm_sym and norm_sym not in conditions_set:
                    conditions_set.add(norm_sym)
                    conditions_list.append({
                        "condition": norm_sym,
                        "recorded_date": v.service_date.isoformat(),
                        "visit_id": str(v.id),
                        "source": "patient_reported",
                    })

            # Extract AYUSH Dashavidha Pariksha snapshots
            if v.prakriti or v.vikriti or v.agni or v.koshtha or v.sattva or (latest_summary and latest_summary.payload_json.get("ayush_assessment")):
                ayush_assessment = latest_summary.payload_json.get("ayush_assessment") if latest_summary else {
                    "prakriti": v.prakriti,
                    "vikriti": v.vikriti,
                    "agni": v.agni,
                    "koshtha": v.koshtha,
                    "sattva": v.sattva,
                }
                ayush_history.append({
                    "visit_id": str(v.id),
                    "service_date": v.service_date.isoformat(),
                    "intake_pathway": v.intake_pathway.value,
                    "assessment": ayush_assessment,
                })

        # Add continuity inference notes
        if len(visits) > 1:
            continuity_labels.append({
                "label": "Multi-encounter history assembled",
                "continuity_status": "unconfirmed_inference",
                "note": "Prescriptions and symptom trends are grouped across encounters for clinical review.",
            })

        return PatientHistoryResponse(
            patient_id=patient.id,
            patient_name=patient.name,
            total_visits=len(visits),
            visits=visit_entries,
            medications=medications_list,
            conditions=conditions_list,
            ayush_history=ayush_history,
            continuity_labels=continuity_labels,
        )
