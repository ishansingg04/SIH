import hashlib
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.logging import logger
from app.core.security import get_password_hash
from app.db.models.ai_job import AIJob
from app.db.models.audit import AuditEvent
from app.db.models.clinic import Clinic
from app.db.models.enums import (
    AIJobStatus,
    AIJobType,
    AgniType,
    InputKind,
    InputStatus,
    IntakePathway,
    KoshthaType,
    PrakritiDosha,
    SattvaType,
    SummaryReviewStatus,
    UserRole,
    VisitStatus,
)
from app.db.models.input import VisitInput
from app.db.models.patient import Patient
from app.db.models.queue import QueueEntry
from app.db.models.summary import Summary
from app.db.models.user import User
from app.db.models.visit import Visit
from app.db.session import SessionLocal, engine
from app.db.base import Base


def hash_phone(phone: str) -> str:
    """Normalize and compute SHA256 hash of phone number."""
    normalized = "".join(filter(str.isdigit, phone))
    return hashlib.sha256(normalized.encode()).hexdigest()


def mask_phone(phone: str) -> str:
    """Mask middle digits of phone number for privacy."""
    normalized = "".join(filter(str.isdigit, phone))
    if len(normalized) >= 10:
        return f"+91-XXXXX-{normalized[-5:]}"
    return "+91-XXXXX-XXXXX"


