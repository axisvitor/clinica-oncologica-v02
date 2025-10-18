"""
Shared pytest fixtures for all tests.

This module provides common fixtures used across unit and integration tests,
including database sessions, test users, authentication tokens, and mock clients.
"""
import pytest
from datetime import datetime
from uuid import uuid4
from typing import Generator
import json

from sqlalchemy import create_engine, event, TypeDecorator, Text, String
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB, INET
from fastapi.testclient import TestClient

from app.models.base import Base
from app.models.user import User, UserRole
from app.utils.security import get_password_hash
from app.main import app
from app.database import get_db


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


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Create a fresh database session for each test.

    Uses an in-memory SQLite database for fast, isolated tests.
    All tables are created before the test and dropped after.

    Note: Automatically converts PostgreSQL JSONB columns to SQLite-compatible
    TEXT columns with JSON serialization.
    """
    # Create in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Replace PostgreSQL types with SQLite-compatible types
    _replace_postgres_types_with_sqlite(engine)

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


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
    phone: str = "11999999999",
    **kwargs
):
    """
    Create a test patient in the database.
    
    Args:
        db_session: Database session
        doctor: Doctor user who owns this patient
        name: Patient name
        email: Patient email (optional)
        phone: Patient phone
        **kwargs: Additional patient attributes
        
    Returns:
        Created Patient instance
    """
    from app.models.patient import Patient
    
    patient = Patient(
        id=kwargs.get('id', uuid4()),
        name=name,
        email=email or f"patient_{uuid4().hex[:8]}@test.com",
        phone=phone,
        doctor_id=doctor.id,
        cpf=kwargs.get('cpf'),
        birth_date=kwargs.get('birth_date'),
        created_at=kwargs.get('created_at', datetime.utcnow()),
        updated_at=kwargs.get('updated_at', datetime.utcnow())
    )
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
    from app.dependencies.auth_dependencies import get_current_user
    
    # Override dependency to return test_user
    app.dependency_overrides[get_current_user] = lambda: test_user
    
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
    
    # Return mock header
    return {"Authorization": f"Bearer admin_token_{admin_user.id}"}


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

