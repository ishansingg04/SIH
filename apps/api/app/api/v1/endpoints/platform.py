from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, get_db, get_request_id, require_roles
from app.core.config import settings
from app.db.models.audit import AuditEvent
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.db.seed import seed_database
from app.db.session import check_database_health
from app.schemas.audit import AuditEventRead
from app.schemas.common import ApiResponse, Meta, PaginatedData

router = APIRouter(prefix="/platform", tags=["Platform & Observability"])


@router.get("/status", response_model=ApiResponse[Dict[str, Any]])
def get_platform_status(request: Request):
    """Retrieve platform observability, configuration flags, and provider modes."""
    request_id = get_request_id(request)
    db_healthy = check_database_health()

    status_data = {
        "app_name": settings.APP_NAME,
        "app_env": settings.APP_ENV,
        "database_connected": db_healthy,
        "ayush_intake_enabled": settings.AYUSH_INTAKE_ENABLED,
        "whisper_provider_mode": settings.WHISPER_PROVIDER_MODE,
        "ai_provider_mode": settings.AI_PROVIDER_MODE,
        "web_speech_fallback_enabled": settings.WEB_SPEECH_FALLBACK,
        "storage_bucket": settings.STORAGE_BUCKET,
    }

    return ApiResponse(
        success=True,
        data=status_data,
        meta=Meta(request_id=request_id),
        error=None,
    )


@router.post("/seed", response_model=ApiResponse[Dict[str, Any]])
def trigger_database_seed(
    request: Request,
    db: Session = Depends(get_db),
):
    """Seed initial clinic, users, demo patient, and AYUSH visit data."""
    request_id = get_request_id(request)
    result = seed_database(db)
    return ApiResponse(
        success=True,
        data=result,
        meta=Meta(request_id=request_id),
        error=None,
    )


@router.get("/audit", response_model=ApiResponse[PaginatedData[AuditEventRead]])
def list_audit_events(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_roles([UserRole.CLINIC_ADMIN, UserRole.SYSTEM_OPERATOR])),
    db: Session = Depends(get_db),
):
    """List append-only audit events for compliance review."""
    request_id = get_request_id(request)
    stmt = select(AuditEvent).order_by(desc(AuditEvent.created_at)).limit(limit).offset(offset)
    events = db.scalars(stmt).all()

    items = [AuditEventRead.model_validate(e) for e in events]
    return ApiResponse(
        success=True,
        data=PaginatedData(items=items, has_more=len(items) == limit),
        meta=Meta(request_id=request_id),
        error=None,
    )
