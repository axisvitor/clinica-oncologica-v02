"""
Shared pytest fixtures for all tests.

This module provides common fixtures used across unit and integration tests,
including database sessions, test users, authentication tokens, and mock clients.
"""
import os
import json
from datetime import datetime, timedelta
from typing import Generator
from uuid import uuid4

import pytest
from dotenv import load_dotenv

from sqlalchemy import create_engine, event, TypeDecorator, Text, String
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB, INET
from fastapi.testclient import TestClient

# Load environment variables before importing application modules so
# pydantic Settings finds SECRET_KEY, DATABASE_URL, etc.
_env_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".env")
)
if os.path.exists(_env_path):
    load_dotenv(_env_path)

from app.db.base import Base  # Use the same Base as root conftest.py
from app.models.user import User, UserRole
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.utils.security import get_password_hash
from app.main import app
from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user, TEST_TOKEN_REGISTRY
from tests.utils.sync_executor import SyncExecutor


# ============================================================================
# SQLite JSONB Compatibility
# ============================================================================

class JSONBCompat(TypeDecorator):
    """
    SQLite-compatible JSONB type.

    Converts PostgreSQL JSONB to SQLite TEXT with JSON serialization.
    This allows tests to run with SQLite in-memory database while
    production uses PostgreSQL JSONB.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert Python dict to JSON string for storage."""
        if value is not None:
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        """Convert JSON string back to Python dict."""
        if value is not None:
            return json.loads(value)
        return value


class INETCompat(TypeDecorator):
    """
    SQLite-compatible INET type.

    Converts PostgreSQL INET (IP address) to SQLite TEXT.
    This allows tests to run with SQLite in-memory database while
    production uses PostgreSQL INET.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert IP address to string for storage."""
        if value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        """Return IP address as string."""
        return value


# ============================================================================
# Database Fixtures
# ============================================================================

def _replace_postgres_types_with_sqlite(engine):
    """
    Replace PostgreSQL-specific types with SQLite-compatible types.

    This function is called before table creation to convert PostgreSQL
    types (JSONB, INET) to SQLite-compatible types (TEXT) with proper
    serialization/deserialization.

    Conversions:
    - JSONB → JSONBCompat (TEXT with JSON serialization)
    - INET → INETCompat (TEXT for IP addresses)
    """
    from sqlalchemy import inspect

    # Iterate through all tables in metadata
    for table in Base.metadata.tables.values():
        for column in table.columns:
            # Replace JSONB with JSONBCompat for SQLite
            if isinstance(column.type, JSONB):
                column.type = JSONBCompat()
            # Replace INET with INETCompat for SQLite
            elif isinstance(column.type, INET):
                column.type = INETCompat()


@pytest.fixture(scope="session")
def test_engine():
    """
    Create a session-scoped test database engine.

    This engine is created once per test session and reused across all tests.
    Using transactions for test isolation instead of recreating the engine.
    """
    # Create in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Replace PostgreSQL types with SQLite-compatible types
    _replace_postgres_types_with_sqlite(engine)

    # Drop and recreate all tables to ensure clean state
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield engine

    # Drop all tables at session end
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """
    Create a fresh database session for each test using transactions.

    Uses transaction rollback for test isolation instead of recreating tables.
    This is much faster and avoids index collision errors.
    """
    # Start a new connection and transaction
    connection = test_engine.connect()
    transaction = connection.begin()

    # Create session bound to this transaction
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=connection,
    )
    session = TestingSessionLocal()

    yield session

    # Rollback transaction to clean up test data
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def db(db_session: Session) -> Generator[Session, None, None]:
    """
    Backward-compatible fixture alias.

    Some legacy contract tests expect a ``db`` fixture; reuse the scoped
    SQLite session so they continue to run without modification.
    """
    yield db_session


