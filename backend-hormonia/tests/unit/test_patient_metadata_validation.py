"""
Unit tests for metadata validation and schema conversion in patient creation.
"""

import logging
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import Response
from starlette.requests import Request

from app.api.v2.routers.patients import crud
from app.schemas.v2.patient import PatientV2Create

LOGGER_NAME = "app.api.v2.routers.patients.crud"


class DummySagaOrchestrator:
    def __init__(self, *args, **kwargs):
        pass


class DummyEvolutionClient:
    def __init__(self, *args, **kwargs):
        pass


class DummyCoordinator:
    def __init__(self):
        self.calls = []

    async def create_patient(
        self,
        patient_data,
        doctor_id,
        current_user=None,
        idempotency_key=None,
    ):
        self.calls.append(
            {
                "patient_data": patient_data,
                "doctor_id": doctor_id,
                "current_user": current_user,
                "idempotency_key": idempotency_key,
            }
        )
        return {"id": "patient-id"}


@pytest.fixture
def create_patient_runner(monkeypatch):
    coordinator = DummyCoordinator()

    monkeypatch.setattr(
        "app.services.patient.onboarding_factory.get_onboarding_coordinator",
        lambda db, saga_orchestrator=None: coordinator,
    )
    monkeypatch.setattr(
        "app.orchestration.saga_orchestrator.SagaOrchestrator",
        DummySagaOrchestrator,
    )
    monkeypatch.setattr(
        "app.integrations.evolution.EvolutionClient",
        DummyEvolutionClient,
    )
    monkeypatch.setattr(
        "app.core.redis_client.get_redis_client",
        lambda: None,
    )

    async def _serialize_patient(patient):
        return patient

    monkeypatch.setattr(crud, "serialize_patient", _serialize_patient)

    async def _run(payload):
        request = Request(
            scope={
                "type": "http",
                "method": "POST",
                "path": "/api/v2/patients",
                "headers": [],
            }
        )
        response = Response()
        patient_model = PatientV2Create(**payload)
        current_user = {"id": str(payload["doctor_id"]), "role": "admin"}

        await crud.create_patient(
            request=request,
            response=response,
            patient_data=patient_model,
            db=MagicMock(),
            current_user=current_user,
            x_idempotency_key=None,
        )

        assert coordinator.calls
        return coordinator.calls[-1]["patient_data"]

    return _run


@pytest.fixture
def base_payload():
    return {
        "name": "Test Patient",
        "phone": "11999999999",
        "doctor_id": uuid4(),
    }


@pytest.mark.asyncio
async def test_metadata_valid_is_accepted(create_patient_runner, base_payload):
    payload = dict(base_payload)
    payload["patient_data"] = {
        "preferences": {"communication_channel": "whatsapp"},
        "insurance": {"provider": "Unimed"},
        "doctor_name": "Dr. Test",
        "system": {"source": "api"},
        "medical_history": {"allergies": ["Penicillin"]},
    }

    patient_create = await create_patient_runner(payload)

    assert patient_create.metadata == payload["patient_data"]


@pytest.mark.asyncio
async def test_metadata_empty_is_accepted(create_patient_runner, base_payload):
    payload = dict(base_payload)
    payload["patient_data"] = {}

    patient_create = await create_patient_runner(payload)

    assert patient_create.metadata is None


@pytest.mark.asyncio
async def test_metadata_custom_fields_only_is_accepted(
    create_patient_runner, base_payload
):
    payload = dict(base_payload)
    payload["patient_data"] = {"custom_fields": {"source": "import"}}

    patient_create = await create_patient_runner(payload)

    assert patient_create.metadata == {"custom_fields": {"source": "import"}}


@pytest.mark.asyncio
async def test_metadata_unknown_field_moves_to_custom_fields(
    create_patient_runner, base_payload, caplog
):
    payload = dict(base_payload)
    payload["patient_data"] = {"unknown_key": "value"}

    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    patient_create = await create_patient_runner(payload)

    assert patient_create.metadata == {"custom_fields": {"unknown_key": "value"}}

    records = [
        record
        for record in caplog.records
        if record.getMessage()
        == "Metadata key moved to custom_fields due to unknown key"
    ]
    assert records

    record = records[0]
    assert record.field == "patient_data.unknown_key"
    assert record.original_value == "value"
    assert record.parsed_value == "custom_fields"


@pytest.mark.asyncio
async def test_metadata_type_mismatch_moves_to_custom_fields(
    create_patient_runner, base_payload, caplog
):
    payload = dict(base_payload)
    payload["patient_data"] = {"preferences": "sms"}

    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    patient_create = await create_patient_runner(payload)

    assert patient_create.metadata == {"custom_fields": {"preferences": "sms"}}

    records = [
        record
        for record in caplog.records
        if record.getMessage()
        == "Metadata key moved to custom_fields due to type mismatch"
    ]
    assert records

    record = records[0]
    assert record.field == "patient_data.preferences"
    assert record.original_value == "sms"
    assert record.parsed_value == "custom_fields"
    assert "dictionary" in record.error.lower()


@pytest.mark.asyncio
async def test_metadata_merges_with_existing_custom_fields(
    create_patient_runner, base_payload
):
    payload = dict(base_payload)
    payload["patient_data"] = {
        "custom_fields": {"existing": "keep"},
        "unknown_key": "value",
    }

    patient_create = await create_patient_runner(payload)

    assert patient_create.metadata["custom_fields"]["existing"] == "keep"
    assert patient_create.metadata["custom_fields"]["unknown_key"] == "value"


@pytest.mark.asyncio
async def test_patient_create_receives_converted_clinical_fields(
    create_patient_runner, base_payload
):
    payload = dict(base_payload)
    payload.update(
        {
            "allergies": "A/B",
            "medications": "Med 500mg/dia",
            "emergency_contact": "Maria - (11) 99999-9999",
        }
    )

    patient_create = await create_patient_runner(payload)

    assert patient_create.allergies == ["A", "B"]
    assert patient_create.current_medications == ["Med 500mg/dia"]
    assert patient_create.emergency_contact_name == "Maria"
    assert patient_create.emergency_contact_phone == "+5511999999999"
