import uuid


def test_response_envelope_structure_on_success(client):
    """Every successful response strictly adheres to ApiResponse schema."""
    response = client.get("/api/v1/platform/status")
    assert response.status_code == 200
    body = response.json()
    assert "success" in body and body["success"] is True
    assert "data" in body and isinstance(body["data"], dict)
    assert "meta" in body and "request_id" in body["meta"]
    assert "error" in body and body["error"] is None


def test_validation_error_envelope_structure(client):
    """Validation errors follow ApiErrorEnvelope with code VALIDATION_ERROR and fields map."""
    # Post invalid payload to login endpoint
    response = client.post("/api/v1/auth/login", json={"email": "not-an-email"})
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert "request_id" in body["meta"]
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "fields" in body["error"]
    assert len(body["error"]["fields"]) > 0


def test_not_found_error_envelope(client):
    """404 Not Found returns proper error envelope."""
    random_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/visits/{random_id}")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"
    assert "not found" in body["error"]["message"].lower()


def test_request_id_propagation(client):
    """Client-provided X-Request-ID is retained in meta and headers."""
    custom_id = "req_custom_test_12345"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id
    body = response.json()
    assert body["meta"]["request_id"] == custom_id
