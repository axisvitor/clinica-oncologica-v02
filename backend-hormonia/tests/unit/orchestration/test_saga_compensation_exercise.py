import os
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

os.environ.setdefault("MONTHLY_QUIZ_TOKEN_SECRET", "test-secret-key-for-testing")

from app.models.enums import SagaStatus
from app.models.flow import PatientFlowState
from app.models.message import Message, MessageStatus
from app.models.patient import Patient
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.orchestration.saga_orchestrator.compensation import SagaCompensator
from app.orchestration.saga_orchestrator.compensation_handlers import (
    compensate_flow,
    compensate_message,
    compensate_patient,
)

pytest_plugins = ["tests.fixtures.saga_fixtures"]


def _make_query(rows):
    query = MagicMock()
    query.filter.return_value = query
    query.all.return_value = rows
    query.first.return_value = rows[0] if rows else None
    return query


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.flush = MagicMock()
    db.delete = MagicMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def make_saga():
    def _factory(current_step: int = 4, step_data: dict | None = None):
        saga = MagicMock(spec=PatientOnboardingSaga)
        saga.id = uuid4()
        saga.patient_id = uuid4()
        saga.current_step = current_step
        saga.status = SagaStatus.FAILED
        saga.execution_log = []
        saga.add_log_entry = MagicMock()
        saga.step_data = step_data if step_data is not None else {}
        return saga

    return _factory


class TestCompensatePatientExercise:
    @pytest.mark.asyncio
    async def test_compensate_patient_deletes_patient_record(
        self, mock_db, make_saga
    ):
        mock_patient = MagicMock(spec=Patient)
        mock_patient.id = uuid4()
        mock_db.query.side_effect = lambda model: _make_query([mock_patient])
        saga = make_saga(step_data={})

        await compensate_patient(mock_db, saga)

        mock_db.delete.assert_called_once_with(mock_patient)
        assert "patient" in saga.step_data.get("compensated_steps", [])

    @pytest.mark.asyncio
    async def test_compensate_patient_with_no_patient_found_is_noop(
        self, mock_db, make_saga
    ):
        mock_db.query.side_effect = lambda model: _make_query([])
        saga = make_saga(step_data={})

        await compensate_patient(mock_db, saga)

        mock_db.delete.assert_not_called()
        assert "patient" in saga.step_data.get("compensated_steps", [])


class TestCompensateFlowExercise:
    @pytest.mark.asyncio
    async def test_compensate_flow_deletes_flow_state(self, mock_db, make_saga):
        mock_flow = MagicMock(spec=PatientFlowState)
        mock_flow.id = uuid4()
        mock_db.query.side_effect = lambda model: _make_query([mock_flow])
        saga = make_saga(step_data={})

        await compensate_flow(mock_db, saga)

        mock_db.delete.assert_called_once_with(mock_flow)
        assert "flow" in saga.step_data.get("compensated_steps", [])

    @pytest.mark.asyncio
    async def test_compensate_flow_with_no_flow_found_is_noop(self, mock_db, make_saga):
        mock_db.query.side_effect = lambda model: _make_query([])
        saga = make_saga(step_data={})

        await compensate_flow(mock_db, saga)

        mock_db.delete.assert_not_called()
        assert "flow" in saga.step_data.get("compensated_steps", [])


class TestCompensateMessageExercise:
    @pytest.mark.asyncio
    async def test_compensate_message_marks_pending_messages_cancelled(
        self, mock_db, make_saga
    ):
        msg1 = MagicMock(spec=Message)
        msg1.status = MessageStatus.SCHEDULED
        msg1.message_metadata = {}
        mock_db.query.side_effect = lambda model: _make_query([msg1])
        saga = make_saga(step_data={})

        await compensate_message(mock_db, saga)

        assert msg1.status == MessageStatus.CANCELLED
        assert msg1.message_metadata.get("cancelled_by") == "saga_compensation"
        assert "message" in saga.step_data.get("compensated_steps", [])

    @pytest.mark.asyncio
    async def test_compensate_message_with_no_messages_is_noop(self, mock_db, make_saga):
        mock_db.query.side_effect = lambda model: _make_query([])
        saga = make_saga(step_data={})

        await compensate_message(mock_db, saga)

        assert "message" in saga.step_data.get("compensated_steps", [])


class TestFullCompensationSequence:
    @pytest.mark.asyncio
    async def test_full_compensation_at_step_4_runs_all_handlers_and_marks_compensated(
        self, mock_db, make_saga, mock_redis
    ):
        saga = make_saga(current_step=4, step_data={})

        mock_patient = MagicMock(spec=Patient)
        mock_flow = MagicMock(spec=PatientFlowState)
        mock_message = MagicMock(spec=Message)
        mock_message.status = MessageStatus.SCHEDULED
        mock_message.message_metadata = {}

        query_map = {
            Message: _make_query([mock_message]),
            PatientFlowState: _make_query([mock_flow]),
            Patient: _make_query([mock_patient]),
        }
        mock_db.query.side_effect = lambda model: query_map[model]

        compensator = SagaCompensator(
            db=mock_db,
            patient_repo=MagicMock(),
            redis_client=mock_redis,
        )

        call_order = []

        async def tracking_retry(
            saga,
            step_num,
            step_name,
            compensate_fn,
            compensation_errors,
            max_retries=3,
        ):
            call_order.append(step_name)
            await compensate_fn(saga)

        compensator._compensate_step_with_retry = tracking_retry

        await compensator._compensate_saga_internal(saga)

        assert call_order == [
            "compensate_message",
            "compensate_flow",
            "compensate_patient",
        ]
        assert saga.step_data.get("compensated_steps", []) == [
            "message",
            "flow",
            "patient",
        ]
        assert saga.status == SagaStatus.COMPENSATED
        mock_db.commit.assert_called_once()
