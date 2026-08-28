import pytest
from sqlalchemy import select
from app.db.models.clinic import Clinic
from app.db.models.enums import AgniType, IntakePathway, KoshthaType, PrakritiDosha, SattvaType, VisitStatus
from app.db.models.patient import Patient
from app.integrations.summary import EvidencePacket, get_summary_adapter


def test_ayush_intake_visit_creation_and_fields(client, db_session):
    """Verify AYUSH Dashavidha Pariksha fields are saved and retrieved in typed structure."""
    clinic = db_session.scalars(select(Clinic)).first()
    patient = db_session.scalars(select(Patient)).first()

    visit_payload = {
        "patient_id": str(patient.id),
        "clinic_id": str(clinic.id),
        "intake_pathway": "AYUSH",
        "consent_given": True,
        "consent_language": "hi",
        "prakriti": {
            "primary_dosha": "VATA_PITTA",
            "secondary_dosha": "PITTA",
            "patient_observations": "Lean constitution, dry skin, sensitive to cold winds",
            "clinician_notes": "Clinician confirms Vata dominant prakriti",
        },
        "vikriti": {
            "aggravated_doshas": ["VATA"],
            "symptom_pattern": "Dry persistent cough and throat tickle",
            "onset_factors": "Cold drinks and wind exposure",
        },
        "agni": {
            "agni_type": "VISHAMA",
            "appetite_level": "Irregular",
            "digestion_speed_hours": 4.0,
            "patient_description": "भूख अनियमित रहती है (Fluctuating hunger)",
        },
        "koshtha": {
            "koshtha_type": "KRURA",
            "bowel_regularity": "Constipated",
            "laxative_dependency": False,
            "patient_notes": "मल त्याग में कठिनाई (Hard stool)",
        },
        "sattva": {
            "sattva_type": "MADHYAMA",
            "sleep_quality": "Interrupted by coughing fits",
            "stress_level": "Medium",
            "wellbeing_prompts": "Mildly anxious about chest discomfort",
        },
        "ayush_notes": "Kiosk AYUSH Hindi intake verified by patient.",
    }

    response = client.post("/api/v1/visits", json=visit_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]

    assert data["intake_pathway"] == "AYUSH"
    assert data["status"] == "WAITING"
    assert data["token"] is not None

    # Verify Dashavidha Pariksha fields
    assert data["prakriti"]["primary_dosha"] == "VATA_PITTA"
    assert data["vikriti"]["aggravated_doshas"] == ["VATA"]
    assert data["agni"]["agni_type"] == "VISHAMA"
    assert data["koshtha"]["koshtha_type"] == "KRURA"
    assert data["sattva"]["sattva_type"] == "MADHYAMA"
    assert data["ayush_notes"] == "Kiosk AYUSH Hindi intake verified by patient."


@pytest.mark.asyncio
async def test_ayush_summary_adapter_contract():
    """Verify AI summary adapter preserves AYUSH assessment with explicit provenance."""
    adapter = get_summary_adapter()
    evidence = EvidencePacket(
        visit_id="test_visit_123",
        transcripts=["मुझे दो दिन से बुखार और खांसी है"],
        ayush_intake={
            "prakriti": {"primary_dosha": "VATA_PITTA"},
            "vikriti": {"aggravated_doshas": ["VATA"], "symptom_pattern": "Dry cough"},
            "agni": {"agni_type": "VISHAMA"},
            "koshtha": {"koshtha_type": "KRURA"},
            "sattva": {"sattva_type": "MADHYAMA"},
        },
    )

    summary_result = await adapter.summarize(evidence)
    assert "ayush_assessment" in summary_result.model_dump()
    assert summary_result.ayush_assessment["prakriti"]["primary_dosha"] == "VATA_PITTA"
    assert summary_result.ayush_assessment["agni"]["agni_type"] == "VISHAMA"
    assert len(summary_result.model_suggestions) > 0
    assert len(summary_result.uncertainty_labels) > 0
