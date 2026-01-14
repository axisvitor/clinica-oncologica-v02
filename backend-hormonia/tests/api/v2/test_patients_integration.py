"""Integration-style tests for the patients v2 API flow."""

import asyncio
import os
from contextlib import asynccontextmanager
from uuid import uuid4, UUID

import httpx
import pytest
from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.main import app
from app.models.patient import Patient
from app.models.user import User, UserRole


@pytest.fixture
async def async_client_with_doctor(db: Session):
    doctor = db.query(User).filter(User.role == UserRole.DOCTOR).first()
    if not doctor:
        pytest.skip("No doctor available for test")

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
        yield async_client, doctor

    app.dependency_overrides.clear()


def _unique_phone():
    return f"11{uuid4().int % 10**9:09d}"


@pytest.fixture
def doctor_session_override(db: Session):
    doctor = db.query(User).filter(User.role == UserRole.DOCTOR).first()
    if not doctor:
        pytest.skip("No doctor available for test")

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

    async def _step_initialize_flow(_self, _saga, _patient, _current_user):
        step_calls["flow"] = True

    async def _step_send_welcome_message(_self, _saga, _patient):
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
        "email": f"flow_{uuid4()}@example.com",
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
        "email": f"idem_{uuid4()}@example.com",
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
        "email": f"metadata_{uuid4()}@example.com",
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
        "email": f"metadata_unknown_{uuid4()}@example.com",
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
        "email": f"clinical_{uuid4()}@example.com",
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
    os.getenv("REDIS_URL") is None, reason="Redis not configured for lock tests"
)
async def test_concurrent_idempotency_same_key(async_client_with_doctor):
    """Concurrent requests with same idempotency key return same patient."""
    async_client, doctor = async_client_with_doctor

    idempotency_key = f"idem-{uuid4()}"
    patient_data = {
        "name": "Concurrent Idem",
        "email": f"concurrent_{uuid4()}@example.com",
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
    os.getenv("REDIS_URL") is None, reason="Redis not configured for lock tests"
)
async def test_concurrent_create_different_patients(async_client_with_doctor):
    """Concurrent requests for different patients create unique records."""
    async_client, doctor = async_client_with_doctor

    payloads = [
        {
            "name": f"Concurrent {i}",
            "email": f"concurrent_{uuid4()}@example.com",
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
