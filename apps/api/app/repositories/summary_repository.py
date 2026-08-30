import uuid
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.db.models.summary import Summary
from app.db.models.visit import Visit
from app.repositories.base_repository import BaseRepository


class SummaryRepository(BaseRepository[Summary]):
    """Repository handling persistence operations for AI Clinical Summaries."""

    def __init__(self, db: Session):
        super().__init__(Summary, db)

    def get_latest_by_visit_id(self, visit_id: uuid.UUID) -> Optional[Summary]:
        """Fetch the latest version of summary for a visit."""
        stmt = (
            select(Summary)
            .where(Summary.visit_id == visit_id)
            .order_by(Summary.version.desc())
            .limit(1)
        )
        return self.db.scalars(stmt).first()

    def get_by_visit_and_version(self, visit_id: uuid.UUID, version: int) -> Optional[Summary]:
        """Fetch a specific version of summary for a visit."""
        stmt = (
            select(Summary)
            .where(Summary.visit_id == visit_id)
            .where(Summary.version == version)
        )
        return self.db.scalars(stmt).first()

    def get_all_by_visit_id(self, visit_id: uuid.UUID) -> List[Summary]:
        """List all versions of summaries for a visit."""
        stmt = (
            select(Summary)
            .where(Summary.visit_id == visit_id)
            .order_by(Summary.version.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_next_version(self, visit_id: uuid.UUID) -> int:
        """Calculate the next incremental version number for a visit's summary."""
        stmt = select(func.max(Summary.version)).where(Summary.visit_id == visit_id)
        max_v = self.db.scalar(stmt)
        return (max_v or 0) + 1

    def get_patient_history_summaries(self, patient_id: uuid.UUID) -> List[Summary]:
        """Fetch latest summaries across all visits for a specific patient."""
        stmt = (
            select(Summary)
            .join(Visit, Summary.visit_id == Visit.id)
            .where(Visit.patient_id == patient_id)
            .order_by(Visit.service_date.desc(), Summary.version.desc())
        )
        return list(self.db.scalars(stmt).all())
