import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure app package is in path and force SQLite in-memory for testing
test_dir = os.path.dirname(os.path.abspath(__file__))
api_dir = os.path.abspath(os.path.join(test_dir, ".."))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["APP_ENV"] = "test"

from app.api.dependencies import get_db
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.db.seed import seed_database
from app.main import app


# Test database in memory
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all tables and seed test data before running tests."""
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        seed_database(session)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Transactional test session fixture that rolls back after test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden database session dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_token(db_session):
    user = db_session.scalars(select(User).where(User.email == "admin@medikiosk.in")).first()
    return create_access_token(
        subject=user.id,
        role=user.role.value,
        clinic_id=str(user.clinic_id) if user.clinic_id else None,
    )


@pytest.fixture
def doctor_token(db_session):
    user = db_session.scalars(select(User).where(User.email == "dr.sharma@medikiosk.in")).first()
    return create_access_token(
        subject=user.id,
        role=user.role.value,
        clinic_id=str(user.clinic_id) if user.clinic_id else None,
    )


@pytest.fixture
def patient_token(db_session):
    user = db_session.scalars(select(User).where(User.email == "asha.devi@medikiosk.in")).first()
    return create_access_token(
        subject=user.id,
        role=user.role.value,
        clinic_id=str(user.clinic_id) if user.clinic_id else None,
    )


@pytest.fixture
def operator_token(db_session):
    user = db_session.scalars(select(User).where(User.email == "operator@medikiosk.in")).first()
    return create_access_token(
        subject=user.id,
        role=user.role.value,
        clinic_id=str(user.clinic_id) if user.clinic_id else None,
    )


@pytest.fixture
def receptionist_token(db_session):
    user = db_session.scalars(select(User).where(User.email == "reception@medikiosk.in")).first()
    return create_access_token(
        subject=user.id,
        role=user.role.value,
        clinic_id=str(user.clinic_id) if user.clinic_id else None,
    )

