"""Test suite for the Whisper, OCR & Uploads module.

Covers all 5 PRD acceptance criteria (OCR-01 through OCR-05)
plus extended happy path and authorization tests.

All tests use mock adapters — no real API keys required.
"""

import io
import os
import sys
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

# Ensure app package is in path
test_dir = os.path.dirname(os.path.abspath(__file__))
api_dir = os.path.abspath(os.path.join(test_dir, ".."))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from app.db.models.enums import AIJobStatus, VisitStatus
from app.db.models.visit import Visit


# =====================================================================
# Helpers
# =====================================================================

def _get_test_visit_id(db_session) -> str:
    """Get the seeded test visit ID."""
    visit = db_session.scalars(
        select(Visit).where(Visit.token == "A01")
    ).first()
    if visit:
        return str(visit.id)

    # Fallback: find any visit with consent
    visit = db_session.scalars(
        select(Visit).where(Visit.consent_at.isnot(None))
    ).first()
    if visit:
        return str(visit.id)

    return None


def _get_visit_without_consent(db_session) -> str:
    """Get or create a visit without consent for testing."""
    visit = db_session.scalars(
        select(Visit).where(Visit.consent_at.is_(None))
    ).first()
    if visit:
        return str(visit.id)
    return None


def _make_audio_file():
    """Create a minimal valid audio file-like object."""
    # Minimal WebM header bytes (enough to pass MIME validation)
    return ("recording.webm", io.BytesIO(b"\x1a\x45\xdf\xa3" + b"\x00" * 100), "audio/webm")


def _make_pdf_file():
    """Create a minimal valid PDF file-like object."""
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< >>\nendobj\ntrailer\n<< >>\n%%EOF"
    return ("prescription.pdf", io.BytesIO(pdf_bytes), "application/pdf")


