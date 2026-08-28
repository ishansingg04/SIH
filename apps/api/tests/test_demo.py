import json
import uuid
from sqlalchemy import select
from app.db.models.clinic import Clinic
from app.db.models.patient import Patient


def test_full_live_demo_journey(client, admin_token, doctor_token, db_session):
    """Executes the complete live sample journey covering health, auth, AYUSH intake, and audit trail."""
    print("\n" + "=" * 70)
    print("MEDIKIOSK LIVE END-TO-END DEMO EXECUTION")
    print("=" * 70)

    # 1. Health Probe
    print("\n--- [Step 1] Liveness Probe (GET /health) ---")
    res = client.get("/health")
    assert res.status_code == 200
    print(f"Status: {res.status_code}")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))

    # 2. Readiness Probe
    print("\n--- [Step 2] Readiness Probe (GET /ready) ---")
    res = client.get("/ready")
    assert res.status_code == 200
    print(f"Status: {res.status_code}")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))

    # 3. Doctor Authentication
    print("\n--- [Step 3] Doctor Authentication (POST /api/v1/auth/login) ---")
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "dr.sharma@medikiosk.in", "password": "Doctor@12345"},
    )
    assert res.status_code == 200
    login_data = res.json()
    print(f"Status: {res.status_code}")
    print(json.dumps(login_data, indent=2, ensure_ascii=False))
    doc_token = login_data["data"]["access_token"]

    # 4. Doctor Profile via Token
    print("\n--- [Step 4] Authenticated Doctor Profile (GET /api/v1/auth/me) ---")
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {doc_token}"})
    assert res.status_code == 200
    print(f"Status: {res.status_code}")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))

    # 5. Get Seeded Clinic & Patient Record
    clinic = db_session.scalars(select(Clinic).where(Clinic.code == "PHC-NORTH-01")).first()
    patient = db_session.scalars(select(Patient).where(Patient.name == "Asha Devi")).first()

    # 6. Create New AYUSH Intake Visit with Dashavidha Pariksha
    print("\n--- [Step 5] Create New AYUSH Visit with Dashavidha Pariksha (POST /api/v1/visits) ---")
    visit_payload = {
        "patient_id": str(patient.id),
        "clinic_id": str(clinic.id),
        "intake_pathway": "AYUSH",
        "consent_given": True,
        "consent_language": "hi",
        "prakriti": {
            "primary_dosha": "VATA_PITTA",
            "secondary_dosha": "PITTA",
            "patient_observations": "दुबला शरीर, सूखी त्वचा, ठंड से संवेदनशीलता (Lean frame, dry skin, sensitive to cold)",
            "clinician_notes": "Vata dominant baseline with secondary Pitta traits",
        },
        "vikriti": {
            "aggravated_doshas": ["VATA"],
            "symptom_pattern": "शाम के समय सूखी खांसी और गले में सूखापन (Evening dry cough & throat irritation)",
            "onset_factors": "ठंडी हवा का संपर्क (Cold air exposure)",
        },
        "agni": {
            "agni_type": "VISHAMA",
            "appetite_level": "Irregular",
            "digestion_speed_hours": 4.5,
            "patient_description": "भूख कभी कम कभी ज्यादा लगती है (Fluctuating appetite)",
        },
        "koshtha": {
            "koshtha_type": "KRURA",
            "bowel_regularity": "Constipated",
            "laxative_dependency": False,
            "patient_notes": "मल त्याग में कठिनाई (Hard stool tendency)",
        },
        "sattva": {
            "sattva_type": "MADHYAMA",
            "sleep_quality": "खांसी के कारण रात में नींद टूटती है (Disturbed sleep due to coughing)",
            "stress_level": "Medium",
            "wellbeing_prompts": "Mild anxiety regarding persistent symptoms",
        },
        "ayush_notes": "Kiosk Hindi voice intake with Dashavidha Pariksha completed.",
    }

    res = client.post("/api/v1/visits", json=visit_payload)
    assert res.status_code == 200
    visit_data = res.json()
    print(f"Status: {res.status_code}")
    print(json.dumps(visit_data, indent=2, ensure_ascii=False))
    visit_id = visit_data["data"]["id"]
    token_issued = visit_data["data"]["token"]

    # 7. Query Visit Details
    print(f"\n--- [Step 6] Query Visit Details for Token {token_issued} (GET /api/v1/visits/{visit_id}) ---")
    res = client.get(f"/api/v1/visits/{visit_id}")
    assert res.status_code == 200
    print(f"Status: {res.status_code}")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))

    # 8. Platform Observability Status
    print("\n--- [Step 7] Platform Status & Feature Flags (GET /api/v1/platform/status) ---")
    res = client.get("/api/v1/platform/status")
    assert res.status_code == 200
    print(f"Status: {res.status_code}")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))

    # 9. Compliance Audit Trail (Admin only)
    print("\n--- [Step 8] Compliance Audit Trail (GET /api/v1/platform/audit) ---")
    res = client.get("/api/v1/platform/audit?limit=3", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    print(f"Status: {res.status_code}")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))

    print("\n" + "=" * 70)
    print("ALL DEMO STEPS EXECUTED AND VALIDATED SUCCESSFULLY!")
    print("=" * 70)