@pytest.fixture(scope="function")
def client(db_session: Session) -> TestClient:
    """
    Create a FastAPI test client with database session override.
    
    Args:
        db_session: Database session fixture
        
    Returns:
        TestClient instance with overridden database dependency
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


# ============================================================================
# User Fixtures
# ============================================================================

def create_test_user(
    db_session: Session,
    email: str = "test@example.com",
    password: str = "testpass123",
    full_name: str = "Test User",
    role: UserRole = UserRole.DOCTOR,
    is_active: bool = True,
    **kwargs
) -> User:
    """
    Create a test user in the database.
    
    Args:
        db_session: Database session
        email: User email (default: test@example.com)
        password: User password (default: testpass123)
        full_name: User full name (default: Test User)
        role: User role (default: DOCTOR)
        is_active: Whether user is active (default: True)
        **kwargs: Additional user attributes
        
    Returns:
        Created User instance
        
    Example:
        user = create_test_user(db_session, email="doctor@test.com")
    """
    user = User(
        id=kwargs.get('id', uuid4()),
        email=email,
        hashed_password=get_password_hash(password),
        full_name=full_name,
        role=role,
        is_active=is_active,
        created_at=kwargs.get('created_at', datetime.utcnow()),
        **{k: v for k, v in kwargs.items() if k not in ['id', 'created_at']}
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_user(db_session: Session) -> User:
    """Create a single sample user for contract tests."""
    return create_test_user(
        db_session,
        email=f"sample_user_{uuid4().hex[:6]}@test.com",
        full_name="Sample User",
        role=UserRole.DOCTOR,
    )


@pytest.fixture
def sample_users(db_session: Session) -> list[User]:
    """Create multiple users with different statuses."""
    users = [
        create_test_user(
            db_session,
            email=f"sample_doctor_{uuid4().hex[:6]}@test.com",
            full_name="Doctor Active",
            role=UserRole.DOCTOR,
            is_active=True,
        ),
        create_test_user(
            db_session,
            email=f"sample_admin_{uuid4().hex[:6]}@test.com",
            full_name="Admin Active",
            role=UserRole.ADMIN,
            is_active=True,
        ),
        create_test_user(
            db_session,
            email=f"sample_inactive_{uuid4().hex[:6]}@test.com",
            full_name="Doctor Inactive",
            role=UserRole.DOCTOR,
            is_active=False,
        ),
    ]
    return users


# ============================================================================
# Patient Fixtures
# ============================================================================
def create_admin_user(
    db_session: Session,
    email: str = "admin@example.com",
    password: str = "adminpass123",
    full_name: str = "Admin User",
    **kwargs
) -> User:
    """
    Create an admin user in the database.
    
    Args:
        db_session: Database session
        email: Admin email (default: admin@example.com)
        password: Admin password (default: adminpass123)
        full_name: Admin full name (default: Admin User)
        **kwargs: Additional user attributes
        
    Returns:
        Created User instance with ADMIN role
        
    Example:
        admin = create_admin_user(db_session)
    """
    return create_test_user(
        db_session=db_session,
        email=email,
        password=password,
        full_name=full_name,
        role=UserRole.ADMIN,
        is_active=True,
        **kwargs
    )


@pytest.fixture
def test_user(db_session: Session) -> User:
    """
    Fixture that creates a standard test user (DOCTOR role).
    
    Returns:
        User instance with DOCTOR role
    """
    return create_test_user(db_session)


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """
    Fixture that creates an admin user.
    
    Returns:
        User instance with ADMIN role
    """
    return create_admin_user(db_session)


@pytest.fixture
def multiple_users(db_session: Session) -> list[User]:
    """
    Fixture that creates multiple test users for pagination/list testing.
    
    Returns:
        List of 10 User instances (5 doctors, 5 admins)
    """
    users = []
    
    # Create 5 doctors
    for i in range(5):
        user = create_test_user(
            db_session,
            email=f"doctor{i}@test.com",
            full_name=f"Doctor {i}",
            role=UserRole.DOCTOR
        )
        users.append(user)
    
    # Create 5 admins
    for i in range(5):
        user = create_admin_user(
            db_session,
            email=f"admin{i}@test.com",
            full_name=f"Admin {i}"
        )
        users.append(user)
    
    return users


# ============================================================================
# Flow Template Fixtures
# ============================================================================

@pytest.fixture
def flow_kind(db_session: Session):
    """
    Fixture that creates a flow kind for testing.

    Returns:
        FlowKind instance for onboarding flow
    """
    from app.models.flow import FlowKind

    flow_kind = FlowKind(
        id=uuid4(),
        flow_type="initial_15_days",
        name="Initial 15 Days Onboarding",
        description="Standard patient onboarding flow for the first 15 days",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(flow_kind)
    db_session.commit()
    db_session.refresh(flow_kind)
    return flow_kind


@pytest.fixture
def flow_template_version(db_session: Session, flow_kind):
    """
    Fixture that creates a flow template version for testing.

    Args:
        db_session: Database session
        flow_kind: FlowKind fixture

    Returns:
        FlowTemplateVersion instance with onboarding messages
    """
    from app.models.flow import FlowTemplateVersion

    onboarding_steps = [
        {
            "step": 0,
            "day": 0,
            "message": "Olá! Bem-vindo(a) à Clínica Oncológica. Estamos aqui para acompanhá-lo(a) durante todo o seu tratamento.",
            "delay_hours": 0
        },
        {
            "step": 1,
            "day": 1,
            "message": "Como você está se sentindo hoje? Lembre-se de que nossa equipe está sempre disponível para ajudá-lo(a).",
            "delay_hours": 24
        },
        {
            "step": 2,
            "day": 3,
            "message": "Não se esqueça de manter-se hidratado(a) e seguir as orientações médicas. Estamos torcendo por você!",
            "delay_hours": 48
        },
        {
            "step": 3,
            "day": 7,
            "message": "Já se passou uma semana! Como tem sido sua experiência? Estamos aqui para qualquer dúvida.",
            "delay_hours": 96
        },
        {
            "step": 4,
            "day": 15,
            "message": "Parabéns por completar os primeiros 15 dias! Continue seguindo as orientações e conte conosco sempre.",
            "delay_hours": 192
        }
    ]

    template_version = FlowTemplateVersion(
        id=uuid4(),
        kind_id=flow_kind.id,
        version_number=1,
        template_name="Onboarding v1.0",
        description="Initial version of the 15-day onboarding flow",
        is_active=True,
        is_draft=False,
        messages=onboarding_steps,
        template_metadata={},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(template_version)
    db_session.commit()
    db_session.refresh(template_version)
    return template_version


# ============================================================================
# Patient Fixtures
# ============================================================================

def create_test_patient(
    db_session: Session,
    doctor: User,
    name: str = "Test Patient",
    email: str = None,
    phone: str = "+5511999999999",
    **kwargs
):
    """
    Create a test patient in the database.

    LGPD Compliance: Uses set_email(), set_phone(), set_cpf() methods
    to properly encrypt and hash sensitive data.

    Args:
        db_session: Database session
        doctor: Doctor user who owns this patient
        name: Patient name
        email: Patient email (optional)
        phone: Patient phone (E.164 format recommended)
        **kwargs: Additional patient attributes (cpf, birth_date, etc.)

    Returns:
        Created Patient instance with encrypted PII fields
    """
    from app.models.patient import Patient

    # Generate default email if not provided
    actual_email = email or f"patient_{uuid4().hex[:8]}@test.com"

    # Normalize phone to E.164 format
    actual_phone = phone
    if phone and not phone.startswith('+'):
        actual_phone = f"+55{phone}"

    # Create patient without PII columns (removed in migration 030)
    patient = Patient(
        id=kwargs.get('id', uuid4()),
        name=name,
        doctor_id=doctor.id,
        birth_date=kwargs.get('birth_date'),
        created_at=kwargs.get('created_at', datetime.utcnow()),
        updated_at=kwargs.get('updated_at', datetime.utcnow())
    )

    # LGPD: Set encrypted fields using proper methods
    if actual_phone:
        patient.set_phone(actual_phone)
    if actual_email:
        patient.set_email(actual_email)
    if kwargs.get('cpf'):
        patient.set_cpf(kwargs['cpf'])

    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


@pytest.fixture
def test_patient(db_session: Session, test_user: User):
    """
    Fixture that creates a patient for test_user (doctor).
    
    Returns:
        Patient instance owned by test_user
    """
    return create_test_patient(db_session, doctor=test_user)


@pytest.fixture
def sample_appointments(
    db_session: Session, sample_users: list[User]
) -> list[Appointment]:
    """Create a few appointments for analytics tests."""
    doctor = sample_users[0]
    patient = create_test_patient(
        db_session,
        doctor=doctor,
        name="Contract Patient",
    )

    appointments: list[Appointment] = []
    statuses = [
        AppointmentStatus.SCHEDULED.value,
        AppointmentStatus.COMPLETED.value,
        AppointmentStatus.CANCELLED.value,
    ]

    for idx, status in enumerate(statuses):
        appointment = Appointment(
            id=uuid4(),
            patient_id=patient.id,
            practitioner_id=doctor.id,
            appointment_type=AppointmentType.CONSULTATION.value,
            status=status,
            scheduled_at=datetime.utcnow() + timedelta(days=idx),
            duration_minutes=30,
            reminder_sent=False,
            confirmation_sent=False,
        )
        db_session.add(appointment)
        appointments.append(appointment)

    db_session.commit()
    return appointments


# ============================================================================
# Authentication Fixtures
# ============================================================================

@pytest.fixture
def auth_headers(test_user: User, client: TestClient) -> dict:
    """
    Create authentication headers for a test user.
    
    Uses dependency override to inject the user into get_current_user.
    
    Args:
        test_user: User to create headers for
        client: Test client
        
    Returns:
        Dictionary with mock Authorization header
    """
    
    # Override dependency to return test_user
    app.dependency_overrides[get_current_user] = lambda: test_user
    TEST_TOKEN_REGISTRY[f"test_token_{test_user.id}"] = test_user
    
    # Return mock header (dependency override is what matters)
    return {"Authorization": f"Bearer test_token_{test_user.id}"}


@pytest.fixture
def admin_auth_headers(admin_user: User, client: TestClient) -> dict:
    """
    Create authentication headers for an admin user.
    
    Uses dependency override to inject the admin into get_current_user.
    
    Args:
        admin_user: Admin user to create headers for
        client: Test client
        
    Returns:
        Dictionary with mock Authorization header
    """
    from app.dependencies.auth_dependencies import get_current_user
    
    # Override dependency to return admin_user
    app.dependency_overrides[get_current_user] = lambda: admin_user
    TEST_TOKEN_REGISTRY[f"admin_token_{admin_user.id}"] = admin_user
    
    # Return mock header
    return {"Authorization": f"Bearer admin_token_{admin_user.id}"}


@pytest.fixture
def admin_token(admin_auth_headers: dict) -> str:
    """
    Return a bearer token string for admin contract tests.

    Relies on ``admin_auth_headers`` to override authentication dependencies.
    """
    return admin_auth_headers["Authorization"].split(" ", 1)[1]


@pytest.fixture
def user_token(auth_headers: dict) -> str:
    """
    Return a bearer token for a regular (non-admin) user.
    """
    return auth_headers["Authorization"].split(" ", 1)[1]


@pytest.fixture
def authenticated_client(client: TestClient, test_user: User) -> TestClient:
    """
    Create an authenticated test client with user token.

    This fixture combines the test client with authentication headers
    for making authenticated requests.

    Args:
        client: Base test client
        test_user: Test user for authentication

    Returns:
        TestClient with default authenticated headers
    """
    # Override dependency to return test_user
    app.dependency_overrides[get_current_user] = lambda: test_user
    TEST_TOKEN_REGISTRY[f"test_token_{test_user.id}"] = test_user

    # Set default headers on the client
    client.headers["Authorization"] = f"Bearer test_token_{test_user.id}"
    return client


@pytest.fixture
def admin_authenticated_client(client: TestClient, admin_user: User) -> TestClient:
    """
    Create an authenticated test client with admin token.

    Args:
        client: Base test client
        admin_user: Admin user for authentication

    Returns:
        TestClient with default admin authenticated headers
    """
    # Override dependency to return admin_user
    app.dependency_overrides[get_current_user] = lambda: admin_user
    TEST_TOKEN_REGISTRY[f"admin_token_{admin_user.id}"] = admin_user

    # Set default headers on the client
    client.headers["Authorization"] = f"Bearer admin_token_{admin_user.id}"
    return client


# ============================================================================
# Mock Client Fixtures
# ============================================================================

@pytest.fixture
def mock_redis(mocker):
    """
    Create a mock Redis client.
    
    Returns:
        Mock Redis client with common methods
    """
    redis = mocker.MagicMock()
    redis.get = mocker.MagicMock(return_value=None)
    redis.set = mocker.MagicMock(return_value=True)
    redis.setex = mocker.MagicMock(return_value=True)
    redis.delete = mocker.MagicMock(return_value=1)
    redis.exists = mocker.MagicMock(return_value=False)
    redis.incr = mocker.MagicMock(return_value=1)
    redis.expire = mocker.MagicMock(return_value=True)
    return redis


@pytest.fixture
def mock_evolution_client(mocker):
    """
    Create a mock Evolution API client.
    
    Returns:
        Mock EvolutionClient with common methods
    """
    client = mocker.MagicMock()
    client.send_message = mocker.AsyncMock(return_value={
        "success": True,
        "message_id": "test_msg_123",
        "status": "sent"
    })
    client.get_instance_status = mocker.AsyncMock(return_value={
        "status": "open",
        "connected": True
    })
    return client


# ============================================================================
# Pytest Configuration
# ============================================================================

# ============================================================================
# V2 Evolution Fixtures - Clinical Fields & Advanced Filters
# ============================================================================

@pytest.fixture
async def test_patient_with_clinical_data(client, auth_headers):
    """Create a test patient with complete clinical data"""
    patient_data = {
        "doctor_id": str(uuid4()),
        "name": "Paciente Completo Dados Clínicos",
        "phone": "+5511999888777",
        "email": "paciente.completo@example.com",
        "allergies": ["Penicilina", "Dipirona"],
        "current_medications": ["Metformina 500mg", "Losartana 50mg"],
        "comorbidities": ["Diabetes Tipo 2", "Hipertensão"],
        "blood_type": "O+",
        "emergency_contact_name": "Contato Emergência",
        "emergency_contact_phone": "+5511888777666"
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers=auth_headers
    )

    assert response.status_code == 201
    return response.json()


@pytest.fixture
async def test_patients_various_phases(client, auth_headers):
    """Create test patients with different treatment phases"""
    phases = ["initial", "maintenance", "followup"]
    created_patients = []

    for i, phase in enumerate(phases):
        patient_data = {
            "doctor_id": str(uuid4()),
            "name": f"Patient {phase.title()}",
            "phone": f"+551199988877{i}",
            "email": f"patient.{phase}@example.com",
            "treatment_phase": phase
        }

        response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=auth_headers
        )

        if response.status_code == 201:
            created_patients.append(response.json())

    return created_patients


@pytest.fixture
async def test_patients_with_flows(client, auth_headers):
    """Create test patients with active and inactive flows"""
    flow_states = [
        ("Active Patient 1", "ACTIVE"),
        ("Active Patient 2", "RUNNING"),
        ("Inactive Patient 1", "COMPLETED"),
        ("Inactive Patient 2", "PAUSED")
    ]

    created_patients = []

    for i, (name, flow_state) in enumerate(flow_states):
        patient_data = {
            "doctor_id": str(uuid4()),
            "name": name,
            "phone": f"+551199977766{i}",
            "email": f"patient.flow{i}@example.com",
            "flow_state": flow_state
        }

        response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=auth_headers
        )

        if response.status_code == 201:
            created_patients.append(response.json())

    return created_patients


@pytest.fixture
async def test_patients_various_dates(client, auth_headers):
    """Create test patients with different creation dates"""
    date_offsets = [-30, -15, -7, -3, -1, 0]  # Days ago
    created_patients = []

    for i, days_ago in enumerate(date_offsets):
        patient_data = {
            "doctor_id": str(uuid4()),
            "name": f"Patient Created {abs(days_ago)} Days Ago",
            "phone": f"+551199966655{i}",
            "email": f"patient.date{i}@example.com"
        }

        response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=auth_headers
        )

        if response.status_code == 201:
            created_patients.append(response.json())

    return created_patients


@pytest.fixture
async def test_patients_various_names(client, auth_headers):
    """Create test patients with names for sorting tests"""
    names = [
        "Alice Silva",
        "Bruno Costa",
        "Carlos Mendes",
        "Diana Oliveira",
        "Eduardo Santos"
    ]

    created_patients = []

    for i, name in enumerate(names):
        patient_data = {
            "doctor_id": str(uuid4()),
            "name": name,
            "phone": f"+551199955544{i}",
            "email": f"{name.lower().replace(' ', '.')}@example.com"
        }

        response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=auth_headers
        )

        if response.status_code == 201:
            created_patients.append(response.json())

    return created_patients


@pytest.fixture
async def test_patients_various_emails(client, auth_headers):
    """Create test patients with emails for sorting tests"""
    emails = [
        "alice@example.com",
        "bruno@example.com",
        "carlos@example.com",
        "diana@example.com"
    ]

    created_patients = []

    for i, email in enumerate(emails):
        patient_data = {
            "doctor_id": str(uuid4()),
            "name": f"Patient {i}",
            "phone": f"+551199944433{i}",
            "email": email
        }

        response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=auth_headers
        )

        if response.status_code == 201:
            created_patients.append(response.json())

    return created_patients


@pytest.fixture
async def test_patients_complex(client, auth_headers):
    """Create complex test dataset for combined filter testing"""
    patients_data = [
        {
            "name": "Alpha Initial Active",
            "treatment_phase": "initial",
            "flow_state": "ACTIVE"
        },
        {
            "name": "Beta Initial Inactive",
            "treatment_phase": "initial",
            "flow_state": "COMPLETED"
        },
        {
            "name": "Charlie Maintenance Active",
            "treatment_phase": "maintenance",
            "flow_state": "RUNNING"
        },
        {
            "name": "Delta Followup Active",
            "treatment_phase": "followup",
            "flow_state": "ACTIVE"
        }
    ]

    created_patients = []

    for i, data in enumerate(patients_data):
        patient_data = {
            "doctor_id": str(uuid4()),
            "name": data["name"],
            "phone": f"+551199933322{i}",
            "email": f"patient.complex{i}@example.com",
            "treatment_phase": data.get("treatment_phase"),
            "flow_state": data.get("flow_state")
        }

        response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=auth_headers
        )

        if response.status_code == 201:
            created_patients.append(response.json())

    return created_patients


@pytest.fixture
def other_doctor_token(db_session, client):
    """Create token for a different doctor user"""
    other_doctor = create_test_user(
        db_session,
        email=f"other_doctor_{uuid4().hex[:6]}@test.com",
        full_name="Other Doctor",
        role=UserRole.DOCTOR
    )

    app.dependency_overrides[get_current_user] = lambda: other_doctor
    TEST_TOKEN_REGISTRY[f"other_doctor_token_{other_doctor.id}"] = other_doctor

    return f"other_doctor_token_{other_doctor.id}"


@pytest.fixture
async def test_patients_multiple_doctors(client, auth_headers, other_doctor_token):
    """Create test patients belonging to different doctors"""
    created_patients = []

    # Create patients for first doctor
    for i in range(3):
        patient_data = {
            "doctor_id": str(uuid4()),
            "name": f"Doctor 1 Patient {i}",
            "phone": f"+551199922211{i}",
            "email": f"doc1.patient{i}@example.com",
            "treatment_phase": "initial"
        }

        response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=auth_headers
        )

        if response.status_code == 201:
            created_patients.append(response.json())

    # Create patients for second doctor
    for i in range(3):
        patient_data = {
            "doctor_id": str(uuid4()),
            "name": f"Doctor 2 Patient {i}",
            "phone": f"+551199911100{i}",
            "email": f"doc2.patient{i}@example.com",
            "treatment_phase": "initial"
        }

        response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers={"Authorization": f"Bearer {other_doctor_token}"}
        )

        if response.status_code == 201:
            created_patients.append(response.json())

    return created_patients


@pytest.fixture
async def test_patient_owned_by_doctor(client, auth_headers):
    """Create a test patient owned by the authenticated doctor"""
    patient_data = {
        "doctor_id": str(uuid4()),
        "name": "Own Patient",
        "phone": "+5511999000111",
        "email": "own.patient@example.com"
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers=auth_headers
    )

    assert response.status_code == 201
    return response.json()


@pytest.fixture
async def test_patient_owned_by_other_doctor(client, other_doctor_token):
    """Create a test patient owned by a different doctor"""
    patient_data = {
        "doctor_id": str(uuid4()),
        "name": "Other Doctor Patient",
        "phone": "+5511999000222",
        "email": "other.patient@example.com"
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers={"Authorization": f"Bearer {other_doctor_token}"}
    )

    assert response.status_code == 201
    return response.json()


@pytest.fixture
def doctor_token(auth_headers: dict) -> str:
    """
    Return a bearer token for a doctor user.

    Alias for user_token for clarity in v2 tests.
    """
    return auth_headers["Authorization"].split(" ", 1)[1]


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
