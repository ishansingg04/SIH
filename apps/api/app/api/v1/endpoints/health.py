from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from app.api.dependencies import get_request_id, get_storage
from app.db.session import check_database_health
from app.integrations.storage import StorageProvider
from app.schemas.common import ApiResponse, Meta

router = APIRouter(tags=["Health & Readiness"])


@router.get("/health", response_model=ApiResponse[dict])
def health_check(request: Request):
    """Liveness probe returning 200 when API process is alive."""
    request_id = get_request_id(request)
    return ApiResponse(
        success=True,
        data={"status": "ok"},
        meta=Meta(request_id=request_id),
        error=None,
    )


@router.get("/ready")
def readiness_check(
    request: Request,
    storage: StorageProvider = Depends(get_storage),
):
    """Readiness probe validating database and storage dependencies."""
    request_id = get_request_id(request)
    db_ok = check_database_health()
    storage_ok = storage.check_health()

    data = {
        "database": "ok" if db_ok else "down",
        "storage": "ok" if storage_ok else "down",
    }

    if not db_ok or not storage_ok:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "data": data,
                "meta": {"request_id": request_id},
                "error": {
                    "code": "DEPENDENCY_UNAVAILABLE",
                    "message": "One or more critical service dependencies are offline",
                    "fields": data,
                },
            },
        )

    return ApiResponse(
        success=True,
        data=data,
        meta=Meta(request_id=request_id),
        error=None,
    )
