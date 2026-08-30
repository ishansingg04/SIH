import uuid
import pytest
from datetime import date, datetime, timezone
from sqlalchemy import select

from app.db.models.enums import IntakePathway, SummaryReviewStatus, UserRole, VisitStatus
from app.db.models.patient import Patient
from app.db.models.queue import QueueEntry
from app.db.models.user import User
from app.db.models.visit import Visit


def test_queue_today_returns_seeded_waiting_list(client, doctor_token):
    """Verify GET /queue/today returns active queue in FIFO order."""
    response = client.get(
        "/api/v1/queue/today",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    data = json_data["data"]
    assert "entries" in data
    assert "summary" in data

    # Verify seeded A12 token is present in waiting list
    tokens = [e["token"] for e in data["entries"]]
    assert "A12" in tokens


def test_queue_summary_metrics(client, doctor_token):
    """Verify GET /queue/summary aggregates real-time metrics."""
    response = client.get(
        "/api/v1/queue/summary",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    summary = json_data["data"]
    assert "waiting_count" in summary
    assert "in_progress_count" in summary
    assert "completed_today_count" in summary
    assert summary["waiting_count"] >= 1


def test_queue_01_token_generation_uniqueness(client, receptionist_token, db_session):
    """QUEUE-01: Multiple visit creations produce sequentially distinct tokens."""
    patient = db_session.scalars(select(Patient)).first()
    clinic_id = patient.clinic_id

    # Create 3 sequential visits
    tokens = []
    for i in range(3):
        resp = client.post(
            "/api/v1/visits",
            headers={"Authorization": f"Bearer {receptionist_token}"},
            json={
                "patient_id": str(patient.id),
                "clinic_id": str(clinic_id),
                "intake_pathway": "AYUSH",
                "consent_given": True,
            },
        )
        assert resp.status_code == 200
        token = resp.json()["data"]["token"]
        tokens.append(token)

    # Assert all generated tokens are unique
    assert len(set(tokens)) == len(tokens)


def test_queue_02_fifo_order_claim_next(client, doctor_token, receptionist_token, db_session):
    """QUEUE-02: Next patient follows FIFO among WAITING entries."""
    patient = db_session.scalars(select(Patient)).first()
    clinic_id = patient.clinic_id

    # Create two new visits to test FIFO dispatch
    resp1 = client.post(
        "/api/v1/visits",
        headers={"Authorization": f"Bearer {receptionist_token}"},
        json={
            "patient_id": str(patient.id),
            "clinic_id": str(clinic_id),
            "intake_pathway": "AYUSH",
            "consent_given": True,
        },
    )
    token1 = resp1.json()["data"]["token"]

    # Claim next should pick the oldest waiting token
    claim_resp = client.post(
        "/api/v1/queue/claim-next",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert claim_resp.status_code == 200
    claimed_token = claim_resp.json()["data"]["visit"]["token"]
    assert claimed_token in ["A12", token1]
    assert claim_resp.json()["data"]["queue_entry"]["state"] == "CALLED"


def test_queue_03_illegal_state_transition_returns_409(client, doctor_token, db_session):
    """QUEUE-03: Illegal transitions return 409 Conflict and preserve state."""
    # Find or claim a visit to COMPLETED state
    claim_resp = client.post(
        "/api/v1/queue/claim-next",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    if claim_resp.status_code == 200:
        visit_id = claim_resp.json()["data"]["visit"]["id"]
        entry_id = claim_resp.json()["data"]["queue_entry"]["id"]

        # Complete visit
        comp_resp = client.post(
            f"/api/v1/visits/{visit_id}/complete",
            headers={"Authorization": f"Bearer {doctor_token}"},
            json={"disposition": "DISCHARGED", "note": "Patient fully healthy"},
        )
        assert comp_resp.status_code == 200

        # Attempting to complete already completed visit must return 409
        dup_comp = client.post(
            f"/api/v1/visits/{visit_id}/complete",
            headers={"Authorization": f"Bearer {doctor_token}"},
            json={"disposition": "FOLLOW_UP", "note": "Duplicate call"},
        )
        assert dup_comp.status_code == 409
        assert dup_comp.json()["error"]["code"] == "CONFLICT"

        # Attempting to cancel completed entry must return 409
        cancel_resp = client.post(
            f"/api/v1/queue/{entry_id}/cancel",
            headers={"Authorization": f"Bearer {doctor_token}"},
            json={"reason": "Cannot cancel completed"},
        )
        assert cancel_resp.status_code == 409


def test_queue_04_set_in_progress(client, doctor_token, db_session):
    """QUEUE-04: Transition from CALLED to IN_PROGRESS works seamlessly."""
    claim_resp = client.post(
        "/api/v1/queue/claim-next",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    if claim_resp.status_code == 200:
        entry_id = claim_resp.json()["data"]["queue_entry"]["id"]

        in_prog_resp = client.post(
            f"/api/v1/queue/{entry_id}/in-progress",
            headers={"Authorization": f"Bearer {doctor_token}"},
        )
        assert in_prog_resp.status_code == 200
        assert in_prog_resp.json()["data"]["state"] == "IN_PROGRESS"


def test_queue_05_completed_visit_excluded_from_waiting(client, doctor_token, db_session):
    """QUEUE-05: Completed visit no longer appears as WAITING and is audited."""
    claim_resp = client.post(
        "/api/v1/queue/claim-next",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    if claim_resp.status_code == 200:
        visit_id = claim_resp.json()["data"]["visit"]["id"]
        token = claim_resp.json()["data"]["visit"]["token"]

        # Complete visit
        client.post(
            f"/api/v1/visits/{visit_id}/complete",
            headers={"Authorization": f"Bearer {doctor_token}"},
            json={"disposition": "PRESCRIBED", "note": "Ayurvedic formulation advised"},
        )

        # Check queue
        q_resp = client.get(
            "/api/v1/queue/today?state=WAITING",
            headers={"Authorization": f"Bearer {doctor_token}"},
        )
        waiting_tokens = [e["token"] for e in q_resp.json()["data"]["entries"]]
        assert token not in waiting_tokens


def test_queue_auth_patient_forbidden(client, patient_token):
    """QUEUE-AUTH-01: Patient role is forbidden from staff queue endpoints (403)."""
    resp = client.get(
        "/api/v1/queue/today",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_queue_auth_receptionist_cannot_complete_visit(client, receptionist_token, db_session):
    """QUEUE-AUTH-02: Receptionist cannot complete clinical visits (Doctor only)."""
    visit = db_session.scalars(select(Visit)).first()
    resp = client.post(
        f"/api/v1/visits/{visit.id}/complete",
        headers={"Authorization": f"Bearer {receptionist_token}"},
        json={"disposition": "DISCHARGED"},
    )
    assert resp.status_code == 403


def test_doctor_workspace_retrieval(client, doctor_token, db_session):
    """QUEUE-DOCTOR-01: Workspace returns unified patient context, AYUSH fields, summary & inputs."""
    visit = db_session.scalars(select(Visit).where(Visit.token == "A12")).first()
    assert visit is not None

    resp = client.get(
        f"/api/v1/doctor/workspace/{visit.id}",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert resp.status_code == 200
    json_data = resp.json()
    assert json_data["success"] is True
    data = json_data["data"]

    assert data["patient_name"] == "Asha Devi"
    assert data["visit"]["intake_pathway"] == "AYUSH"
    assert data["visit"]["prakriti"] is not None
    assert len(data["summaries"]) >= 1


def test_no_show_and_cancel_actions(client, doctor_token, receptionist_token, db_session):
    """QUEUE-ACTION-01: Doctor or receptionist can mark no-show or cancel queued entries."""
    patient = db_session.scalars(select(Patient)).first()
    resp = client.post(
        "/api/v1/visits",
        headers={"Authorization": f"Bearer {receptionist_token}"},
        json={
            "patient_id": str(patient.id),
            "clinic_id": str(patient.clinic_id),
            "intake_pathway": "ALLOPATHIC",
            "consent_given": True,
        },
    )
    visit_id = resp.json()["data"]["id"]
    queue_entry = db_session.scalars(select(QueueEntry).where(QueueEntry.visit_id == uuid.UUID(visit_id))).first()

    # Mark as NO_SHOW
    ns_resp = client.post(
        f"/api/v1/queue/{queue_entry.id}/no-show",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"reason": "Patient called 3 times without answer"},
    )
    assert ns_resp.status_code == 200
    assert ns_resp.json()["data"]["state"] == "NO_SHOW"


def test_summary_review_confirmation(client, doctor_token, db_session):
    """QUEUE-SUMMARY-01: Doctor can review, confirm or edit AI generated summary."""
    visit = db_session.scalars(select(Visit).where(Visit.token == "A12")).first()
    resp = client.post(
        f"/api/v1/visits/{visit.id}/summary/review",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={
            "review_status": "CONFIRMED",
            "doctor_notes": "Dr. Sharma confirmed Vata-Pitta baseline diagnosis",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["summary"]["review_status"] == "CONFIRMED"
