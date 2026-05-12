import logging
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, status

from app.api.v2 import patients_shared_helpers as helpers
from app.api.v2.patients_shared_helpers import (
    assert_admin_or_assigned_doctor,
    load_patient_with_access,
)
from app.models.patient import Patient
from app.models.user import User, UserRole


class _ScalarResult:
    def __init__(self, patient):
        self._patient = patient

    def scalar_one_or_none(self):
        return self._patient


class _FakeAsyncSession:
    def __init__(self, patient):
        self._patient = patient
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _ScalarResult(self._patient)


def _patient(*, patient_id: UUID | None = None, doctor_id: UUID | None = None) -> Patient:
    return Patient(
        id=patient_id or uuid4(),
        name="Sensitive Patient Name",
        doctor_id=doctor_id,
    )


def _doctor_session(
    user_id: UUID | str | None,
    role: str | UserRole = "doctor",
) -> dict:
    payload = {"role": role}
    if user_id is not None:
        payload["id"] = str(user_id)
    return payload


def _deny_records(caplog):
    return [
        record
        for record in caplog.records
        if record.name == helpers.__name__
        and record.getMessage() == "Patient access denied"
    ]


def test_dict_user_assigned_doctor_passes():
    doctor_id = uuid4()

    assert_admin_or_assigned_doctor(
        current_user={"id": str(doctor_id), "role": "doctor"},
        patient_doctor_id=doctor_id,
        patient_id=uuid4(),
    )


def test_user_model_assigned_doctor_passes():
    doctor_id = uuid4()
    current_user = User(
        id=doctor_id,
        email="doctor@example.com",
        role=UserRole.DOCTOR,
    )

    assert_admin_or_assigned_doctor(
        current_user=current_user,
        patient_doctor_id=doctor_id,
        patient_id=uuid4(),
    )


def test_admin_passes_for_foreign_and_unassigned_patients():
    admin_id = uuid4()

    assert_admin_or_assigned_doctor(
        current_user={"id": str(admin_id), "role": "admin"},
        patient_doctor_id=uuid4(),
        patient_id=uuid4(),
    )
    assert_admin_or_assigned_doctor(
        current_user=User(
            id=admin_id,
            email="admin@example.com",
            role=UserRole.ADMIN,
        ),
        patient_doctor_id=None,
        patient_id=uuid4(),
    )


def test_foreign_doctor_gets_generic_403_and_structured_deny_log(caplog):
    caplog.set_level(logging.WARNING, logger=helpers.__name__)
    actor_id = uuid4()
    patient_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        assert_admin_or_assigned_doctor(
            current_user=_doctor_session(actor_id),
            patient_doctor_id=uuid4(),
            patient_id=patient_id,
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "Not enough permissions to access this patient"

    records = _deny_records(caplog)
    assert len(records) == 1
    record = records[0]
    assert record.actor_id == str(actor_id)
    assert record.actor_role == "doctor"
    assert record.patient_id == str(patient_id)
    assert record.resource_id == str(patient_id)
    assert record.reason == "foreign_patient"

    log_text = caplog.text
    assert "Sensitive Patient Name" not in log_text
    assert "patient@example.com" not in log_text
    assert "+5511999998888" not in log_text
    assert "message content" not in log_text
    assert "secret" not in log_text.lower()


@pytest.mark.parametrize(
    "current_user",
    [
        {"role": "doctor"},
        {"id": "not-a-uuid", "role": "doctor"},
        {"role": "admin"},
        {"id": "not-a-uuid", "role": "admin"},
    ],
)
def test_missing_or_invalid_user_id_gets_403(current_user, caplog):
    caplog.set_level(logging.WARNING, logger=helpers.__name__)

    with pytest.raises(HTTPException) as exc_info:
        assert_admin_or_assigned_doctor(
            current_user=current_user,
            patient_doctor_id=uuid4(),
            patient_id=uuid4(),
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    records = _deny_records(caplog)
    assert len(records) == 1
    assert records[0].actor_id is None
    assert records[0].actor_role == current_user["role"]
    assert records[0].reason == "invalid_user_id"


def test_malformed_session_role_fails_closed_with_403(caplog):
    caplog.set_level(logging.WARNING, logger=helpers.__name__)
    actor_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        assert_admin_or_assigned_doctor(
            current_user={"id": str(actor_id), "role": "owner"},
            patient_doctor_id=actor_id,
            patient_id=uuid4(),
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    records = _deny_records(caplog)
    assert len(records) == 1
    assert records[0].actor_id == str(actor_id)
    assert records[0].actor_role is None
    assert records[0].reason == "invalid_user_context"


def test_unassigned_patient_gets_403_for_doctor(caplog):
    caplog.set_level(logging.WARNING, logger=helpers.__name__)
    doctor_id = uuid4()
    patient_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        assert_admin_or_assigned_doctor(
            current_user=_doctor_session(doctor_id),
            patient_doctor_id=None,
            patient_id=patient_id,
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    records = _deny_records(caplog)
    assert len(records) == 1
    assert records[0].actor_id == str(doctor_id)
    assert records[0].actor_role == "doctor"
    assert records[0].patient_id == str(patient_id)
    assert records[0].reason == "patient_unassigned"


@pytest.mark.asyncio
async def test_load_patient_with_access_returns_patient_for_assigned_doctor():
    doctor_id = uuid4()
    patient = _patient(doctor_id=doctor_id)
    db = _FakeAsyncSession(patient)

    loaded = await load_patient_with_access(
        db=db,
        patient_id=patient.id,
        current_user=_doctor_session(doctor_id),
    )

    assert loaded is patient
    assert len(db.statements) == 1


@pytest.mark.asyncio
async def test_load_patient_with_access_allows_admin_for_foreign_patient():
    patient = _patient(doctor_id=uuid4())
    db = _FakeAsyncSession(patient)
    admin = User(
        id=uuid4(),
        email="admin@example.com",
        role=UserRole.ADMIN,
    )

    loaded = await load_patient_with_access(
        db=db,
        patient_id=str(patient.id),
        current_user=admin,
    )

    assert loaded is patient
    assert len(db.statements) == 1


@pytest.mark.asyncio
async def test_load_patient_with_access_not_found_returns_404():
    db = _FakeAsyncSession(None)

    with pytest.raises(HTTPException) as exc_info:
        await load_patient_with_access(
            db=db,
            patient_id=uuid4(),
            current_user=_doctor_session(uuid4()),
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "Patient not found"
    assert len(db.statements) == 1


def test_logging_failure_does_not_change_authorization_outcome(monkeypatch):
    def _raise_logging_error(*args, **kwargs):
        raise RuntimeError("logger unavailable")

    monkeypatch.setattr(helpers.logger, "warning", _raise_logging_error)

    with pytest.raises(HTTPException) as exc_info:
        assert_admin_or_assigned_doctor(
            current_user=_doctor_session(uuid4()),
            patient_doctor_id=uuid4(),
            patient_id=uuid4(),
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "Not enough permissions to access this patient"
