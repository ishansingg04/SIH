"""Upload validation and VisitInput management service.

Owned by: feature/ocr-whisper
Handles media acceptance rules, storage key generation, VisitInput CRUD,
and cross-clinic access guards.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.core.logging import logger
from app.db.models.enums import InputKind, InputStatus
from app.db.models.input import VisitInput
from app.db.models.visit import Visit


# Allowed MIME types — reject executable content
ALLOWED_AUDIO_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/x-wav",
    "audio/x-m4a",
}

ALLOWED_DOCUMENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}

# Executable / dangerous types that must always be rejected
BLOCKED_TYPES = {
    "application/x-executable",
    "application/x-msdos-program",
    "application/x-msdownload",
    "application/octet-stream",
    "application/x-sh",
    "application/x-csh",
    "text/x-shellscript",
}


def validate_audio_file(content_type: str, size_bytes: int) -> None:
    """Validate audio file type and size. Raises ValidationException on failure."""
    if content_type in BLOCKED_TYPES:
        raise ValidationException(
            message="Executable or dangerous file types are not allowed",
            fields={"content_type": content_type},
        )

    if content_type not in ALLOWED_AUDIO_TYPES:
        raise ValidationException(
            message=f"Unsupported audio type: {content_type}. Allowed: {', '.join(sorted(ALLOWED_AUDIO_TYPES))}",
            fields={"content_type": content_type},
        )

    max_bytes = settings.MAX_AUDIO_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise ValidationException(
            message=f"Audio file exceeds maximum size of {settings.MAX_AUDIO_SIZE_MB}MB",
            fields={"size_bytes": size_bytes, "max_bytes": max_bytes},
        )


def validate_document_file(content_type: str, size_bytes: int) -> None:
    """Validate document file type and size. Raises ValidationException on failure."""
    if content_type in BLOCKED_TYPES:
        raise ValidationException(
            message="Executable or dangerous file types are not allowed",
            fields={"content_type": content_type},
        )

    if content_type not in ALLOWED_DOCUMENT_TYPES:
        raise ValidationException(
            message=f"Unsupported document type: {content_type}. Allowed: {', '.join(sorted(ALLOWED_DOCUMENT_TYPES))}",
            fields={"content_type": content_type},
        )

    max_bytes = settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise ValidationException(
            message=f"Document file exceeds maximum size of {settings.MAX_DOCUMENT_SIZE_MB}MB",
            fields={"size_bytes": size_bytes, "max_bytes": max_bytes},
        )


def build_object_key(
    clinic_id: uuid.UUID,
    visit_id: uuid.UUID,
    kind: InputKind,
    original_filename: str,
) -> str:
    """Build private bucket object key with clinic/visit prefix.

    Format: {clinic_id}/{visit_id}/{kind}/{uuid4}.{ext}
    Original filename is retained only as display metadata, never used as key.
    """
    ext = "bin"
    if "." in original_filename:
        ext = original_filename.rsplit(".", 1)[-1].lower()

    unique_id = uuid.uuid4().hex[:12]
    return f"{clinic_id}/{visit_id}/{kind.value.lower()}/{unique_id}.{ext}"


def check_consent(visit: Visit) -> None:
    """Ensure visit has recorded consent before accepting media uploads."""
    if visit.consent_at is None:
        raise ForbiddenException(
            "Patient consent must be recorded before uploading media. "
            "Ensure consent_at is set on the visit."
        )


def create_visit_input(
    db: Session,
    visit: Visit,
    kind: InputKind,
    object_key: str,
    language: Optional[str] = None,
    original_filename: Optional[str] = None,
) -> VisitInput:
    """Create a new VisitInput record linked to the visit."""
    provenance = {
        "source": "upload",
        "kind": kind.value,
        "confidence": 0.0,  # Not yet processed
    }
    if language:
        provenance["language"] = language
    if original_filename:
        provenance["original_filename"] = original_filename

    visit_input = VisitInput(
        visit_id=visit.id,
        kind=kind,
        object_key=object_key,
        status=InputStatus.PENDING,
        provenance=provenance,
    )
    db.add(visit_input)
    db.flush()

    logger.info(
        f"Created VisitInput {visit_input.id} for visit {visit.id} "
        f"(kind={kind.value}, key={object_key})"
    )
    return visit_input


def get_authorized_input(
    db: Session,
    input_id: uuid.UUID,
    visit_id: Optional[uuid.UUID] = None,
) -> VisitInput:
    """Fetch a VisitInput with access guard.

    If visit_id is provided, verifies the input belongs to that visit.
    Raises NotFoundException for missing or cross-clinic access violations.
    """
    visit_input = db.get(VisitInput, input_id)

    if not visit_input or visit_input.is_deleted:
        raise NotFoundException(f"Input with ID {input_id} not found")

    if visit_id and visit_input.visit_id != visit_id:
        # Cross-clinic / cross-visit access attempt — return 404 (not 403)
        # to avoid leaking existence of the resource
        logger.warning(
            f"Cross-visit access attempt: input {input_id} belongs to "
            f"visit {visit_input.visit_id}, requested via visit {visit_id}"
        )
        raise NotFoundException(f"Input with ID {input_id} not found")

    return visit_input


def update_input_status(
    db: Session,
    input_id: uuid.UUID,
    status: InputStatus,
    text: Optional[str] = None,
    confidence: Optional[float] = None,
) -> VisitInput:
    """Update VisitInput status and extracted text after processing."""
    visit_input = db.get(VisitInput, input_id)
    if not visit_input:
        raise NotFoundException(f"Input with ID {input_id} not found")

    visit_input.status = status
    if text is not None:
        visit_input.text = text

    # Update provenance with processing result
    provenance = dict(visit_input.provenance)
    if confidence is not None:
        provenance["confidence"] = confidence
    provenance["processed_at"] = datetime.now(timezone.utc).isoformat()
    visit_input.provenance = provenance

    db.flush()
    return visit_input


def soft_delete_input(db: Session, input_id: uuid.UUID) -> None:
    """Soft-delete a VisitInput. Preserves source object for audit trail."""
    visit_input = db.get(VisitInput, input_id)
    if not visit_input:
        raise NotFoundException(f"Input with ID {input_id} not found")

    visit_input.is_deleted = True
    db.flush()
    logger.info(f"Soft-deleted VisitInput {input_id}")
