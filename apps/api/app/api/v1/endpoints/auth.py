from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, get_db, get_request_id
from app.core.config import settings
from app.core.exceptions import UnauthorizedException
from app.core.security import create_access_token, verify_password
from app.db.models.user import User
from app.schemas.common import ApiResponse, Meta
from app.schemas.user import LoginRequest, TokenResponse, UserRead
from app.services.audit_service import AuditService

router = APIRouter(prefix="/auth", tags=["Authentication Foundation"])


@router.post("/login", response_model=ApiResponse[TokenResponse])
def login(
    request: Request,
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate user with email and password, returning JWT access token."""
    request_id = get_request_id(request)
    stmt = select(User).where(User.email == payload.email)
    user = db.scalars(stmt).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedException("Invalid email or password")

    if not user.is_active:
        raise UnauthorizedException("Account is disabled")

    access_token = create_access_token(
        subject=user.id,
        role=user.role.value,
        clinic_id=str(user.clinic_id) if user.clinic_id else None,
    )

    # Log audit event
    audit_service = AuditService(db)
    audit_service.record_event(
        action="USER_LOGIN",
        entity_type="user",
        entity_id=str(user.id),
        request_id=request_id,
        actor_id=user.id,
        actor_role=user.role.value,
        payload={"email": user.email},
    )
    db.commit()

    token_data = TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_seconds=settings.JWT_EXPIRE_MINUTES * 60,
        user=UserRead.model_validate(user),
    )

    return ApiResponse(
        success=True,
        data=token_data,
        meta=Meta(request_id=request_id),
        error=None,
    )


@router.get("/me", response_model=ApiResponse[UserRead])
def get_current_user_profile(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Retrieve profile of currently authenticated user."""
    request_id = get_request_id(request)
    return ApiResponse(
        success=True,
        data=UserRead.model_validate(current_user),
        meta=Meta(request_id=request_id),
        error=None,
    )
