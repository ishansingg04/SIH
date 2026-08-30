from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application Settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Core Application Settings
    APP_NAME: str = "MediKiosk API"
    APP_ENV: str = Field(default="local", description="local | staging | production")
    DEBUG: bool = Field(default=False)
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///./medikiosk.db",
        description="PostgreSQL or SQLite connection string",
    )

    # Security & JWT
    JWT_SECRET: str = Field(
        default="medikiosk-insecure-dev-secret-key-change-in-production-32char",
        description="Secret key for signing JWT tokens",
    )
    JWT_EXPIRE_MINUTES: int = Field(default=30, description="Token expiry in minutes")
    JWT_ALGORITHM: str = Field(default="HS256")

    # AI & Speech Integrations
    GROQ_API_KEY: Optional[str] = Field(default=None, description="Groq Whisper/LLM API Key")
    GEMINI_API_KEY: Optional[str] = Field(default=None, description="Google Gemini API Key")
    WHISPER_PROVIDER_MODE: str = Field(
        default="mock",
        description="mock | groq-hosted",
    )
    AI_PROVIDER_MODE: str = Field(
        default="mock",
        description="mock | groq | openai | gemini",
    )
    WEB_SPEECH_FALLBACK: bool = Field(
        default=True,
        description="Enable browser Web Speech API fallback",
    )
    OCR_PROVIDER_MODE: str = Field(
        default="composite",
        description="composite | paddleocr | groq-vision | mock",
    )
    PADDLEOCR_ENDPOINT: Optional[str] = Field(
        default="http://localhost:8866/predict/ocr_system",
        description="URL for hosted PaddleOCR microservice",
    )
    OCR_FALLBACK_ENABLED: bool = Field(
        default=True,
        description="Enable automatic fallback to secondary OCR provider if primary fails",
    )
    OCR_FALLBACK_TO_MOCK: bool = Field(
        default=True,
        description="Enable graceful fallback to deterministic mock OCR if all remote providers fail",
    )
    GROQ_OCR_MODEL: str = Field(
        default="llama-3.2-90b-vision-preview",
        description="Groq vision model for OCR extraction",
    )

    # Upload and Job Processing Limits
    MAX_AUDIO_SIZE_MB: int = Field(default=25, description="Maximum audio file size in MB")
    MAX_DOCUMENT_SIZE_MB: int = Field(default=20, description="Maximum document file size in MB")
    MAX_JOB_RETRIES: int = Field(default=3, description="Maximum retry attempts for AI jobs")

    # AYUSH & Clinical Workflow Feature Flags
    AYUSH_INTAKE_ENABLED: bool = Field(
        default=True,
        description="Enable Dashavidha Pariksha AYUSH intake pathways",
    )

    # Object Storage (S3 / MinIO compatible)
    STORAGE_ENDPOINT: str = Field(
        default="http://localhost:9000",
        description="Storage server URL",
    )
    STORAGE_ACCESS_KEY: str = Field(default="local-access-key")
    STORAGE_SECRET_KEY: str = Field(default="local-secret-key")
    STORAGE_BUCKET: str = Field(default="medikiosk-private")
    STORAGE_REGION: str = Field(default="us-east-1")
    STORAGE_USE_SSL: bool = Field(default=False)

    # CORS Configuration
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated allowed origins",
    )

    # Observability
    LOG_LEVEL: str = Field(default="INFO")

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        if not self.CORS_ORIGINS:
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() in ("production", "prod")

    @property
    def is_staging(self) -> bool:
        return self.APP_ENV.lower() in ("staging", "stage")

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        # Standardize postgres:// to postgresql+psycopg:// if needed for SQLAlchemy 2.0
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg://", 1)
        if v.startswith("postgresql://") and not v.startswith("postgresql+"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v


settings = Settings()
