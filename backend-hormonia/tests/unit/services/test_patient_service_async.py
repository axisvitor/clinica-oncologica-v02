from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.models.user import UserRole
from app.services.patient.sync_service import PatientSyncService
from app.services.patient.validation_service import PatientValidationService


class _FakeScalarResult:
    def __init__(self, values):
        self._values = list(values)

    def first(self):
        return self._values[0] if self._values else None


class _FakeExecuteResult:
    def __init__(self, values=None):
        self._values = list(values or [])

    def scalars(self):
        return _FakeScalarResult(self._values)


class _QueueAsyncSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.execute = AsyncMock(side_effect=self._execute)
        self.commit = AsyncMock()
        self.refresh = AsyncMock()
        self.rollback = AsyncMock()
        self.add = Mock()

    async def _execute(self, statement):
        if not self._responses:
            raise AssertionError("Unexpected execute call with no queued response")
        return self._responses.pop(0)

    def query(self, *args, **kwargs):
        raise AssertionError("sync db.query should not be used")


class _SyncDuplicateDb:
    def __init__(self, patient):
        self._patient = patient
        self.execute_calls = []

    def execute(self, statement):
        self.execute_calls.append(statement)
        return _FakeExecuteResult([self._patient])

    def query(self, *args, **kwargs):
        raise AssertionError("sync db.query should not be used")


@pytest.mark.asyncio
async def test_merge_patients_async_path_uses_execute_without_sync_query():
    primary_id = uuid4()
    duplicate_id = uuid4()
    primary = SimpleNamespace(
        id=primary_id,
        patient_data={"source": "primary"},
        email=None,
        birth_date=None,
        treatment_type=None,
        treatment_start_date=None,
    )
    duplicate = SimpleNamespace(
        id=duplicate_id,
        patient_data={"legacy": "value"},
        email="duplicate@example.com",
        birth_date=None,
        treatment_type="chemo",
        treatment_start_date=None,
    )

    db = _QueueAsyncSession(
        [
            _FakeExecuteResult([primary]),
            _FakeExecuteResult([duplicate]),
            _FakeExecuteResult(),
            _FakeExecuteResult(),
            _FakeExecuteResult(),
            _FakeExecuteResult([duplicate]),
        ]
    )
    service = PatientSyncService(db=db)

    merged = await service.merge_patients(primary_id, duplicate_id)

    assert merged is primary
    assert merged.email == "duplicate@example.com"
    assert merged.patient_data["source"] == "primary"
    assert merged.patient_data["legacy"] == "value"
    assert duplicate.patient_data["deleted"] is True
    assert duplicate.flow_state.name == "INACTIVE"
    assert db.execute.await_count == 6
    assert db.commit.await_count == 3
    assert db.refresh.await_count == 1


def test_duplicate_email_check_uses_select_execute_path(monkeypatch):
    existing = SimpleNamespace(name="Paciente Existente")
    db = _SyncDuplicateDb(patient=existing)
    service = PatientSyncService(db=db)

    fake_crypto = SimpleNamespace(hash_email=lambda value: f"hash:{value}")
    monkeypatch.setattr(
        "app.services.encryption.get_lgpd_encryption_service",
        lambda: fake_crypto,
        raising=False,
    )

    found = service.check_duplicate_email("existing@example.com")

    assert found is existing
    assert len(db.execute_calls) == 1


@pytest.mark.asyncio
async def test_validate_doctor_exists_async_uses_execute_not_query():
    doctor = SimpleNamespace(id=uuid4(), role=UserRole.DOCTOR)
    db = _QueueAsyncSession([_FakeExecuteResult([doctor])])
    validation = PatientValidationService(db=db)

    result = await validation._validate_doctor_exists_async(doctor.id)

    assert result is True
    assert db.execute.await_count == 1
