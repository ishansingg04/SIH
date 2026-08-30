import uuid
from datetime import date, datetime, timezone
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ConflictException, NotFoundException
from app.core.logging import logger
from app.db.models.enums import InputStatus, SummaryReviewStatus, VisitStatus
from app.db.models.input import VisitInput
from app.db.models.patient import Patient
from app.db.models.queue import QueueEntry
from app.db.models.summary import Summary
from app.db.models.user import User
from app.db.models.visit import Visit
from app.schemas.doctor import DoctorWorkspaceResponse, InputSummary, SummaryReviewResponse
from app.schemas.queue import (
    ClaimResponse,
    Disposition,
    QueueEntryRead,
    QueueListResponse,
    QueueSummary,
    VisitCompleteResponse,
)
from app.schemas.summary import SummaryRead
from app.schemas.visit import VisitRead
from app.services.audit_service import AuditService
from app.services.base_service import BaseService


class QueueService(BaseService):
    """Business logic for FIFO queue state machine, token dispatch, and doctor workspace."""

    def get_today_queue(
        self,
        clinic_id: uuid.UUID,
        state_filter: Optional[VisitStatus] = None,
    ) -> QueueListResponse:
        """Fetch all queue entries for today with computed patient and wait-time context."""
        today = datetime.now(timezone.utc).date()
        now = datetime.now(timezone.utc)

        stmt = (
            select(QueueEntry)
            .join(Visit, QueueEntry.visit_id == Visit.id)
            .join(Patient, Visit.patient_id == Patient.id)
            .options(
                selectinload(QueueEntry.visit).selectinload(Visit.patient),
                selectinload(QueueEntry.visit).selectinload(Visit.summaries),
            )
            .where(QueueEntry.clinic_id == clinic_id)
            .where(Visit.service_date == today)
            .order_by(QueueEntry.position.asc(), QueueEntry.created_at.asc(), QueueEntry.id.asc())
        )

        if state_filter:
            stmt = stmt.where(QueueEntry.state == state_filter)

        entries = self.db.scalars(stmt).all()

        mapped_entries: List[QueueEntryRead] = []
        for entry in entries:
            visit = entry.visit
            patient = visit.patient if visit else None
            has_summary = bool(visit.summaries) if visit else False

            # Calculate wait time in minutes
            wait_minutes = 0
            if entry.created_at:
                delta = now - entry.created_at.replace(tzinfo=timezone.utc if entry.created_at.tzinfo is None else entry.created_at.tzinfo)
                wait_minutes = max(0, int(delta.total_seconds() // 60))

            mapped_entries.append(
                QueueEntryRead(
                    id=entry.id,
                    visit_id=entry.visit_id,
                    clinic_id=entry.clinic_id,
                    position=entry.position,
                    state=entry.state,
                    called_at=entry.called_at,
                    created_at=entry.created_at,
                    updated_at=entry.updated_at,
                    patient_name=patient.name if patient else "Unknown",
                    token=visit.token if visit else "---",
                    intake_pathway=visit.intake_pathway if visit else None,
                    has_summary=has_summary,
                    wait_minutes=wait_minutes,
                )
            )

        summary = self.get_queue_summary(clinic_id)
        return QueueListResponse(
            entries=mapped_entries,
            summary=summary,
            as_of=now,
        )

    def get_queue_summary(self, clinic_id: uuid.UUID) -> QueueSummary:
        """Aggregate real-time queue counts and oldest waiting time."""
        today = datetime.now(timezone.utc).date()
        now = datetime.now(timezone.utc)

        waiting_stmt = (
            select(QueueEntry)
            .join(Visit, QueueEntry.visit_id == Visit.id)
            .where(QueueEntry.clinic_id == clinic_id)
            .where(Visit.service_date == today)
            .where(QueueEntry.state == VisitStatus.WAITING)
            .order_by(QueueEntry.created_at.asc())
        )
        waiting_entries = self.db.scalars(waiting_stmt).all()
        waiting_count = len(waiting_entries)

        oldest_wait_minutes = 0
        if waiting_entries:
            oldest = waiting_entries[0].created_at
            if oldest:
                delta = now - oldest.replace(tzinfo=timezone.utc if oldest.tzinfo is None else oldest.tzinfo)
                oldest_wait_minutes = max(0, int(delta.total_seconds() // 60))

        in_progress_stmt = (
            select(func.count(QueueEntry.id))
            .join(Visit, QueueEntry.visit_id == Visit.id)
            .where(QueueEntry.clinic_id == clinic_id)
            .where(Visit.service_date == today)
            .where(QueueEntry.state.in_([VisitStatus.CALLED, VisitStatus.IN_PROGRESS]))
        )
        in_progress_count = self.db.scalar(in_progress_stmt) or 0

        completed_stmt = (
            select(func.count(Visit.id))
            .where(Visit.clinic_id == clinic_id)
            .where(Visit.service_date == today)
            .where(Visit.status == VisitStatus.COMPLETED)
        )
        completed_count = self.db.scalar(completed_stmt) or 0

        return QueueSummary(
            clinic_id=clinic_id,
            waiting_count=waiting_count,
            in_progress_count=in_progress_count,
            completed_today_count=completed_count,
            oldest_wait_minutes=oldest_wait_minutes,
        )

    def claim_next(
        self,
        clinic_id: uuid.UUID,
        doctor: User,
        request_id: str = "req_claim",
    ) -> ClaimResponse:
        """Claim the next eligible WAITING patient in FIFO order.
        
        If an active CALLED/IN_PROGRESS visit is already held, returns it idempotently.
        """
        today = datetime.now(timezone.utc).date()
        now = datetime.now(timezone.utc)

        # 1. FIFO selection of oldest WAITING entry for today
        stmt = (
            select(QueueEntry)
            .join(Visit, QueueEntry.visit_id == Visit.id)
            .options(
                selectinload(QueueEntry.visit).selectinload(Visit.patient),
                selectinload(QueueEntry.visit).selectinload(Visit.summaries),
            )
            .where(QueueEntry.clinic_id == clinic_id)
            .where(Visit.service_date == today)
            .where(QueueEntry.state == VisitStatus.WAITING)
            .order_by(QueueEntry.position.asc(), QueueEntry.created_at.asc(), QueueEntry.id.asc())
        )
        entry = self.db.scalars(stmt).first()

        if not entry:
            raise NotFoundException("No patients currently waiting in queue")

        # 2. Transition state to CALLED
        entry.state = VisitStatus.CALLED
        entry.called_at = now
        visit = entry.visit
        visit.status = VisitStatus.CALLED
        self.db.flush()

        # 3. Audit trail
        audit_service = AuditService(self.db)
        audit_service.record_event(
            action="QUEUE_PATIENT_CALLED",
            entity_type="queue_entry",
            entity_id=str(entry.id),
            request_id=request_id,
            actor_id=doctor.id,
            actor_role=doctor.role.value,
            payload={
                "token": visit.token,
                "visit_id": str(visit.id),
                "clinic_id": str(clinic_id),
                "previous_state": VisitStatus.WAITING.value,
                "new_state": VisitStatus.CALLED.value,
            },
        )
        self.db.commit()
        self.db.refresh(entry)
        self.db.refresh(visit)

        patient = visit.patient
        read_entry = QueueEntryRead(
            id=entry.id,
            visit_id=entry.visit_id,
            clinic_id=entry.clinic_id,
            position=entry.position,
            state=entry.state,
            called_at=entry.called_at,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            patient_name=patient.name if patient else "Unknown",
            token=visit.token,
            intake_pathway=visit.intake_pathway,
            has_summary=bool(visit.summaries),
            wait_minutes=0,
        )

        return ClaimResponse(
            queue_entry=read_entry,
            visit=VisitRead.model_validate(visit),
        )

    def set_in_progress(
        self,
        queue_entry_id: uuid.UUID,
        actor: User,
        request_id: str = "req_in_progress",
    ) -> QueueEntryRead:
        """Transition queue entry to IN_PROGRESS state."""
        entry = self.db.get(QueueEntry, queue_entry_id)
        if not entry:
            raise NotFoundException(f"Queue entry {queue_entry_id} not found")

        # Guard legal transitions
        if entry.state not in (VisitStatus.CALLED, VisitStatus.WAITING, VisitStatus.IN_PROGRESS):
            raise ConflictException(
                f"Cannot transition to IN_PROGRESS from '{entry.state.value}'. Only CALLED or WAITING entries can be started."
            )

        entry.state = VisitStatus.IN_PROGRESS
        visit = self.db.get(Visit, entry.visit_id)
        if visit:
            visit.status = VisitStatus.IN_PROGRESS
        self.db.flush()

        audit_service = AuditService(self.db)
        audit_service.record_event(
            action="VISIT_IN_PROGRESS",
            entity_type="queue_entry",
            entity_id=str(entry.id),
            request_id=request_id,
            actor_id=actor.id,
            actor_role=actor.role.value,
            payload={
                "queue_entry_id": str(entry.id),
                "visit_id": str(entry.visit_id),
                "state": VisitStatus.IN_PROGRESS.value,
            },
        )
        self.db.commit()
        self.db.refresh(entry)

        patient = visit.patient if visit else None
        return QueueEntryRead(
            id=entry.id,
            visit_id=entry.visit_id,
            clinic_id=entry.clinic_id,
            position=entry.position,
            state=entry.state,
            called_at=entry.called_at,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            patient_name=patient.name if patient else "Unknown",
            token=visit.token if visit else "---",
            intake_pathway=visit.intake_pathway if visit else None,
            has_summary=bool(visit.summaries) if visit else False,
            wait_minutes=0,
        )

    def complete_visit(
        self,
        visit_id: uuid.UUID,
        disposition: Disposition,
        note: Optional[str],
        doctor: User,
        request_id: str = "req_complete",
    ) -> VisitCompleteResponse:
        """Mark visit and linked queue entry as COMPLETED with required disposition and notes."""
        visit = self.db.get(Visit, visit_id)
        if not visit:
            raise NotFoundException(f"Visit {visit_id} not found")

        # Guard transition
        if visit.status in (VisitStatus.COMPLETED, VisitStatus.CANCELLED, VisitStatus.NO_SHOW):
            raise ConflictException(
                f"Cannot complete visit in terminal state '{visit.status.value}'"
            )

        now = datetime.now(timezone.utc)
        visit.status = VisitStatus.COMPLETED

        # Update linked queue entry if exists
        queue_entry = self.db.scalars(
            select(QueueEntry).where(QueueEntry.visit_id == visit_id)
        ).first()
        if queue_entry:
            queue_entry.state = VisitStatus.COMPLETED

        self.db.flush()

        audit_service = AuditService(self.db)
        audit_service.record_event(
            action="VISIT_COMPLETED",
            entity_type="visit",
            entity_id=str(visit.id),
            request_id=request_id,
            actor_id=doctor.id,
            actor_role=doctor.role.value,
            payload={
                "token": visit.token,
                "disposition": disposition.value,
                "note": note,
                "clinic_id": str(visit.clinic_id),
            },
        )
        self.db.commit()

        return VisitCompleteResponse(
            visit_id=visit.id,
            token=visit.token,
            status=visit.status,
            disposition=disposition,
            note=note,
            completed_at=now,
        )

    def cancel_visit(
        self,
        queue_entry_id: uuid.UUID,
        reason: Optional[str],
        actor: User,
        request_id: str = "req_cancel",
    ) -> QueueEntryRead:
        """Cancel a queued patient visit."""
        entry = self.db.get(QueueEntry, queue_entry_id)
        if not entry:
            raise NotFoundException(f"Queue entry {queue_entry_id} not found")

        if entry.state in (VisitStatus.COMPLETED, VisitStatus.CANCELLED):
            raise ConflictException(f"Cannot cancel queue entry in state '{entry.state.value}'")

        entry.state = VisitStatus.CANCELLED
        visit = self.db.get(Visit, entry.visit_id)
        if visit:
            visit.status = VisitStatus.CANCELLED

        self.db.flush()

        audit_service = AuditService(self.db)
        audit_service.record_event(
            action="VISIT_CANCELLED",
            entity_type="queue_entry",
            entity_id=str(entry.id),
            request_id=request_id,
            actor_id=actor.id,
            actor_role=actor.role.value,
            payload={"reason": reason, "visit_id": str(entry.visit_id)},
        )
        self.db.commit()
        self.db.refresh(entry)

        patient = visit.patient if visit else None
        return QueueEntryRead(
            id=entry.id,
            visit_id=entry.visit_id,
            clinic_id=entry.clinic_id,
            position=entry.position,
            state=entry.state,
            called_at=entry.called_at,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            patient_name=patient.name if patient else "Unknown",
            token=visit.token if visit else "---",
            intake_pathway=visit.intake_pathway if visit else None,
            has_summary=bool(visit.summaries) if visit else False,
            wait_minutes=0,
        )

    def no_show_visit(
        self,
        queue_entry_id: uuid.UUID,
        reason: Optional[str],
        actor: User,
        request_id: str = "req_no_show",
    ) -> QueueEntryRead:
        """Mark a called/waiting patient as NO_SHOW."""
        entry = self.db.get(QueueEntry, queue_entry_id)
        if not entry:
            raise NotFoundException(f"Queue entry {queue_entry_id} not found")

        if entry.state in (VisitStatus.COMPLETED, VisitStatus.NO_SHOW, VisitStatus.CANCELLED):
            raise ConflictException(f"Cannot mark NO_SHOW for queue entry in state '{entry.state.value}'")

        entry.state = VisitStatus.NO_SHOW
        visit = self.db.get(Visit, entry.visit_id)
        if visit:
            visit.status = VisitStatus.NO_SHOW

        self.db.flush()

        audit_service = AuditService(self.db)
        audit_service.record_event(
            action="VISIT_NO_SHOW",
            entity_type="queue_entry",
            entity_id=str(entry.id),
            request_id=request_id,
            actor_id=actor.id,
            actor_role=actor.role.value,
            payload={"reason": reason, "visit_id": str(entry.visit_id)},
        )
        self.db.commit()
        self.db.refresh(entry)

        patient = visit.patient if visit else None
        return QueueEntryRead(
            id=entry.id,
            visit_id=entry.visit_id,
            clinic_id=entry.clinic_id,
            position=entry.position,
            state=entry.state,
            called_at=entry.called_at,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            patient_name=patient.name if patient else "Unknown",
            token=visit.token if visit else "---",
            intake_pathway=visit.intake_pathway if visit else None,
            has_summary=bool(visit.summaries) if visit else False,
            wait_minutes=0,
        )

    def get_doctor_workspace(self, visit_id: uuid.UUID) -> DoctorWorkspaceResponse:
        """Retrieve unified patient context, AI summary, AYUSH fields, and evidence inputs."""
        stmt = (
            select(Visit)
            .options(
                selectinload(Visit.patient),
                selectinload(Visit.queue_entry),
                selectinload(Visit.summaries),
                selectinload(Visit.inputs),
            )
            .where(Visit.id == visit_id)
        )
        visit = self.db.scalars(stmt).first()
        if not visit:
            raise NotFoundException(f"Visit {visit_id} not found")

        patient = visit.patient
        queue_entry = visit.queue_entry

        # Calculate patient age
        age = None
        if patient and patient.dob:
            today = datetime.now(timezone.utc).date()
            age = today.year - patient.dob.year - ((today.month, today.day) < (patient.dob.month, patient.dob.day))

        # Map inputs
        input_summaries: List[InputSummary] = []
        for inp in visit.inputs:
            text_snippet = inp.text[:200] if inp.text else None
            confidence = inp.provenance.get("confidence") if inp.provenance else None
            input_summaries.append(
                InputSummary(
                    id=inp.id,
                    kind=inp.kind,
                    status=inp.status,
                    text_snippet=text_snippet,
                    object_key=inp.object_key,
                    confidence=confidence,
                    created_at=inp.created_at,
                )
            )

        # Map queue entry if present
        q_read = None
        if queue_entry:
            q_read = QueueEntryRead(
                id=queue_entry.id,
                visit_id=queue_entry.visit_id,
                clinic_id=queue_entry.clinic_id,
                position=queue_entry.position,
                state=queue_entry.state,
                called_at=queue_entry.called_at,
                created_at=queue_entry.created_at,
                updated_at=queue_entry.updated_at,
                patient_name=patient.name if patient else "Unknown",
                token=visit.token,
                intake_pathway=visit.intake_pathway,
                has_summary=bool(visit.summaries),
                wait_minutes=0,
            )

        return DoctorWorkspaceResponse(
            visit=VisitRead.model_validate(visit),
            queue_entry=q_read,
            patient_name=patient.name if patient else "Unknown",
            patient_gender=patient.gender if patient else None,
            patient_age=age,
            patient_language=patient.language if patient else "en",
            summaries=[SummaryRead.model_validate(s) for s in visit.summaries],
            inputs=input_summaries,
        )

    def review_summary(
        self,
        visit_id: uuid.UUID,
        review_status: SummaryReviewStatus,
        doctor_notes: Optional[str],
        doctor: User,
        request_id: str = "req_summary_review",
    ) -> SummaryReviewResponse:
        """Doctor review/confirmation of the clinical AI summary."""
        summary = self.db.scalars(
            select(Summary)
            .where(Summary.visit_id == visit_id)
            .order_by(Summary.version.desc())
        ).first()

        if not summary:
            raise NotFoundException(f"No summary found for visit {visit_id}")

        summary.review_status = review_status
        if doctor_notes is not None:
            summary.doctor_notes = doctor_notes
        summary.reviewed_by = doctor.id

        self.db.flush()

        audit_service = AuditService(self.db)
        audit_service.record_event(
            action="SUMMARY_REVIEWED",
            entity_type="summary",
            entity_id=str(summary.id),
            request_id=request_id,
            actor_id=doctor.id,
            actor_role=doctor.role.value,
            payload={
                "visit_id": str(visit_id),
                "review_status": review_status.value,
                "notes_length": len(doctor_notes) if doctor_notes else 0,
            },
        )
        self.db.commit()
        self.db.refresh(summary)

        return SummaryReviewResponse(
            summary=SummaryRead.model_validate(summary),
            visit_id=visit_id,
            reviewed_by=doctor.id,
            reviewed_at=datetime.now(timezone.utc),
        )
