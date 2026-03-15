"""
Shared fixtures for API v2 tests.

Provides comprehensive test fixtures for authentication, users, patients,
alerts, and other resources needed for thorough API testing.
"""

import pytest
from uuid import uuid4
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch
import inspect

from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.patient import Patient, FlowState
from app.models.flow import FlowKind, FlowTemplateVersion
from app.models.alert import Alert, AlertSeverity
from app.utils.security import get_password_hash
from app.dependencies.auth_dependencies import (
    get_current_user,
    get_current_user_from_session,
    get_current_user_object_from_session,
    get_optional_user,
    get_permissions_for_role,
)
from app.dependencies import get_request_context, RequestContext
from fastapi import Request
from fastapi.testclient import TestClient
from app.middleware.csrf import get_csrf_token
from app.utils.db_retry import reset_circuit_breaker
from tests.utils.async_test_client import AsyncTestClient


# ============================================================================
# User Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_db_circuit_breaker_state():
    """Prevent global DB circuit breaker state leakage across tests."""
    reset_circuit_breaker()
    yield
    reset_circuit_breaker()

@pytest.fixture
def mock_firebase():
    """Mock Firebase authentication service."""
    with patch('firebase_admin.auth') as mock_auth:
        mock_auth.verify_id_token = MagicMock()
        with patch(
            "app.api.v2.routers.auth.verify_token",
            new_callable=AsyncMock,
        ) as mock_router_verify:
            async def _bridge_verify_token(id_token: str):
                result = mock_auth.verify_id_token(id_token)
                if inspect.isawaitable(result):
                    return await result
                return result

            mock_router_verify.side_effect = _bridge_verify_token
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
        firebase_uid="A1B2C3D4E5F6G7H8I9J0K1L2M3N4",
        hashed_password=get_password_hash("adminpass123"),
        full_name="Test Admin",
        display_name="Administrador Teste",
        photo_url="https://example.com/admin-photo.png",
        preferences={"theme": "dark", "language": "pt-BR"},
        last_login=datetime(2026, 3, 12, 9, 0, 0),
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
        firebase_uid="B1C2D3E4F5G6H7I8J9K0L1M2N3O4",
        hashed_password=get_password_hash("doctorpass123"),
        full_name="Test Doctor",
        display_name="Dra. Test Doctor",
        photo_url="https://example.com/doctor-photo.png",
        preferences={"theme": "light", "language": "en-US"},
        last_login=datetime(2026, 3, 11, 14, 30, 0),
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
        firebase_uid="C1D2E3F4G5H6I7J8K9L0M1N2O3P4",
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
        patient_data = dict(kwargs.get("patient_data") or {})
        if kwargs.get("cancer_type"):
            patient_data.setdefault("cancer_type", kwargs["cancer_type"])

        patient = Patient(
            id=kwargs.get('id', uuid4()),
            name=kwargs.get('name', 'Test Patient'),
            doctor_id=kwargs.get('doctor_id', test_doctor_user.id),
            birth_date=kwargs.get('birth_date', date(1990, 1, 1)),
            treatment_type=kwargs.get('treatment_type'),
            treatment_start_date=kwargs.get('treatment_start_date'),
            diagnosis=kwargs.get('diagnosis'),
            treatment_phase=kwargs.get('treatment_phase'),
            doctor_notes=kwargs.get('doctor_notes'),
            patient_data=patient_data or None,
            flow_state=kwargs.get('flow_state', FlowState.ONBOARDING)
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


@pytest.fixture
def test_patient(test_patient_instance):
    """API v2 default patient tied to the API v2 doctor fixture."""
    return test_patient_instance


# ============================================================================
# Flow Template Seed (Required for auto-enrollment)
# ============================================================================

@pytest.fixture(autouse=True)
def seed_flow_templates(db_session: Session):
    """Ensure default flow kind/template exists for saga enrollment."""
    flow_kind = (
        db_session.query(FlowKind)
        .filter(FlowKind.kind_key == "onboarding")
        .first()
    )
    if not flow_kind:
        flow_kind = FlowKind(
            kind_key="onboarding",
            display_name="Initial 15 Days",
            description="Default onboarding flow for tests",
            is_active=True,
        )
        db_session.add(flow_kind)
        db_session.flush()

    active_version = (
        db_session.query(FlowTemplateVersion)
        .filter(
            FlowTemplateVersion.flow_kind_id == flow_kind.id,
            FlowTemplateVersion.is_active,
        )
        .first()
    )
    if not active_version:
        db_session.add(
            FlowTemplateVersion(
                flow_kind_id=flow_kind.id,
                version_number=1,
                template_name="onboarding",
                is_active=True,
                steps=[],
            )
        )
        db_session.flush()

    yield


# ============================================================================
# CSRF Auto-Injection for API v2 Tests
# ============================================================================

@pytest.fixture(autouse=True)
def auto_csrf_headers(monkeypatch: pytest.MonkeyPatch):
    """Inject CSRF headers/cookies for state-changing requests in v2 tests."""
    def _wrap_request(original_request):
        def _request(self, method: str, url: str, **kwargs):
            method_upper = method.upper()
            if method_upper in {"POST", "PUT", "PATCH", "DELETE"}:
                headers = kwargs.get("headers")
                if headers is None:
                    headers = {}
                else:
                    headers = dict(headers)

                has_csrf_header = (
                    "X-CSRF-Token" in headers or "X-CSRFToken" in headers
                )
                if not has_csrf_header:
                    csrf_token = get_csrf_token()
                    headers["X-CSRF-Token"] = csrf_token
                    cookie_header = headers.get("Cookie")
                    if cookie_header:
                        if "csrf_token=" not in cookie_header:
                            headers["Cookie"] = (
                                f"{cookie_header}; csrf_token={csrf_token}"
                            )
                    else:
                        headers["Cookie"] = f"csrf_token={csrf_token}"
                    self.cookies.set("csrf_token", csrf_token)

                kwargs["headers"] = headers

            return original_request(self, method, url, **kwargs)

        return _request

    monkeypatch.setattr(TestClient, "request", _wrap_request(TestClient.request))
    monkeypatch.setattr(
        AsyncTestClient,
        "request",
        _wrap_request(AsyncTestClient.request),
    )


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


def _build_canonical_session_user(user: User) -> dict:
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    last_login = user.get_last_login() if hasattr(user, "get_last_login") else getattr(user, "last_login", None)
    display_name = user.get_display_name() if hasattr(user, "get_display_name") else getattr(user, "display_name", user.full_name)
    photo_url = user.get_photo_url() if hasattr(user, "get_photo_url") else getattr(user, "photo_url", None)
    preferences = user.get_preferences_data() if hasattr(user, "get_preferences_data") else dict(getattr(user, "preferences", {}) or {})
    email_verified = user.get_email_verified() if hasattr(user, "get_email_verified") else bool(getattr(user, "email_verified", False))
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": role,
        "is_active": user.is_active,
        "firebase_uid": user.firebase_uid,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "last_login": last_login.isoformat() if last_login else None,
        "display_name": display_name,
        "photo_url": photo_url,
        "preferences": preferences,
        "email_verified": email_verified,
        "permissions": get_permissions_for_role(role),
    }


