"""Pydantic schemas and contracts for Adaptive Voice-Based Patient Interview."""

from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field
from app.core.questions import QuestionInputType, SlotType


class ExtractedFactItem(BaseModel):
    id: str = Field(default_factory=lambda: f"fact_{uuid.uuid4().hex[:8]}")
    slot: str
    value: str  # Always stored in standardized English
    source: str = "patient_voice"  # "patient_voice", "patient_typed", "document_extracted", "system_inferred"
    confidence: float = 0.95
    verified: bool = True
    category: str = "patient_reported"  # "patient_reported", "ayush_assessment", "red_flag", "medical_history"
    original_text: Optional[str] = None  # Original Hindi or raw utterance for auditability


class FactUpdateRequest(BaseModel):
    value: str
    verified: bool = True


class NextQuestionSchema(BaseModel):
    id: str
    slot: str
    text: str
    input_type: QuestionInputType = QuestionInputType.VOICE_OR_TEXT
    required: bool = True
    options: Optional[List[str]] = None


class InterviewStartRequest(BaseModel):
    initial_text: Optional[str] = None
    language: str = "en"
    pathway: str = "ALLOPATHIC"
    max_questions: int = Field(default=6, ge=1, le=12)


class InterviewTurnRequest(BaseModel):
    question_id: Optional[str] = None
    answer_text: Optional[str] = None
    skipped: bool = False
    language: Optional[str] = None


class InterviewTurnItem(BaseModel):
    turn_index: int
    question_id: str
    question_text: str
    answer_text: Optional[str] = None
    transcript: Optional[str] = None
    input_source: str = "text"  # "voice" or "text"
    skipped: bool = False
    created_at: str


class InterviewTurnResponse(BaseModel):
    next_question: Optional[NextQuestionSchema] = None
    extracted_facts: List[ExtractedFactItem] = Field(default_factory=list)
    missing_slots: List[str] = Field(default_factory=list)
    interview_complete: bool = False
    red_flags: List[Dict[str, Any]] = Field(default_factory=list)
    turn_number: int = 1
    max_questions: int = 6
    transcript: Optional[str] = None  # Transcript of the latest turn if audio was provided


class InterviewStateResponse(BaseModel):
    visit_id: str
    status: str  # "IN_PROGRESS", "COMPLETED", "ABANDONED"
    language: str = "en"
    pathway: str = "ALLOPATHIC"
    current_question: Optional[NextQuestionSchema] = None
    answered_questions: List[str] = Field(default_factory=list)
    turns: List[InterviewTurnItem] = Field(default_factory=list)
    extracted_facts: List[ExtractedFactItem] = Field(default_factory=list)
    missing_slots: List[str] = Field(default_factory=list)
    red_flags: List[Dict[str, Any]] = Field(default_factory=list)
    progress_percentage: int = 0
    turns_completed: int = 0
    max_questions: int = 6
    is_complete: bool = False


class InterviewCompleteResponse(BaseModel):
    visit_id: str
    status: str = "COMPLETED"
    facts_count: int
    extracted_facts: List[ExtractedFactItem]
    red_flags: List[Dict[str, Any]] = Field(default_factory=list)
    briefing_text: str  # Standardized English clinical briefing for doctor
    ayush_intake_synced: bool = False
