from fastapi import APIRouter
from app.api.v1.api_router import api_v1_router
from app.api.v1.endpoints import health

main_router = APIRouter()

# Root level health and readiness probes
main_router.include_router(health.router)

# Versioned API routes
main_router.include_router(api_v1_router, prefix="/api/v1")
