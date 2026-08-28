from typing import Any, Dict, Optional


class AppException(Exception):
    """Base application exception with standardized code and HTTP status."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        fields: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.fields = fields or {}


class ValidationException(AppException):
    """Input validation failure (422)."""

    def __init__(self, message: str = "Validation failed", fields: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            fields=fields,
        )


class UnauthorizedException(AppException):
    """Authentication required or token expired (401)."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=401,
        )


class ForbiddenException(AppException):
    """Insufficient permissions (403)."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=403,
        )


class NotFoundException(AppException):
    """Requested resource not found (404)."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=404,
        )


class ConflictException(AppException):
    """Resource state or idempotency conflict (409)."""

    def __init__(self, message: str = "Conflict detected"):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=409,
        )


class DependencyUnavailableException(AppException):
    """External dependency down or degraded (503)."""

    def __init__(self, message: str = "Service dependency unavailable"):
        super().__init__(
            message=message,
            code="DEPENDENCY_UNAVAILABLE",
            status_code=503,
        )
