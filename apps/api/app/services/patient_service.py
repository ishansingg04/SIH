from sqlalchemy.orm import Session
from app.core.exceptions import NotFoundException
from app.db.models.patient import Patient
from app.db.models.user import User
from app.schemas.patient import PatientUpdate

class PatientService:
    def __init__(self, db: Session):
        self.db = db

    def get_my_profile(self, user: User) -> Patient:
        """Retrieve the patient profile for the currently authenticated user."""
        patient = self.db.query(Patient).filter(Patient.user_id == user.id).first()
        if not patient:
            raise NotFoundException("Patient profile not found for this user")
        return patient

    def update_my_profile(self, user: User, payload: PatientUpdate) -> Patient:
        """Update the safe profile fields for the authenticated user's patient profile."""
        patient = self.get_my_profile(user)
        
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(patient, key, value)
            
        self.db.commit()
        self.db.refresh(patient)
        return patient
