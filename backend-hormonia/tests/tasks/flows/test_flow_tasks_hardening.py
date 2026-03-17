from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest


def _build_flow_states(count: int) -> list[SimpleNamespace]:
    return [SimpleNamespace(patient_id=uuid4(), step_data={}, state_data={}) for _ in range(count)]


@pytest.mark.asyncio
async def test_process_daily_flows_applies_batch_stagger_and_throttle():
    from app.tasks.flows_taskiq import process_daily_flows

    flow_states = _build_flow_states(5)

    @contextmanager
    def _fake_scoped_session():
        yield Mock()

    repo = Mock()
    repo.get_active_flows.return_value = flow_states
    process_by_id = AsyncMock(
        side_effect=[
            {"status": "error", "error": "db_error_1"},
            {"status": "error", "error": "db_error_2"},
            {"status": "success"},
            {"status": "success"},
            {"status": "success"},
        ]
    )
    sleep_mock = AsyncMock()

    with patch("app.database.get_scoped_session", _fake_scoped_session), patch(
        "app.repositories.flow.FlowStateRepository", return_value=repo
    ), patch(
        "app.tasks.flows_taskiq._process_single_patient_flow_by_id",
        new=process_by_id,
    ), patch("asyncio.sleep", new=sleep_mock), patch(
        "app.config.settings.tasks.FLOW_BATCH_SIZE",
        2,
    ), patch(
        "app.config.settings.tasks.FLOW_PROCESSING_TIMEOUT",
        10,
    ), patch(
        "app.config.settings.tasks.FLOW_MAX_CONCURRENT",
        6,
    ):
        result = await process_daily_flows.fn(limit=100)

    assert result["processed_count"] == 5
    assert result["success_count"] == 3
    assert result["error_count"] == 2
    assert process_by_id.await_count == 5
    assert len(sleep_mock.await_args_list) == 2
    assert sleep_mock.await_args_list[0].args[0] == pytest.approx(0.9)
    assert sleep_mock.await_args_list[1].args[0] == pytest.approx(0.15)


@pytest.mark.asyncio
async def test_process_daily_flows_handles_unexpected_result_payload_safely():
    from app.tasks.flows_taskiq import process_daily_flows

    flow_states = _build_flow_states(1)

    @contextmanager
    def _fake_scoped_session():
        yield Mock()

    repo = Mock()
    repo.get_active_flows.return_value = flow_states
    process_by_id = AsyncMock(return_value="unexpected")

    with patch("app.database.get_scoped_session", _fake_scoped_session), patch(
        "app.repositories.flow.FlowStateRepository", return_value=repo
    ), patch(
        "app.tasks.flows_taskiq._process_single_patient_flow_by_id",
        new=process_by_id,
    ), patch(
        "app.config.settings.tasks.FLOW_BATCH_SIZE",
        1,
    ), patch(
        "app.config.settings.tasks.FLOW_PROCESSING_TIMEOUT",
        10,
    ), patch(
        "app.config.settings.tasks.FLOW_MAX_CONCURRENT",
        1,
    ):
        result = await process_daily_flows.fn(limit=10)

    assert result["processed_count"] == 1
    assert result["success_count"] == 0
    assert result["error_count"] == 1
    assert "Unexpected result type str" in result["errors"][0]["error"]
    assert result["patients_processed"][0]["status"] == "error"
