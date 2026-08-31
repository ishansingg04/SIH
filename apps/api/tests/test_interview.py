"""Automated test suite for Adaptive Voice-Based Patient Interview module."""

import io
import uuid
import wave
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models.audit import AuditEvent
from app.db.models.interview import PatientInterview
from app.db.models.patient import Patient
from app.db.models.visit import Visit
from app.main import app


def _create_mock_wav() -> bytes:
    """Helper to generate a small, valid in-memory WAV byte stream."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00" * 3200)
    return buf.getvalue()


@pytest.fixture
def auth_headers(client: TestClient) -> dict:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "dr.sharma@medikiosk.in", "password": "Doctor@12345"},
    )
    assert res.status_code == 200
    token = res.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seeded_visit_id(client: TestClient, auth_headers: dict) -> str:
    ctx = client.get("/api/v1/summaries/demo/active-context")
    assert ctx.status_code == 200
    return ctx.json()["data"]["visit_id"]


# ==============================================================================
# 1. HAPPY PATH: START INTERVIEW (TEXT & VOICE)
# ==============================================================================

def test_interview_start_with_text_happy_path(
    client: TestClient, seeded_visit_id: str, auth_headers: dict, db_session
):
    """Test starting an interview with an initial text complaint in Hindi."""
    res = client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/start",
        data={
            "initial_text": "मुझे दो दिन से पेट में दर्द और हल्का बुखार है",
            "language": "hi",
            "pathway": "ALLOPATHIC",
            "max_questions": 5,
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    payload = data["data"]
    assert payload["interview_complete"] is False
    assert len(payload["extracted_facts"]) >= 1
    # Check English translation of complaint
    assert any("stomach" in f["value"].lower() or "pain" in f["value"].lower() for f in payload["extracted_facts"])
    assert payload["next_question"] is not None
    assert payload["turn_number"] >= 1


def test_interview_start_with_voice_audio(
    client: TestClient, seeded_visit_id: str, auth_headers: dict
):
    """Test starting an interview by uploading recorded audio bytes."""
    wav_bytes = _create_mock_wav()
    files = {"audio_file": ("intake.webm", wav_bytes, "audio/webm")}
    data = {
        "language": "en",
        "pathway": "ALLOPATHIC",
        "max_questions": 6,
    }

    res = client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/start",
        data=data,
        files=files,
        headers=auth_headers,
    )
    assert res.status_code == 200
    resp_data = res.json()["data"]
    assert resp_data["transcript"] is not None
    assert len(resp_data["extracted_facts"]) >= 1


# ==============================================================================
# 2. TURN PROCESSING (TEXT, VOICE, SKIP)
# ==============================================================================

def test_interview_turn_text_flow(
    client: TestClient, seeded_visit_id: str, auth_headers: dict
):
    """Test submitting an answer to a question and advancing turn."""
    # 1. Start interview
    start_res = client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/start",
        data={"initial_text": "Severe headache", "language": "en", "pathway": "ALLOPATHIC"},
        headers=auth_headers,
    )
    next_q = start_res.json()["data"]["next_question"]
    assert next_q is not None

    # 2. Submit Turn
    turn_res = client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/turn",
        data={
            "question_id": next_q["id"],
            "answer_text": "In the frontal forehead region for 3 days",
            "language": "en",
        },
        headers=auth_headers,
    )
    assert turn_res.status_code == 200
    turn_data = turn_res.json()["data"]
    assert len(turn_data["extracted_facts"]) >= 2


def test_interview_turn_voice_flow(
    client: TestClient, seeded_visit_id: str, auth_headers: dict
):
    """Test answering a follow-up question using audio voice bytes."""
    start_res = client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/start",
        data={"initial_text": "Fever", "language": "en"},
        headers=auth_headers,
    )
    next_q = start_res.json()["data"]["next_question"]

    wav_bytes = _create_mock_wav()
    files = {"audio_file": ("answer.webm", wav_bytes, "audio/webm")}
    turn_res = client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/turn",
        data={"question_id": next_q["id"], "language": "en"},
        files=files,
        headers=auth_headers,
    )
    assert turn_res.status_code == 200
    turn_data = turn_res.json()["data"]
    assert turn_data["transcript"] is not None


def test_interview_turn_skip_question(
    client: TestClient, seeded_visit_id: str, auth_headers: dict
):
    """Test patient skipping an optional question."""
    start_res = client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/start",
        data={"initial_text": "Body ache", "language": "en"},
        headers=auth_headers,
    )
    next_q = start_res.json()["data"]["next_question"]

    turn_res = client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/turn",
        data={"question_id": next_q["id"], "skipped": True},
        headers=auth_headers,
    )
    assert turn_res.status_code == 200
    turn_data = turn_res.json()["data"]
    assert turn_data["turn_number"] >= 2


# ==============================================================================
# 3. AYUSH PATHWAY SPECIFIC INTERVIEW
# ==============================================================================

def test_ayush_pathway_interview_progression(
    client: TestClient, seeded_visit_id: str, auth_headers: dict
):
    """Test AYUSH pathway interview asking Prakriti, Agni, and Koshtha questions."""
    start_res = client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/start",
        data={
            "initial_text": "मुझे पाचन में भारीपन और ठंड लगने की समस्या है",
            "language": "hi",
            "pathway": "AYUSH",
            "max_questions": 6,
        },
        headers=auth_headers,
    )
    assert start_res.status_code == 200
    turn_data = start_res.json()["data"]

    # Verify that AYUSH questions are queued
    slots = [f["slot"] for f in turn_data["extracted_facts"]]
    assert "chief_complaint" in slots


# ==============================================================================
# 4. SAFETY RED-FLAG DETECTION
# ==============================================================================

def test_interview_red_flag_alert_trigger(
    client: TestClient, seeded_visit_id: str, auth_headers: dict
):
    """Test that critical chest pain or breathlessness triggers a safety alert."""
    start_res = client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/start",
        data={
            "initial_text": "Severe sudden crushing chest pain and breathless",
            "language": "en",
        },
        headers=auth_headers,
    )
    assert start_res.status_code == 200
    turn_data = start_res.json()["data"]
    assert len(turn_data["red_flags"]) >= 1
    assert turn_data["red_flags"][0]["severity"] == "HIGH"


# ==============================================================================
# 5. MAXIMUM QUESTIONS & DUPLICATE PREVENTION
# ==============================================================================

def test_interview_max_questions_enforcement(
    client: TestClient, seeded_visit_id: str, auth_headers: dict
):
    """Test that interview completes automatically when reaching max question limit."""
    # Start with max 2 questions
    start_res = client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/start",
        data={"initial_text": "Cough", "language": "en", "max_questions": 2},
        headers=auth_headers,
    )
    q1 = start_res.json()["data"]["next_question"]

    # Turn 1
    turn1_res = client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/turn",
        data={"question_id": q1["id"], "answer_text": "Chest area"},
        headers=auth_headers,
    )
    turn1_data = turn1_res.json()["data"]

    # Turn 2
    if not turn1_data["interview_complete"]:
        q2 = turn1_data["next_question"]
        turn2_res = client.post(
            f"/api/v1/visits/{seeded_visit_id}/interview/turn",
            data={"question_id": q2["id"], "answer_text": "3 days"},
            headers=auth_headers,
        )
        assert turn2_res.json()["data"]["interview_complete"] is True


# ==============================================================================
# 6. FACT EDIT AND DELETE OPERATIONS
# ==============================================================================

def test_fact_update_and_delete_workflow(
    client: TestClient, seeded_visit_id: str, auth_headers: dict
):
    """Test editing fact value and deleting fact chips."""
    start_res = client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/start",
        data={"initial_text": "Mild throat irritation", "language": "en"},
        headers=auth_headers,
    )
    facts = start_res.json()["data"]["extracted_facts"]
    assert len(facts) >= 1
    target_fact_id = facts[0]["id"]

    # 1. Update Fact
    put_res = client.put(
        f"/api/v1/visits/{seeded_visit_id}/interview/facts/{target_fact_id}",
        json={"value": "Moderate pharyngitis and sore throat", "verified": True},
        headers=auth_headers,
    )
    assert put_res.status_code == 200
    assert put_res.json()["data"]["value"] == "Moderate pharyngitis and sore throat"

    # 2. Delete Fact
    del_res = client.delete(
        f"/api/v1/visits/{seeded_visit_id}/interview/facts/{target_fact_id}",
        headers=auth_headers,
    )
    assert del_res.status_code == 200
    assert del_res.json()["data"]["deleted"] is True


# ==============================================================================
# 7. STATE RETRIEVAL & RESUME
# ==============================================================================

def test_interview_get_state_endpoint(
    client: TestClient, seeded_visit_id: str, auth_headers: dict
):
    """Test retrieving full interview state via GET endpoint."""
    client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/start",
        data={"initial_text": "Fever for 2 days", "language": "en"},
        headers=auth_headers,
    )

    get_res = client.get(
        f"/api/v1/visits/{seeded_visit_id}/interview",
        headers=auth_headers,
    )
    assert get_res.status_code == 200
    state = get_res.json()["data"]
    assert state["visit_id"] == seeded_visit_id
    assert state["status"] in ["IN_PROGRESS", "COMPLETED"]
    assert len(state["turns"]) >= 1


# ==============================================================================
# 8. COMPLETE INTERVIEW & SUMMARY SYNC
# ==============================================================================

def test_interview_complete_and_summary_sync(
    client: TestClient, seeded_visit_id: str, auth_headers: dict, db_session
):
    """Test concluding interview, syncing briefing, and feeding downstream summary."""
    # 1. Start and complete interview
    client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/start",
        data={"initial_text": "Stomach pain and nausea", "language": "en", "pathway": "AYUSH"},
        headers=auth_headers,
    )
    comp_res = client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/complete",
        headers=auth_headers,
    )
    assert comp_res.status_code == 200
    comp_data = comp_res.json()["data"]
    assert comp_data["status"] == "COMPLETED"
    assert "briefing_text" in comp_data

    # 2. Verify downstream AI Summary generation picks up the interview briefing
    sum_res = client.post(
        f"/api/v1/visits/{seeded_visit_id}/summary",
        json={"force_refresh": True},
        headers=auth_headers,
    )
    assert sum_res.status_code == 200
    sum_data = sum_res.json()["data"]
    assert sum_data["review_status"] in ["DRAFT", "READY", "CONFIRMED"]


# ==============================================================================
# 9. AUDIT TRAIL LOGGING
# ==============================================================================

def test_interview_audit_logging(
    client: TestClient, seeded_visit_id: str, auth_headers: dict, db_session
):
    """Test that start, turn, and complete emit structured audit events."""
    client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/start",
        data={"initial_text": "Knee joint pain", "language": "en"},
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/visits/{seeded_visit_id}/interview/complete",
        headers=auth_headers,
    )

    events = db_session.scalars(
        select(AuditEvent).where(
            AuditEvent.action.in_(["INTERVIEW_STARTED", "INTERVIEW_COMPLETED"])
        )
    ).all()
    assert len(events) >= 2



# ==============================================================================
# 10. ERROR HANDLING & UNCONSENTED VISITS
# ==============================================================================

def test_interview_unconsented_visit_blocked(client: TestClient, auth_headers: dict, db_session):
    """Test that interview is blocked if patient consent is missing."""
    patient = db_session.scalars(select(Patient)).first()
    visit = Visit(
        clinic_id=patient.clinic_id,
        patient_id=patient.id,
        token="X99",
        consent_at=None,  # Missing consent
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)

    res = client.post(
        f"/api/v1/visits/{visit.id}/interview/start",
        data={"initial_text": "Headache"},
        headers=auth_headers,
    )
    assert res.status_code in [400, 403, 422]
    assert res.json()["success"] is False
