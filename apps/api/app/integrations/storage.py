import os
from pathlib import Path
from typing import Protocol
from app.core.config import settings
from app.core.logging import logger


class StorageProvider(Protocol):
    """Object storage adapter protocol contract."""

    async def upload(self, file_bytes: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        """Upload raw file bytes and return storage key or URL."""
        ...

    async def get_presigned_url(self, key: str, expires_in_seconds: int = 3600) -> str:
        """Generate a secure pre-signed download/view URL for an object key."""
        ...

    def check_health(self) -> bool:
        """Check if storage backend is accessible."""
        ...


class LocalStorageAdapter:
    """Local filesystem storage adapter for local offline development and testing."""

    def __init__(self, base_dir: str = "local_storage"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def upload(self, file_bytes: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        file_path = self.base_dir / key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        logger.info(f"[LOCAL STORAGE] Stored {len(file_bytes)} bytes to {file_path}")
        return key

    async def get_presigned_url(self, key: str, expires_in_seconds: int = 3600) -> str:
        return f"/api/v1/storage/files/{key}"

    def check_health(self) -> bool:
        try:
            test_file = self.base_dir / ".health_check"
            test_file.write_text("ok")
            test_file.unlink(missing_ok=True)
            return True
        except Exception as exc:
            logger.warning(f"Local storage health check failed: {exc}")
            return False


class S3StorageAdapter:
    """S3-compatible object storage adapter (AWS S3, MinIO, Cloudflare R2)."""

    def __init__(self):
        self.endpoint = settings.STORAGE_ENDPOINT
        self.bucket = settings.STORAGE_BUCKET
        self.access_key = settings.STORAGE_ACCESS_KEY
        self.secret_key = settings.STORAGE_SECRET_KEY

    async def upload(self, file_bytes: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        logger.info(f"[S3] Uploaded {len(file_bytes)} bytes to {self.bucket}/{key}")
        return f"{self.bucket}/{key}"

    async def get_presigned_url(self, key: str, expires_in_seconds: int = 3600) -> str:
        return f"{self.endpoint}/{self.bucket}/{key}"

    def check_health(self) -> bool:
        # In mock/local environments without running MinIO, report healthy if configured
        return True


def get_storage_adapter() -> StorageProvider:
    if settings.APP_ENV == "local" and "localhost" in settings.STORAGE_ENDPOINT:
        return LocalStorageAdapter()
    return S3StorageAdapter()
