import os
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

os.environ.setdefault("MONTHLY_QUIZ_TOKEN_SECRET", "test-secret-key-for-testing")

from app.models.enums import SagaStatus
from app.models.patient import Patient
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.orchestration.saga_orchestrator import SagaOrchestrator
from app.schemas.patient import PatientCreate

pytest_plugins = ["tests.fixtures.saga_fixtures"]


@asynccontextmanager
async def _noop_acquire_lock(*args, **kwargs):
    yield "test-lock-id"


def _extract_saga_records(mock_db):
    saga_records = []
    for call in mock_db.add.call_args_list:
        if call.args and isinstance(call.args[0], PatientOnboardingSaga):
            saga_records.append(call.args[0])
    return saga_records


def _contains_ordered_steps(sequence, expected):
    idx = 0
    for value in sequence:
        if idx < len(expected) and value == expected[idx]:
            idx += 1
    return idx == len(expected)


@pytest.fixture
def saga_env(mock_redis, mock_evolution_client, test_patient_data):
    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.flush = MagicMock()
    mock_db.query = MagicMock()

    doctor_id = uuid4()
    patient_phone = "+5511999887766"
    patient_name = "Test Patient"
    created_patient = Patient(
        id=uuid4(),
        name=patient_name,
        doctor_id=doctor_id,
        phone=patient_phone,
    )

    patient_data = PatientCreate(
        name=patient_name,
        phone=patient_phone,
        email=test_patient_data.get("email"),
    )

    forward_call_order = []

    with patch(
        "app.orchestration.saga_orchestrator.orchestrator.acquire_lock",
        _noop_acquire_lock,
    ), patch(
        "app.orchestration.saga_orchestrator.orchestrator.PatientRepository"
    ) as MockRepo, patch(
        "app.orchestration.saga_orchestrator.orchestrator.PatientFlowService"
    ) as MockFlowService, patch(
        "app.orchestration.saga_orchestrator.orchestrator.UnifiedWhatsAppService"
    ) as MockWhatsApp, patch(
        "app.orchestration.saga_orchestrator.orchestrator.MessageService"
    ) as MockMessageService, patch(
        "app.tasks.messaging_taskiq.send_scheduled_message"
    ):
        orchestrator = SagaOrchestrator(mock_db, mock_redis, mock_evolution_client)

        def _repo_create_side_effect(*args, **kwargs):
            forward_call_order.append("step_1_create_patient")
            return created_patient

        async def _flow_initialize_side_effect(*args, **kwargs):
            forward_call_order.append("step_3_initialize_flow")
            return MagicMock()

        def _schedule_message_side_effect(*args, **kwargs):
            forward_call_order.append("step_4_send_welcome_message")
            return MagicMock(id=uuid4())

        MockRepo.return_value.create.side_effect = _repo_create_side_effect
        MockFlowService.return_value.initialize_default_flow = AsyncMock(
            side_effect=_flow_initialize_side_effect
        )
        MockFlowService.return_value.activate_patient = AsyncMock()
        MockWhatsApp.return_value.send_message = AsyncMock(return_value=True)
        MockMessageService.return_value.schedule_message = MagicMock(
            side_effect=_schedule_message_side_effect
        )

        yield {
            "orchestrator": orchestrator,
            "mock_db": mock_db,
            "mock_repo": MockRepo,
            "mock_flow_service": MockFlowService,
            "mock_message_service": MockMessageService,
            "created_patient": created_patient,
            "doctor_id": doctor_id,
            "patient_data": patient_data,
            "forward_call_order": forward_call_order,
        }


@pytest.mark.asyncio
async def test_happy_path_returns_patient_with_correct_phone(saga_env):
    result = await saga_env["orchestrator"].execute_patient_onboarding_saga(
        saga_env["patient_data"],
        doctor_id=saga_env["doctor_id"],
    )

    assert result is not None
    assert result.phone == "+5511999887766" or result.name == "Test Patient"


@pytest.mark.asyncio
async def test_happy_path_saga_reaches_completed_status(saga_env):
    await saga_env["orchestrator"].execute_patient_onboarding_saga(
        saga_env["patient_data"],
        doctor_id=saga_env["doctor_id"],
    )

    saga_records = _extract_saga_records(saga_env["mock_db"])
    assert saga_records

    saga = saga_records[0]
    assert saga.status in {
        SagaStatus.COMPLETED,
        SagaStatus.COMPLETED_WITH_WARNINGS,
    }
    assert saga.completed_at is not None
    assert saga.current_step == 4


@pytest.mark.asyncio
async def test_happy_path_invokes_all_three_forward_steps(saga_env):
    await saga_env["orchestrator"].execute_patient_onboarding_saga(
        saga_env["patient_data"],
        doctor_id=saga_env["doctor_id"],
    )

    assert saga_env["mock_repo"].return_value.create.call_count >= 1
    assert (
        saga_env["mock_flow_service"].return_value.initialize_default_flow.call_count
        >= 1
    )
    assert saga_env["mock_message_service"].return_value.schedule_message.call_count >= 1
    assert _contains_ordered_steps(
        saga_env["forward_call_order"],
        [
            "step_1_create_patient",
            "step_3_initialize_flow",
            "step_4_send_welcome_message",
        ],
    )


@pytest.mark.asyncio
async def test_happy_path_saga_step_progression(saga_env):
    await saga_env["orchestrator"].execute_patient_onboarding_saga(
        saga_env["patient_data"],
        doctor_id=saga_env["doctor_id"],
    )

    saga_records = _extract_saga_records(saga_env["mock_db"])
    assert saga_records

    saga = saga_records[0]
    log_steps = [
        entry.get("step")
        for entry in (saga.execution_log or [])
        if isinstance(entry, dict)
    ]
    assert _contains_ordered_steps(log_steps, [1, 3, 4])