@pytest.fixture
def auth_headers_admin(test_admin_user: User) -> dict:
    """Authentication headers for admin user."""
    from app.main import app
    from app.middleware.csrf import get_csrf_token

    session_user = _build_canonical_session_user(test_admin_user)
    role = session_user["role"]

    async def _override_session(request: Request):
        request.state.user_id = session_user.get("id")
        request.state.user_role = session_user.get("role")
        return session_user

    async def _override_current_user(request: Request):
        request.state.user = test_admin_user
        request.state.user_id = str(test_admin_user.id)
        request.state.user_role = role
        return test_admin_user
    
    async def _override_optional_user(credentials=None, services=None):
        return test_admin_user
    
    async def _override_current_user_object():
        return test_admin_user

    async def _override_request_context(request: Request):
        return RequestContext(
            ip_address="127.0.0.1",
            user_agent="pytest",
            user_id=test_admin_user.id,
            session_id=f"admin-session-{test_admin_user.id}",
        )

    app.dependency_overrides[get_current_user_from_session] = _override_session
    app.dependency_overrides[get_current_user_object_from_session] = _override_current_user_object
    app.dependency_overrides[get_current_user] = _override_current_user
    app.dependency_overrides[get_optional_user] = _override_optional_user
    app.dependency_overrides[get_request_context] = _override_request_context

    csrf_token = get_csrf_token()
    headers = {
        "X-Session-ID": f"admin-session-{test_admin_user.id}",
        "Authorization": f"Bearer admin-token-{test_admin_user.id}",
        "X-CSRF-Token": csrf_token,
        "Cookie": f"csrf_token={csrf_token}",
    }
    yield headers
    app.dependency_overrides.pop(get_current_user_from_session, None)
    app.dependency_overrides.pop(get_current_user_object_from_session, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_user, None)
    app.dependency_overrides.pop(get_request_context, None)


