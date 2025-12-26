"""
Shared fixtures for API v2 tests.

Provides comprehensive test fixtures for authentication, users, patients,
alerts, and other resources needed for thorough API testing.
"""

import pytest
from uuid import uuid4
from datetime import date, datetime, timezone
from unittest.mock import Mock, MagicMock, AsyncMock, patch

from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.user import User, UserRole
from app.models.patient import Patient, FlowState
from app.models.alert import Alert, AlertSeverity
from app.utils.security import get_password_hash


# ============================================================================
# User Fixtures
# ============================================================================

@pytest.fixture
def mock_firebase():
    """Mock Firebase authentication service."""
    with patch('firebase_admin.auth') as mock_auth:
        mock_auth.verify_id_token = MagicMock()
        yield mock_auth


@pytest.fixture
def mock_redis():
    """Mock Redis manager for session and cache testing."""
    with patch('app.core.redis_manager.RedisManager') as mock_redis_class:
        mock_instance = MagicMock()
        mock_instance.get_session = MagicMock()
        mock_instance.get_user_by_uid = MagicMock()
        mock_instance.get = MagicMock()
        mock_instance.set = MagicMock()
        mock_instance.delete = MagicMock()
        mock_instance.delete_pattern = MagicMock()
        mock_redis_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def test_admin_user(db_session: Session) -> User:
    """Create admin user for testing."""
    admin = User(
        id=uuid4(),
        email="admin@example.com",
        firebase_uid="admin-firebase-uid",
        hashed_password=get_password_hash("adminpass123"),
        full_name="Test Admin",
        role=UserRole.ADMIN,
        is_active=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def test_doctor_user(db_session: Session) -> User:
    """Create doctor user for testing."""
    doctor = User(
        id=uuid4(),
        email="doctor@example.com",
        firebase_uid="doctor-firebase-uid",
        hashed_password=get_password_hash("doctorpass123"),
        full_name="Test Doctor",
        role=UserRole.DOCTOR,
        is_active=True
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


@pytest.fixture
def test_inactive_user(db_session: Session) -> User:
    """Create inactive user for testing."""
    inactive = User(
        id=uuid4(),
        email="inactive@example.com",
        firebase_uid="inactive-firebase-uid",
        hashed_password=get_password_hash("inactivepass123"),
        full_name="Inactive User",
        role=UserRole.DOCTOR,
        is_active=False
    )
    db_session.add(inactive)
    db_session.commit()
    db_session.refresh(inactive)
    return inactive


# ============================================================================
# Patient Fixtures
# ============================================================================

@pytest.fixture
def test_patient_data() -> dict:
    """Sample patient data for testing."""
    return {
        "name": "Test Patient",
        "email": "patient@example.com",
        "phone": "+5511999999999",
        "cpf": "12345678900",
        "birth_date": "1990-01-15",
        "cancer_type": "breast",
        "treatment_start_date": "2025-01-01"
    }


@pytest.fixture
def create_test_patient(db_session: Session, test_doctor_user: User):
    """Factory fixture to create test patients."""
    def _create_patient(**kwargs):
        patient = Patient(
            id=kwargs.get('id', uuid4()),
            name=kwargs.get('name', 'Test Patient'),
            doctor_id=kwargs.get('doctor_id', test_doctor_user.id),
            birth_date=kwargs.get('birth_date', date(1990, 1, 1)),
            cancer_type=kwargs.get('cancer_type'),
            treatment_start_date=kwargs.get('treatment_start_date'),
            flow_state=kwargs.get('flow_state', FlowState.PENDING)
        )

        # Handle encrypted fields
        if 'email' in kwargs:
            patient.set_email(kwargs['email'])
        if 'phone' in kwargs:
            patient.set_phone(kwargs['phone'])
        if 'cpf' in kwargs:
            patient.set_cpf(kwargs['cpf'])

        db_session.add(patient)
        db_session.commit()
        db_session.refresh(patient)
        return patient

    return _create_patient


@pytest.fixture
def test_patient_instance(create_test_patient):
    """Create a single test patient instance."""
    return create_test_patient()


# ============================================================================
# Alert Fixtures
# ============================================================================

@pytest.fixture
def create_test_alert(db_session: Session):
    """Factory fixture to create test alerts."""
    def _create_alert(patient: Patient, **kwargs):
        alert = Alert(
            id=kwargs.get('id', uuid4()),
            patient_id=patient.id,
            alert_type=kwargs.get('alert_type', 'test_alert'),
            severity=kwargs.get('severity', AlertSeverity.HIGH),
            description=kwargs.get('description', 'Test alert description'),
            acknowledged=kwargs.get('acknowledged', False),
            acknowledged_by=kwargs.get('acknowledged_by'),
            acknowledged_at=kwargs.get('acknowledged_at')
        )
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)
        return alert

    return _create_alert


# ============================================================================
# Authentication Fixtures
# ============================================================================

@pytest.fixture
def auth_headers_admin(test_admin_user: User) -> dict:
    """Authentication headers for admin user."""
    return {
        "X-Session-ID": f"admin-session-{test_admin_user.id}",
        "Authorization": f"Bearer admin-token-{test_admin_user.id}"
    }


@pytest.fixture
def auth_headers_doctor(test_doctor_user: User) -> dict:
    """Authentication headers for doctor user."""
    return {
        "X-Session-ID": f"doctor-session-{test_doctor_user.id}",
        "Authorization": f"Bearer doctor-token-{test_doctor_user.id}"
    }


@pytest.fixture
def auth_headers():
    """Generic authentication headers (alias for compatibility)."""
    return {
        "X-Session-ID": "test-session-id",
        "Authorization": "Bearer test-token"
    }


@pytest.fixture
def mock_authenticated_session(mock_redis, test_doctor_user: User):
    """Mock authenticated session in Redis."""
    mock_redis.get_session.return_value = {
        "firebase_uid": test_doctor_user.firebase_uid,
        "user_id": str(test_doctor_user.id),
        "email": test_doctor_user.email,
        "role": test_doctor_user.role.value
    }
    mock_redis.get_user_by_uid.return_value = {
        "id": str(test_doctor_user.id),
        "firebase_uid": test_doctor_user.firebase_uid,
        "email": test_doctor_user.email,
        "full_name": test_doctor_user.full_name,
        "role": test_doctor_user.role.value,
        "is_active": True
    }
    return mock_redis


# ============================================================================
# Test Data Generators
# ============================================================================

@pytest.fixture
def generate_patients(create_test_patient):
    """Generate multiple test patients."""
    def _generate(count: int = 10, **kwargs):
        patients = []
        for i in range(count):
            patient_kwargs = {
                "name": f"Patient {i}",
                "birth_date": date(1990 + i % 30, 1, 1),
                **kwargs
            }
            patients.append(create_test_patient(**patient_kwargs))
        return patients

    return _generate


@pytest.fixture
def generate_alerts(create_test_alert, test_patient_instance):
    """Generate multiple test alerts."""
    def _generate(count: int = 5, patient: Patient = None, **kwargs):
        target_patient = patient or test_patient_instance
        alerts = []
        severities = [AlertSeverity.LOW, AlertSeverity.MEDIUM, AlertSeverity.HIGH, AlertSeverity.CRITICAL]

        for i in range(count):
            alert_kwargs = {
                "alert_type": f"test_alert_{i}",
                "severity": severities[i % len(severities)],
                "description": f"Test alert {i}",
                **kwargs
            }
            alerts.append(create_test_alert(target_patient, **alert_kwargs))
        return alerts

    return _generate


# ============================================================================
# CSV Import Fixtures
# ============================================================================

@pytest.fixture
def valid_csv_content() -> str:
    """Valid CSV content for import testing."""
    return """name,email,phone,cpf,birth_date,cancer_type
John Doe,john@example.com,11999999999,12345678900,1990-01-15,breast
Jane Smith,jane@example.com,11988888888,98765432100,1985-05-20,lung
Bob Johnson,bob@example.com,11977777777,45678912300,1978-11-30,prostate"""


@pytest.fixture
def invalid_csv_content() -> str:
    """Invalid CSV content for import testing."""
    return """wrong,headers,here
John Doe,invalid-email,not-a-phone"""


# ============================================================================
# Performance Testing Fixtures
# ============================================================================

@pytest.fixture
def large_dataset(generate_patients):
    """Generate large dataset for performance testing."""
    return generate_patients(count=100)


@pytest.fixture
def benchmark_timer():
    """Timer utility for performance testing."""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None
            self.elapsed = None

        def __enter__(self):
            self.start_time = time.time()
            return self

        def __exit__(self, *args):
            self.elapsed = time.time() - self.start_time

        def assert_within(self, max_seconds: float, message: str = None):
            msg = message or f"Operation took {self.elapsed:.2f}s, expected < {max_seconds}s"
            assert self.elapsed < max_seconds, msg

    return Timer


# ============================================================================
# Mock External Services
# ============================================================================

@pytest.fixture
def mock_whatsapp_service():
    """Mock WhatsApp/Evolution API service."""
    with patch('app.integrations.evolution.client.EvolutionClient') as mock_client:
        instance = MagicMock()
        instance.send_message = AsyncMock(return_value={"status": "success"})
        instance.get_instance_status = AsyncMock(return_value={"connected": True})
        mock_client.return_value = instance
        yield instance


@pytest.fixture
def mock_ai_service():
    """Mock AI/Gemini service."""
    with patch('app.integrations.gemini_client.GeminiClient') as mock_client:
        instance = MagicMock()
        instance.generate_response = AsyncMock(return_value="AI generated response")
        instance.analyze_sentiment = AsyncMock(return_value={"sentiment": "positive", "score": 0.8})
        mock_client.return_value = instance
        yield instance


# ============================================================================
# Cleanup Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_test_data(db_session: Session):
    """Automatically cleanup test data after each test."""
    yield
    # Rollback is handled by the db_session fixture
    # This is here for future custom cleanup if needed
