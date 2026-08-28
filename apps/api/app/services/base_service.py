from sqlalchemy.orm import Session


class BaseService:
    """Base domain service maintaining transaction boundary."""

    def __init__(self, db: Session):
        self.db = db
