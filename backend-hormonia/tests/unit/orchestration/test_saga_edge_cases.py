import asyncio
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
from app.orchestration.saga_orchestrator.compensation import (
    SagaCompensator,
    SagaCompensationError,
)
from app.schemas.patient import PatientCreate

pytest_plugins = ["tests.fixtures.saga_fixtures"]


@asynccontextmanager
async def _noop_acquire_lock(*args, **kwargs):
    yield "test-lock-id"


@asynccontextmanager
async def _blocking_acquire_lock(*args, **kwargs):
    raise RuntimeError("Could not acquire lock: resource busy")
    yield  # pragma: no cover


def _extract_saga_records(mock_db):
    records = []
    for call in mock_db.add.call_args_list:
        if call.args and isinstance(call.args[0], PatientOnboardingSaga):
            records.append(call.args[0])
    return records


def _build_orchestrator(mock_redis, mock_evolution_client):
    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.rollback = MagicMock()
    mock_db.flush = MagicMock()
    mock_db.query = MagicMock()

    with patch("app.orchestration.saga_orchestrator.orchestrator.PatientRepository"), patch(
        "app.orchestration.saga_orchestrator.orchestrator.PatientFlowService"
    ), patch(
        "app.orchestration.saga_orchestrator.orchestrator.UnifiedWhatsAppService"
    ), patch(
        "app.orchestration.saga_orchestrator.orchestrator.MessageService"
    ):
        orchestrator = SagaOrchestrator(mock_db, mock_redis, mock_evolution_client)

    return orchestrator, mock_db


def _make_saga_for_compensation():
    saga = MagicMock(spec=PatientOnboardingSaga)
    saga.id = uuid4()
    saga.patient_id = uuid4()
    saga.current_step = 4
    saga.status = SagaStatus.FAILED
    saga.step_data = {}
    saga.execution_log = []

    def _add_log_entry(step, action, status, message=None):
        entry = {
            "step": step,
            "action": action,
            "status": status,
        }
        if message:
            entry["message"] = message
        saga.execution_log.append(entry)

    saga.add_log_entry = MagicMock(side_effect=_add_log_entry)
    return saga


class TestSagaTimeout:
    @pytest.mark.asyncio
    async def test_timeout_during_step_execution_marks_saga_failed(
        self, mock_redis, mock_evolution_client
    ):
        orchestrator, mock_db = _build_orchestrator(mock_redis, mock_evolution_client)
        orchestrator.step_executor.step_create_patient = AsyncMock(
            side_effect=asyncio.TimeoutError("Saga execution timeout")
        )
        orchestrator.compensator.compensate_saga = AsyncMock(return_value=None)

        with patch(
            "app.orchestration.saga_orchestrator.orchestrator.acquire_lock",
            _noop_acquire_lock,
        ):
            result = await orchestrator.execute_patient_onboarding_saga(
                PatientCreate(name="Timeout Test", phone="+5511999887766")
            )

        assert result is None

        saga_records = _extract_saga_records(mock_db)
        assert saga_records
        failure_saga = saga_records[-1]
        assert failure_saga.status == SagaStatus.FAILED
        assert failure_saga.error_message
        assert "timeout" in failure_saga.error_message.lower()
        orchestrator.compensator.compensate_saga.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_timeout_does_not_corrupt_saga_state(
        self, mock_redis, mock_evolution_client
    ):
        orchestrator, mock_db = _build_orchestrator(mock_redis, mock_evolution_client)

        created_patient = Patient(
            id=uuid4(),
            name="Timeout Step Two",
            phone="+5511999887001",
        )

        async def _step_create_patient_side_effect(saga, *_args, **_kwargs):
            saga.patient_id = created_patient.id
            saga.current_step = 1
            saga.status = SagaStatus.STEP_1_PATIENT_CREATED
            return created_patient

        orchestrator.step_executor.step_create_patient = AsyncMock(
            side_effect=_step_create_patient_side_effect
        )
        orchestrator.step_executor.step_initialize_flow = AsyncMock(
            side_effect=asyncio.TimeoutError("Flow initialization timeout")
        )
        orchestrator.step_executor.step_send_welcome_message = AsyncMock(return_value=None)
        orchestrator.compensator.compensate_saga = AsyncMock(return_value=None)

        with patch(
            "app.orchestration.saga_orchestrator.orchestrator.acquire_lock",
            _noop_acquire_lock,
        ):
            result = await orchestrator.execute_patient_onboarding_saga(
                PatientCreate(name="Timeout Step Two", phone="+5511999887001")
            )

        assert result is None

        saga_records = _extract_saga_records(mock_db)
        assert saga_records
        failure_saga = saga_records[-1]
        assert failure_saga.current_step >= 1
        assert failure_saga.status in {SagaStatus.FAILED, SagaStatus.COMPENSATED}
        assert failure_saga.status not in {
            SagaStatus.STARTED,
            SagaStatus.STEP_1_PATIENT_CREATED,
            SagaStatus.STEP_3_FLOW_INITIALIZED,
        }


class TestSagaConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_saga_for_same_phone_is_blocked_by_lock(
        self, mock_redis, mock_evolution_client
    ):
        orchestrator, mock_db = _build_orchestrator(mock_redis, mock_evolution_client)

        with patch(
            "app.orchestration.saga_orchestrator.orchestrator.acquire_lock",
            _blocking_acquire_lock,
        ):
            with pytest.raises(RuntimeError, match="Could not acquire lock"):
                await orchestrator.execute_patient_onboarding_saga(
                    PatientCreate(name="Lock Blocked", phone="+5511999887002")
                )

        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_different_phones_can_execute_concurrently(
        self, mock_redis, mock_evolution_client
    ):
        lock_keys = []

        @asynccontextmanager
        async def _tracking_acquire_lock(key, *args, **kwargs):
            lock_keys.append(key)
            yield "test-lock-id"

        orchestrator, _mock_db = _build_orchestrator(mock_redis, mock_evolution_client)

        patient_1 = Patient(id=uuid4(), name="Patient 1", phone="+5511999887003")
        patient_2 = Patient(id=uuid4(), name="Patient 2", phone="+5511999887004")

        orchestrator.step_executor.step_create_patient = AsyncMock(
            side_effect=[patient_1, patient_2]
        )
        orchestrator.step_executor.step_initialize_flow = AsyncMock(return_value=None)
        orchestrator.step_executor.step_send_welcome_message = AsyncMock(return_value=None)

        with patch(
            "app.orchestration.saga_orchestrator.orchestrator.acquire_lock",
            _tracking_acquire_lock,
        ):
            result_1 = await orchestrator.execute_patient_onboarding_saga(
                PatientCreate(name="Patient 1", phone="+5511999887003")
            )
            result_2 = await orchestrator.execute_patient_onboarding_saga(
                PatientCreate(name="Patient 2", phone="+5511999887004")
            )

        assert result_1 is not None
        assert result_2 is not None
        assert result_1.phone == "+5511999887003"
        assert result_2.phone == "+5511999887004"
        assert len(lock_keys) == 2
        assert lock_keys[0] != lock_keys[1]


class TestStepRetryExhaustion:
    @pytest.mark.asyncio
    async def test_compensation_handler_retry_exhaustion_does_not_block_other_handlers(
        self, mock_redis
    ):
        mock_db = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.rollback = MagicMock()
        saga = _make_saga_for_compensation()

        compensator = SagaCompensator(
            db=mock_db,
            patient_repo=MagicMock(),
            redis_client=mock_redis,
        )

        compensator._compensate_message = AsyncMock(side_effect=Exception("DB error"))
        compensator._compensate_flow = AsyncMock(return_value=None)
        compensator._compensate_patient = AsyncMock(return_value=None)
        compensator._track_compensation_failure = AsyncMock(return_value=None)

        with patch(
            "app.orchestration.saga_orchestrator.compensation.asyncio.sleep",
            new=AsyncMock(return_value=None),
        ):
            with pytest.raises(SagaCompensationError):
                await compensator._compensate_saga_internal(saga)

        assert compensator._compensate_message.await_count == 3
        compensator._compensate_flow.assert_awaited_once()
        compensator._compensate_patient.assert_awaited_once()
        assert saga.status == SagaStatus.FAILED

    @pytest.mark.asyncio
    async def test_retry_exhaustion_records_error_in_saga_step_data(
        self, mock_redis
    ):
        mock_db = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.rollback = MagicMock()
        saga = _make_saga_for_compensation()

        compensator = SagaCompensator(
            db=mock_db,
            patient_repo=MagicMock(),
            redis_client=mock_redis,
        )

        compensator._compensate_message = AsyncMock(side_effect=Exception("DB error"))
        compensator._compensate_flow = AsyncMock(return_value=None)
        compensator._compensate_patient = AsyncMock(return_value=None)
        compensator._track_compensation_failure = AsyncMock(return_value=None)

        with patch(
            "app.orchestration.saga_orchestrator.compensation.asyncio.sleep",
            new=AsyncMock(return_value=None),
        ):
            with pytest.raises(SagaCompensationError):
                await compensator._compensate_saga_internal(saga)

        assert any(
            entry.get("status") == "compensation_failed"
            and entry.get("action") == "compensate_message"
            and "DB error" in entry.get("message", "")
            for entry in saga.execution_log
        )
        assert compensator._track_compensation_failure.await_count >= 1
