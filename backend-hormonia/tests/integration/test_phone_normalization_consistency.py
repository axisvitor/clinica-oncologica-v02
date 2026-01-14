import time
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.models.patient import Patient
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.repositories.patient import PatientRepository
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services.patient.crud_service import PatientCRUDService
from app.services.patient.integrity_service import PatientIntegrityService


DOCTOR_ID = UUID("28844c5c-6bb8-484f-9502-b6a22c466745")


def _build_phone_variants(seed: int) -> tuple[str, str, str]:
    suffix = f"{seed % 100000000:08d}"
    digits = f"11{9}{suffix}"
    formatted = f"(11) 9{suffix[:4]}-{suffix[4:]}"
    e164 = f"+55{digits}"
    return digits, formatted, e164


def _unique_email(seed: int) -> str:
    return f"phone_norm_{seed}@example.com"


@pytest.fixture
def integration_client(real_db_session):
    def _override_user():
        return {
            "id": str(DOCTOR_ID),
            "email": "admin@example.com",
            "role": "admin",
            "is_active": True,
        }

    app.dependency_overrides[get_db] = lambda: real_db_session
    app.dependency_overrides[get_current_user_from_session] = _override_user

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.integration
def test_phone_normalization_v1_schema_persists_e164(
    real_db_session,
    cleanup_patients,
):
    seed = int(time.time() * 1000)
    digits, _, expected = _build_phone_variants(seed)
    patient_data = PatientCreate(
        name=f"Phone Norm V1 {seed}",
        phone=digits,
        email=_unique_email(seed),
    )

    repo = PatientRepository(real_db_session)
    patient = repo.create(
        {**patient_data.model_dump(exclude_unset=True), "doctor_id": DOCTOR_ID}
    )
    cleanup_patients.track(patient.id)

    db_patient = (
        real_db_session.query(Patient).filter(Patient.id == patient.id).first()
    )
    assert db_patient is not None
    assert db_patient.phone == expected


@pytest.mark.integration
def test_phone_normalization_v2_api_persists_e164(
    integration_client,
    real_db_session,
    cleanup_patients,
):
    seed = int(time.time() * 1000)
    _, formatted, expected = _build_phone_variants(seed)
    payload = {
        "name": f"Phone Norm V2 {seed}",
        "phone": formatted,
        "email": _unique_email(seed),
        "doctor_id": str(DOCTOR_ID),
    }

    response = integration_client.post(
        "/api/v2/patients",
        json=payload,
        headers={"X-Session-ID": f"session-{seed}"},
    )
    assert response.status_code == 201, response.text
    patient_id = response.json().get("id")
    assert patient_id

    cleanup_patients.track(UUID(patient_id))
    db_patient = (
        real_db_session.query(Patient)
        .filter(Patient.id == UUID(patient_id))
        .first()
    )
    assert db_patient is not None
    assert db_patient.phone == expected


@pytest.mark.integration
@pytest.mark.asyncio
async def test_phone_normalization_saga_persists_e164(
    real_saga_orchestrator,
    real_db_session,
    cleanup_patients,
    cleanup_sagas,
):
    seed = int(time.time() * 1000)
    _, formatted, expected = _build_phone_variants(seed)
    patient_data = PatientCreate(
        name=f"Phone Norm Saga {seed}",
        phone=formatted,
        email=_unique_email(seed),
    )

    patient = await real_saga_orchestrator.execute_patient_onboarding_saga(
        patient_data=patient_data,
        doctor_id=DOCTOR_ID,
    )
    assert patient is not None
    cleanup_patients.track(patient.id)

    db_patient = (
        real_db_session.query(Patient).filter(Patient.id == patient.id).first()
    )
    assert db_patient is not None
    assert db_patient.phone == expected

    saga = (
        real_db_session.query(PatientOnboardingSaga)
        .filter(PatientOnboardingSaga.patient_id == patient.id)
        .first()
    )
    if saga:
        cleanup_sagas.track(saga.id)


@pytest.mark.integration
def test_phone_duplicate_check_normalizes_variants(
    real_db_session,
    cleanup_patients,
):
    seed = int(time.time() * 1000)
    digits, formatted, expected = _build_phone_variants(seed)
    patient_data = PatientCreate(
        name=f"Phone Norm Duplicate {seed}",
        phone=digits,
        email=_unique_email(seed),
    )

    repo = PatientRepository(real_db_session)
    patient = repo.create(
        {**patient_data.model_dump(exclude_unset=True), "doctor_id": DOCTOR_ID}
    )
    cleanup_patients.track(patient.id)

    integrity_service = PatientIntegrityService(real_db_session, repo)
    duplicate_formatted = integrity_service._check_duplicate_phone(
        formatted, doctor_id=DOCTOR_ID
    )
    duplicate_e164 = integrity_service._check_duplicate_phone(
        expected, doctor_id=DOCTOR_ID
    )

    assert duplicate_formatted is not None
    assert duplicate_formatted.id == patient.id
    assert duplicate_e164 is not None
    assert duplicate_e164.id == patient.id


@pytest.mark.integration
def test_phone_update_normalizes_format(
    real_db_session,
    cleanup_patients,
):
    seed = int(time.time() * 1000)
    digits, formatted, expected = _build_phone_variants(seed)
    patient_data = PatientCreate(
        name=f"Phone Norm Update {seed}",
        phone=digits,
        email=_unique_email(seed),
    )

    repo = PatientRepository(real_db_session)
    patient = repo.create(
        {**patient_data.model_dump(exclude_unset=True), "doctor_id": DOCTOR_ID}
    )
    cleanup_patients.track(patient.id)

    service = PatientCRUDService(real_db_session, repo)
    updated = service.update_patient(
        patient.id,
        PatientUpdate(phone=formatted),
    )

    real_db_session.refresh(updated)
    assert updated.phone == expected
