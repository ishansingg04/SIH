from sqlalchemy import select
from app.db.models.audit import AuditEvent
from app.db.models.clinic import Clinic
from app.db.models.enums import IntakePathway, UserRole, VisitStatus
from app.db.models.patient import Patient
from app.db.models.queue import QueueEntry
from app.db.models.summary import Summary
from app.db.models.user import User
from app.db.models.visit import Visit


def test_seed_data_integrity(db_session):
    """Verify all required seed entities are present and relations match."""
    # 1. Clinic
    clinic = db_session.scalars(select(Clinic).where(Clinic.code == "PHC-NORTH-01")).first()
    assert clinic is not None
    assert clinic.ayush_enabled is True
    assert "hi" in clinic.supported_languages

    # 2. Users
    roles_seeded = {u.role for u in db_session.scalars(select(User)).all()}
    assert UserRole.CLINIC_ADMIN in roles_seeded
    assert UserRole.DOCTOR in roles_seeded
    assert UserRole.RECEPTIONIST in roles_seeded
    assert UserRole.SYSTEM_OPERATOR in roles_seeded
    assert UserRole.PATIENT in roles_seeded

    # 3. Patient
    patient = db_session.scalars(select(Patient).where(Patient.name == "Asha Devi")).first()
    assert patient is not None
    assert patient.language == "hi"
    assert patient.phone_masked is not None

    # 4. Visit
    visit = db_session.scalars(select(Visit).where(Visit.token == "A12")).first()
    assert visit is not None
    assert visit.intake_pathway == IntakePathway.AYUSH
    assert visit.status == VisitStatus.WAITING
    assert visit.prakriti is not None
    assert visit.agni is not None
    assert visit.koshtha is not None
    assert visit.sattva is not None

    # 5. Queue Entry
    queue_entry = db_session.scalars(select(QueueEntry).where(QueueEntry.visit_id == visit.id)).first()
    assert queue_entry is not None
    assert queue_entry.state == VisitStatus.WAITING

    # 6. Summary
    summary = db_session.scalars(select(Summary).where(Summary.visit_id == visit.id)).first()
    assert summary is not None
    assert "ayush_assessment" in summary.payload_json

    # 7. Audit Event
    audit = db_session.scalars(select(AuditEvent).where(AuditEvent.entity_id == str(visit.id))).first()
    assert audit is not None
    assert audit.action == "VISIT_CREATED"
