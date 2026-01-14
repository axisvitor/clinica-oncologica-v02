"""Shared fixtures for API tests."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies.auth_dependencies import TEST_TOKEN_REGISTRY, get_current_user
from app.infrastructure.cache import get_unified_cache_manager
from app.main import app
from app.middleware.csrf import get_csrf_token
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.models.user import UserRole
from tests.conftest import create_test_user


@pytest.fixture
def admin_user(db_session):
    return create_test_user(
        db_session,
        email=f"admin_{uuid4().hex}@example.com",
        full_name="Admin User",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def regular_user(db_session):
    return create_test_user(
        db_session,
        email=f"user_{uuid4().hex}@example.com",
        full_name="Regular User",
        role=UserRole.DOCTOR,
    )


@pytest.fixture
def admin_token(admin_user):
    token = f"admin_token_{admin_user.id}"
    app.dependency_overrides[get_current_user] = lambda: admin_user
    if TEST_TOKEN_REGISTRY is not None:
        TEST_TOKEN_REGISTRY[token] = admin_user
    yield token
    if TEST_TOKEN_REGISTRY is not None:
        TEST_TOKEN_REGISTRY.pop(token, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def user_token(regular_user):
    token = f"test_token_{regular_user.id}"
    app.dependency_overrides[get_current_user] = lambda: regular_user
    if TEST_TOKEN_REGISTRY is not None:
        TEST_TOKEN_REGISTRY[token] = regular_user
    yield token
    if TEST_TOKEN_REGISTRY is not None:
        TEST_TOKEN_REGISTRY.pop(token, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def sample_user(db_session):
    return create_test_user(
        db_session,
        email=f"sample_{uuid4().hex}@example.com",
        full_name="Sample User",
        role=UserRole.DOCTOR,
        password="SamplePass123!",
    )


@pytest.fixture
def sample_users(db_session):
    users = []
    for _ in range(3):
        users.append(
            create_test_user(
                db_session,
                email=f"sample_{uuid4().hex}@example.com",
                full_name="Sample User",
                role=UserRole.DOCTOR,
            )
        )
    return users


@pytest.fixture
def sample_appointments(db_session, sample_users):
    from datetime import datetime, timezone
    from tests.conftest import create_test_patient

    appointments = []
    for user in sample_users:
        patient = create_test_patient(
            db_session,
            doctor=user,
            name=f"Appointment Patient {uuid4().hex}",
        )
        appointment = Appointment(
            patient_id=patient.id,
            practitioner_id=user.id,
            appointment_type=AppointmentType.CONSULTATION.value,
            status=AppointmentStatus.SCHEDULED.value,
            scheduled_at=datetime.now(timezone.utc),
        )
        db_session.add(appointment)
        appointments.append(appointment)

    db_session.commit()
    for appointment in appointments:
        db_session.refresh(appointment)
    return appointments


@pytest.fixture(autouse=True)
def auto_csrf_headers(monkeypatch: pytest.MonkeyPatch):
    """Inject CSRF headers/cookies for state-changing requests in API tests."""
    original_request = TestClient.request

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

    monkeypatch.setattr(TestClient, "request", _request)


@pytest.fixture(autouse=True)
def clear_system_stats_cache():
    cache_manager = get_unified_cache_manager()
    cache_manager.delete("system_metrics", ["admin-system-stats"])
    yield
    cache_manager.delete("system_metrics", ["admin-system-stats"])
