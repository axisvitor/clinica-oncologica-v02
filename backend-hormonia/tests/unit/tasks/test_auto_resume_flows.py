from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.exceptions import FlowStateConflictError
from app.tasks.flow_automation import resume_paused_flows
from app.utils.timezone import now_sao_paulo


@pytest.fixture
def run_resume_task():
    def _run(rows, resume_side_effect=None):
        db = Mock()
        result = Mock()
        result.fetchall.return_value = rows
        db.execute.return_value = result

        @contextmanager
        def _db_session():
            yield db

        with patch("app.tasks.flow_automation.get_db_session", _db_session):
            with patch("app.tasks.flow_automation.FlowStateRepository", return_value=Mock()):
                with patch("app.tasks.flow_automation.FlowManagementService") as mgmt_cls:
                    mgmt_service = Mock()
                    mgmt_service.resume_patient_flow = AsyncMock(side_effect=resume_side_effect)
                    mgmt_cls.return_value = mgmt_service

                    output = resume_paused_flows.run()

        return output, mgmt_service

    return _run


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


def test_expired_auto_resume_triggers_resume(run_resume_task):
    past = (now_sao_paulo() - timedelta(hours=2)).isoformat()
    output, mgmt_service = run_resume_task([_flow_row(past)])

    mgmt_service.resume_patient_flow.assert_awaited_once_with(patient_id="patient-id")
    assert output["flows_resumed"] == 1
    assert output["errors"] == []


def test_future_auto_resume_not_triggered(run_resume_task):
    future = (now_sao_paulo() + timedelta(hours=2)).isoformat()
    output, mgmt_service = run_resume_task([_flow_row(future)])

    mgmt_service.resume_patient_flow.assert_not_awaited()
    assert output["flows_resumed"] == 0
    assert output["errors"] == []


def test_indefinite_pause_not_auto_resumed(run_resume_task):
    output, mgmt_service = run_resume_task([_flow_row(None)])

    mgmt_service.resume_patient_flow.assert_not_awaited()
    assert output["flows_resumed"] == 0
    assert output["errors"] == []


def test_already_resumed_flow_handled_gracefully(run_resume_task):
    past = (now_sao_paulo() - timedelta(hours=2)).isoformat()

    with patch("app.tasks.flow_automation.logger.warning") as warning_mock:
        output, mgmt_service = run_resume_task(
            [_flow_row(past)],
            resume_side_effect=FlowStateConflictError("Flow is not currently paused"),
        )

    mgmt_service.resume_patient_flow.assert_awaited_once_with(patient_id="patient-id")
    warning_mock.assert_called_once()
    assert output["flows_resumed"] == 0
    assert output["errors"] == []