@pytest.fixture
def auth_headers_doctor(test_doctor_user: User) -> dict:
    """Authentication headers for doctor user."""
    from app.main import app
    from app.middleware.csrf import get_csrf_token

    session_user = _build_canonical_session_user(test_doctor_user)
    role = session_user["role"]

    async def _override_session(request: Request):
        request.state.user_id = session_user.get("id")
        request.state.user_role = session_user.get("role")
        return session_user

    async def _override_current_user(request: Request):
        request.state.user = test_doctor_user
        request.state.user_id = str(test_doctor_user.id)
        request.state.user_role = role
        return test_doctor_user
    
    async def _override_optional_user(credentials=None, services=None):
        return test_doctor_user
    
    async def _override_current_user_object():
        return test_doctor_user

    async def _override_request_context(request: Request):
        return RequestContext(
            ip_address="127.0.0.1",
            user_agent="pytest",
            user_id=test_doctor_user.id,
            session_id=f"doctor-session-{test_doctor_user.id}",
        )

    app.dependency_overrides[get_current_user_from_session] = _override_session
    app.dependency_overrides[get_current_user_object_from_session] = _override_current_user_object
    app.dependency_overrides[get_current_user] = _override_current_user
    app.dependency_overrides[get_optional_user] = _override_optional_user
    app.dependency_overrides[get_request_context] = _override_request_context

    csrf_token = get_csrf_token()
    headers = {
        "X-Session-ID": f"doctor-session-{test_doctor_user.id}",
        "Authorization": f"Bearer doctor-token-{test_doctor_user.id}",
        "X-CSRF-Token": csrf_token,
        "Cookie": f"csrf_token={csrf_token}",
    }
    yield headers
    app.dependency_overrides.pop(get_current_user_from_session, None)
    app.dependency_overrides.pop(get_current_user_object_from_session, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_user, None)
    app.dependency_overrides.pop(get_request_context, None)


@pytest.fixture
def auth_headers(auth_headers_doctor):
    """Generic authentication headers (defaults to doctor)."""
    return auth_headers_doctor


@pytest.fixture
def auth_headers_patient(test_patient: Patient) -> dict:
    """Authentication headers for patient-like role used in RBAC tests."""
    from app.main import app
    from app.middleware.csrf import get_csrf_token

    patient_role = "patient"
    patient_user = SimpleNamespace(
        id=test_patient.id,
        email="patient@example.com",
        full_name=test_patient.name,
        role=patient_role,
        is_active=True,
        firebase_uid=f"patient-{test_patient.id}",
    )
    session_user = {
        "id": str(test_patient.id),
        "email": "patient@example.com",
        "full_name": test_patient.name,
        "role": patient_role,
        "is_active": True,
        "firebase_uid": f"patient-{test_patient.id}",
        "permissions": get_permissions_for_role(patient_role),
    }

    async def _override_session(request: Request):
        request.state.user_id = session_user.get("id")
        request.state.user_role = session_user.get("role")
        return session_user

    async def _override_current_user(request: Request):
        request.state.user = patient_user
        request.state.user_id = str(test_patient.id)
        request.state.user_role = patient_role
        return patient_user

    async def _override_optional_user(credentials=None, services=None):
        return patient_user

    async def _override_current_user_object():
        return patient_user

    async def _override_request_context(request: Request):
        return RequestContext(
            ip_address="127.0.0.1",
            user_agent="pytest",
            user_id=test_patient.id,
            session_id=f"patient-session-{test_patient.id}",
        )

    app.dependency_overrides[get_current_user_from_session] = _override_session
    app.dependency_overrides[get_current_user_object_from_session] = _override_current_user_object
    app.dependency_overrides[get_current_user] = _override_current_user
    app.dependency_overrides[get_optional_user] = _override_optional_user
    app.dependency_overrides[get_request_context] = _override_request_context

    csrf_token = get_csrf_token()
    headers = {
        "X-Session-ID": f"patient-session-{test_patient.id}",
        "Authorization": f"Bearer patient-token-{test_patient.id}",
        "X-CSRF-Token": csrf_token,
        "Cookie": f"csrf_token={csrf_token}",
    }
    yield headers
    app.dependency_overrides.pop(get_current_user_from_session, None)
    app.dependency_overrides.pop(get_current_user_object_from_session, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_user, None)
    app.dependency_overrides.pop(get_request_context, None)


