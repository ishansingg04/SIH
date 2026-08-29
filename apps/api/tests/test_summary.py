import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from app.db.models.audit import AuditEvent
from app.db.models.enums import (
    AgniType,
    InputKind,
    InputStatus,
    IntakePathway,
    KoshthaType,
    PrakritiDosha,
    SattvaType,
    SummaryReviewStatus,
    VisitStatus,
)
from app.db.models.input import VisitInput
from app.db.models.patient import Patient
from app.db.models.summary import Summary
from app.db.models.visit import Visit
from app.integrations.summary import EvidencePacket, GroqSummaryAdapter, SummaryResult


def test_generate_summary_consented_visit_happy_path(client, doctor_token, db_session):
    """Test standard clinical summary generation for a consented visit."""
    # Find seed visit for Asha Devi
    visit = db_session.scalars(select(Visit)).first()
    assert visit is not None

    headers = {"Authorization": f"Bearer {doctor_token}"}
    response = client.post(f"/api/v1/visits/{visit.id}/summary", json={"force_refresh": False}, headers=headers)

    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    data = res_json["data"]
    assert data["visit_id"] == str(visit.id)
    assert data["version"] == 1
    assert data["review_status"] == SummaryReviewStatus.DRAFT.value
    assert data["confidence"] > 0.8
    assert "patient_reported" in data["payload_json"]
    assert "document_extracted" in data["payload_json"]
    assert "ayush_assessment" in data["payload_json"]
    assert "model_suggestions" in data["payload_json"]


def test_generate_summary_unconsented_visit_blocked(client, doctor_token, db_session):
    """AI-01 / Safety: Generation is blocked if patient consent is missing."""
    patient = db_session.scalars(select(Patient)).first()
    visit = db_session.scalars(select(Visit)).first()

    # Create unconsented visit
    unconsented_visit = Visit(
        patient_id=patient.id,
        clinic_id=visit.clinic_id,
        status=VisitStatus.WAITING,
        intake_pathway=IntakePathway.ALLOPATHIC,
        token="B01",
        service_date=datetime.now(timezone.utc).date(),
        consent_at=None,  # No consent
        consent_language="en",
    )
    db_session.add(unconsented_visit)
    db_session.commit()

    headers = {"Authorization": f"Bearer {doctor_token}"}
    response = client.post(f"/api/v1/visits/{unconsented_visit.id}/summary", json={}, headers=headers)

    assert response.status_code == 403
    res_json = response.json()
    assert res_json["success"] is False
    assert "consent" in res_json["error"]["message"].lower()


def test_ayush_dashavidha_pariksha_summary_provenance(client, doctor_token, db_session):
    """AI-02 / AYUSH: Verify Dashavidha Pariksha findings have explicit output labels."""
    patient = db_session.scalars(select(Patient)).first()
    visit = db_session.scalars(select(Visit)).first()

    ayush_visit = Visit(
        patient_id=patient.id,
        clinic_id=visit.clinic_id,
        status=VisitStatus.WAITING,
        intake_pathway=IntakePathway.AYUSH,
        token="AY01",
        service_date=datetime.now(timezone.utc).date(),
        consent_at=datetime.now(timezone.utc),
        consent_language="hi",
        prakriti={"primary_dosha": PrakritiDosha.PITTA.value, "details": "High metabolic rate"},
        vikriti={"aggravated_doshas": [PrakritiDosha.VATA.value], "symptom_pattern": "Restlessness"},
        agni={"agni_type": AgniType.TIKSHNA.value, "appetite_level": "High hunger"},
        koshtha={"koshtha_type": KoshthaType.MRIDU.value, "bowel_regularity": "Loose"},
        sattva={"sattva_type": SattvaType.PRAVARA.value, "sleep_quality": "Good"},
        ayush_notes="Patient prefers herbal formulations",
    )
    db_session.add(ayush_visit)
    db_session.commit()

    headers = {"Authorization": f"Bearer {doctor_token}"}
    response = client.post(f"/api/v1/visits/{ayush_visit.id}/summary", json={}, headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]

    ayush_assessment = data["payload_json"]["ayush_assessment"]
    assert ayush_assessment["prakriti"]["output_label"] == "AYUSH - Prakriti"
    assert ayush_assessment["vikriti"]["output_label"] == "AYUSH - Vikriti"
    assert ayush_assessment["agni"]["output_label"] == "AYUSH - Agni"
    assert ayush_assessment["koshtha"]["output_label"] == "AYUSH - Koshtha"
    assert ayush_assessment["sattva"]["output_label"] == "AYUSH - Sattva"


