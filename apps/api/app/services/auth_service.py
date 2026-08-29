import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.exceptions import ConflictException
from app.core.security import get_password_hash
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.db.models.patient import Patient
from app.schemas.auth import RegisterRequest
from app.services.audit_service import AuditService
from app.db.seed import hash_phone, mask_phone

class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)

    def register(self, payload: RegisterRequest, request_id: str) -> tuple[User, Patient]:
        """Atomically register a new patient and user identity."""
        phone_hash = hash_phone(payload.phone)
        
        # Check for existing patient by phone
        existing_patient = self.db.query(Patient).filter(Patient.phone_hash == phone_hash).first()
        if existing_patient:
            raise ConflictException("User with this phone number already exists")
            
        synthetic_email = f"{payload.phone.replace('+', '').strip()}@patient.medikiosk.local"
        
        # Check for existing user by email
        existing_user = self.db.query(User).filter(User.email == synthetic_email).first()
        if existing_user:
            raise ConflictException("User account already exists")

        now = datetime.now(timezone.utc)
        
        # Create User
        user = User(
            id=uuid.uuid4(),
            email=synthetic_email,
            password_hash=get_password_hash(payload.password),
            full_name=payload.name,
            role=UserRole.PATIENT,
            is_active=True,
        )
        self.db.add(user)
        
        # Create Patient
        patient = Patient(
            id=uuid.uuid4(),
            user_id=user.id,
            name=payload.name,
            phone_hash=phone_hash,
            phone_masked=mask_phone(payload.phone),
            language=payload.language,
            consent_version="1.0",
            consent_timestamp=now,
            consent_language=payload.language,
            consent_actor="patient",
        )
        self.db.add(patient)

        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            raise ConflictException("Database conflict during registration")

        # Audit events
        self.audit_service.record_event(
            action="PATIENT_REGISTERED",
            entity_type="patient",
            entity_id=str(patient.id),
            request_id=request_id,
            actor_id=user.id,
            actor_role=user.role.value,
            payload={"language": payload.language, "consent": payload.consent},
        )
        self.audit_service.record_event(
            action="CONSENT_GRANTED",
            entity_type="patient",
            entity_id=str(patient.id),
            request_id=request_id,
            actor_id=user.id,
            actor_role=user.role.value,
            payload={"version": "1.0", "language": payload.language, "actor": "patient"},
        )
        
        self.db.commit()
        return user, patient
