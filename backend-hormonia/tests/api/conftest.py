"""Shared fixtures for API tests."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies.auth_dependencies import get_current_user, get_current_user_from_session
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
    """Override auth to return admin_user for all authenticated endpoints.

    Overrides both get_current_user (Bearer-token flow) and get_admin_user
    (admin router dependency) so admin contract tests work without real auth.
    """
    from app.api.v2.routers.admin.dependencies import get_admin_user

    token = f"admin_token_{admin_user.id}"
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_current_user_from_session] = lambda: {
        "id": str(admin_user.id),
        "email": admin_user.email,
        "full_name": admin_user.full_name,
        "role": admin_user.role.value if hasattr(admin_user.role, "value") else str(admin_user.role),
        "is_active": admin_user.is_active,
        "firebase_uid": getattr(admin_user, "firebase_uid", None),
        "permissions": [],
    }
    app.dependency_overrides[get_admin_user] = lambda: admin_user
    yield token
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_user_from_session, None)
    app.dependency_overrides.pop(get_admin_user, None)


@pytest.fixture
def user_token(regular_user):
    """Override auth to return regular_user for all authenticated endpoints."""
    token = f"test_token_{regular_user.id}"
    app.dependency_overrides[get_current_user] = lambda: regular_user
    app.dependency_overrides[get_current_user_from_session] = lambda: {
        "id": str(regular_user.id),
        "email": regular_user.email,
        "full_name": regular_user.full_name,
        "role": regular_user.role.value if hasattr(regular_user.role, "value") else str(regular_user.role),
        "is_active": regular_user.is_active,
        "firebase_uid": getattr(regular_user, "firebase_uid", None),
        "permissions": [],
    }
    yield token
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_user_from_session, None)


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
            scheduled_at=now_sao_paulo(),
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
from app.utils.timezone import now_sao_paulo
