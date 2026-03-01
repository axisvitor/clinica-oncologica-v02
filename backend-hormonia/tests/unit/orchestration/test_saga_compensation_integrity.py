import re
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models.enums import SagaStatus
from app.models.message import Message, MessageStatus
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.orchestration.saga_orchestrator.compensation import SagaCompensator
from app.orchestration.saga_orchestrator.compensation_handlers import (
    compensate_flow,
    compensate_message,
    compensate_patient,
)
from app.orchestration.saga_orchestrator.steps import SagaStepExecutor


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_source(relative_path: str) -> str:
    return (_backend_root() / relative_path).read_text(encoding="utf-8")


def _extract_async_method(source: str, method_name: str) -> str:
    match = re.search(
        rf"(?ms)^    async def {method_name}\(.*?(?=^    async def |\Z)",
        source,
    )
    assert match is not None, f"Method {method_name} not found"
    return match.group(0)


class TestStepToHandlerMapping:
    def test_every_active_step_has_compensation_handler(self) -> None:
        active_steps = {
            1: {"forward": "step_create_patient", "handler": "compensate_patient"},
            3: {"forward": "step_initialize_flow", "handler": "compensate_flow"},
            4: {"forward": "step_send_welcome_message", "handler": "compensate_message"},
        }
        handlers = {
            "compensate_message": compensate_message,
            "compensate_flow": compensate_flow,
            "compensate_patient": compensate_patient,
        }

        for step in active_steps.values():
            assert hasattr(SagaStepExecutor, step["forward"])
            assert callable(handlers[step["handler"]])

        assert len(active_steps) == 3

    def test_step_2_is_deprecated_and_intentionally_uncompensated(self) -> None:
        compensation_source = (
            _backend_root()
            / "app"
            / "orchestration"
            / "saga_orchestrator"
            / "compensation.py"
        ).read_text(encoding="utf-8")
        steps_source = (
            _backend_root()
            / "app"
            / "orchestration"
            / "saga_orchestrator"
            / "steps.py"
        ).read_text(encoding="utf-8")

        assert "Step 2" in compensation_source
        assert "deprecated" in compensation_source.lower()
        assert hasattr(SagaStatus, "STEP_2_FIREBASE_USER_CREATED")
        assert "STEP_2" not in steps_source

    def test_compensator_wraps_all_handlers(self) -> None:
        assert hasattr(SagaCompensator, "_compensate_message")
        assert hasattr(SagaCompensator, "_compensate_flow")
        assert hasattr(SagaCompensator, "_compensate_patient")


class TestCompensationReverseOrder:
    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.commit = MagicMock()
        db.rollback = MagicMock()
        return db

    @pytest.fixture
    def compensator(self, mock_db):
        return SagaCompensator(
            db=mock_db,
            patient_repo=MagicMock(),
            redis_client=MagicMock(),
        )

    @pytest.fixture
    def make_saga(self):
        def _factory(current_step: int, patient_id=...) -> MagicMock:
            saga = MagicMock(spec=PatientOnboardingSaga)
            saga.id = uuid4()
            saga.patient_id = uuid4() if patient_id is ... else patient_id
            saga.current_step = current_step
            saga.status = SagaStatus.FAILED
            saga.execution_log = []
            saga.add_log_entry = MagicMock()
            saga.step_data = {}
            return saga

        return _factory

    @pytest.mark.asyncio
    async def test_compensation_at_step_4_runs_all_three_in_reverse_order(
        self, compensator, make_saga
    ):
        saga = make_saga(current_step=4)
        call_order = []

        async def tracking_retry(
            saga,
            step_num,
            step_name,
            compensate_fn,
            compensation_errors,
            max_retries=3,
        ):
            call_order.append((step_num, step_name))

        compensator._compensate_step_with_retry = tracking_retry

        await compensator._compensate_saga_internal(saga)

        assert call_order == [
            (4, "compensate_message"),
            (3, "compensate_flow"),
            (1, "compensate_patient"),
        ]
        assert saga.status == SagaStatus.COMPENSATED

    @pytest.mark.asyncio
    async def test_compensation_at_step_3_skips_message_handler(
        self, compensator, make_saga
    ):
        saga = make_saga(current_step=3)
        call_order = []

        async def tracking_retry(
            saga,
            step_num,
            step_name,
            compensate_fn,
            compensation_errors,
            max_retries=3,
        ):
            call_order.append((step_num, step_name))

        compensator._compensate_step_with_retry = tracking_retry

        await compensator._compensate_saga_internal(saga)

        assert call_order == [
            (3, "compensate_flow"),
            (1, "compensate_patient"),
        ]

    @pytest.mark.asyncio
    async def test_compensation_at_step_1_runs_only_patient_handler(
        self, compensator, make_saga
    ):
        saga = make_saga(current_step=1)
        call_order = []

        async def tracking_retry(
            saga,
            step_num,
            step_name,
            compensate_fn,
            compensation_errors,
            max_retries=3,
        ):
            call_order.append((step_num, step_name))

        compensator._compensate_step_with_retry = tracking_retry

        await compensator._compensate_saga_internal(saga)

        assert call_order == [(1, "compensate_patient")]

    @pytest.mark.asyncio
    async def test_compensation_at_step_0_runs_no_handlers(
        self, compensator, make_saga, mock_db
    ):
        saga = make_saga(current_step=0, patient_id=None)
        call_order = []

        async def tracking_retry(
            saga,
            step_num,
            step_name,
            compensate_fn,
            compensation_errors,
            max_retries=3,
        ):
            call_order.append((step_num, step_name))

        compensator._compensate_step_with_retry = tracking_retry

        await compensator._compensate_saga_internal(saga)

        assert call_order == []
        assert saga.status == SagaStatus.COMPENSATED
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_compensation_at_step_1_without_patient_id_runs_no_handlers(
        self, compensator, make_saga
    ):
        saga = make_saga(current_step=1, patient_id=None)
        call_order = []

        async def tracking_retry(
            saga,
            step_num,
            step_name,
            compensate_fn,
            compensation_errors,
            max_retries=3,
        ):
            call_order.append((step_num, step_name))

        compensator._compensate_step_with_retry = tracking_retry

        await compensator._compensate_saga_internal(saga)

        assert call_order == []


