"""Tests for retry_failed_followup_send Taskiq task.

Taskiq migration: No Celery imports. Tasks are async; tested via await task.fn().
SmartRetryMiddleware handles retry scheduling — tasks just raise on failure.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.follow_up_system.enums import FollowUpType
from app.services.follow_up_system.models import FollowUpAction
from app.tasks.flows_taskiq import retry_failed_followup_send
from app.tasks.helpers.flow_helpers import (
    FOLLOWUP_RETRY_BACKOFF,
    FOLLOWUP_RETRY_BASE_DELAY,
    FOLLOWUP_RETRY_MAX,
)
from app.utils.timezone import now_sao_paulo


def _build_action() -> FollowUpAction:
    return FollowUpAction(
        action_id=uuid4(),
        patient_id=uuid4(),
        follow_up_type=FollowUpType.CONVERSATION_CONTINUATION,
        priority="high",
        scheduled_for=now_sao_paulo(),
        parameters={"message_content": "Check-in"},
    )


def _fake_context(retries: int = 0):
    """Build a minimal fake Taskiq context with retry labels."""
    ctx = MagicMock()
    ctx.message.labels = {"_retries": str(retries)}
    return ctx


@pytest.mark.asyncio
async def test_retry_failed_followup_send_returns_action_not_found_without_parameters():
    result = await retry_failed_followup_send.fn(
        action_id=str(uuid4()),
        patient_id=str(uuid4()),
        parameters=None,
        context=_fake_context(0),
    )
    assert result["status"] == "action_not_found"


@pytest.mark.asyncio
async def test_retry_failed_followup_send_reschedules_action_successfully():
    db = MagicMock()
    follow_up_service = MagicMock()
    follow_up_service.action_executor._schedule_message_action = AsyncMock(
        return_value=True
    )
    follow_up_service.redis_store.update_action_status = AsyncMock(return_value=True)

    action_id = uuid4()
    patient_id = uuid4()

    with patch(
        "app.tasks.flows_taskiq.get_scoped_session",
    ) as mock_session, patch(
        "app.services.follow_up_system.service.FollowUpSystemService",
        return_value=follow_up_service,
    ):
        mock_session.return_value.__enter__ = MagicMock(return_value=db)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        result = await retry_failed_followup_send.fn(
            action_id=str(action_id),
            patient_id=str(patient_id),
            parameters={"message_content": "Retry me"},
            follow_up_type=FollowUpType.CONVERSATION_CONTINUATION.value,
            priority="medium",
            context=_fake_context(0),
        )

    assert result == {
        "status": "ok",
        "action_id": str(action_id),
        "attempt": 1,
    }
    follow_up_service.redis_store.update_action_status.assert_awaited_once()


@pytest.mark.asyncio
async def test_retry_failed_followup_send_raises_on_transient_failure():
    """Taskiq pattern: transient failures raise, SmartRetryMiddleware handles retry."""
    db = MagicMock()
    follow_up_service = MagicMock()
    follow_up_service.action_executor._schedule_message_action = AsyncMock(
        side_effect=RuntimeError("boom")
    )
    follow_up_service.redis_store.update_action_status = AsyncMock(return_value=True)

    with patch(
        "app.tasks.flows_taskiq.get_scoped_session",
    ) as mock_session, patch(
        "app.services.follow_up_system.service.FollowUpSystemService",
        return_value=follow_up_service,
    ):
        mock_session.return_value.__enter__ = MagicMock(return_value=db)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(RuntimeError, match="boom"):
            await retry_failed_followup_send.fn(
                action_id=str(uuid4()),
                patient_id=str(uuid4()),
                parameters={"message_content": "Retry me"},
                follow_up_type=FollowUpType.CONVERSATION_CONTINUATION.value,
                context=_fake_context(1),  # retries=1, < max
            )


@pytest.mark.asyncio
async def test_retry_failed_followup_send_marks_failed_after_retry_exhaustion():
    """When retries >= max, the task returns permanently_failed instead of raising."""
    db = MagicMock()
    follow_up_service = MagicMock()
    follow_up_service.action_executor._schedule_message_action = AsyncMock(
        side_effect=RuntimeError("boom")
    )
    follow_up_service.redis_store.update_action_status = AsyncMock(return_value=True)

    with patch(
        "app.tasks.flows_taskiq.get_scoped_session",
    ) as mock_session, patch(
        "app.services.follow_up_system.service.FollowUpSystemService",
        return_value=follow_up_service,
    ):
        mock_session.return_value.__enter__ = MagicMock(return_value=db)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        result = await retry_failed_followup_send.fn(
            action_id=str(uuid4()),
            patient_id=str(uuid4()),
            parameters={"message_content": "Retry me"},
            follow_up_type=FollowUpType.CONVERSATION_CONTINUATION.value,
            context=_fake_context(FOLLOWUP_RETRY_MAX),  # retries exhausted
        )

    assert result["status"] == "permanently_failed"
    assert result["attempts"] == FOLLOWUP_RETRY_MAX
    follow_up_service.redis_store.update_action_status.assert_awaited_once()
    assert (
        follow_up_service.redis_store.update_action_status.await_args.kwargs["status"]
        == "failed"
    )
