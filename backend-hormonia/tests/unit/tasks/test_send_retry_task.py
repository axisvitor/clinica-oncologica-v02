"""Tests for retry_failed_flow_send Taskiq task.

Taskiq migration: No Celery imports. Tasks are async; tested via await task.fn().
SmartRetryMiddleware handles retry scheduling — tasks just raise on failure.
"""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.exceptions import ExternalServiceError
from app.models.message import MessageStatus
from app.tasks.flows_taskiq import retry_failed_flow_send
from app.tasks.helpers.flow_helpers import (
    SEND_RETRY_BACKOFF_FACTOR,
    SEND_RETRY_BASE_DELAY,
    SEND_RETRY_MAX_RETRIES,
)


@contextmanager
def _db_session(db):
    yield db


def _message(
    *,
    status: MessageStatus = MessageStatus.FAILED,
    flow_context: dict | None = None,
):
    metadata = {"source": "flow_sequential"}
    if flow_context is not None:
        metadata["flow_context"] = flow_context

    return SimpleNamespace(
        id=uuid4(),
        patient_id=uuid4(),
        status=status,
        retry_count=0,
        failure_reason=None,
        last_retry_at=None,
        next_retry_at=None,
        message_metadata=metadata,
    )


def _fake_context(retries: int = 0):
    """Build a minimal fake Taskiq context with retry labels."""
    ctx = MagicMock()
    ctx.message.labels = {"_retries": str(retries)}
    return ctx


@pytest.mark.asyncio
async def test_retry_failed_flow_send_returns_message_not_found():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with patch(
        "app.tasks.flows_taskiq.get_scoped_session",
        return_value=_db_session(db),
    ):
        result = await retry_failed_flow_send.fn(
            message_id=str(uuid4()),
            context=_fake_context(0),
        )

    assert result["status"] == "message_not_found"


@pytest.mark.asyncio
async def test_retry_failed_flow_send_skips_already_finalized_message():
    message = _message(status=MessageStatus.SENT)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message

    with patch(
        "app.tasks.flows_taskiq.get_scoped_session",
        return_value=_db_session(db),
    ):
        result = await retry_failed_flow_send.fn(
            message_id=str(message.id),
            context=_fake_context(0),
        )

    assert result["status"] == "already_finalized"
    assert result["message_status"] == MessageStatus.SENT.value


@pytest.mark.asyncio
async def test_retry_failed_flow_send_resends_message_with_flow_context():
    message = _message()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message
    service = MagicMock()
    service.send_message = AsyncMock(return_value=True)
    flow_context = {"flow_type": "onboarding", "flow_day": 3, "message_index": 1}

    with patch(
        "app.tasks.flows_taskiq.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows_taskiq.UnifiedWhatsAppService",
        return_value=service,
    ):
        result = await retry_failed_flow_send.fn(
            message_id=str(message.id),
            flow_context=flow_context,
            context=_fake_context(0),
        )

    assert message.status == MessageStatus.PENDING
    assert message.retry_count == 1
    service.send_message.assert_awaited_once_with(message, flow_context=flow_context)
    assert result == {
        "status": "ok",
        "message_id": str(message.id),
        "attempt": 1,
    }


@pytest.mark.asyncio
async def test_retry_failed_flow_send_raises_on_transient_failure():
    """Taskiq pattern: transient failures raise, SmartRetryMiddleware handles retry."""
    message = _message()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message
    service = MagicMock()
    service.send_message = AsyncMock(side_effect=ExternalServiceError("timeout"))

    with patch(
        "app.tasks.flows_taskiq.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows_taskiq.UnifiedWhatsAppService",
        return_value=service,
    ):
        with pytest.raises(ExternalServiceError):
            await retry_failed_flow_send.fn(
                message_id=str(message.id),
                context=_fake_context(1),  # retries=1, < max (5)
            )


@pytest.mark.asyncio
async def test_retry_failed_flow_send_treats_false_result_as_retryable():
    """When send returns False, the task raises ExternalServiceError."""
    message = _message()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message
    service = MagicMock()
    service.send_message = AsyncMock(return_value=False)

    with patch(
        "app.tasks.flows_taskiq.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows_taskiq.UnifiedWhatsAppService",
        return_value=service,
    ):
        with pytest.raises(ExternalServiceError):
            await retry_failed_flow_send.fn(
                message_id=str(message.id),
                context=_fake_context(0),
            )


@pytest.mark.asyncio
async def test_retry_failed_flow_send_marks_failed_when_retries_exhausted():
    """When retries >= max, the task returns permanently_failed instead of raising."""
    message = _message()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message
    service = MagicMock()
    service.send_message = AsyncMock(side_effect=ExternalServiceError("timeout"))
    flow_state = MagicMock()
    flow_state.current_step = 4
    flow_state.state_data = {"existing": True}
    flow_repo = MagicMock()
    flow_repo.get_active_flow.return_value = flow_state

    with patch(
        "app.tasks.flows_taskiq.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows_taskiq.UnifiedWhatsAppService",
        return_value=service,
    ), patch(
        "app.tasks.helpers.flow_helpers.FlowStateRepository",
        return_value=flow_repo,
    ):
        result = await retry_failed_flow_send.fn(
            message_id=str(message.id),
            flow_context={"flow_type": "onboarding"},
            context=_fake_context(5),  # retries=5 = max
        )

    assert message.status == MessageStatus.FAILED
    assert result["status"] == "permanently_failed"
    assert result["permanently_failed"] is True


@pytest.mark.asyncio
async def test_retry_failed_flow_send_preserves_explicit_flow_context():
    message = _message()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message
    service = MagicMock()
    service.send_message = AsyncMock(return_value=True)
    flow_context = {
        "flow_type": "adherence",
        "flow_day": 7,
        "message_index": 2,
        "expects_response": True,
    }

    with patch(
        "app.tasks.flows_taskiq.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows_taskiq.UnifiedWhatsAppService",
        return_value=service,
    ):
        await retry_failed_flow_send.fn(
            message_id=str(message.id),
            flow_context=flow_context,
            context=_fake_context(0),
        )

    assert service.send_message.call_args.kwargs["flow_context"] == flow_context


@pytest.mark.asyncio
async def test_retry_failed_flow_send_uses_metadata_flow_context_when_none_provided():
    stored_flow_context = {
        "flow_type": "onboarding",
        "flow_day": 2,
        "message_index": 0,
        "expects_response": False,
    }
    message = _message(flow_context=stored_flow_context)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message
    service = MagicMock()
    service.send_message = AsyncMock(return_value=True)

    with patch(
        "app.tasks.flows_taskiq.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows_taskiq.UnifiedWhatsAppService",
        return_value=service,
    ):
        await retry_failed_flow_send.fn(
            message_id=str(message.id),
            context=_fake_context(0),
        )

    assert service.send_message.call_args.kwargs["flow_context"] == stored_flow_context
