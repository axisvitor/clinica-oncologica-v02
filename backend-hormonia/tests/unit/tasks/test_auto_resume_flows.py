"""Tests for auto-resume paused flows (Taskiq version)."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from contextlib import contextmanager

import pytest

from app.exceptions import FlowStateConflictError
from app.tasks.flows_taskiq import resume_paused_flows
from app.utils.timezone import now_sao_paulo


def _scoped_session(db):
    @contextmanager
    def _ctx():
        yield db

    return _ctx()


def _flow_row(auto_resume_at):
    state_data = {"paused": True}
    if auto_resume_at is not None:
        state_data["auto_resume_at"] = auto_resume_at

    return SimpleNamespace(
        id="flow-id",
        patient_id="patient-id",
        status="paused",
        state_data=state_data,
    )


@pytest.fixture
def run_resume_task():
    async def _run(rows, resume_side_effect=None):
        mock_async_db = AsyncMock()
        result_mock = Mock()
        result_mock.fetchall.return_value = rows
        mock_async_db.execute.return_value = result_mock

        sync_db = Mock()

        with patch(
            "app.database.get_scoped_session", return_value=_scoped_session(sync_db)
        ):
            with patch(
                "app.repositories.flow.FlowStateRepository", return_value=Mock()
            ):
                with patch(
                    "app.services.flow_management.FlowManagementService"
                ) as mgmt_cls:
                    mgmt_service = Mock()
                    mgmt_service.resume_patient_flow = AsyncMock(
                        side_effect=resume_side_effect
                    )
                    mgmt_cls.return_value = mgmt_service

                    output = await resume_paused_flows.fn(db=mock_async_db)

        return output, mgmt_service

    return _run


@pytest.mark.asyncio
async def test_expired_auto_resume_triggers_resume(run_resume_task):
    past = (now_sao_paulo() - timedelta(hours=2)).isoformat()
    output, mgmt_service = await run_resume_task([_flow_row(past)])

    mgmt_service.resume_patient_flow.assert_awaited_once_with(patient_id="patient-id")
    assert output["flows_resumed"] == 1
    assert output["errors"] == []


@pytest.mark.asyncio
async def test_future_auto_resume_not_triggered(run_resume_task):
    future = (now_sao_paulo() + timedelta(hours=2)).isoformat()
    output, mgmt_service = await run_resume_task([_flow_row(future)])

    mgmt_service.resume_patient_flow.assert_not_awaited()
    assert output["flows_resumed"] == 0
    assert output["errors"] == []


@pytest.mark.asyncio
async def test_indefinite_pause_not_auto_resumed(run_resume_task):
    output, mgmt_service = await run_resume_task([_flow_row(None)])

    mgmt_service.resume_patient_flow.assert_not_awaited()
    assert output["flows_resumed"] == 0
    assert output["errors"] == []


@pytest.mark.asyncio
async def test_already_resumed_flow_handled_gracefully(run_resume_task):
    past = (now_sao_paulo() - timedelta(hours=2)).isoformat()

    output, mgmt_service = await run_resume_task(
        [_flow_row(past)],
        resume_side_effect=FlowStateConflictError("Flow is not currently paused"),
    )

    mgmt_service.resume_patient_flow.assert_awaited_once_with(patient_id="patient-id")
    assert output["flows_resumed"] == 0
    assert output["errors"] == []
