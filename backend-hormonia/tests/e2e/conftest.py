"""
E2E Test Configuration and Fixtures
Provides shared fixtures for backend E2E tests
"""
import asyncio
import os
from typing import AsyncGenerator, Generator
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from faker import Faker

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.quiz import Quiz, QuizResponse, QuizTemplate
from app.models.flow import Flow, FlowState
from app.models.alert import Alert
from app.core.security import get_password_hash


# Test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/hormonia_e2e_test"
)

fake = Faker("pt_BR")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def engine():
    """Create test database engine"""
    engine = create_engine(TEST_DATABASE_URL, echo=False)

    # Drop all tables and recreate
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield engine

    # Cleanup
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(engine) -> Generator[Session, None, None]:
    """Create a new database session for each test"""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture(scope="function")
def override_get_db(db_session):
    """Override the get_db dependency"""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(override_get_db) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def admin_user(db_session) -> User:
    """Create admin user for testing"""
    user = User(
        email="admin@test.com",
        username="admin_test",
        full_name="Admin Test User",
        hashed_password=get_password_hash("Test@1234"),
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def medico_user(db_session) -> User:
    """Create medico user for testing"""
    user = User(
        email="medico@test.com",
        username="medico_test",
        full_name="Médico Test User",
        hashed_password=get_password_hash("Test@1234"),
        role=UserRole.MEDICO,
        is_active=True,
        is_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def patient_user(db_session) -> Patient:
    """Create patient for testing"""
    patient = Patient(
        email=fake.email(),
        name=fake.name(),
        phone=fake.phone_number(),
        cpf=fake.cpf(),
        birth_date=fake.date_of_birth(minimum_age=18, maximum_age=80),
        gender=fake.random_element(elements=("F", "M")),
        is_active=True,
        metadata_={
            "treatment_type": "Hormonal",
            "diagnosis_date": datetime.now().isoformat()
        }
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


@pytest.fixture
def quiz_template(db_session) -> QuizTemplate:
    """Create quiz template for testing"""
    template = QuizTemplate(
        title="E2E Test Quiz",
        description="Quiz template for E2E testing",
        questions=[
            {
                "id": "q1",
                "text": "Como você está se sentindo?",
                "type": "scale",
                "options": ["1", "2", "3", "4", "5"]
            },
            {
                "id": "q2",
                "text": "Teve algum efeito colateral?",
                "type": "multiple_choice",
                "options": ["Náusea", "Fadiga", "Dor", "Nenhum"]
            }
        ],
        is_active=True,
        version="1.0"
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


@pytest.fixture
def active_flow(db_session, patient_user) -> Flow:
    """Create active flow for testing"""
    flow = Flow(
        patient_id=patient_user.id,
        flow_type="monthly_quiz",
        state=FlowState.ACTIVE,
        current_step="quiz_pending",
        metadata_={
            "quiz_month": datetime.now().strftime("%Y-%m"),
            "reminder_sent": False
        }
    )
    db_session.add(flow)
    db_session.commit()
    db_session.refresh(flow)
    return flow


@pytest_asyncio.fixture
async def auth_headers_admin(async_client, admin_user) -> dict:
    """Get authentication headers for admin user"""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={
            "email": "admin@test.com",
            "password": "Test@1234"
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers_medico(async_client, medico_user) -> dict:
    """Get authentication headers for medico user"""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={
            "email": "medico@test.com",
            "password": "Test@1234"
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_evolution_api(monkeypatch):
    """Mock Evolution API for WhatsApp testing"""
    class MockEvolutionAPI:
        async def send_message(self, instance: str, number: str, message: str):
            return {"success": True, "message_id": "mock_message_123"}

        async def get_instance_status(self, instance: str):
            return {"status": "open", "connected": True}

    monkeypatch.setattr("app.services.whatsapp.EvolutionAPI", MockEvolutionAPI)
    return MockEvolutionAPI()


@pytest.fixture
def mock_clamav(monkeypatch):
    """Mock ClamAV for file scanning"""
    class MockClamAV:
        def scan_file(self, file_path: str):
            return {"status": "clean"}

    monkeypatch.setattr("app.services.security.ClamAVScanner", MockClamAV)
    return MockClamAV()


@pytest.fixture
def cleanup_uploads():
    """Cleanup uploaded files after tests"""
    yield

    # Cleanup logic
    upload_dir = "/tmp/test_uploads"
    if os.path.exists(upload_dir):
        import shutil
        shutil.rmtree(upload_dir)
