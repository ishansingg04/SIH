import pytest
from app.core.security import create_access_token
from app.db.models.enums import UserRole


def test_login_successful_with_seed_user(client):
    """Seed user can log in and receive JWT token."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "dr.sharma@medikiosk.in", "password": "Doctor@12345"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "access_token" in body["data"]
    assert body["data"]["user"]["email"] == "dr.sharma@medikiosk.in"
    assert body["data"]["user"]["role"] == "doctor"


def test_login_failed_with_invalid_credentials(client):
    """Login with bad password returns 401 UNAUTHORIZED."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "dr.sharma@medikiosk.in", "password": "WrongPassword123"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_role_based_access_control_on_audit_logs(client, admin_token, doctor_token, patient_token, operator_token):
    """Clinic Admin and System Operator can read audit logs, Doctor and Patient are rejected with 403 FORBIDDEN."""
    # 1. No token -> 401
    res_no_auth = client.get("/api/v1/platform/audit")
    assert res_no_auth.status_code == 401

    # 2. Patient token -> 403
    res_patient = client.get(
        "/api/v1/platform/audit",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert res_patient.status_code == 403
    assert res_patient.json()["error"]["code"] == "FORBIDDEN"

    # 3. Doctor token -> 403
    res_doctor = client.get(
        "/api/v1/platform/audit",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert res_doctor.status_code == 403

    # 4. Clinic Admin -> 200
    res_admin = client.get(
        "/api/v1/platform/audit",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["success"] is True

    # 5. System Operator -> 200
    res_op = client.get(
        "/api/v1/platform/audit",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert res_op.status_code == 200

def test_register_successful(client):
    """New patient can register successfully."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "phone": "+919999999999",
            "name": "Test Patient",
            "language": "hi",
            "consent": True,
            "password": "SecurePassword123!"
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "id" in body["data"]

def test_register_duplicate_phone(client):
    """Registering with an existing phone number fails."""
    # Register first
    client.post(
        "/api/v1/auth/register",
        json={
            "phone": "+918888888888",
            "name": "Test Patient 1",
            "language": "en",
            "consent": True,
            "password": "SecurePassword123!"
        },
    )
    # Register again
    response = client.post(
        "/api/v1/auth/register",
        json={
            "phone": "+918888888888",
            "name": "Test Patient 2",
            "language": "hi",
            "consent": True,
            "password": "SecurePassword123!"
        },
    )
    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "CONFLICT"

def test_login_with_phone_successful(client):
    """Patient can log in using their phone number."""
    client.post(
        "/api/v1/auth/register",
        json={
            "phone": "+917777777777",
            "name": "Login Patient",
            "language": "en",
            "consent": True,
            "password": "SecurePassword123!"
        },
    )
    
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "+917777777777", "password": "SecurePassword123!"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "access_token" in body["data"]
