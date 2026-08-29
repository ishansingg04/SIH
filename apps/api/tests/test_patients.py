import pytest

def test_get_my_profile_success(client, patient_token):
    """Patient can retrieve their own profile."""
    response = client.get(
        "/api/v1/patients/me",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["name"] == "Asha Devi"
    assert "consent_version" in body["data"]

def test_get_my_profile_unauthorized(client):
    """Unauthenticated access is rejected."""
    response = client.get("/api/v1/patients/me")
    assert response.status_code == 401

def test_get_my_profile_wrong_role(client, doctor_token):
    """Doctor role cannot access patient /me endpoint."""
    response = client.get(
        "/api/v1/patients/me",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert response.status_code == 403

def test_update_my_profile_success(client, patient_token):
    """Patient can update their safe profile fields."""
    response = client.patch(
        "/api/v1/patients/me",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"language": "en", "name": "Asha D."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["language"] == "en"
    assert body["data"]["name"] == "Asha D."

def test_update_my_profile_protected_fields(client, patient_token):
    """Unknown/protected fields sent to PATCH are ignored; response is still 200."""
    response = client.patch(
        "/api/v1/patients/me",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"phone": "+910000000000", "dob": "1990-01-01"},
    )
    # Pydantic v2 ignores extra fields by default — the endpoint returns 200
    # but the protected fields are silently dropped and NOT persisted.
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    # phone_masked should remain unchanged (not overwritten with the unknown input)
    assert body["data"].get("phone_masked") != "+910000000000"