class TestTransactionBoundaries:
    def test_forward_steps_use_flush_not_commit(self) -> None:
        steps_source = _read_source(
            "app/orchestration/saga_orchestrator/steps.py"
        )

        for method_name in (
            "step_create_patient",
            "step_initialize_flow",
            "step_send_welcome_message",
        ):
            method_body = _extract_async_method(steps_source, method_name)
            assert "_db_flush" in method_body
            assert "_db_commit" not in method_body

    def test_orchestrator_commits_once_on_forward_success(self) -> None:
        orchestrator_source = _read_source(
            "app/orchestration/saga_orchestrator/orchestrator.py"
        )
        method_body = _extract_async_method(
            orchestrator_source,
            "execute_patient_onboarding_saga",
        )
        try_block = method_body.split("except Exception as e:", 1)[0]

        assert try_block.count("_db_commit") == 1
        assert method_body.count("_db_flush") >= 1

    def test_orchestrator_rollback_on_forward_failure(self) -> None:
        orchestrator_source = _read_source(
            "app/orchestration/saga_orchestrator/orchestrator.py"
        )
        method_body = _extract_async_method(
            orchestrator_source,
            "execute_patient_onboarding_saga",
        )
        except_block = method_body.split("except Exception as e:", 1)[1]

        assert "_db_rollback" in except_block
        assert "_db_commit" in except_block
        assert except_block.index("_db_rollback") < except_block.index("_db_commit")

    def test_compensation_has_independent_commit(self) -> None:
        compensation_source = _read_source(
            "app/orchestration/saga_orchestrator/compensation.py"
        )
        method_body = _extract_async_method(
            compensation_source,
            "_compensate_saga_internal",
        )

        assert "_db_commit" in method_body


class TestIdempotencyGuards:
    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        query = MagicMock()
        query.filter.return_value = query
        query.all.return_value = []
        db.query.return_value = query
        return db

    @pytest.fixture
    def make_saga(self):
        def _factory(step_data=None):
            saga = MagicMock(spec=PatientOnboardingSaga)
            saga.id = uuid4()
            saga.patient_id = uuid4()
            saga.step_data = {} if step_data is None else step_data
            return saga

        return _factory

    @pytest.mark.asyncio
    async def test_compensate_message_skips_when_already_compensated(
        self, mock_db, make_saga
    ):
        saga = make_saga(step_data={"compensated_steps": ["message"]})

        await compensate_message(mock_db, saga)

        mock_db.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_compensate_flow_skips_when_already_compensated(
        self, mock_db, make_saga
    ):
        saga = make_saga(step_data={"compensated_steps": ["flow"]})

        await compensate_flow(mock_db, saga)

        mock_db.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_compensate_patient_skips_when_already_compensated(
        self, mock_db, make_saga
    ):
        saga = make_saga(step_data={"compensated_steps": ["patient"]})

        await compensate_patient(mock_db, saga)

        mock_db.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_compensate_message_is_safe_on_double_execution(
        self, mock_db, make_saga
    ):
        query = MagicMock()
        query.filter.return_value = query
        message = MagicMock(spec=Message)
        message.status = MessageStatus.SCHEDULED
        message.message_metadata = {}
        query.all.return_value = [message]
        mock_db.query.return_value = query

        saga = make_saga(step_data={})

        await compensate_message(mock_db, saga)
        assert "message" in saga.step_data["compensated_steps"]
        assert message.status == MessageStatus.CANCELLED

        await compensate_message(mock_db, saga)
        assert mock_db.query.call_count == 1

    def test_step_initialize_flow_checks_existing_flow_state(self) -> None:
        steps_source = _read_source("app/orchestration/saga_orchestrator/steps.py")
        method_body = _extract_async_method(steps_source, "step_initialize_flow")

        assert "existing_flow" in method_body or "PatientFlowState" in method_body

    def test_step_send_welcome_message_checks_existing_message(self) -> None:
        steps_source = _read_source("app/orchestration/saga_orchestrator/steps.py")
        method_body = _extract_async_method(steps_source, "step_send_welcome_message")

        assert "existing_message" in method_body or "idempotency_key" in method_body

    def test_step_create_patient_handles_integrity_error(self) -> None:
        steps_source = _read_source("app/orchestration/saga_orchestrator/steps.py")
        method_body = _extract_async_method(steps_source, "step_create_patient")

        assert "IntegrityError" in method_body
