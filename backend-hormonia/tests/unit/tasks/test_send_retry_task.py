from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from celery.exceptions import MaxRetriesExceededError

from app.exceptions import ExternalServiceError
from app.models.message import MessageStatus
from app.tasks.flows.send_retry import (
    SEND_RETRY_BACKOFF_FACTOR,
    SEND_RETRY_BASE_DELAY,
    SEND_RETRY_MAX_RETRIES,
    retry_failed_flow_send,
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


def _async_to_sync_return(value):
    def _factory(fn):
        def _call(*args, **kwargs):
            coro = fn(*args, **kwargs)
            coro.close()
            return value

        return _call

    return _factory


def _async_to_sync_raise(exc):
    def _factory(fn):
        def _call(*args, **kwargs):
            coro = fn(*args, **kwargs)
            coro.close()
            raise exc

        return _call

    return _factory


@pytest.fixture(autouse=True)
def _task_context():
    original_retries = retry_failed_flow_send.request.retries
    original_max_retries = retry_failed_flow_send.max_retries
    retry_failed_flow_send.request.retries = 0
    retry_failed_flow_send.max_retries = SEND_RETRY_MAX_RETRIES
    yield
    retry_failed_flow_send.request.retries = original_retries
    retry_failed_flow_send.max_retries = original_max_retries


def test_retry_failed_flow_send_returns_message_not_found():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with patch(
        "app.tasks.flows.send_retry.get_scoped_session",
        return_value=_db_session(db),
    ), patch("app.tasks.flows.send_retry.UnifiedWhatsAppService") as service_cls:
        result = retry_failed_flow_send.run(str(uuid4()))

    assert result["status"] == "message_not_found"
    service_cls.assert_not_called()


def test_retry_failed_flow_send_skips_already_finalized_message():
    message = _message(status=MessageStatus.SENT)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message

    with patch(
        "app.tasks.flows.send_retry.get_scoped_session",
        return_value=_db_session(db),
    ), patch("app.tasks.flows.send_retry.UnifiedWhatsAppService") as service_cls:
        result = retry_failed_flow_send.run(str(message.id))

    assert result["status"] == "already_finalized"
    assert result["message_status"] == MessageStatus.SENT.value
    service_cls.assert_not_called()


def test_retry_failed_flow_send_resends_message_with_flow_context():
    message = _message()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message
    service = MagicMock()
    service.send_message = AsyncMock(return_value=True)
    flow_context = {"flow_type": "onboarding", "flow_day": 3, "message_index": 1}

    with patch(
        "app.tasks.flows.send_retry.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows.send_retry.UnifiedWhatsAppService",
        return_value=service,
    ), patch(
        "app.tasks.flows.send_retry.async_to_sync",
        side_effect=_async_to_sync_return(True),
    ):
        result = retry_failed_flow_send.run(str(message.id), flow_context=flow_context)

    assert message.status == MessageStatus.PENDING
    assert message.retry_count == 1
    service.send_message.assert_called_once_with(message, flow_context=flow_context)
    assert result == {
        "status": "ok",
        "message_id": str(message.id),
        "attempt": 1,
    }


def test_retry_failed_flow_send_retries_with_exponential_backoff_and_jitter():
    message = _message()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message
    service = MagicMock()
    service.send_message = AsyncMock(return_value=True)
    retry_failed_flow_send.request.retries = 1

    with patch(
        "app.tasks.flows.send_retry.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows.send_retry.UnifiedWhatsAppService",
        return_value=service,
    ), patch(
        "app.tasks.flows.send_retry.async_to_sync",
        side_effect=_async_to_sync_raise(ExternalServiceError("timeout")),
    ), patch("app.tasks.flows.send_retry.random.randint", return_value=7), patch(
        "app.tasks.flows.send_retry.retry_failed_flow_send.retry",
        side_effect=RuntimeError("retry called"),
    ) as retry_mock:
        with pytest.raises(RuntimeError, match="retry called"):
            retry_failed_flow_send.run(str(message.id))

    expected_countdown = (
        SEND_RETRY_BASE_DELAY
        * (SEND_RETRY_BACKOFF_FACTOR ** retry_failed_flow_send.request.retries)
    ) + 7
    retry_mock.assert_called_once()
    assert retry_mock.call_args.kwargs["countdown"] == expected_countdown
    assert isinstance(retry_mock.call_args.kwargs["exc"], ExternalServiceError)


def test_retry_failed_flow_send_treats_false_result_as_retryable_failure():
    message = _message()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message
    service = MagicMock()
    service.send_message = AsyncMock(return_value=False)

    with patch(
        "app.tasks.flows.send_retry.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows.send_retry.UnifiedWhatsAppService",
        return_value=service,
    ), patch(
        "app.tasks.flows.send_retry.async_to_sync",
        side_effect=_async_to_sync_return(False),
    ), patch("app.tasks.flows.send_retry.random.randint", return_value=3), patch(
        "app.tasks.flows.send_retry.retry_failed_flow_send.retry",
        side_effect=RuntimeError("retry called"),
    ) as retry_mock:
        with pytest.raises(RuntimeError, match="retry called"):
            retry_failed_flow_send.run(str(message.id))

    assert retry_mock.call_args.kwargs["countdown"] == SEND_RETRY_BASE_DELAY + 3
    assert isinstance(retry_mock.call_args.kwargs["exc"], ExternalServiceError)


def test_retry_failed_flow_send_marks_failed_when_retries_exhausted():
    message = _message()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message
    service = MagicMock()
    service.send_message = AsyncMock(return_value=True)
    flow_state = MagicMock()
    flow_state.current_step = 4
    flow_state.state_data = {"existing": True}
    flow_repo = MagicMock()
    flow_repo.get_active_flow.return_value = flow_state
    retry_failed_flow_send.request.retries = SEND_RETRY_MAX_RETRIES

    with patch(
        "app.tasks.flows.send_retry.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows.send_retry.UnifiedWhatsAppService",
        return_value=service,
    ), patch(
        "app.tasks.flows.send_retry.async_to_sync",
        side_effect=_async_to_sync_raise(ExternalServiceError("timeout")),
    ), patch(
        "app.tasks.flows.send_retry.retry_failed_flow_send.retry",
        side_effect=MaxRetriesExceededError("done"),
    ), patch(
        "app.tasks.flows.send_retry.FlowStateRepository",
        return_value=flow_repo,
    ), patch("app.tasks.flows.send_retry.logger.error") as error_mock:
        result = retry_failed_flow_send.run(
            str(message.id),
            flow_context={"flow_type": "onboarding"},
        )

    assert message.status == MessageStatus.FAILED
    assert result["status"] == "permanently_failed"
    assert result["message_id"] == str(message.id)
    assert result["attempts"] == SEND_RETRY_MAX_RETRIES
    assert result["permanently_failed"] is True
    assert flow_state.state_data["delivery_failures"][0]["message_id"] == str(message.id)
    assert flow_state.state_data["skip_waiting_for_message"] == str(message.id)
    assert flow_state.state_data["last_delivery_failure"]
    assert db.commit.call_count >= 1
    error_mock.assert_called_once()


def test_retry_failed_flow_send_preserves_explicit_flow_context_for_retry():
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
        "app.tasks.flows.send_retry.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows.send_retry.UnifiedWhatsAppService",
        return_value=service,
    ), patch(
        "app.tasks.flows.send_retry.async_to_sync",
        side_effect=_async_to_sync_return(True),
    ):
        retry_failed_flow_send.run(str(message.id), flow_context=flow_context)

    assert service.send_message.call_args.kwargs["flow_context"] == flow_context


def test_retry_failed_flow_send_uses_metadata_flow_context_when_none_provided():
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
        "app.tasks.flows.send_retry.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows.send_retry.UnifiedWhatsAppService",
        return_value=service,
    ), patch(
        "app.tasks.flows.send_retry.async_to_sync",
        side_effect=_async_to_sync_return(True),
    ):
        retry_failed_flow_send.run(str(message.id))

    assert service.send_message.call_args.kwargs["flow_context"] == stored_flow_context
