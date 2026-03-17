from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.flow_management import FlowManagementService
from app.tasks.flows_taskiq import process_daily_flows


class _SessionContext:
    def __init__(self, db):
        self._db = db

    def __enter__(self):
        return self._db

    def __exit__(self, exc_type, exc, tb):
        return False


async def _run_daily_filter(flows):
    db = MagicMock()
    flow_repo = MagicMock()
    flow_repo.get_active_flows.return_value = flows

    with patch("app.database.get_scoped_session", return_value=_SessionContext(db)):
        with patch("app.repositories.flow.FlowStateRepository", return_value=flow_repo):
            with patch(
                "app.tasks.flows_taskiq._process_single_patient_flow_by_id",
                new=AsyncMock(return_value={"status": "success"}),
            ):
                return await process_daily_flows.fn(limit=50)


@pytest.mark.asyncio
async def test_pause_field_is_state_data_not_step_data() -> None:
    flow = SimpleNamespace(
        patient_id=uuid4(),
        state_data={"paused": True},
        step_data={},
        status="paused",
    )

    result = await _run_daily_filter([flow])

    assert result["processed_count"] == 0
    assert result["success_count"] == 0
    assert result["error_count"] == 0


@pytest.mark.asyncio
async def test_unpause_flow_passes_filter() -> None:
    flow = SimpleNamespace(
        patient_id=uuid4(),
        state_data={"paused": False},
        step_data={},
        status="active",
    )

    result = await _run_daily_filter([flow])

    assert result["processed_count"] == 1
    assert result["success_count"] == 1
    assert result["error_count"] == 0


@pytest.mark.asyncio
async def test_old_step_data_paused_does_not_block() -> None:
    flow = SimpleNamespace(
        patient_id=uuid4(),
        state_data={},
        step_data={"paused": {"timestamp": "legacy"}},
        status="active",
    )

    result = await _run_daily_filter([flow])

    assert result["processed_count"] == 1
    assert result["success_count"] == 1
    assert result["error_count"] == 0


@pytest.mark.asyncio
async def test_pause_idempotent_updates_resume_at() -> None:
    now = datetime(2026, 2, 24, 12, 0, tzinfo=timezone.utc)
    patient_id = uuid4()

    flow_state = SimpleNamespace(
        id=uuid4(),
        patient_id=patient_id,
        state_data={},
        status="active",
        version=3,
        last_interaction_at=None,
    )

    flow_repo = MagicMock()
    flow_repo.db = MagicMock()
    flow_repo.get_active_flow.return_value = flow_state
    db = MagicMock()

    with patch("app.services.flow_management.EnhancedFlowEngine") as engine_cls:
        engine_cls.return_value = MagicMock()
        service = FlowManagementService(flow_repo=flow_repo, db=db)

    with patch("app.services.flow_management.now_sao_paulo", return_value=now):
        first = await service.pause_patient_flow(
            patient_id=patient_id,
            reason="pause one",
            duration_hours=1,
        )
        second = await service.pause_patient_flow(
            patient_id=patient_id,
            reason="pause two",
            duration_hours=2,
        )

    assert first.status == "paused"
    assert second.status == "paused"
    assert flow_state.state_data["paused"] is True
    assert flow_state.state_data["pause_reason"] == "pause two"
    assert flow_state.state_data["auto_resume_at"] == (now + timedelta(hours=2)).isoformat()
    assert db.commit.call_count == 2
