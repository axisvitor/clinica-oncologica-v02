from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.message import MessageStatus
from app.services.flow_management import FlowManagementService


def _build_service(flow_state, pending_messages=None):
    flow_repo = MagicMock()
    flow_repo.db = MagicMock()
    flow_repo.get_active_flow.return_value = flow_state

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = pending_messages or []

    with patch("app.services.flow_management.EnhancedFlowEngine") as engine_cls:
        engine_cls.return_value = MagicMock()
        service = FlowManagementService(flow_repo=flow_repo, db=db)

    return service, db, flow_repo


class TestPauseMidFlow:
    @pytest.mark.asyncio
    async def test_pause_active_flow_sets_paused_state(self) -> None:
        now = datetime(2026, 3, 1, 15, 0, tzinfo=timezone.utc)
        flow_state = SimpleNamespace(
            id=uuid4(),
            status="active",
            state_data={},
            version=1,
            completed_at=None,
            last_interaction_at=None,
        )
        service, db, _flow_repo = _build_service(flow_state)

        with patch("app.services.flow_management.now_sao_paulo", return_value=now):
            result = await service.pause_patient_flow(patient_id=uuid4())

        assert result.status == "paused"
        assert flow_state.status == "paused"
        assert flow_state.state_data["paused"] is True
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_with_auto_resume_sets_auto_resume_at(self) -> None:
        now = datetime(2026, 3, 1, 15, 0, tzinfo=timezone.utc)
        flow_state = SimpleNamespace(
            id=uuid4(),
            status="active",
            state_data={},
            version=2,
            completed_at=None,
            last_interaction_at=None,
        )
        service, _db, _flow_repo = _build_service(flow_state)

        with patch("app.services.flow_management.now_sao_paulo", return_value=now):
            await service.pause_patient_flow(patient_id=uuid4(), duration_hours=24)

        assert flow_state.status == "paused"
        assert flow_state.state_data["paused"] is True
        assert flow_state.state_data.get("auto_resume_at") == (
            now + timedelta(hours=24)
        ).isoformat()


class TestResumeAfterPause:
    @pytest.mark.asyncio
    async def test_resume_paused_flow_restores_active_state(self) -> None:
        now = datetime(2026, 3, 1, 16, 0, tzinfo=timezone.utc)
        flow_state = SimpleNamespace(
            id=uuid4(),
            status="paused",
            state_data={
                "paused": True,
                "auto_resume_at": "2026-03-01T12:00:00+00:00",
            },
            version=4,
            completed_at=None,
            last_interaction_at=None,
        )
        service, db, _flow_repo = _build_service(flow_state)

        with patch("app.services.flow_management.now_sao_paulo", return_value=now):
            result = await service.resume_patient_flow(patient_id=uuid4())

        assert result.status == "active"
        assert flow_state.status == "active"
        assert flow_state.state_data["paused"] is False
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_resume_clears_auto_resume_at(self) -> None:
        now = datetime(2026, 3, 1, 16, 30, tzinfo=timezone.utc)
        flow_state = SimpleNamespace(
            id=uuid4(),
            status="paused",
            state_data={"paused": True, "auto_resume_at": "2026-03-01T12:00:00+00:00"},
            version=5,
            completed_at=None,
            last_interaction_at=None,
        )
        service, _db, _flow_repo = _build_service(flow_state)

        with patch("app.services.flow_management.now_sao_paulo", return_value=now):
            await service.resume_patient_flow(patient_id=uuid4())

        assert "auto_resume_at" not in flow_state.state_data


class TestCancelDuringExecution:
    @pytest.mark.asyncio
    async def test_cancel_active_flow_does_not_trigger_saga_compensation(self) -> None:
        now = datetime(2026, 3, 1, 17, 0, tzinfo=timezone.utc)
        flow_state = SimpleNamespace(
            id=uuid4(),
            status="active",
            state_data={},
            version=1,
            completed_at=None,
            last_interaction_at=None,
        )
        service, db, _flow_repo = _build_service(flow_state, pending_messages=[])

        with patch(
            "app.orchestration.saga_orchestrator.compensation.SagaCompensator.compensate_saga",
            new_callable=AsyncMock,
        ) as compensate_saga:
            with patch("app.services.flow_management.now_sao_paulo", return_value=now):
                result = await service.cancel_patient_flow(
                    patient_id=uuid4(),
                    user_id=uuid4(),
                )

        assert result["status"] == "cancelled"
        assert flow_state.status == "cancelled"
        assert flow_state.state_data["cancelled"] is True
        compensate_saga.assert_not_awaited()
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_during_paused_flow_clears_pause_and_cancels(self) -> None:
        flow_state = SimpleNamespace(
            id=uuid4(),
            status="paused",
            state_data={"paused": True, "auto_resume_at": "2026-03-01T12:00:00+00:00"},
            version=6,
            completed_at=None,
            last_interaction_at=None,
        )
        service, _db, _flow_repo = _build_service(flow_state, pending_messages=[])

        await service.cancel_patient_flow(patient_id=uuid4(), user_id=uuid4())

        assert flow_state.status == "cancelled"
        assert flow_state.state_data["paused"] is False
        assert flow_state.state_data["cancelled"] is True
        assert "auto_resume_at" not in flow_state.state_data

    @pytest.mark.asyncio
    async def test_cancel_marks_pending_messages_cancelled(self) -> None:
        flow_state = SimpleNamespace(
            id=uuid4(),
            status="active",
            state_data={},
            version=3,
            completed_at=None,
            last_interaction_at=None,
        )
        pending_messages = [
            SimpleNamespace(
                id=uuid4(), status=MessageStatus.SCHEDULED, message_metadata={}
            ),
            SimpleNamespace(id=uuid4(), status=MessageStatus.PENDING, message_metadata={}),
        ]
        service, _db, _flow_repo = _build_service(flow_state, pending_messages)

        await service.cancel_patient_flow(patient_id=uuid4(), user_id=uuid4())

        assert all(message.status == MessageStatus.CANCELLED for message in pending_messages)
