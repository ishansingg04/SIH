import pytest
from app.api.dependencies import get_storage
from app.integrations.storage import StorageProvider


def test_health_check_returns_200(client):
    """BACKEND-02: Health check passes with 200 and standard envelope."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "ok"
    assert "request_id" in data["meta"]
    assert data["error"] is None
    assert "X-Request-ID" in response.headers


def test_readiness_check_healthy(client):
    """BACKEND-02: Readiness returns healthy state for active dependencies."""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["database"] == "ok"
    assert data["data"]["storage"] == "ok"


def test_readiness_check_degraded_when_storage_fails(client):
    """BACKEND-02: Readiness returns 503 DEPENDENCY_UNAVAILABLE when storage is degraded."""
    class FailingStorage:
        def check_health(self) -> bool:
            return False

    from app.main import app
    app.dependency_overrides[get_storage] = lambda: FailingStorage()

    try:
        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
        assert data["error"]["fields"]["storage"] == "down"
    finally:
        app.dependency_overrides.pop(get_storage, None)
