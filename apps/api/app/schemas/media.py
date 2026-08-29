"""Media upload and job status Pydantic schemas.

Owned by: feature/ocr-whisper
These schemas define the API response contracts for audio/document uploads,
job status polling, retry responses, and signed URL access.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import AIJobStatus, AIJobType, InputKind


class AudioUploadResponse(BaseModel):
    """Response after successful audio upload and transcription job enqueue."""

    input_id: uuid.UUID
    job_id: uuid.UUID
    status: str = "PENDING"
    language: str
    provider: str
    web_speech_fallback: bool = Field(
        description="Whether browser Web Speech API fallback is enabled"
    )


class DocumentUploadResponse(BaseModel):
    """Response after successful document upload and OCR job enqueue."""

    input_id: uuid.UUID
    job_id: uuid.UUID
    status: str = "PENDING"
    kind: InputKind
    display_name: str
    provider: str


class JobStatusResponse(BaseModel):
    """Polling response for job/input processing status."""

    job_id: uuid.UUID
    input_id: uuid.UUID
    visit_id: uuid.UUID
    type: AIJobType
    status: AIJobStatus
    progress: int = Field(ge=0, le=100, description="Computed progress percentage")
    attempts: int
    max_retries: int
    error_code: Optional[str] = None
    result_preview: Optional[str] = Field(
        default=None, description="First 200 chars of extracted text"
    )
    source_url: Optional[str] = Field(
        default=None, description="Short-lived presigned URL for source file"
    )
    created_at: datetime
    updated_at: datetime


class SignedUrlResponse(BaseModel):
    """Presigned URL for secure object access."""

    key: str
    url: str
    expires_in_seconds: int = 3600


class WorkerJobItem(BaseModel):
    """Single job item for operator observability listing."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    visit_id: uuid.UUID
    type: AIJobType
    status: AIJobStatus
    attempts: int
    provider: str
    error_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class WorkerJobListResponse(BaseModel):
    """List of jobs for operator observability."""

    jobs: List[WorkerJobItem]
    total: int
