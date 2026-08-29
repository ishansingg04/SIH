import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.core.logging import logger
from app.db.models.enums import InputKind, InputStatus, SummaryReviewStatus
from app.db.models.summary import Summary
from app.db.models.visit import Visit
from app.integrations.summary import EvidencePacket, SummaryProvider, get_summary_adapter
from app.repositories.summary_repository import SummaryRepository
from app.schemas.summary import SummaryReviewDecision
from app.services.audit_service import AuditService
from app.services.base_service import BaseService


class SummaryService(BaseService):
    """Domain service managing clinical summarization, provider integration, and doctor review workflows."""

    def __init__(self, db: Session, provider: Optional[SummaryProvider] = None):
        super().__init__(db)
        self.repository = SummaryRepository(db)
        self.provider = provider or get_summary_adapter()
        self.audit_service = AuditService(db)

    async def generate_summary(
        self,
        visit_id: uuid.UUID,
        force_refresh: bool = False,
        actor_id: Optional[uuid.UUID] = None,
        request_id: str = "req_unknown",
    ) -> Summary:
        """Generate or retrieve a structured, evidence-linked clinical summary for a visit."""
        visit = self.db.get(Visit, visit_id)
        if not visit:
            raise NotFoundException(f"Visit with ID {visit_id} not found")

        # Invariant: Patient consent must be recorded before clinical processing
        if not visit.consent_at:
            raise ForbiddenException("Patient consent required before clinical processing")

        # Check for existing summary if force_refresh is not requested
        if not force_refresh:
            existing = self.repository.get_latest_by_visit_id(visit_id)
            if existing:
                logger.info(f"Returning existing summary version {existing.version} for visit {visit_id}")
                return existing

        # 1. Collect audio transcripts & text inputs
        transcripts: List[str] = []
        document_texts: List[str] = []

        for inp in visit.inputs:
            if inp.is_deleted:
                continue
            if inp.kind in (InputKind.AUDIO, InputKind.TEXT) and inp.text:
                transcripts.append(inp.text)
            elif inp.kind in (InputKind.IMAGE, InputKind.PDF) and inp.text:
                document_texts.append(inp.text)

        # 2. Collect AYUSH Dashavidha Pariksha inputs
        ayush_intake = None
        if visit.prakriti or visit.vikriti or visit.agni or visit.koshtha or visit.sattva or visit.ayush_notes:
            ayush_intake = {
                "prakriti": visit.prakriti,
                "vikriti": visit.vikriti,
                "agni": visit.agni,
                "koshtha": visit.koshtha,
                "sattva": visit.sattva,
                "ayush_notes": visit.ayush_notes,
            }

        # 3. Assemble EvidencePacket
        evidence = EvidencePacket(
            visit_id=str(visit_id),
            transcripts=transcripts,
            document_texts=document_texts,
            ayush_intake=ayush_intake,
        )

        # 4. Invoke Provider Adapter (Mock / Groq / OpenAI)
        try:
            result = await self.provider.summarize(evidence)
        except Exception as exc:
            logger.error(f"AI summarization provider error for visit {visit_id}: {exc}")
            raise ValidationException(f"Summarization provider failed: {str(exc)}")

        # 5. Build structured payload
        payload_data = {
            "chief_complaint": result.chief_complaint,
            "patient_reported": result.patient_reported,
            "document_extracted": result.document_extracted,
            "ayush_assessment": result.ayush_assessment,
            "model_suggestions": result.model_suggestions,
            "uncertainty_labels": result.uncertainty_labels,
            "red_flags_for_doctor_review": result.red_flags_for_doctor_review,
            "unknowns": result.unknowns,
        }

        # 6. Calculate next monotonic version
        next_version = self.repository.get_next_version(visit_id)

        summary = Summary(
            visit_id=visit_id,
            version=next_version,
            payload_json=payload_data,
            confidence=result.confidence,
            review_status=SummaryReviewStatus.DRAFT,
        )

        self.db.add(summary)
        self.db.flush()

        # 7. Audit event logging
        self.audit_service.record_event(
            action="SUMMARY_GENERATED",
            entity_type="summary",
            entity_id=str(summary.id),
            request_id=request_id,
            actor_id=actor_id,
            actor_role="system_ai",
            payload={
                "visit_id": str(visit_id),
                "version": next_version,
                "provider": result.provider,
                "confidence": result.confidence,
            },
        )

        self.db.commit()
        self.db.refresh(summary)
        return summary

    def get_summary_by_visit(self, visit_id: uuid.UUID, version: Optional[int] = None) -> Summary:
        """Retrieve the latest or specific version of a summary."""
        visit = self.db.get(Visit, visit_id)
        if not visit:
            raise NotFoundException(f"Visit with ID {visit_id} not found")

        if version:
            summary = self.repository.get_by_visit_and_version(visit_id, version)
            if not summary:
                raise NotFoundException(f"Summary version {version} not found for visit {visit_id}")
            return summary

        summary = self.repository.get_latest_by_visit_id(visit_id)
        if not summary:
            raise NotFoundException(f"No summary found for visit {visit_id}. Generate a summary first.")
        return summary

    def review_summary(
        self,
        summary_id: uuid.UUID,
        decision: SummaryReviewDecision,
        edits: Optional[Dict[str, Any]] = None,
        doctor_notes: Optional[str] = None,
        doctor_id: Optional[uuid.UUID] = None,
        request_id: str = "req_unknown",
    ) -> Summary:
        """Process doctor review: approve, reject, or edit the AI-generated summary."""
        summary = self.repository.get_by_id(summary_id)
        if not summary:
            raise NotFoundException(f"Summary with ID {summary_id} not found")

        if decision == SummaryReviewDecision.APPROVE:
            summary.review_status = SummaryReviewStatus.CONFIRMED
        elif decision == SummaryReviewDecision.REJECT:
            summary.review_status = SummaryReviewStatus.REJECTED
        elif decision == SummaryReviewDecision.EDIT:
            summary.review_status = SummaryReviewStatus.EDITED
            if edits:
                # Merge doctor edits into payload_json
                current_payload = dict(summary.payload_json)
                for key, val in edits.items():
                    current_payload[key] = val
                summary.payload_json = current_payload

        summary.reviewed_by = doctor_id
        if doctor_notes is not None:
            summary.doctor_notes = doctor_notes

        self.db.flush()

        # Audit logging
        self.audit_service.record_event(
            action="SUMMARY_REVIEWED",
            entity_type="summary",
            entity_id=str(summary.id),
            request_id=request_id,
            actor_id=doctor_id,
            actor_role="doctor",
            payload={
                "visit_id": str(summary.visit_id),
                "version": summary.version,
                "decision": decision.value,
                "new_status": summary.review_status.value,
                "has_edits": bool(edits),
            },
        )

        self.db.commit()
        self.db.refresh(summary)
        return summary
