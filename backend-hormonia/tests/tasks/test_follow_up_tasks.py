from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from app.tasks.follow_up import execute_pending_follow_ups, process_escalation_alerts
from app.services.follow_up_system.enums import (
    EscalationLevel,
    FollowUpType,
    NotificationChannel,
)
from app.services.follow_up_system.models import FollowUpAction, EscalationAlert
from app.services.analytics.data_extraction import MedicalConcernType


@contextmanager
def _fake_db_session():
    yield Mock()


def _build_action_dict(action: FollowUpAction) -> dict:
    return {
        "action_id": str(action.action_id),
        "patient_id": str(action.patient_id),
        "follow_up_type": action.follow_up_type.value,
        "priority": action.priority,
        "scheduled_for": action.scheduled_for.isoformat(),
        "parameters": action.parameters,
        "created_by": action.created_by,
        "status": action.status,
        "created_at": action.created_at.isoformat(),
        "executed_at": None,
        "execution_result": None,
    }


def test_execute_pending_follow_ups_rebuilds_actions_from_redis():
    now = datetime.now(timezone.utc)
    patient_id = uuid4()
    action_one = FollowUpAction(
        action_id=uuid4(),
        patient_id=patient_id,
        follow_up_type=FollowUpType.EMPATHETIC_RESPONSE,
        priority="high",
        scheduled_for=now - timedelta(minutes=10),
        parameters={"message_content": "Hello"},
    )
    action_two = FollowUpAction(
        action_id=uuid4(),
        patient_id=patient_id,
        follow_up_type=FollowUpType.CONVERSATION_CONTINUATION,
        priority="normal",
        scheduled_for=now - timedelta(minutes=5),
        parameters={"message_content": "Follow up"},
    )

    pending_dicts = [
        _build_action_dict(action_one),
        _build_action_dict(action_two),
    ]

    redis_store = Mock()
    redis_store.get_pending_actions = AsyncMock(return_value=pending_dicts)
    redis_store.update_action_status = AsyncMock(return_value=True)

    follow_up_service = Mock()
    follow_up_service.pending_actions = {}
    follow_up_service.redis_store = redis_store
    follow_up_service.rehydrate_from_redis = AsyncMock()
    follow_up_service.sync_memory_to_redis = AsyncMock()
    follow_up_service._dict_to_follow_up_action = Mock(
        side_effect=[action_one, action_two]
    )

    executed_actions = []

    def _fake_execute(_db, _service, action):
        executed_actions.append(action)
        return {"success": True}

    with patch("app.tasks.follow_up.get_db_session", _fake_db_session), patch(
        "app.services.follow_up_system.service.FollowUpSystemService",
        return_value=follow_up_service,
    ), patch("app.tasks.follow_up._execute_follow_up_action", side_effect=_fake_execute):
        result = execute_pending_follow_ups.run()

    assert result["success"] is True
    assert result["executed_count"] == 2
    assert follow_up_service._dict_to_follow_up_action.call_count == 2
    assert action_one.action_id in follow_up_service.pending_actions
    assert action_two.action_id in follow_up_service.pending_actions
    assert executed_actions == [action_one, action_two]


def test_process_escalation_alerts_rehydrates_from_redis():
    patient_id = uuid4()
    alert = EscalationAlert(
        alert_id=uuid4(),
        patient_id=patient_id,
        escalation_level=EscalationLevel.LOW,
        concern_type=MedicalConcernType.SIDE_EFFECT,
        description="Follow-up escalation",
        original_message="Need attention",
        recommended_actions=["Call patient"],
        notification_channels=[NotificationChannel.WHATSAPP],
        requires_immediate_response=False,
    )
    alert.created_at = datetime.now(timezone.utc) - timedelta(minutes=45)

    follow_up_service = Mock()
    follow_up_service.active_alerts = {}

    async def _rehydrate():
        follow_up_service.active_alerts[alert.alert_id] = alert

    follow_up_service.rehydrate_from_redis = AsyncMock(side_effect=_rehydrate)

    with patch("app.tasks.follow_up.get_db_session", _fake_db_session), patch(
        "app.services.follow_up_system.service.FollowUpSystemService",
        return_value=follow_up_service,
    ):
        result = process_escalation_alerts.run()

    assert result["success"] is True
    assert result["processed_count"] == 1
    assert result["escalated_count"] == 1
    assert alert.escalation_level == EscalationLevel.MEDIUM
