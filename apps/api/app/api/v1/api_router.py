from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    doctor,
    health,
    interview,
    patients,
    platform,
    processing,
    queue,
    summaries,
    uploads,
    visits,
)

api_v1_router = APIRouter()

api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(platform.router)
api_v1_router.include_router(visits.router)
api_v1_router.include_router(patients.router)
api_v1_router.include_router(queue.router)
api_v1_router.include_router(doctor.router)
api_v1_router.include_router(doctor.visits_doctor_router)
api_v1_router.include_router(uploads.router)
api_v1_router.include_router(processing.router)
api_v1_router.include_router(summaries.router)
api_v1_router.include_router(interview.router)


