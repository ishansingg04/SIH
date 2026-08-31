"""FastAPI router endpoints for Adaptive Voice-Based Patient Interview."""

from typing import Optional
import uuid
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_active_user_optional,
    get_db,
    get_request_id,
)
from app.db.models.user import User
from app.schemas.common import ApiResponse, Meta
from app.schemas.interview import (
    ExtractedFactItem,
    FactUpdateRequest,
    InterviewCompleteResponse,
    InterviewStartRequest,
    InterviewStateResponse,
    InterviewTurnRequest,
    InterviewTurnResponse,
)
from app.services.interview_service import InterviewService

router = APIRouter(prefix="/visits/{visit_id}/interview", tags=["Adaptive Patient Interview"])


@router.post("/start", response_model=ApiResponse[InterviewTurnResponse])
async def start_interview(
    visit_id: uuid.UUID,
    request: Request,
    initial_text: Optional[str] = Form(default=None),
    language: str = Form(default="en"),
    pathway: str = Form(default="ALLOPATHIC"),
    max_questions: int = Form(default=6),
    audio_file: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """Start an adaptive patient interview session (accepts voice audio or text)."""
    request_id = get_request_id(request)
    audio_bytes = None
    filename = "initial_speech.webm"
    if audio_file:
        audio_bytes = await audio_file.read()
        filename = audio_file.filename or "initial_speech.webm"

    payload = InterviewStartRequest(
        initial_text=initial_text,
        language=language,
        pathway=pathway,
        max_questions=max_questions,
    )
    service = InterviewService(db)
    result = await service.start_interview(
        visit_id=visit_id,
        payload=payload,
        audio_bytes=audio_bytes,
        filename=filename,
        current_user=current_user,
    )
    return ApiResponse(data=result, meta=Meta(request_id=request_id))


@router.post("/turn", response_model=ApiResponse[InterviewTurnResponse])
async def process_interview_turn(
    visit_id: uuid.UUID,
    request: Request,
    question_id: Optional[str] = Form(default=None),
    answer_text: Optional[str] = Form(default=None),
    skipped: bool = Form(default=False),
    language: Optional[str] = Form(default=None),
    audio_file: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """Submit an answer to the current interview question (via voice audio or typed text)."""
    request_id = get_request_id(request)
    audio_bytes = None
    filename = "answer.webm"
    if audio_file:
        audio_bytes = await audio_file.read()
        filename = audio_file.filename or "answer.webm"

    payload = InterviewTurnRequest(
        question_id=question_id,
        answer_text=answer_text,
        skipped=skipped,
        language=language,
    )
    service = InterviewService(db)
    result = await service.process_turn(
        visit_id=visit_id,
        payload=payload,
        audio_bytes=audio_bytes,
        filename=filename,
        current_user=current_user,
    )
    return ApiResponse(data=result, meta=Meta(request_id=request_id))


@router.get("", response_model=ApiResponse[InterviewStateResponse])
def get_interview_state(
    visit_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """Retrieve the current persistent interview state, answered questions, and fact chips."""
    request_id = get_request_id(request)
    service = InterviewService(db)
    result = service.get_interview_state(visit_id=visit_id, current_user=current_user)
    return ApiResponse(data=result, meta=Meta(request_id=request_id))


@router.put("/facts/{fact_id}", response_model=ApiResponse[ExtractedFactItem])
def update_fact(
    visit_id: uuid.UUID,
    fact_id: str,
    payload: FactUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """Edit or verify an extracted clinical fact chip."""
    request_id = get_request_id(request)
    service = InterviewService(db)
    result = service.update_fact(
        visit_id=visit_id,
        fact_id=fact_id,
        payload=payload,
        current_user=current_user,
    )
    return ApiResponse(data=result, meta=Meta(request_id=request_id))


@router.delete("/facts/{fact_id}", response_model=ApiResponse[dict])
def delete_fact(
    visit_id: uuid.UUID,
    fact_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """Delete an incorrectly extracted fact chip."""
    request_id = get_request_id(request)
    service = InterviewService(db)
    result = service.delete_fact(
        visit_id=visit_id,
        fact_id=fact_id,
        current_user=current_user,
    )
    return ApiResponse(data=result, meta=Meta(request_id=request_id))


@router.post("/complete", response_model=ApiResponse[InterviewCompleteResponse])
async def complete_interview(
    visit_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """Conclude the interview, compile the English briefing, and sync with AI summary pipeline."""
    request_id = get_request_id(request)
    service = InterviewService(db)
    result = await service.complete_interview(visit_id=visit_id, current_user=current_user)
    return ApiResponse(data=result, meta=Meta(request_id=request_id))
