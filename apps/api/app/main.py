from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.middleware import RequestContextMiddleware, register_exception_handlers
from app.api.router import main_router
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown routines."""
    setup_logging(settings.LOG_LEVEL)
    logger.info(f"Starting {settings.APP_NAME} in '{settings.APP_ENV}' environment...")
    # In local/test mode, ensure metadata tables are initialized
    if settings.APP_ENV == "local" or settings.DATABASE_URL.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
        logger.info("Local database tables verified/created.")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}...")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="MediKiosk Platform API — AI-enabled clinic operations for Bharat",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # 1. CORS Middleware (configured for Vercel and local development)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Request ID and Timing Middleware
    app.add_middleware(RequestContextMiddleware)

    # 3. Global Standardized Exception Handlers
    register_exception_handlers(app)

    # 4. Mount API Routers
    app.include_router(main_router)

    # 5. Mount static test UI for doctor queue console
    from pathlib import Path
    doctor_test_dir = Path(__file__).parent / "doctor_test"
    if doctor_test_dir.exists():
        from fastapi.staticfiles import StaticFiles
        app.mount(
            "/doctor-test",
            StaticFiles(directory=str(doctor_test_dir), html=True),
            name="doctor-test",
        )

    return app


app = create_app()

