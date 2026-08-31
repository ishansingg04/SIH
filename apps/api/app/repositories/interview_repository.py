import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models.interview import PatientInterview
from app.repositories.base_repository import BaseRepository


class InterviewRepository(BaseRepository[PatientInterview]):
    def __init__(self, db: Session):
        super().__init__(PatientInterview, db)

    def get_by_visit_id(self, visit_id: uuid.UUID) -> Optional[PatientInterview]:
        stmt = select(PatientInterview).where(PatientInterview.visit_id == visit_id)
        return self.db.scalars(stmt).first()
