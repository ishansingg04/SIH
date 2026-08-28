import time
import uuid
from typing import Callable
from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.exceptions import AppException
from app.core.logging import logger


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware attaching request IDs, calculating latency, and logging requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract or generate Request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = f"req_{uuid.uuid4().hex[:12]}"

        request.state.request_id = request_id

        start_time = time.time()
        actor_role = "anonymous"

        try:
            response = await call_next(request)
            latency_ms = round((time.time() - start_time) * 1000, 2)
            response.headers["X-Request-ID"] = request_id

            logger.info(
                f"{request.method} {request.url.path} -> {response.status_code} ({latency_ms}ms)",
                extra={
                    "request_id": request_id,
                    "route": request.url.path,
                    "status": response.status_code,
                    "latency_ms": latency_ms,
                    "actor_role": actor_role,
                },
            )
            return response
        except Exception as exc:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                f"Unhandled error processing {request.method} {request.url.path}: {exc}",
                extra={
                    "request_id": request_id,
                    "route": request.url.path,
                    "status": 500,
                    "latency_ms": latency_ms,
                    "actor_role": actor_role,
                },
                exc_info=True,
            )
            raise exc


def register_exception_handlers(app: FastAPI) -> None:
    """Registers standardized error response envelopes for all exception categories."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "req_unknown")
        return JSONResponse(
            status_code=exc.status_code,
            headers={"X-Request-ID": request_id},
            content={
                "success": False,
                "data": None,
                "meta": {"request_id": request_id},
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "fields": exc.fields if exc.fields else {},
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "req_unknown")
        # Format Pydantic validation error details
        fields_errors = {}
        for err in exc.errors():
            loc = ".".join(str(item) for item in err.get("loc", []) if item != "body")
            fields_errors[loc or "body"] = err.get("msg")

        return JSONResponse(
            status_code=422,
            headers={"X-Request-ID": request_id},
            content={
                "success": False,
                "data": None,
                "meta": {"request_id": request_id},
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Input validation failed. Please correct the highlighted fields.",
                    "fields": fields_errors,
                },
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "req_unknown")
        code_map = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            422: "VALIDATION_ERROR",
            503: "DEPENDENCY_UNAVAILABLE",
        }
        error_code = code_map.get(exc.status_code, "INTERNAL_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            headers={"X-Request-ID": request_id},
            content={
                "success": False,
                "data": None,
                "meta": {"request_id": request_id},
                "error": {
                    "code": error_code,
                    "message": str(exc.detail),
                    "fields": {},
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "req_unknown")
        logger.exception(f"Unexpected internal server error on {request.url.path}: {exc}")
        return JSONResponse(
            status_code=500,
            headers={"X-Request-ID": request_id},
            content={
                "success": False,
                "data": None,
                "meta": {"request_id": request_id},
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred. Please contact clinic staff.",
                    "fields": {},
                },
            },
        )
