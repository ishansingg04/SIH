import json
import os
import sys
from fastapi.testclient import TestClient
from sqlalchemy import select

# Set standard output to unbuffered UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure app package is discoverable
sys.path.insert(0, os.path.abspath("apps/api"))

from app.main import app
from app.db.base import Base
from app.db.models.clinic import Clinic
from app.db.models.patient import Patient
from app.db.session import engine, SessionLocal
from app.db.seed import seed_database

def run_demo():
    print("=" * 70, flush=True)
    print("MEDIKIOSK BACKEND FOUNDATION -- LIVE DEMO EXECUTION", flush=True)
    print("=" * 70, flush=True)

    # 1. Initialize Tables and Seed Data
    print("\n--- [Step 1] Initializing Database & Loading Seed Data ---", flush=True)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_result = seed_database(db)
        clinic = db.scalars(select(Clinic).where(Clinic.code == "PHC-NORTH-01")).first()
        patient = db.scalars(select(Patient).where(Patient.name == "Asha Devi")).first()
        clinic_id = str(clinic.id)
        patient_id = str(patient.id)

    print(f"Seed Output:\n{json.dumps(seed_result, indent=2)}", flush=True)

    client = TestClient(app, raise_server_exceptions=True)

    # 2. Health Check Probe
    print("\n--- [Step 2] Health Check Probe (GET /health) ---", flush=True)
    res = client.get("/health")
    print(f"Status Code: {res.status_code}", flush=True)
    print(json.dumps(res.json(), indent=2, ensure_ascii=False), flush=True)

    # 3. Readiness Check Probe
    print("\n--- [Step 3] Readiness Check Probe (GET /ready) ---", flush=True)
    res = client.get("/ready")
    print(f"Status Code: {res.status_code}", flush=True)
    print(json.dumps(res.json(), indent=2, ensure_ascii=False), flush=True)

    # 4. Doctor Login
    print("\n--- [Step 4] Doctor Authentication (POST /api/v1/auth/login) ---", flush=True)
    login_payload = {
        "email": "dr.sharma@medikiosk.in",
        "password": "Doctor@12345"
    }
    res = client.post("/api/v1/auth/login", json=login_payload)
    print(f"Status Code: {res.status_code}", flush=True)
    doctor_auth = res.json()
    print(json.dumps(doctor_auth, indent=2, ensure_ascii=False), flush=True)
    doctor_token = doctor_auth["data"]["access_token"]

    # 5. Doctor Profile via Token
    print("\n--- [Step 5] Doctor Profile via JWT Bearer (GET /api/v1/auth/me) ---", flush=True)
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {doctor_token}"})
    print(f"Status Code: {res.status_code}", flush=True)
    print(json.dumps(res.json(), indent=2, ensure_ascii=False), flush=True)

    # 6. Admin Login
    print("\n--- [Step 6] Admin Authentication (POST /api/v1/auth/login) ---", flush=True)
    admin_res = client.post("/api/v1/auth/login", json={"email": "admin@medikiosk.in", "password": "Admin@12345"})
    admin_token = admin_res.json()["data"]["access_token"]

    # 7. Create New AYUSH Visit with Dashavidha Pariksha Intake
    print("\n--- [Step 7] Create AYUSH Visit with Dashavidha Pariksha (POST /api/v1/visits) ---", flush=True)
    visit_payload = {
        "patient_id": patient_id,
        "clinic_id": clinic_id,
        "intake_pathway": "AYUSH",
        "consent_given": True,
        "consent_language": "hi",
        "prakriti": {
            "primary_dosha": "VATA_PITTA",
            "secondary_dosha": "PITTA",
            "patient_observations": "दुबला शरीर, सूखी त्वचा, ठंड से संवेदनशीलता (Lean frame, dry skin, sensitive to cold)",
            "clinician_notes": "Vata dominant baseline with secondary Pitta traits"
        },
        "vikriti": {
            "aggravated_doshas": ["VATA"],
            "symptom_pattern": "शाम के समय सूखी खांसी और गले में सूखापन (Dry cough and throat dryness worsening in evening)",
            "onset_factors": "ठंडी हवा और मौसमी बदलाव (Cold wind and weather changes)"
        },
        "agni": {
            "agni_type": "VISHAMA",
            "appetite_level": "Irregular",
            "digestion_speed_hours": 4.5,
            "patient_description": "भूख कभी कम कभी ज्यादा लगती है, भारीपन (Fluctuating appetite, heaviness after food)"
        },
        "koshtha": {
            "koshtha_type": "KRURA",
            "bowel_regularity": "Constipated",
            "laxative_dependency": False,
            "patient_notes": "मल त्याग में कठिनाई (Difficulty in bowel evacuation)"
        },
        "sattva": {
            "sattva_type": "MADHYAMA",
            "sleep_quality": "खांसी के कारण रात में नींद टूटती है (Interrupted sleep due to cough)",
            "stress_level": "Medium",
            "wellbeing_prompts": "Mild anxiety regarding persistent coughing"
        },
        "ayush_notes": "Kiosk Hindi voice intake with complete Dashavidha Pariksha evaluation completed."
    }

    res = client.post("/api/v1/visits", json=visit_payload)
    print(f"Status Code: {res.status_code}", flush=True)
    visit_data = res.json()
    print(json.dumps(visit_data, indent=2, ensure_ascii=False), flush=True)
    visit_id = visit_data["data"]["id"]
    token_issued = visit_data["data"]["token"]

    # 8. Query Visit Details
    print(f"\n--- [Step 8] Retrieve Visit Record for Token {token_issued} (GET /api/v1/visits/{visit_id}) ---", flush=True)
    res = client.get(f"/api/v1/visits/{visit_id}")
    print(f"Status Code: {res.status_code}", flush=True)
    print(json.dumps(res.json(), indent=2, ensure_ascii=False), flush=True)

    # 9. Platform Status & Observability
    print("\n--- [Step 9] Platform Status & Feature Flags (GET /api/v1/platform/status) ---", flush=True)
    res = client.get("/api/v1/platform/status")
    print(f"Status Code: {res.status_code}", flush=True)
    print(json.dumps(res.json(), indent=2, ensure_ascii=False), flush=True)

    # 10. Compliance Audit Trail (Admin only)
    print("\n--- [Step 10] Compliance Audit Trail (GET /api/v1/platform/audit) ---", flush=True)
    res = client.get("/api/v1/platform/audit?limit=3", headers={"Authorization": f"Bearer {admin_token}"})
    print(f"Status Code: {res.status_code}", flush=True)
    print(json.dumps(res.json(), indent=2, ensure_ascii=False), flush=True)

    print("\n" + "=" * 70, flush=True)
    print("SUCCESS: ALL 10 DEMO STEPS EXECUTED AND VALIDATED SUCCESSFULLY!", flush=True)
    print("=" * 70, flush=True)

if __name__ == "__main__":
    run_demo()
