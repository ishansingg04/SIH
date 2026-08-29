from fastapi import APIRouter
from app.api.v1.endpoints import auth, health, platform, visits, patients

api_v1_router = APIRouter()

api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(platform.router)
api_v1_router.include_router(visits.router)
api_v1_router.include_router(patients.router)
