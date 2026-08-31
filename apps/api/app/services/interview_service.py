"""Interview Service orchestrating conversational turns, speech transcription,
slot filling, multi-lingual questions, fact updates, and clinical briefing sync.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    ValidationException,
)

from app.core.logging import logger
from app.core.questions import (
    QUESTION_BY_ID,
    InterviewQuestion,
    QuestionInputType,
    SlotType,
    get_default_slots_for_pathway,
    get_next_question,
    get_question_by_id,
)
from app.db.models.audit import AuditEvent
from app.db.models.enums import InputKind, InputStatus, UserRole
from app.db.models.input import VisitInput
from app.db.models.interview import PatientInterview
from app.db.models.user import User
from app.db.models.visit import Visit
from app.integrations.interview_llm import (
    ExtractionPacket,
    get_interview_llm_adapter,
)
from app.integrations.speech import get_speech_adapter
from app.repositories.interview_repository import InterviewRepository
from app.schemas.interview import (
    ExtractedFactItem,
    FactUpdateRequest,
    InterviewCompleteResponse,
    InterviewStartRequest,
    InterviewStateResponse,
    InterviewTurnItem,
    InterviewTurnRequest,
    InterviewTurnResponse,
    NextQuestionSchema,
)


from app.services.audit_service import AuditService


class InterviewService:
    def __init__(self, db: Session):
        self.db = db
        self.interview_repo = InterviewRepository(db)
        self.audit_service = AuditService(db)


    async def start_interview(
        self,
        visit_id: uuid.UUID,
        payload: InterviewStartRequest,
        audio_bytes: Optional[bytes] = None,
        filename: str = "initial_speech.webm",
        current_user: Optional[User] = None,
    ) -> InterviewTurnResponse:
        """Initialize or resume an adaptive patient interview session."""
        visit = self.db.get(Visit, visit_id)

        if not visit:
            raise NotFoundException(
f"Visit with ID {visit_id} does not exist.")

        if not visit.consent_at:
            raise ForbiddenException(
                "Patient consent is required before initiating an AI interview."
            )


        pathway = (payload.pathway or (visit.intake_pathway.value if visit.intake_pathway else "ALLOPATHIC")).upper()
        language = payload.language or visit.consent_language or "en"
        max_q = payload.max_questions or 6

        # Transcribe audio if provided
        initial_text = payload.initial_text or ""
        transcript_text = None
        if audio_bytes and len(audio_bytes) > 0:
            speech_adapter = get_speech_adapter()
            transcript_res = await speech_adapter.transcribe(
                audio_bytes=audio_bytes,
                language=language,
                filename=filename,
            )
            initial_text = transcript_res.text
            transcript_text = transcript_res.text

            # Save initial audio as a visit input for provenance
            v_input = VisitInput(
                visit_id=visit_id,
                kind=InputKind.AUDIO,
                text=transcript_res.text,
                status=InputStatus.COMPLETED,
                provenance={
                    "source": "patient_voice_intake",
                    "language": language,
                    "provider": transcript_res.provider,
                },
            )
            self.db.add(v_input)

        # Check existing interview
        interview = self.interview_repo.get_by_visit_id(visit_id)
        default_slots = [s.value for s in get_default_slots_for_pathway(pathway)]

        if not interview:
            interview = PatientInterview(
                visit_id=visit_id,
                status="IN_PROGRESS",
                language=language,
                pathway=pathway,
                turns=[],
                extracted_facts=[],
                missing_slots=default_slots,
                answered_questions=[],
                red_flags=[],
                question_count=0,
                max_questions=max_q,
            )
            self.db.add(interview)
            self.db.flush()
        else:
            interview.language = language
            interview.pathway = pathway
            interview.max_questions = max_q
            # If interview was finished, reset it to allow fresh intake
            if interview.status == "COMPLETED" or not interview.missing_slots or (payload.initial_text or audio_bytes):
                interview.status = "IN_PROGRESS"
                interview.turns = []
                interview.extracted_facts = []
                interview.missing_slots = default_slots
                interview.answered_questions = []
                interview.red_flags = []
                interview.question_count = 0


        extracted_facts_objs: List[ExtractedFactItem] = [
            ExtractedFactItem(**f) if isinstance(f, dict) else f
            for f in (interview.extracted_facts or [])
        ]
        red_flags_list = list(interview.red_flags or [])
        missing_slots_list = list(interview.missing_slots or default_slots)
        answered_q_list = list(interview.answered_questions or [])

        # Process initial utterance if present
        if initial_text.strip():
            llm_adapter = get_interview_llm_adapter()
            packet = ExtractionPacket(
                patient_utterance=initial_text,
                language=language,
                pathway=pathway,
                current_slot=SlotType.CHIEF_COMPLAINT.value,
                existing_facts=[f.model_dump() for f in extracted_facts_objs],
                missing_slots=missing_slots_list,
            )
            extraction_res = await llm_adapter.extract_facts(packet)

            for fact in extraction_res.extracted_facts:
                extracted_facts_objs.append(fact)

            for filled in extraction_res.filled_slots:
                if filled in missing_slots_list:
                    missing_slots_list.remove(filled)

            if extraction_res.red_flags:
                red_flags_list.extend(extraction_res.red_flags)

            answered_q_list.append("q_chief_complaint")

            turn_record = {
                "turn_index": 1,
                "question_id": "q_chief_complaint",
                "question_text": "Initial Problem Statement",
                "answer_text": initial_text,
                "transcript": transcript_text,
                "input_source": "voice" if audio_bytes else "text",
                "skipped": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            interview.turns = list(interview.turns or []) + [turn_record]
            interview.question_count = (interview.question_count or 0) + 1

        # Select next question
        next_q_obj = get_next_question(
            missing_slots=missing_slots_list,
            answered_question_ids=answered_q_list,
            pathway=pathway,
            language=language,
        )

        is_complete = False
        if not next_q_obj or interview.question_count >= interview.max_questions:
            is_complete = True
            interview.status = "COMPLETED"
            interview.current_question_id = None
        else:
            interview.current_question_id = next_q_obj.id

        interview.extracted_facts = [f.model_dump() for f in extracted_facts_objs]
        interview.missing_slots = missing_slots_list
        interview.answered_questions = answered_q_list
        interview.red_flags = red_flags_list

        # Audit event
        actor_id = current_user.id if current_user else None
        self.audit_service.record_event(
            action="INTERVIEW_STARTED",
            entity_type="patient_interview",
            entity_id=str(interview.id),
            request_id="req_interview_start",
            actor_id=actor_id,
            actor_role=current_user.role.value if current_user else "patient",
            payload={
                "visit_id": str(visit_id),
                "language": language,
                "pathway": pathway,
                "facts_count": len(extracted_facts_objs),
            },
        )
        self.db.commit()
        self.db.refresh(interview)


        next_q_schema = None
        if next_q_obj and not is_complete:
            next_q_schema = NextQuestionSchema(
                id=next_q_obj.id,
                slot=next_q_obj.slot.value,
                text=next_q_obj.get_text(language),
                input_type=next_q_obj.input_type,
                required=next_q_obj.required,
                options=next_q_obj.get_options(language),
            )

        return InterviewTurnResponse(
            next_question=next_q_schema,
            extracted_facts=extracted_facts_objs,
            missing_slots=missing_slots_list,
            interview_complete=is_complete,
            red_flags=red_flags_list,
            turn_number=interview.question_count + 1,
            max_questions=interview.max_questions,
            transcript=transcript_text,
        )

    async def process_turn(
        self,
        visit_id: uuid.UUID,
        payload: InterviewTurnRequest,
        audio_bytes: Optional[bytes] = None,
        filename: str = "answer.webm",
        current_user: Optional[User] = None,
    ) -> InterviewTurnResponse:
        """Process an answer to the current question and generate the next turn."""
        visit = self.db.get(Visit, visit_id)

        if not visit:
            raise NotFoundException(
f"Visit with ID {visit_id} does not exist.")

        interview = self.interview_repo.get_by_visit_id(visit_id)
        if not interview:
            raise NotFoundException(
f"No active interview found for visit {visit_id}. Start one first.")

        if interview.status == "COMPLETED":
            return await self._build_turn_response(interview, is_complete=True)

        language = payload.language or interview.language or "en"
        q_id = payload.question_id or interview.current_question_id
        q_def: Optional[InterviewQuestion] = get_question_by_id(q_id) if q_id else None
        slot_name = q_def.slot.value if q_def else "general_notes"

        answered_list = list(interview.answered_questions or [])
        if q_id and q_id not in answered_list:
            answered_list.append(q_id)

        missing_slots = list(interview.missing_slots or [])
        extracted_facts: List[ExtractedFactItem] = [
            ExtractedFactItem(**f) if isinstance(f, dict) else f
            for f in (interview.extracted_facts or [])
        ]
        red_flags_list = list(interview.red_flags or [])
        transcript_text = None

        if payload.skipped:
            logger.info(f"Question {q_id} skipped by patient.")
            turn_record = {
                "turn_index": len(interview.turns or []) + 1,
                "question_id": q_id or "unknown",
                "question_text": q_def.get_text(language) if q_def else "Skipped question",
                "answer_text": None,
                "transcript": None,
                "input_source": "text",
                "skipped": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            interview.turns = list(interview.turns or []) + [turn_record]
            if slot_name in missing_slots:
                missing_slots.remove(slot_name)

        else:
            answer_text = payload.answer_text or ""
            if audio_bytes and len(audio_bytes) > 0:
                speech_adapter = get_speech_adapter()
                t_res = await speech_adapter.transcribe(
                    audio_bytes=audio_bytes,
                    language=language,
                    filename=filename,
                )
                answer_text = t_res.text
                transcript_text = t_res.text

                # Store audio input
                v_input = VisitInput(
                    visit_id=visit_id,
                    kind=InputKind.AUDIO,
                    text=t_res.text,
                    status=InputStatus.COMPLETED,
                    provenance={
                        "source": f"interview_turn_{len(interview.turns or []) + 1}",
                        "question_id": q_id,
                        "language": language,
                    },
                )
                self.db.add(v_input)

            if answer_text.strip():
                llm_adapter = get_interview_llm_adapter()
                packet = ExtractionPacket(
                    patient_utterance=answer_text,
                    language=language,
                    pathway=interview.pathway,
                    current_slot=slot_name,
                    existing_facts=[f.model_dump() for f in extracted_facts],
                    missing_slots=missing_slots,
                )
                extraction_res = await llm_adapter.extract_facts(packet)

                for fact in extraction_res.extracted_facts:
                    extracted_facts.append(fact)

                for filled in extraction_res.filled_slots:
                    if filled in missing_slots:
                        missing_slots.remove(filled)

                if extraction_res.red_flags:
                    red_flags_list.extend(extraction_res.red_flags)

            turn_record = {
                "turn_index": len(interview.turns or []) + 1,
                "question_id": q_id or "unknown",
                "question_text": q_def.get_text(language) if q_def else "Question",
                "answer_text": answer_text,
                "transcript": transcript_text,
                "input_source": "voice" if audio_bytes else "text",
                "skipped": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            interview.turns = list(interview.turns or []) + [turn_record]

        interview.question_count = (interview.question_count or 0) + 1
        interview.extracted_facts = [f.model_dump() for f in extracted_facts]
        interview.missing_slots = missing_slots
        interview.answered_questions = answered_list
        interview.red_flags = red_flags_list

        # Pick next question
        next_q_obj = get_next_question(
            missing_slots=missing_slots,
            answered_question_ids=answered_list,
            pathway=interview.pathway,
            language=language,
        )

        is_complete = False
        if not next_q_obj or interview.question_count >= interview.max_questions or len(missing_slots) == 0:
            is_complete = True
            interview.status = "COMPLETED"
            interview.current_question_id = None
        else:
            interview.current_question_id = next_q_obj.id

        actor_id = current_user.id if current_user else None
        self.audit_service.record_event(
            action="INTERVIEW_TURN_COMPLETED",
            entity_type="patient_interview",
            entity_id=str(interview.id),
            request_id="req_interview_turn",
            actor_id=actor_id,
            actor_role=current_user.role.value if current_user else "patient",
            payload={
                "turn_index": len(interview.turns),
                "question_id": q_id,
                "skipped": payload.skipped,
                "is_complete": is_complete,
            },
        )
        self.db.commit()
        self.db.refresh(interview)


        next_q_schema = None
        if next_q_obj and not is_complete:
            next_q_schema = NextQuestionSchema(
                id=next_q_obj.id,
                slot=next_q_obj.slot.value,
                text=next_q_obj.get_text(language),
                input_type=next_q_obj.input_type,
                required=next_q_obj.required,
                options=next_q_obj.get_options(language),
            )

        return InterviewTurnResponse(
            next_question=next_q_schema,
            extracted_facts=extracted_facts,
            missing_slots=missing_slots,
            interview_complete=is_complete,
            red_flags=red_flags_list,
            turn_number=interview.question_count + 1,
            max_questions=interview.max_questions,
            transcript=transcript_text,
        )

    def get_interview_state(
        self,
        visit_id: uuid.UUID,
        current_user: Optional[User] = None,
    ) -> InterviewStateResponse:
        """Retrieve full persistent interview state."""
        visit = self.db.get(Visit, visit_id)

        if not visit:
            raise NotFoundException(
f"Visit with ID {visit_id} does not exist.")

        interview = self.interview_repo.get_by_visit_id(visit_id)
        if not interview:
            raise NotFoundException(
f"No interview found for visit {visit_id}.")

        extracted_facts = [
            ExtractedFactItem(**f) if isinstance(f, dict) else f
            for f in (interview.extracted_facts or [])
        ]
        turns = [
            InterviewTurnItem(**t) if isinstance(t, dict) else t
            for t in (interview.turns or [])
        ]

        next_q_schema = None
        if interview.current_question_id and interview.status != "COMPLETED":
            q_def = get_question_by_id(interview.current_question_id)
            if q_def:
                next_q_schema = NextQuestionSchema(
                    id=q_def.id,
                    slot=q_def.slot.value,
                    text=q_def.get_text(interview.language),
                    input_type=q_def.input_type,
                    required=q_def.required,
                    options=q_def.get_options(interview.language),
                )

        turns_completed = len(turns)
        max_q = interview.max_questions or 6
        progress = min(100, int((turns_completed / max(max_q, 1)) * 100))

        return InterviewStateResponse(
            visit_id=str(visit_id),
            status=interview.status,
            language=interview.language,
            pathway=interview.pathway,
            current_question=next_q_schema,
            answered_questions=list(interview.answered_questions or []),
            turns=turns,
            extracted_facts=extracted_facts,
            missing_slots=list(interview.missing_slots or []),
            red_flags=list(interview.red_flags or []),
            progress_percentage=progress,
            turns_completed=turns_completed,
            max_questions=max_q,
            is_complete=(interview.status == "COMPLETED"),
        )

    def update_fact(
        self,
        visit_id: uuid.UUID,
        fact_id: str,
        payload: FactUpdateRequest,
        current_user: Optional[User] = None,
    ) -> ExtractedFactItem:
        """Update or correct an extracted clinical fact value."""
        interview = self.interview_repo.get_by_visit_id(visit_id)
        if not interview:
            raise NotFoundException(
f"No interview found for visit {visit_id}.")

        facts = list(interview.extracted_facts or [])
        updated_fact = None
        for f in facts:
            if f.get("id") == fact_id:
                f["value"] = payload.value
                f["verified"] = payload.verified
                updated_fact = ExtractedFactItem(**f)
                break

        if not updated_fact:
            raise NotFoundException(
f"Fact with ID '{fact_id}' not found in interview.")

        interview.extracted_facts = facts
        self.db.commit()
        return updated_fact

    def delete_fact(
        self,
        visit_id: uuid.UUID,
        fact_id: str,
        current_user: Optional[User] = None,
    ) -> Dict[str, Any]:
        """Delete an incorrectly extracted fact chip."""
        interview = self.interview_repo.get_by_visit_id(visit_id)
        if not interview:
            raise NotFoundException(
f"No interview found for visit {visit_id}.")

        facts = list(interview.extracted_facts or [])
        initial_len = len(facts)
        facts = [f for f in facts if f.get("id") != fact_id]

        if len(facts) == initial_len:
            raise NotFoundException(
f"Fact with ID '{fact_id}' not found in interview.")

        interview.extracted_facts = facts
        self.db.commit()
        return {"deleted": True, "fact_id": fact_id, "remaining_facts_count": len(facts)}

    async def complete_interview(
        self,
        visit_id: uuid.UUID,
        current_user: Optional[User] = None,
    ) -> InterviewCompleteResponse:
        """Complete the interview, compile verified facts, and sync with downstream AI summary."""
        visit = self.db.get(Visit, visit_id)

        if not visit:
            raise NotFoundException(
f"Visit with ID {visit_id} does not exist.")

        interview = self.interview_repo.get_by_visit_id(visit_id)
        if not interview:
            raise NotFoundException(
f"No interview found for visit {visit_id}.")

        interview.status = "COMPLETED"
        interview.current_question_id = None

        extracted_facts = [
            ExtractedFactItem(**f) if isinstance(f, dict) else f
            for f in (interview.extracted_facts or [])
        ]

        # 1. Build standardized English clinical briefing
        briefing_lines = []
        ayush_synced = False
        ayush_map: Dict[str, Any] = {}

        for f in extracted_facts:
            slot_name = f.slot.replace("_", " ").title()
            briefing_lines.append(f"• {slot_name}: {f.value}")

            # Map AYUSH specific fields
            if f.slot in ["prakriti", "vikriti", "agni", "koshtha", "sattva"]:
                ayush_map[f.slot] = {"observation": f.value, "verified": f.verified}

        briefing_text = "\n".join(briefing_lines) if briefing_lines else "No clinical facts extracted."

        # 2. Sync AYUSH fields directly onto Visit table if applicable
        if ayush_map:
            if "prakriti" in ayush_map:
                visit.prakriti = {"primary_dosha": "VATA_PITTA", "details": ayush_map["prakriti"]["observation"]}
            if "vikriti" in ayush_map:
                visit.vikriti = {"aggravated_doshas": ["VATA"], "details": ayush_map["vikriti"]["observation"]}
            if "agni" in ayush_map:
                visit.agni = {"agni_type": "VISHAMA", "details": ayush_map["agni"]["observation"]}
            if "koshtha" in ayush_map:
                visit.koshtha = {"koshtha_type": "KRURA", "details": ayush_map["koshtha"]["observation"]}
            if "sattva" in ayush_map:
                visit.sattva = {"sattva_type": "MADHYAMA", "details": ayush_map["sattva"]["observation"]}
            ayush_synced = True

        # 3. Create a compiled VisitInput (FORM kind) so downstream summary engine ingests it
        compiled_input = VisitInput(
            visit_id=visit_id,
            kind=InputKind.TEXT,
            text=f"Adaptive Interview Briefing (Standardized English):\n{briefing_text}",
            status=InputStatus.COMPLETED,
            provenance={
                "source": "adaptive_voice_interview",
                "interview_id": str(interview.id),
                "facts_count": len(extracted_facts),
                "language": interview.language,
            },
        )

        self.db.add(compiled_input)

        # 4. Record audit event
        actor_id = current_user.id if current_user else None
        self.audit_service.record_event(
            action="INTERVIEW_COMPLETED",
            entity_type="patient_interview",
            entity_id=str(interview.id),
            request_id="req_interview_complete",
            actor_id=actor_id,
            actor_role=current_user.role.value if current_user else "patient",
            payload={
                "facts_count": len(extracted_facts),
                "red_flags_count": len(interview.red_flags or []),
                "ayush_synced": ayush_synced,
            },
        )
        self.db.commit()
        self.db.refresh(interview)


        return InterviewCompleteResponse(
            visit_id=str(visit_id),
            status="COMPLETED",
            facts_count=len(extracted_facts),
            extracted_facts=extracted_facts,
            red_flags=list(interview.red_flags or []),
            briefing_text=briefing_text,
            ayush_intake_synced=ayush_synced,
        )

    async def _build_turn_response(self, interview: PatientInterview, is_complete: bool) -> InterviewTurnResponse:
        facts = [
            ExtractedFactItem(**f) if isinstance(f, dict) else f
            for f in (interview.extracted_facts or [])
        ]
        return InterviewTurnResponse(
            next_question=None,
            extracted_facts=facts,
            missing_slots=list(interview.missing_slots or []),
            interview_complete=is_complete,
            red_flags=list(interview.red_flags or []),
            turn_number=interview.question_count,
            max_questions=interview.max_questions,
        )
