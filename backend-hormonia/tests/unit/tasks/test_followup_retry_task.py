import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from celery.exceptions import MaxRetriesExceededError

from app.services.follow_up_system.enums import FollowUpType
from app.services.follow_up_system.execution.message import MessageExecutor
from app.services.follow_up_system.models import FollowUpAction
from app.tasks.flows.followup_retry import (
    FOLLOWUP_RETRY_BACKOFF,
    FOLLOWUP_RETRY_BASE_DELAY,
    FOLLOWUP_RETRY_MAX,
    retry_failed_followup_send,
)
from app.utils.timezone import now_sao_paulo


@contextmanager
def _db_session(db):
    yield db


def _async_to_sync_bridge(fn):
    def _call(*args, **kwargs):
        result = fn(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return asyncio.run(result)
        return result

    return _call


def _build_action() -> FollowUpAction:
    return FollowUpAction(
        action_id=uuid4(),
        patient_id=uuid4(),
        follow_up_type=FollowUpType.CONVERSATION_CONTINUATION,
        priority="high",
        scheduled_for=now_sao_paulo(),
        parameters={"message_content": "Check-in"},
    )


@pytest.fixture(autouse=True)
def _task_context():
    original_retries = retry_failed_followup_send.request.retries
    original_max_retries = retry_failed_followup_send.max_retries
    retry_failed_followup_send.request.retries = 0
    retry_failed_followup_send.max_retries = FOLLOWUP_RETRY_MAX
    yield
    retry_failed_followup_send.request.retries = original_retries
    retry_failed_followup_send.max_retries = original_max_retries


def test_retry_failed_followup_send_returns_action_not_found_without_parameters():
    result = retry_failed_followup_send.run(str(uuid4()), str(uuid4()), parameters=None)

    assert result["status"] == "action_not_found"


def test_retry_failed_followup_send_reschedules_action_successfully():
    db = MagicMock()
    follow_up_service = MagicMock()
    follow_up_service.action_executor._schedule_message_action = AsyncMock(
        return_value=True
    )
    follow_up_service.redis_store.update_action_status = AsyncMock(return_value=True)

    action_id = uuid4()
    patient_id = uuid4()

    with patch(
        "app.tasks.flows.followup_retry.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows.followup_retry.async_to_sync",
        side_effect=_async_to_sync_bridge,
    ), patch(
        "app.services.follow_up_system.service.FollowUpSystemService",
        return_value=follow_up_service,
    ):
        result = retry_failed_followup_send.run(
            str(action_id),
            str(patient_id),
            parameters={"message_content": "Retry me"},
            follow_up_type=FollowUpType.CONVERSATION_CONTINUATION.value,
            priority="medium",
        )

    assert result == {
        "status": "ok",
        "action_id": str(action_id),
        "attempt": 1,
    }
    follow_up_service.redis_store.update_action_status.assert_awaited_once()


def test_retry_failed_followup_send_retries_with_exponential_backoff():
    db = MagicMock()
    follow_up_service = MagicMock()
    follow_up_service.action_executor._schedule_message_action = AsyncMock(
        side_effect=RuntimeError("boom")
    )
    follow_up_service.redis_store.update_action_status = AsyncMock(return_value=True)
    retry_failed_followup_send.request.retries = 1

    with patch(
        "app.tasks.flows.followup_retry.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows.followup_retry.async_to_sync",
        side_effect=_async_to_sync_bridge,
    ), patch(
        "app.services.follow_up_system.service.FollowUpSystemService",
        return_value=follow_up_service,
    ), patch("app.tasks.flows.followup_retry.random.randint", return_value=4), patch(
        "app.tasks.flows.followup_retry.retry_failed_followup_send.retry",
        side_effect=RuntimeError("retry called"),
    ) as retry_mock:
        with pytest.raises(RuntimeError, match="retry called"):
            retry_failed_followup_send.run(
                str(uuid4()),
                str(uuid4()),
                parameters={"message_content": "Retry me"},
                follow_up_type=FollowUpType.CONVERSATION_CONTINUATION.value,
            )

    expected_countdown = (
        FOLLOWUP_RETRY_BASE_DELAY
        * (FOLLOWUP_RETRY_BACKOFF ** retry_failed_followup_send.request.retries)
    ) + 4
    assert retry_mock.call_args.kwargs["countdown"] == expected_countdown


def test_retry_failed_followup_send_marks_failed_after_retry_exhaustion():
    db = MagicMock()
    follow_up_service = MagicMock()
    follow_up_service.action_executor._schedule_message_action = AsyncMock(
        side_effect=RuntimeError("boom")
    )
    follow_up_service.redis_store.update_action_status = AsyncMock(return_value=True)
    retry_failed_followup_send.request.retries = FOLLOWUP_RETRY_MAX

    with patch(
        "app.tasks.flows.followup_retry.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows.followup_retry.async_to_sync",
        side_effect=_async_to_sync_bridge,
    ), patch(
        "app.services.follow_up_system.service.FollowUpSystemService",
        return_value=follow_up_service,
    ), patch(
        "app.tasks.flows.followup_retry.retry_failed_followup_send.retry",
        side_effect=MaxRetriesExceededError("done"),
    ):
        result = retry_failed_followup_send.run(
            str(uuid4()),
            str(uuid4()),
            parameters={"message_content": "Retry me"},
            follow_up_type=FollowUpType.CONVERSATION_CONTINUATION.value,
        )

    assert result["status"] == "permanently_failed"
    assert result["attempts"] == FOLLOWUP_RETRY_MAX
    follow_up_service.redis_store.update_action_status.assert_awaited_once()
    assert (
        follow_up_service.redis_store.update_action_status.await_args.kwargs["status"]
        == "failed"
    )


@pytest.mark.asyncio
async def test_message_executor_enqueues_retry_on_failure():
    action = _build_action()
    scheduler = AsyncMock(side_effect=RuntimeError("scheduler down"))
    executor = MessageExecutor(MagicMock(), {}, scheduler=scheduler)

    with patch(
        "app.tasks.flows.followup_retry.retry_failed_followup_send.apply_async"
    ) as apply_async:
        success = await executor._execute_message_action(action)

    assert success is False
    assert action.execution_result["retry_enqueued"] is True
    apply_async.assert_called_once()