def seed_database(db: Session, include_sample_summary: bool = False) -> Dict[str, Any]:
    """Populate initial baseline seed data for MediKiosk platform."""
    logger.info("Starting database seeding...")

    # 1. Create Demo Clinic
    clinic = db.scalars(select(Clinic).where(Clinic.code == "PHC-NORTH-01")).first()
    if not clinic:
        clinic = Clinic(
            id=uuid.uuid4(),
            name="Ayush Kalyan Community Health Center",
            code="PHC-NORTH-01",
            address="Sector 4, Rohini, New Delhi - 110085",
            is_active=True,
            ayush_enabled=True,
            supported_languages=["en", "hi"],
            queue_policy={"mode": "FIFO", "prefix": "A"},
        )
        db.add(clinic)
        db.flush()
        logger.info(f"Seeded Clinic: {clinic.name} ({clinic.code})")

    # 2. Seed Standard Users
    users_data = [
        ("admin@medikiosk.in", "Admin@12345", "Dr. Rajesh Gupta (Admin)", UserRole.CLINIC_ADMIN, clinic.id),
        ("dr.sharma@medikiosk.in", "Doctor@12345", "Dr. Priya Sharma", UserRole.DOCTOR, clinic.id),
        ("reception@medikiosk.in", "Reception@12345", "Ramesh Kumar (Reception)", UserRole.RECEPTIONIST, clinic.id),
        ("operator@medikiosk.in", "Operator@12345", "DevOps Operator", UserRole.SYSTEM_OPERATOR, None),
        ("asha.devi@medikiosk.in", "Patient@12345", "Asha Devi", UserRole.PATIENT, clinic.id),
    ]

    seeded_users = {}
    for email, pwd, name, role, c_id in users_data:
        user = db.scalars(select(User).where(User.email == email)).first()
        if not user:
            user = User(
                id=uuid.uuid4(),
                email=email,
                password_hash=get_password_hash(pwd),
                full_name=name,
                role=role,
                is_active=True,
                clinic_id=c_id,
            )
            db.add(user)
            db.flush()
            logger.info(f"Seeded User: {email} ({role.value})")
        seeded_users[email] = user

    # 3. Seed Demo Patient (Asha Devi)
    phone = "+919876543210"
    p_hash = hash_phone(phone)
    asha_user = seeded_users["asha.devi@medikiosk.in"]
    patient = db.scalars(select(Patient).where(Patient.phone_hash == p_hash)).first()
    if not patient:
        now_seed = datetime.now(timezone.utc)
        patient = Patient(
            id=uuid.uuid4(),
            user_id=asha_user.id,
            name="Asha Devi",
            phone_hash=p_hash,
            phone_masked=mask_phone(phone),
            dob=date(1988, 5, 14),
            gender="Female",
            language="hi",
            clinic_id=clinic.id,
            is_deleted=False,
            consent_version="1.0",
            consent_timestamp=now_seed,
            consent_language="hi",
            consent_actor="seed",
        )
        db.add(patient)
        db.flush()
        logger.info("Seeded Patient: Asha Devi")
    elif not patient.user_id:
        patient.user_id = asha_user.id
        db.flush()
        logger.info("Backfilled user_id for Asha Devi patient record")

    # 4. Seed Demo Visit (Token A12)
    now = datetime.now(timezone.utc)
    today = now.date()

    visit = db.scalars(
        select(Visit)
        .where(Visit.clinic_id == clinic.id)
        .where(Visit.token == "A12")
        .where(Visit.service_date == today)
    ).first()

    if not visit:
        visit = Visit(
            id=uuid.uuid4(),
            patient_id=patient.id,
            clinic_id=clinic.id,
            status=VisitStatus.WAITING,
            intake_pathway=IntakePathway.AYUSH,
            token="A12",
            service_date=today,
            consent_at=now,
            consent_language="hi",
            created_by=seeded_users["asha.devi@medikiosk.in"].id,
            prakriti={"primary_dosha": "VATA_PITTA"} if include_sample_summary else None,
            vikriti={"aggravated_doshas": ["VATA"]} if include_sample_summary else None,
            agni={"agni_type": "VISHAMA"} if include_sample_summary else None,
            koshtha={"koshtha_type": "KRURA"} if include_sample_summary else None,
            sattva={"sattva_type": "MADHYAMA"} if include_sample_summary else None,
            ayush_notes=None,
        )
        db.add(visit)
        db.flush()
        logger.info("Seeded Visit: Token A12 (AYUSH pathway)")

        # 5. Queue Entry
        queue_entry = QueueEntry(
            id=uuid.uuid4(),
            visit_id=visit.id,
            clinic_id=clinic.id,
            position=1,
            state=VisitStatus.WAITING,
        )
        db.add(queue_entry)

        # 6. Sample Summary for Testing Suite (only if requested)
        if include_sample_summary:
            summary = Summary(
                id=uuid.uuid4(),
                visit_id=visit.id,
                version=1,
                payload_json={
                    "patient_reported": {"chief_complaint": "Fever and cough", "duration": "2 days"},
                    "document_extracted": {"prior_prescriptions": ["Paracetamol 500mg"]},
                    "ayush_assessment": {"prakriti": "VATA_PITTA", "agni": "VISHAMA", "koshtha": "KRURA", "sattva": "MADHYAMA"},
                    "model_suggestions": [{"category": "clinical_consideration", "suggestion": "Rule out acute bronchitis"}],
                    "uncertainty_labels": [],
                },
                confidence=0.94,
                review_status=SummaryReviewStatus.DRAFT,
                doctor_notes=None,
            )
            db.add(summary)

        # 7. Initial Audit Event
        audit = AuditEvent(
            id=uuid.uuid4(),
            actor_id=seeded_users["asha.devi@medikiosk.in"].id,
            actor_role="patient",
            action="VISIT_CREATED",
            entity_type="visit",
            entity_id=str(visit.id),
            request_id="req_seed_initialization",
            payload_json={"token": "A12", "pathway": "AYUSH", "clinic_code": "PHC-NORTH-01"},
            created_at=now,
        )
        db.add(audit)


    db.commit()
    logger.info("Database seeding completed successfully.")

    return {
        "status": "seeded",
        "clinic_code": "PHC-NORTH-01",
        "demo_patient": "Asha Devi",
        "demo_token": "A12",
        "users_seeded": list(seeded_users.keys()),
    }


if __name__ == "__main__":
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        res = seed_database(session)
        print(f"Seed Result: {res}")