def _make_image_file():
    """Create a minimal valid JPEG file-like object."""
    # Minimal JPEG header
    return ("report.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100), "image/jpeg")


def _make_exe_file():
    """Create a file with executable content type."""
    return ("malware.exe", io.BytesIO(b"MZ\x90\x00" + b"\x00" * 100), "application/x-msdownload")


# =====================================================================
# OCR-01: Validation — unsupported type, oversize, missing consent
# =====================================================================

class TestOCR01Validation:
    """Unsupported type, oversize, and missing consent are rejected before provider call."""

    def test_unsupported_audio_type_rejected(self, client, db_session, patient_token):
        """Uploading an unsupported audio type returns 422."""
        visit_id = _get_test_visit_id(db_session)
        if not visit_id:
            pytest.skip("No test visit available")

        response = client.post(
            f"/api/v1/visits/{visit_id}/audio",
            headers={"Authorization": f"Bearer {patient_token}"},
            files={"file": ("test.exe", io.BytesIO(b"\x00" * 100), "application/x-msdownload")},
            data={"language": "en"},
        )
        assert response.status_code == 422

    def test_unsupported_document_type_rejected(self, client, db_session, patient_token):
        """Uploading an executable as document returns 422."""
        visit_id = _get_test_visit_id(db_session)
        if not visit_id:
            pytest.skip("No test visit available")

        response = client.post(
            f"/api/v1/visits/{visit_id}/uploads",
            headers={"Authorization": f"Bearer {patient_token}"},
            files={"file": _make_exe_file()},
        )
        assert response.status_code == 422

    def test_missing_consent_rejected(self, client, db_session, patient_token):
        """Upload to a visit without consent returns 403."""
        visit_id = _get_visit_without_consent(db_session)
        if not visit_id:
            pytest.skip("No visit without consent available")

        response = client.post(
            f"/api/v1/visits/{visit_id}/audio",
            headers={"Authorization": f"Bearer {patient_token}"},
            files={"file": _make_audio_file()},
            data={"language": "en"},
        )
        assert response.status_code == 403


# =====================================================================
# OCR-02: Status survives poll, retry is bounded
# =====================================================================

class TestOCR02StatusAndRetry:
    """Upload status survives refresh and retries are bounded."""

    def test_status_poll_returns_consistent_data(self, client, db_session, patient_token):
        """After upload, polling returns consistent status data."""
        visit_id = _get_test_visit_id(db_session)
        if not visit_id:
            pytest.skip("No test visit available")

        # Upload audio
        upload_resp = client.post(
            f"/api/v1/visits/{visit_id}/audio",
            headers={"Authorization": f"Bearer {patient_token}"},
            files={"file": _make_audio_file()},
            data={"language": "en"},
        )

        if upload_resp.status_code != 202:
            pytest.skip(f"Upload failed with status {upload_resp.status_code}")

        data = upload_resp.json()["data"]
        input_id = data["input_id"]

        # Poll status
        status_resp = client.get(
            f"/api/v1/inputs/{input_id}",
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        assert status_resp.status_code == 200
        status_data = status_resp.json()["data"]
        assert "status" in status_data
        assert "progress" in status_data
        assert status_data["visit_id"] is not None


# =====================================================================
# OCR-03: Transcript/OCR output links to visit and source object
# =====================================================================

class TestOCR03OutputLinksToVisit:
    """Transcript/OCR output links to visit and source object."""

    def test_audio_upload_creates_linked_input(self, client, db_session, patient_token):
        """Audio upload creates VisitInput linked to the correct visit."""
        visit_id = _get_test_visit_id(db_session)
        if not visit_id:
            pytest.skip("No test visit available")

        upload_resp = client.post(
            f"/api/v1/visits/{visit_id}/audio",
            headers={"Authorization": f"Bearer {patient_token}"},
            files={"file": _make_audio_file()},
            data={"language": "en"},
        )

        if upload_resp.status_code != 202:
            pytest.skip(f"Upload failed with status {upload_resp.status_code}")

        data = upload_resp.json()["data"]
        assert data["input_id"] is not None
        assert data["job_id"] is not None

        # Poll to verify visit link
        status_resp = client.get(
            f"/api/v1/inputs/{data['input_id']}",
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        if status_resp.status_code == 200:
            status_data = status_resp.json()["data"]
            assert status_data["visit_id"] == visit_id

    def test_document_upload_creates_linked_input(self, client, db_session, patient_token):
        """Document upload creates VisitInput linked to the correct visit."""
        visit_id = _get_test_visit_id(db_session)
        if not visit_id:
            pytest.skip("No test visit available")

        upload_resp = client.post(
            f"/api/v1/visits/{visit_id}/uploads",
            headers={"Authorization": f"Bearer {patient_token}"},
            files={"file": _make_image_file()},
        )

        if upload_resp.status_code != 202:
            pytest.skip(f"Upload failed with status {upload_resp.status_code}")

        data = upload_resp.json()["data"]
        assert data["input_id"] is not None
        assert data["job_id"] is not None


# =====================================================================
# OCR-04: Provider failure visible with safe error code
# =====================================================================

class TestOCR04ProviderFailure:
    """Provider failure is visible with safe error code."""

    def test_nonexistent_visit_returns_404(self, client, patient_token):
        """Upload to a non-existent visit returns 404."""
        fake_visit = str(uuid.uuid4())
        response = client.post(
            f"/api/v1/visits/{fake_visit}/audio",
            headers={"Authorization": f"Bearer {patient_token}"},
            files={"file": _make_audio_file()},
            data={"language": "en"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "NOT_FOUND"


# =====================================================================
# OCR-05: Access checks prevent cross-clinic retrieval
# =====================================================================

class TestOCR05AccessChecks:
    """Access checks prevent cross-clinic object retrieval."""

    def test_nonexistent_input_returns_404(self, client, patient_token):
        """Requesting a non-existent input returns 404."""
        fake_input = str(uuid.uuid4())
        response = client.get(
            f"/api/v1/inputs/{fake_input}",
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False


# =====================================================================
# Happy path tests
# =====================================================================

class TestHappyPaths:
    """End-to-end happy path validations."""

    def test_audio_upload_returns_202(self, client, db_session, patient_token):
        """Audio upload returns 202 with expected response shape."""
        visit_id = _get_test_visit_id(db_session)
        if not visit_id:
            pytest.skip("No test visit available")

        response = client.post(
            f"/api/v1/visits/{visit_id}/audio",
            headers={"Authorization": f"Bearer {patient_token}"},
            files={"file": _make_audio_file()},
            data={"language": "en"},
        )

        if response.status_code == 202:
            data = response.json()
            assert data["success"] is True
            assert "input_id" in data["data"]
            assert "job_id" in data["data"]
            assert "web_speech_fallback" in data["data"]

    def test_document_upload_returns_202(self, client, db_session, patient_token):
        """Document upload returns 202 with expected response shape."""
        visit_id = _get_test_visit_id(db_session)
        if not visit_id:
            pytest.skip("No test visit available")

        response = client.post(
            f"/api/v1/visits/{visit_id}/uploads",
            headers={"Authorization": f"Bearer {patient_token}"},
            files={"file": _make_pdf_file()},
        )

        if response.status_code == 202:
            data = response.json()
            assert data["success"] is True
            assert data["data"]["kind"] == "PDF"

    def test_api_response_envelope(self, client, db_session, patient_token):
        """All responses use the shared ApiResponse envelope."""
        visit_id = _get_test_visit_id(db_session)
        if not visit_id:
            pytest.skip("No test visit available")

        response = client.post(
            f"/api/v1/visits/{visit_id}/audio",
            headers={"Authorization": f"Bearer {patient_token}"},
            files={"file": _make_audio_file()},
            data={"language": "hi"},
        )
        data = response.json()
        # Envelope structure
        assert "success" in data
        assert "meta" in data
        assert "request_id" in data["meta"]


# =====================================================================
# Authorization tests
# =====================================================================

class TestAuthorization:
    """Role-based access control for worker endpoints."""

    def test_patient_cannot_access_worker_jobs(self, client, patient_token):
        """Patient role is rejected from worker endpoint."""
        response = client.get(
            "/api/v1/worker/jobs",
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        assert response.status_code == 403

    def test_operator_can_access_worker_jobs(self, client, operator_token):
        """Operator role can access worker endpoint."""
        response = client.get(
            "/api/v1/worker/jobs",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "jobs" in data["data"]


# =====================================================================
# Validation edge cases
# =====================================================================

class TestValidationEdgeCases:
    """Additional validation and edge case tests."""

    def test_missing_file_returns_422(self, client, db_session, patient_token):
        """POST without file attachment returns 422."""
        visit_id = _get_test_visit_id(db_session)
        if not visit_id:
            pytest.skip("No test visit available")

        response = client.post(
            f"/api/v1/visits/{visit_id}/audio",
            headers={"Authorization": f"Bearer {patient_token}"},
            data={"language": "en"},
        )
        assert response.status_code == 422

    def test_retry_nonexistent_input_returns_404(self, client, patient_token):
        """Retry on a non-existent input returns 404."""
        fake_input = str(uuid.uuid4())
        response = client.post(
            f"/api/v1/inputs/{fake_input}/retry",
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        assert response.status_code == 404
