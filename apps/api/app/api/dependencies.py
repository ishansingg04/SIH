import uuid
from typing import Callable, List, Optional
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.logging import logger
from app.core.security import decode_access_token
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.db.session import get_db
from app.integrations.ocr import OCRProvider, get_ocr_adapter
from app.integrations.speech import SpeechProvider, get_speech_adapter
from app.integrations.storage import StorageProvider, get_storage_adapter
from app.integrations.summary import SummaryProvider, get_summary_adapter
from app.services.audit_service import AuditService

security_scheme = HTTPBearer(auto_error=False)


def get_request_id(request: Request) -> str:
    """Retrieve unique request ID attached by middleware or header."""
    return getattr(request.state, "request_id", "req_unknown")


def get_audit_service(db: Session = Depends(get_db)) -> AuditService:
    """Dependency injecting the append-only audit service."""
    return AuditService(db)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate JWT Bearer token and return active User instance."""
    if not credentials:
        raise UnauthorizedException("Missing authentication credentials")

    token = credentials.credentials
    payload = decode_access_token(token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedException("Token payload missing user identifier")

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise UnauthorizedException("Invalid user ID format in token")

    user = db.get(User, user_uuid)
    if not user:
        raise UnauthorizedException("User account not found")

    if not user.is_active:
        raise ForbiddenException("User account is inactive")

    return user


def get_current_active_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Optional authentication for public/kiosk endpoints where user may or may not be logged in."""
    if not credentials:
        return None
    try:
        return get_current_user(credentials, db)
    except Exception:
        return None


def require_roles(allowed_roles: List[UserRole]) -> Callable[[User], User]:
    """Role-Based Access Control (RBAC) dependency factory."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            logger.warning(
                f"User {current_user.id} with role '{current_user.role}' attempted unauthorized access to route requiring {allowed_roles}"
            )
            raise ForbiddenException(
                f"Access forbidden: requires one of [{', '.join(r.value for r in allowed_roles)}]"
            )
        return current_user

    return role_checker


# Provider Adapter dependencies
def get_storage() -> StorageProvider:
    return get_storage_adapter()


def get_speech() -> SpeechProvider:
    return get_speech_adapter()


def get_ocr() -> OCRProvider:
    return get_ocr_adapter()


def get_summary() -> SummaryProvider:
    return get_summary_adapter()
