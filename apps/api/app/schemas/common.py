from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Meta(BaseModel):
    """Metadata envelope present in every API response."""

    request_id: str = Field(..., description="Unique correlation identifier for the request")


class ApiErrorDetail(BaseModel):
    """Structured error payload details."""

    code: str = Field(..., description="Machine-readable error taxonomy code")
    message: str = Field(..., description="Human-readable error description")
    fields: Optional[Dict[str, Any]] = Field(default=None, description="Field-specific validation error details")


class ApiResponse(BaseModel, Generic[T]):
    """Standardized top-level API response envelope for successful requests."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool = Field(default=True, description="Indicates request success status")
    data: Optional[T] = Field(default=None, description="Payload data returned by the endpoint")
    meta: Meta = Field(..., description="Request metadata and correlation ID")
    error: Optional[ApiErrorDetail] = Field(default=None, description="Null for successful responses")


class ApiErrorEnvelope(BaseModel):
    """Standardized top-level API response envelope for failed requests."""

    success: bool = Field(default=False, description="Always false for error responses")
    data: Optional[Any] = Field(default=None, description="Always null for error responses")
    meta: Meta = Field(..., description="Request metadata and correlation ID")
    error: ApiErrorDetail = Field(..., description="Standardized error details")


class PaginationParams(BaseModel):
    """Standard cursor and limit query parameters for list endpoints."""

    limit: int = Field(default=20, ge=1, le=100, description="Max items to return")
    cursor: Optional[str] = Field(default=None, description="Cursor for next page")


class PaginatedData(BaseModel, Generic[T]):
    """Generic wrapper for paginated lists."""

    items: List[T]
    total: Optional[int] = None
    next_cursor: Optional[str] = None
    has_more: bool = False
