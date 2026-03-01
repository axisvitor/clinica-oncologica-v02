from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.exceptions import FlowStateNotFoundError
from app.models.message import MessageStatus
from app.services.flow_management import FlowManagementService


def _build_service(flow_state, pending_messages):
    flow_repo = MagicMock()
    flow_repo.db = MagicMock()
    flow_repo.get_active_flow.return_value = flow_state

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = pending_messages

    with patch("app.services.flow_management.EnhancedFlowEngine") as engine_cls:
        engine_cls.return_value = MagicMock()
        service = FlowManagementService(flow_repo=flow_repo, db=db)

    return service, db


@pytest.mark.asyncio
async def test_cancel_active_flow_clears_state() -> None:
    now = datetime(2026, 2, 24, 15, 0, tzinfo=timezone.utc)
    flow_state = SimpleNamespace(
        id=uuid4(),
        status="active",
        state_data={},
        version=3,
        completed_at=None,
        last_interaction_at=None,
    )

    service, db = _build_service(flow_state, [])

    with patch("app.services.flow_management.now_sao_paulo", return_value=now):
        result = await service.cancel_patient_flow(patient_id=uuid4(), user_id=uuid4())

    assert result["status"] == "cancelled"
    assert flow_state.status == "cancelled"
    assert flow_state.completed_at == now
    assert flow_state.state_data["cancelled"] is True
    assert flow_state.state_data["paused"] is False
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_clears_pending_messages() -> None:
    flow_state = SimpleNamespace(
        id=uuid4(),
        status="active",
        state_data={},
        version=1,
        completed_at=None,
        last_interaction_at=None,
    )
    pending_messages = [
        SimpleNamespace(id=uuid4(), status=MessageStatus.PENDING, message_metadata={}),
        SimpleNamespace(id=uuid4(), status=MessageStatus.SCHEDULED, message_metadata={}),
    ]
    service, _db = _build_service(flow_state, pending_messages)

    await service.cancel_patient_flow(patient_id=uuid4(), user_id=uuid4())

    assert all(message.status == MessageStatus.CANCELLED for message in pending_messages)


@pytest.mark.asyncio
async def test_cancel_revokes_celery_tasks() -> None:
    flow_state = SimpleNamespace(
        id=uuid4(),
        status="active",
        state_data={},
        version=1,
        completed_at=None,
        last_interaction_at=None,
    )
    pending_messages = [
        SimpleNamespace(
            id=uuid4(),
            status=MessageStatus.PENDING,
            message_metadata={"celery_task_id": "task-1"},
        ),
        SimpleNamespace(
            id=uuid4(),
            status=MessageStatus.SCHEDULED,
            message_metadata={"celery_task_id": "task-2"},
        ),
    ]
    service, _db = _build_service(flow_state, pending_messages)

    async_result = MagicMock()
    async_result.revoke = MagicMock()

    with patch("celery.result.AsyncResult", return_value=async_result):
        await service.cancel_patient_flow(patient_id=uuid4(), user_id=uuid4())

    assert async_result.revoke.call_count == 2


@pytest.mark.asyncio
async def test_cancel_overrides_pause_directly() -> None:
    flow_state = SimpleNamespace(
        id=uuid4(),
        status="paused",
        state_data={"paused": True, "auto_resume_at": "2026-02-24T12:00:00+00:00"},
        version=5,
        completed_at=None,
        last_interaction_at=None,
    )
    service, _db = _build_service(flow_state, [])

    await service.cancel_patient_flow(patient_id=uuid4(), user_id=uuid4())

    assert flow_state.state_data["paused"] is False
    assert "auto_resume_at" not in flow_state.state_data
    assert flow_state.state_data["cancelled"] is True


@pytest.mark.asyncio
async def test_cancel_nonexistent_flow_raises_not_found() -> None:
    flow_repo = MagicMock()
    flow_repo.get_active_flow.return_value = None
    flow_repo.db = MagicMock()
    db = MagicMock()

    with patch("app.services.flow_management.EnhancedFlowEngine") as engine_cls:
        engine_cls.return_value = MagicMock()
        service = FlowManagementService(flow_repo=flow_repo, db=db)

    with pytest.raises(FlowStateNotFoundError):
        await service.cancel_patient_flow(patient_id=uuid4(), user_id=uuid4())
