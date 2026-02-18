"""Tests for patient create idempotency (DB + Redis)."""

from datetime import datetime, timedelta, timezone
from typing import Dict
from uuid import UUID, uuid4

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.dependencies.auth_dependencies import get_current_user_from_session
from app.main import app
from app.models.patient import Patient
from app.models.user import UserRole
from tests.conftest import create_test_user
import app.repositories.patient.base as patient_repo_module


class TimeController:
    """Mutable clock for time-based tests."""

    def __init__(self, now: datetime):
        self.now = now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


class RedisStub:
    """Redis stub with TTL support."""

    def __init__(self, clock: TimeController):
        self._clock = clock
        self._store: Dict[str, tuple[str, datetime]] = {}

    def get(self, key: str):
        entry = self._store.get(key)
        if not entry:
            return None
        value, expires_at = entry
        if expires_at and self._clock.now >= expires_at:
            self._store.pop(key, None)
            return None
        return value

    def setex(self, key: str, ttl: int, value: str):
        self._store[key] = (value, self._clock.now + timedelta(seconds=ttl))


@pytest.fixture
def time_controller(monkeypatch: pytest.MonkeyPatch) -> TimeController:
    controller = TimeController(datetime(2025, 1, 1, tzinfo=SAO_PAULO_TZ))

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            current = controller.now
            if tz:
                return current.astimezone(tz)
            return current.replace(tzinfo=None)

    monkeypatch.setattr(patient_repo_module, "datetime", FrozenDateTime)
    return controller


@pytest.fixture
def redis_stub(time_controller: TimeController) -> RedisStub:
    return RedisStub(time_controller)


@pytest.fixture
def redis_client_stub(monkeypatch: pytest.MonkeyPatch, redis_stub: RedisStub) -> RedisStub:
    monkeypatch.setattr("app.core.redis_client.get_redis_client", lambda: redis_stub)
    return redis_stub


@pytest.fixture
def auth_client_factory(client: TestClient, db: Session):
    """Factory that returns (client, headers_dict) with proper auth setup."""
    from app.dependencies.auth_dependencies import (
        get_current_user,
        get_current_user_object_from_session,
        get_permissions_for_role,
    )
    from app.main import app

    def _make(user):
        role = user.role.value if hasattr(user.role, "value") else str(user.role)
        session_user = {
            "id": str(user.id),
            "email": user.email,
            "full_name": getattr(user, "full_name", user.email),
            "role": role,
            "is_active": True,
            "firebase_uid": getattr(user, "firebase_uid", "test-uid"),
            "permissions": get_permissions_for_role(role),
        }

        async def _override_session(_request: Request):
            _request.state.user_id = session_user.get("id")
            _request.state.user_role = session_user.get("role")
            return session_user

        async def _override_current_user(_request: Request):
            _request.state.user = user
            _request.state.user_id = str(user.id)
            _request.state.user_role = role
            return user

        app.dependency_overrides[get_current_user_from_session] = _override_session
        app.dependency_overrides[get_current_user_object_from_session] = lambda: user
        app.dependency_overrides[get_current_user] = _override_current_user

        headers = {
            "X-Session-ID": f"test-session-{user.id}",
            "Authorization": f"Bearer test-token-{user.id}",
        }
        return client, headers

    yield _make
    app.dependency_overrides.pop(get_current_user_from_session, None)
    app.dependency_overrides.pop(get_current_user_object_from_session, None)
    app.dependency_overrides.pop(get_current_user, None)


def _patient_payload(doctor_id):
    phone_digits = f"{uuid4().int:010d}"[-8:]
    return {
        "name": "Idempotent Patient",
        "email": f"idem_{uuid4()}@gmail.com",
        "phone": f"(11) 9{phone_digits[:4]}-{phone_digits[4:]}",
        "doctor_id": str(doctor_id),  # Convert UUID to string for JSON
    }