@pytest.fixture
def admin_headers(auth_headers_admin):
    """Alias for admin auth headers used by some test suites."""
    return auth_headers_admin


@pytest.fixture
def admin_auth_headers(auth_headers_admin):
    """Legacy alias used by auth tests."""
    return auth_headers_admin


@pytest.fixture
def admin_token(auth_headers_admin):
    """Legacy token-only alias that keeps v2 admin auth overrides active."""
    auth_header = auth_headers_admin.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer ") :]
    return auth_header


@pytest.fixture
def doctor_headers(auth_headers_doctor):
    """Alias for doctor auth headers used by some test suites."""
    return auth_headers_doctor


@pytest.fixture
def doctor_token(auth_headers_doctor):
    """Legacy token-only alias used by advanced filter tests."""
    auth_header = auth_headers_doctor.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer ") :]
    return auth_header


@pytest.fixture
def auth_headers_physician(auth_headers_doctor):
    """Legacy alias used by alerts tests."""
    return auth_headers_doctor


@pytest.fixture
def mock_authenticated_session(mock_redis, test_doctor_user: User):
    """Mock authenticated session in Redis."""
    mock_redis.get_session.return_value = {
        "firebase_uid": test_doctor_user.firebase_uid,
        "user_id": str(test_doctor_user.id),
        "email": test_doctor_user.email,
        "role": test_doctor_user.role.value,
        "last_login": test_doctor_user.last_login.isoformat()
        if test_doctor_user.last_login
        else None,
        "display_name": test_doctor_user.display_name,
        "photo_url": test_doctor_user.photo_url,
        "preferences": dict(test_doctor_user.preferences or {}),
    }
    canonical_user_payload = {
        "id": str(test_doctor_user.id),
        "email": test_doctor_user.email,
        "full_name": test_doctor_user.full_name,
        "role": test_doctor_user.role.value,
        "is_active": True,
        "last_login": test_doctor_user.last_login.isoformat()
        if test_doctor_user.last_login
        else None,
        "display_name": test_doctor_user.display_name,
        "photo_url": test_doctor_user.photo_url,
        "preferences": dict(test_doctor_user.preferences or {}),
    }
    mock_redis.get_user_by_id.return_value = canonical_user_payload
    mock_redis.get_user_by_uid.return_value = canonical_user_payload
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
def test_patients_various_phases(create_test_patient):
    """Seed patients with different treatment phases for filter tests."""
    return [
        create_test_patient(name="Phase Initial", treatment_phase="initial"),
        create_test_patient(name="Phase Maintenance", treatment_phase="maintenance"),
        create_test_patient(name="Phase Followup", treatment_phase="followup"),
    ]


@pytest.fixture
def test_patients_with_flows(create_test_patient):
    """Seed patients with active and inactive flow states."""
    return [
        create_test_patient(name="Flow Onboarding", flow_state=FlowState.ONBOARDING),
        create_test_patient(name="Flow Paused", flow_state=FlowState.PAUSED),
        create_test_patient(name="Flow Completed", flow_state=FlowState.COMPLETED),
    ]


