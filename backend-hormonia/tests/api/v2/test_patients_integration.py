"""Integration-style tests for the patients v2 API flow."""

import asyncio
import os
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from uuid import uuid4, UUID

import httpx
import pytest
from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

try:
    import redis
except ImportError:  # pragma: no cover - optional dependency in some environments
    redis = None

from app.utils.security import get_password_hash
from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.main import app
from app.models.patient import Patient
from app.models.user import User, UserRole


@pytest.fixture
async def async_client_with_doctor(db: Session):
    doctor = _get_or_create_doctor(db)

    SessionLocal = sessionmaker(bind=db.get_bind())

    async def _override_session(_request: Request):
        return {
            "id": str(doctor.id),
            "email": doctor.email,
            "role": doctor.role.value if hasattr(doctor.role, "value") else str(doctor.role),
        }

    def _override_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user_from_session] = _override_session

    async with httpx.AsyncClient(app=app, base_url="http://test") as async_client:
        csrf_response = await async_client.get("/csrf-token")
        if csrf_response.status_code == 200:
            csrf_payload = csrf_response.json()
            csrf_token = csrf_payload.get("csrf_token")
            if csrf_token:
                async_client.headers["X-CSRF-Token"] = csrf_token
        yield async_client, doctor

    app.dependency_overrides.clear()


def _unique_email(prefix: str = "test") -> str:
    return f"{prefix}_{uuid4()}@gmail.com"


def _unique_phone():
    return f"119{uuid4().int % 10**8:08d}"


def _get_or_create_doctor(db: Session) -> User:
    doctor = db.query(User).filter(User.role == UserRole.DOCTOR).first()
    if doctor:
        return doctor

    doctor = User(
        id=uuid4(),
        email=_unique_email("doctor"),
        hashed_password=get_password_hash("testpass123"),
        full_name="Test Doctor",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


def _redis_available() -> bool:
    if redis is None:
        return False
    redis_url = os.getenv("TEST_REDIS_URL") or os.getenv("REDIS_URL")
    if not redis_url:
        return False
    parsed = urlparse(redis_url)
    host = parsed.hostname or ""
    if host not in {"localhost", "127.0.0.1"} and os.getenv(
        "ALLOW_REMOTE_REDIS_TESTS", ""
    ).lower() not in ("1", "true", "yes"):
        return False
    try:
        client = redis.Redis.from_url(
            redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        client.close()
        return True
    except Exception:
        return False


@pytest.fixture
def doctor_session_override(db: Session):
    doctor = _get_or_create_doctor(db)

    async def _override_session(_request: Request):
        return {
            "id": str(doctor.id),
            "email": doctor.email,
            "role": doctor.role.value if hasattr(doctor.role, "value") else str(doctor.role),
        }

    app.dependency_overrides[get_current_user_from_session] = _override_session
    yield doctor
    app.dependency_overrides.pop(get_current_user_from_session, None)


def test_create_patient_full_flow(client, doctor_session_override, monkeypatch):
    """Create patient triggers saga steps for flow init and welcome message."""
    doctor = doctor_session_override

    step_calls = {"flow": False, "welcome": False}

    async def _step_initialize_flow(
        _self,
        _saga,
        _patient,
        _current_user,
        idempotency_key=None,
    ):
        step_calls["flow"] = True

    async def _step_send_welcome_message(
        _self,
        _saga,
        _patient,
        idempotency_key=None,
    ):
        step_calls["welcome"] = True

    @asynccontextmanager
    async def _noop_lock(*_args, **_kwargs):
        yield

    monkeypatch.setattr(
        "app.orchestration.saga_orchestrator.orchestrator.SagaStepExecutor.step_initialize_flow",
        _step_initialize_flow,
    )
    monkeypatch.setattr(
        "app.orchestration.saga_orchestrator.orchestrator.SagaStepExecutor.step_send_welcome_message",
        _step_send_welcome_message,
    )
    monkeypatch.setattr(
        "app.orchestration.saga_orchestrator.orchestrator.acquire_lock",
        _noop_lock,
    )

    patient_data = {
        "name": "Flow Patient",
        "email": _unique_email("flow"),
        "phone": "(11) 98765-4321",
        "doctor_id": str(doctor.id),
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
    )

    assert response.status_code == 201
    assert step_calls["flow"] is True
    assert step_calls["welcome"] is True


def test_create_patient_idempotency_duplicate(client, doctor_session_override):
    """Duplicate idempotency key returns same patient and 200."""
    doctor = doctor_session_override

    idempotency_key = f"idem-{uuid4()}"
    patient_data = {
        "name": "Idempotency Patient",
        "email": _unique_email("idem"),
        "phone": "(11) 98765-4321",
        "doctor_id": str(doctor.id),
    }

    response1 = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers={"X-Idempotency-Key": idempotency_key},
    )
    assert response1.status_code == 201
    patient1 = response1.json()

    response2 = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers={"X-Idempotency-Key": idempotency_key},
    )
    assert response2.status_code == 200
    patient2 = response2.json()

    assert patient1["id"] == patient2["id"]