def test_idempotency_db_hit_rbac_respected(
    auth_client_factory,
    db: Session,
    redis_client_stub: RedisStub,
):
    doctor = create_test_user(db, email=f"doc_{uuid4()}@example.com", role=UserRole.DOCTOR)
    other_doctor = create_test_user(
        db, email=f"doc_{uuid4()}@example.com", role=UserRole.DOCTOR
    )

    client, headers = auth_client_factory(doctor)
    idempotency_key = f"idem-{uuid4()}"
    payload = _patient_payload(doctor.id)

    response1 = client.post(
        "/api/v2/patients",
        json=payload,
        headers={**headers, "X-Idempotency-Key": idempotency_key},
    )
    assert response1.status_code == 201, f"Expected 201, got {response1.status_code}: {response1.text}"
    patient1 = response1.json()

    response2 = client.post(
        "/api/v2/patients",
        json=payload,
        headers={**headers, "X-Idempotency-Key": idempotency_key},
    )
    assert response2.status_code == 200
    assert response2.json()["id"] == patient1["id"]

    other_client, other_headers = auth_client_factory(other_doctor)
    response3 = other_client.post(
        "/api/v2/patients",
        json=payload,
        headers={**other_headers, "X-Idempotency-Key": idempotency_key},
    )
    assert response3.status_code == 403


def test_idempotency_redis_hit_returns_cached_payload(
    auth_client_factory,
    db: Session,
    redis_client_stub: RedisStub,
    monkeypatch: pytest.MonkeyPatch,
):
    doctor = create_test_user(db, email=f"doc_{uuid4()}@example.com", role=UserRole.DOCTOR)
    client, headers = auth_client_factory(doctor)

    idempotency_key = f"idem-{uuid4()}"
    payload = _patient_payload(doctor.id)

    response1 = client.post(
        "/api/v2/patients",
        json=payload,
        headers={**headers, "X-Idempotency-Key": idempotency_key},
    )
    assert response1.status_code == 201
    patient1 = response1.json()

    cache_key = f"idempotency:patient:create:{idempotency_key}"
    cached = redis_client_stub.get(cache_key)
    assert cached is not None

    monkeypatch.setattr(
        "app.repositories.patient.PatientRepository.get_by_idempotency_key",
        lambda _self, _key: None,
    )

    response2 = client.post(
        "/api/v2/patients",
        json=payload,
        headers={**headers, "X-Idempotency-Key": idempotency_key},
    )
    assert response2.status_code == 200
    assert response2.json()["id"] == patient1["id"]


def test_idempotency_redis_down_fallbacks_to_db(
    auth_client_factory,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    class RedisDown:
        def get(self, _key):
            raise RuntimeError("redis down")

        def setex(self, _key, _ttl, _value):
            raise RuntimeError("redis down")

    monkeypatch.setattr("app.core.redis_client.get_redis_client", lambda: RedisDown())

    doctor = create_test_user(db, email=f"doc_{uuid4()}@example.com", role=UserRole.DOCTOR)
    client, headers = auth_client_factory(doctor)

    idempotency_key = f"idem-{uuid4()}"
    payload = _patient_payload(doctor.id)

    response1 = client.post(
        "/api/v2/patients",
        json=payload,
        headers={**headers, "X-Idempotency-Key": idempotency_key},
    )
    assert response1.status_code == 201
    patient1 = response1.json()

    response2 = client.post(
        "/api/v2/patients",
        json=payload,
        headers={**headers, "X-Idempotency-Key": idempotency_key},
    )
    assert response2.status_code == 200
    assert response2.json()["id"] == patient1["id"]


def test_idempotency_expired_key_allows_new_creation(
    auth_client_factory,
    db: Session,
    redis_client_stub: RedisStub,
    time_controller: TimeController,
):
    doctor = create_test_user(db, email=f"doc_{uuid4()}@example.com", role=UserRole.DOCTOR)
    client, headers = auth_client_factory(doctor)

    idempotency_key = f"idem-{uuid4()}"
    payload = _patient_payload(doctor.id)

    response1 = client.post(
        "/api/v2/patients",
        json=payload,
        headers={**headers, "X-Idempotency-Key": idempotency_key},
    )
    assert response1.status_code == 201
    patient1 = response1.json()

    patient_uuid = UUID(patient1["id"])
    patient = db.query(Patient).filter(Patient.id == patient_uuid).first()
    patient.created_at = time_controller.now
    db.commit()

    time_controller.advance(hours=25)

    payload_new = _patient_payload(doctor.id)
    response2 = client.post(
        "/api/v2/patients",
        json=payload_new,
        headers={**headers, "X-Idempotency-Key": idempotency_key},
    )

    assert response2.status_code == 201
    patient2 = response2.json()
    assert patient2["id"] != patient1["id"]

    db.refresh(patient)
    assert patient.idempotency_key is None

from app.utils.timezone import SAO_PAULO_TZ