@pytest.fixture
def test_patients_various_dates(create_test_patient, db_session: Session):
    """Seed patients with controlled created_at values for date/sort filters."""
    now = datetime.utcnow()
    p_old = create_test_patient(name="Date Old", treatment_phase="initial")
    p_mid = create_test_patient(name="Date Mid", treatment_phase="initial")
    p_new = create_test_patient(name="Date New", treatment_phase="initial")

    p_old.created_at = now - timedelta(days=10)
    p_mid.created_at = now - timedelta(days=3)
    p_new.created_at = now - timedelta(hours=6)
    db_session.commit()

    return [p_old, p_mid, p_new]


@pytest.fixture
def test_patients_various_names(create_test_patient):
    """Seed patients with sortable names."""
    return [
        create_test_patient(name="Zoe Patient", treatment_phase="initial"),
        create_test_patient(name="Ana Patient", treatment_phase="initial"),
        create_test_patient(name="Bruno Patient", treatment_phase="initial"),
    ]


@pytest.fixture
def test_patients_various_emails(create_test_patient):
    """Seed patients with sortable emails."""
    return [
        create_test_patient(name="Email C", email="c@example.com", treatment_phase="initial"),
        create_test_patient(name="Email A", email="a@example.com", treatment_phase="initial"),
        create_test_patient(name="Email B", email="b@example.com", treatment_phase="initial"),
    ]


@pytest.fixture
def test_patients_complex(create_test_patient, db_session: Session):
    """Seed a mixed dataset used by combined filter/sort/pagination tests."""
    now = datetime.utcnow()
    created = []
    for idx in range(12):
        phase = "initial" if idx % 2 == 0 else "maintenance"
        flow_state = FlowState.PAUSED if idx % 3 == 0 else FlowState.COMPLETED
        patient = create_test_patient(
            name=f"Complex {idx:02d}",
            treatment_phase=phase,
            flow_state=flow_state,
        )
        patient.created_at = now - timedelta(days=idx)
        created.append(patient)

    db_session.commit()
    return created


@pytest.fixture
def test_patients_multiple_doctors(
    db_session: Session,
    create_test_patient,
    test_doctor_user: User,
):
    """Seed patients for at least two doctors to validate RBAC list behavior."""
    other_doctor = User(
        id=uuid4(),
        email="doctor2@example.com",
        firebase_uid="E1F2G3H4I5J6K7L8M9N0O1P2Q3R4",
        hashed_password=get_password_hash("doctorpass123"),
        full_name="Test Doctor 2",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add(other_doctor)
    db_session.commit()
    db_session.refresh(other_doctor)

    own_patient = create_test_patient(
        name="Doctor One Patient",
        doctor_id=test_doctor_user.id,
        treatment_phase="initial",
        flow_state=FlowState.PAUSED,
    )
    other_patient = create_test_patient(
        name="Doctor Two Patient",
        doctor_id=other_doctor.id,
        treatment_phase="initial",
        flow_state=FlowState.PAUSED,
    )
    return [own_patient, other_patient]


@pytest.fixture
def test_patient_with_clinical_data(create_test_patient):
    """Patient fixture pre-populated with clinical metadata fields."""
    return create_test_patient(
        name="Clinical Data Patient",
        treatment_phase="maintenance",
        patient_data={
            "medical_history": {
                "allergies": ["Dipirona"],
                "medications": ["Losartana 50mg"],
                "conditions": ["Hipertensão"],
            },
            "blood_type": "O+",
            "emergency_contact": {
                "name": "Contato Clínico",
                "phone": "+5511999999999",
            },
        },
    )


@pytest.fixture
def test_patient_owned_by_doctor(create_test_patient):
    """Patient owned by the authenticated doctor."""
    return create_test_patient(name="Owned Patient", treatment_phase="initial")


@pytest.fixture
def test_patient_owned_by_other_doctor(db_session: Session, create_test_patient):
    """Patient owned by another doctor for RBAC denial tests."""
    other_doctor = User(
        id=uuid4(),
        email="doctor-rbac-other@example.com",
        firebase_uid="F1G2H3I4J5K6L7M8N9O0P1Q2R3S4",
        hashed_password=get_password_hash("doctorpass123"),
        full_name="Other Doctor",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add(other_doctor)
    db_session.commit()
    db_session.refresh(other_doctor)
    return create_test_patient(
        name="Other Doctor Patient",
        doctor_id=other_doctor.id,
        treatment_phase="initial",
    )


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