def test_create_patient_invalid_data_no_record(client, doctor_session_override, db: Session):
    """Invalid payload returns 422 and does not create patient."""
    doctor = doctor_session_override

    initial_count = db.query(Patient).count()

    patient_data = {
        "name": "Invalid Data",
        "email": "invalid-email",
        "phone": "(11) 98765-4321",
        "doctor_id": str(doctor.id),
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
    )

    assert response.status_code == 422
    assert db.query(Patient).count() == initial_count


def test_create_patient_with_valid_metadata_stores_metadata(
    client, doctor_session_override, db: Session
):
    """Create patient with valid metadata stores patient_data in DB."""
    doctor = doctor_session_override

    patient_data = {
        "name": "Metadata Patient",
        "email": _unique_email("metadata"),
        "phone": _unique_phone(),
        "doctor_id": str(doctor.id),
        "patient_data": {
            "preferences": {"communication_channel": "whatsapp"},
            "insurance": {"provider": "Unimed"},
            "doctor_name": "Dr. Integration",
            "system": {"source": "api"},
        },
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
    )

    assert response.status_code == 201
    patient_id = response.json()["id"]
    patient = db.query(Patient).filter(Patient.id == UUID(patient_id)).first()

    assert patient is not None
    assert patient.patient_data is not None
    assert patient.patient_data["preferences"]["communication_channel"] == "whatsapp"
    assert patient.patient_data["insurance"]["provider"] == "Unimed"
    assert patient.patient_data["doctor_name"] == "Dr. Integration"
    assert patient.patient_data["system"]["source"] == "api"


def test_create_patient_with_unknown_metadata_moves_to_custom_fields(
    client, doctor_session_override, db: Session
):
    """Unknown metadata keys are moved to custom_fields."""
    doctor = doctor_session_override

    patient_data = {
        "name": "Metadata Unknown Patient",
        "email": _unique_email("metadata_unknown"),
        "phone": _unique_phone(),
        "doctor_id": str(doctor.id),
        "patient_data": {"unknown_key": "value"},
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
    )

    assert response.status_code == 201
    patient_id = response.json()["id"]
    patient = db.query(Patient).filter(Patient.id == UUID(patient_id)).first()

    assert patient is not None
    assert patient.patient_data is not None
    assert patient.patient_data["custom_fields"]["unknown_key"] == "value"


def test_create_patient_with_clinical_fields_conversion(
    client, doctor_session_override, db: Session
):
    """Clinical field strings are converted to v1 schema structures."""
    doctor = doctor_session_override

    patient_data = {
        "name": "Clinical Fields Patient",
        "email": _unique_email("clinical"),
        "phone": _unique_phone(),
        "doctor_id": str(doctor.id),
        "allergies": "A/B",
        "medications": "Med 500mg/dia",
        "emergency_contact": "Contato - (11) 99999-9999",
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
    )

    assert response.status_code == 201
    patient_id = response.json()["id"]
    patient = db.query(Patient).filter(Patient.id == UUID(patient_id)).first()

    assert patient is not None
    assert patient.patient_data is not None
    assert patient.patient_data["medical_history"]["allergies"] == ["A", "B"]
    assert patient.patient_data["medical_history"]["medications"] == ["Med 500mg/dia"]
    assert patient.patient_data["emergency_contact"]["name"] == "Contato"
    assert patient.patient_data["emergency_contact"]["phone"] == "+5511999999999"


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _redis_available(), reason="Redis not available for lock tests"
)
async def test_concurrent_idempotency_same_key(async_client_with_doctor):
    """Concurrent requests with same idempotency key return same patient."""
    async_client, doctor = async_client_with_doctor

    idempotency_key = f"idem-{uuid4()}"
    patient_data = {
        "name": "Concurrent Idem",
        "email": _unique_email("concurrent"),
        "phone": "(11) 98765-4321",
        "doctor_id": str(doctor.id),
    }

    async def _post():
        return await async_client.post(
            "/api/v2/patients",
            json=patient_data,
            headers={"X-Idempotency-Key": idempotency_key},
        )

    responses = await asyncio.gather(*[_post() for _ in range(3)])
    statuses = {resp.status_code for resp in responses}
    assert statuses.issubset({200, 201})

    patient_ids = {resp.json()["id"] for resp in responses}
    assert len(patient_ids) == 1


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _redis_available(), reason="Redis not available for lock tests"
)
async def test_concurrent_create_different_patients(async_client_with_doctor):
    """Concurrent requests for different patients create unique records."""
    async_client, doctor = async_client_with_doctor

    payloads = [
            {
                "name": f"Concurrent {i}",
                "email": _unique_email("concurrent"),
                "phone": f"(11) 98{i:03}5-4321",
                "doctor_id": str(doctor.id),
            }
        for i in range(3)
    ]

    async def _post(data):
        return await async_client.post("/api/v2/patients", json=data)

    responses = await asyncio.gather(*[_post(data) for data in payloads])
    assert all(resp.status_code == 201 for resp in responses)

    patient_ids = {resp.json()["id"] for resp in responses}
    assert len(patient_ids) == len(payloads)