def test_summary_caching_and_force_refresh_versioning(client, doctor_token, db_session):
    """Test summary monotonic version increment on force_refresh."""
    visit = db_session.scalars(select(Visit)).first()
    headers = {"Authorization": f"Bearer {doctor_token}"}

    # First call: version 1
    resp1 = client.post(f"/api/v1/visits/{visit.id}/summary", json={"force_refresh": False}, headers=headers)
    assert resp1.status_code == 200
    v1_id = resp1.json()["data"]["id"]
    assert resp1.json()["data"]["version"] == 1

    # Second call without force_refresh: returns cached version 1
    resp2 = client.post(f"/api/v1/visits/{visit.id}/summary", json={"force_refresh": False}, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["data"]["id"] == v1_id
    assert resp2.json()["data"]["version"] == 1

    # Third call with force_refresh: generates version 2
    resp3 = client.post(f"/api/v1/visits/{visit.id}/summary", json={"force_refresh": True}, headers=headers)
    assert resp3.status_code == 200
    assert resp3.json()["data"]["version"] == 2
    assert resp3.json()["data"]["id"] != v1_id


def test_doctor_review_approve_workflow(client, doctor_token, db_session):
    """AI-03: Doctor review approval transitions status to CONFIRMED and logs audit event."""
    visit = db_session.scalars(select(Visit)).first()
    headers = {"Authorization": f"Bearer {doctor_token}"}

    # Generate draft summary
    gen_resp = client.post(f"/api/v1/visits/{visit.id}/summary", json={"force_refresh": True}, headers=headers)
    summary_id = gen_resp.json()["data"]["id"]

    # Approve summary
    review_resp = client.post(
        f"/api/v1/summaries/{summary_id}/review",
        json={"decision": "APPROVE", "doctor_notes": "All symptoms and findings verified in clinic."},
        headers=headers,
    )
    assert review_resp.status_code == 200
    data = review_resp.json()["data"]
    assert data["review_status"] == SummaryReviewStatus.CONFIRMED.value
    assert data["doctor_notes"] == "All symptoms and findings verified in clinic."
    assert data["reviewed_by"] is not None

    # Check audit trail
    audit = db_session.scalars(
        select(AuditEvent)
        .where(AuditEvent.action == "SUMMARY_REVIEWED")
        .where(AuditEvent.entity_id == summary_id)
    ).first()
    assert audit is not None
    assert audit.payload_json["decision"] == "APPROVE"
    assert audit.payload_json["new_status"] == "CONFIRMED"


def test_doctor_review_edit_workflow(client, doctor_token, db_session):
    """AI-03: Doctor review edit modifies payload and sets status to EDITED."""
    visit = db_session.scalars(select(Visit)).first()
    headers = {"Authorization": f"Bearer {doctor_token}"}

    gen_resp = client.post(f"/api/v1/visits/{visit.id}/summary", json={"force_refresh": True}, headers=headers)
    summary_id = gen_resp.json()["data"]["id"]

    edits = {
        "patient_reported": {
            "chief_complaint": "Persistent dry cough for 5 days (corrected by doctor)",
            "symptoms": ["Dry cough", "Sore throat"],
            "duration_days": 5,
        }
    }

    review_resp = client.post(
        f"/api/v1/summaries/{summary_id}/review",
        json={"decision": "EDIT", "edits": edits, "doctor_notes": "Corrected symptom duration after clinical inquiry."},
        headers=headers,
    )
    assert review_resp.status_code == 200
    data = review_resp.json()["data"]
    assert data["review_status"] == SummaryReviewStatus.EDITED.value
    assert data["payload_json"]["patient_reported"]["duration_days"] == 5


def test_doctor_review_reject_workflow(client, doctor_token, db_session):
    """AI-03: Doctor review rejection sets status to REJECTED."""
    visit = db_session.scalars(select(Visit)).first()
    headers = {"Authorization": f"Bearer {doctor_token}"}

    gen_resp = client.post(f"/api/v1/visits/{visit.id}/summary", json={"force_refresh": True}, headers=headers)
    summary_id = gen_resp.json()["data"]["id"]

    review_resp = client.post(
        f"/api/v1/summaries/{summary_id}/review",
        json={"decision": "REJECT", "doctor_notes": "Transcript audio contaminated with background noise."},
        headers=headers,
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["data"]["review_status"] == SummaryReviewStatus.REJECTED.value


def test_doctor_review_rbac_unauthorized_role_rejected(client, patient_token, db_session):
    """Security: Patient or unpermitted role cannot review clinical summaries."""
    summary = db_session.scalars(select(Summary)).first()
    if not summary:
        visit = db_session.scalars(select(Visit)).first()
        summary = Summary(visit_id=visit.id, version=1, payload_json={}, confidence=1.0)
        db_session.add(summary)
        db_session.commit()

    headers = {"Authorization": f"Bearer {patient_token}"}
    resp = client.post(
        f"/api/v1/summaries/{summary.id}/review",
        json={"decision": "APPROVE"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["success"] is False


def test_patient_longitudinal_history_assembly(client, doctor_token, db_session):
    """AI-04: Longitudinal history aggregates visits, medications, conditions across visits."""
    patient = db_session.scalars(select(Patient)).first()
    visit = db_session.scalars(select(Visit)).first()

    # Add an earlier visit with a prior prescription
    prior_visit = Visit(
        patient_id=patient.id,
        clinic_id=visit.clinic_id,
        status=VisitStatus.COMPLETED,
        intake_pathway=IntakePathway.ALLOPATHIC,
        token="A01",
        service_date=datetime(2026, 8, 1, tzinfo=timezone.utc).date(),
        consent_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    db_session.add(prior_visit)
    db_session.flush()

    prior_summary = Summary(
        visit_id=prior_visit.id,
        version=1,
        payload_json={
            "patient_reported": {"chief_complaint": "Seasonal allergy", "symptoms": ["Sneezing", "Watery eyes"]},
            "document_extracted": {"prior_prescriptions": ["Cetirizine 10mg", "Paracetamol 500mg"]},
            "ayush_assessment": {},
        },
        confidence=0.95,
        review_status=SummaryReviewStatus.CONFIRMED,
    )
    db_session.add(prior_summary)
    db_session.commit()

    headers = {"Authorization": f"Bearer {doctor_token}"}
    response = client.get(f"/api/v1/patients/{patient.id}/history", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]

    assert data["patient_id"] == str(patient.id)
    assert data["total_visits"] >= 2
    assert len(data["visits"]) >= 2

    # Check deduplicated medications
    med_names = [m["name"] for m in data["medications"]]
    assert "Cetirizine 10mg" in med_names
    assert "Paracetamol 500mg" in med_names


def test_get_visit_summary_detail_endpoint(client, doctor_token, db_session):
    """Test GET /api/v1/visits/{id}/summary returns structured detail and facts."""
    visit = db_session.scalars(select(Visit)).first()
    headers = {"Authorization": f"Bearer {doctor_token}"}

    # Ensure summary exists
    client.post(f"/api/v1/visits/{visit.id}/summary", json={}, headers=headers)

    response = client.get(f"/api/v1/visits/{visit.id}/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "READY"
    assert data["visit_id"] == str(visit.id)
    assert isinstance(data["facts"], list)
    assert len(data["facts"]) > 0


from app.integrations.summary import EvidencePacket, GeminiSummaryAdapter, GroqSummaryAdapter, SummaryResult


@pytest.mark.asyncio
async def test_groq_summary_adapter_graceful_fallback_on_missing_key():
    """AI-05: Groq adapter gracefully falls back to mock summary when key is absent."""
    adapter = GroqSummaryAdapter(api_key="")
    evidence = EvidencePacket(
        visit_id="test-visit-123",
        transcripts=["Patient complains of headache and fatigue"],
        document_texts=["Prior lab report normal"],
    )
    result = await adapter.summarize(evidence)
    assert isinstance(result, SummaryResult)
    assert result.confidence > 0.0
    assert "patient_reported" in result.model_dump()


@pytest.mark.asyncio
async def test_gemini_summary_adapter():
    """Test Gemini summary adapter contract (live when key present, fallback when absent)."""
    adapter = GeminiSummaryAdapter()
    evidence = EvidencePacket(
        visit_id="test-visit-gemini",
        transcripts=["Patient states: 3 din se gala kharab hai aur bukhar hai."],
        document_texts=["Prescription: Tab. Paracetamol 500mg"],
        ayush_intake={
            "prakriti": {"primary_dosha": "PITTA_KAPHA"},
            "vikriti": {"aggravated_doshas": ["PITTA"], "symptom_pattern": "Burning sensation in throat"},
            "agni": {"agni_type": "TIKSHNA", "appetite_level": "Sharp"},
            "koshtha": {"koshtha_type": "MRIDU", "bowel_regularity": "Regular"},
            "sattva": {"sattva_type": "PRAVARA", "sleep_quality": "Normal"},
        }
    )
    result = await adapter.summarize(evidence)
    assert isinstance(result, SummaryResult)
    assert result.confidence > 0.0
    assert "ayush_assessment" in result.model_dump()
    assert result.ayush_assessment["prakriti"]["output_label"] == "AYUSH - Prakriti"
    assert result.ayush_assessment["agni"]["output_label"] == "AYUSH - Agni"
