from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.exceptions import ExternalServiceError
from app.models.failed_message import FailureReason
from app.models.message import MessageStatus
from app.services.dlq.base import FlowMessageRetryConfig
from app.tasks.messaging import send_scheduled_message


@contextmanager
def _db_session(db):
    yield db


def _mock_message(status: MessageStatus = MessageStatus.SENDING, metadata=None):
    message = MagicMock()
    message.id = uuid4()
    message.patient_id = uuid4()
    message.type = SimpleNamespace(value="text")
    message.status = status
    message.retry_count = 0
    message.message_metadata = metadata or {"flow_context": {"flow_type": "quiz"}}
    return message


def _run_async_return(value):
    def _side_effect(coro):
        coro.close()
        return value

    return _side_effect


def _run_async_raise(exc):
    def _side_effect(coro):
        coro.close()
        raise exc

    return _side_effect


@pytest.fixture(autouse=True)
def _task_context():
    original_retries = send_scheduled_message.request.retries
    original_max_retries = send_scheduled_message.max_retries
    send_scheduled_message.request.retries = 0
    send_scheduled_message.max_retries = 3
    yield
    send_scheduled_message.request.retries = original_retries
    send_scheduled_message.max_retries = original_max_retries


def test_send_scheduled_message_routes_to_dlq_on_final_failure():
    message = _mock_message()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message
    send_scheduled_message.request.retries = 3
    send_scheduled_message.max_retries = 3

    with patch(
        "app.tasks.messaging.run_async",
        side_effect=_run_async_raise(ExternalServiceError("timeout")),
    ), patch(
        "app.tasks.messaging.get_db_session", return_value=_db_session(db)
    ), patch("app.services.dlq.service.DLQService.add_to_dlq") as add_to_dlq:
        result = send_scheduled_message.run(str(message.id))

    assert result["success"] is False
    assert "Max retries exceeded" in result["error"]
    add_to_dlq.assert_called_once()
    call_kwargs = add_to_dlq.call_args.kwargs
    assert call_kwargs["message_id"] == message.id
    assert call_kwargs["patient_id"] == message.patient_id
    assert call_kwargs["error_type"] == "ExternalServiceError"
    assert call_kwargs["failure_reason"] == FailureReason.MAX_RETRIES_EXCEEDED


def test_send_scheduled_message_does_not_dlq_on_retriable_failure():
    message = _mock_message()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message
    send_scheduled_message.request.retries = 1
    send_scheduled_message.max_retries = 3

    with patch(
        "app.tasks.messaging.run_async",
        side_effect=_run_async_raise(ExternalServiceError("timeout")),
    ), patch(
        "app.tasks.messaging.get_db_session", return_value=_db_session(db)
    ), patch("app.tasks.messaging.send_scheduled_message.handle_retry") as handle_retry, patch(
        "app.services.dlq.service.DLQService.add_to_dlq"
    ) as add_to_dlq:
        with pytest.raises(ExternalServiceError):
            send_scheduled_message.run(str(message.id))

    handle_retry.assert_called_once()
    add_to_dlq.assert_not_called()


def test_send_scheduled_message_non_retriable_routes_to_dlq():
    message = _mock_message()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message

    with patch(
        "app.tasks.messaging.run_async",
        side_effect=_run_async_return(
            {
            "found": True,
            "non_retriable": True,
            "error": "Invalid phone",
            "flow_context": {"flow_type": "quiz"},
            }
        ),
    ), patch("app.tasks.messaging.get_db_session", return_value=_db_session(db)), patch(
        "app.services.dlq.service.DLQService.add_to_dlq"
    ) as add_to_dlq:
        result = send_scheduled_message.run(str(message.id))

    assert result["success"] is False
    add_to_dlq.assert_called_once()
    assert (
        add_to_dlq.call_args.kwargs["failure_reason"]
        == FailureReason.UNKNOWN
    )


def test_dlq_routing_failure_does_not_crash_task():
    message = _mock_message()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message

    with patch(
        "app.tasks.messaging.run_async",
        side_effect=_run_async_return(
            {"found": True, "non_retriable": True, "error": "Invalid phone"}
        ),
    ), patch("app.tasks.messaging.get_db_session", return_value=_db_session(db)), patch(
        "app.services.dlq.service.DLQService.add_to_dlq", side_effect=Exception("dlq down")
    ):
        result = send_scheduled_message.run(str(message.id))

    assert result["success"] is False
    assert result["status"] == "failed"


def test_flow_message_retry_config_values():
    cfg = FlowMessageRetryConfig()

    assert cfg.MAX_RETRY_ATTEMPTS == 3
    assert cfg.RETRY_DELAYS == [30, 120, 600]


def test_dlq_payload_contains_flow_context():
    message = _mock_message(metadata={"flow_context": {"flow_type": "quiz"}})
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = message
    send_scheduled_message.request.retries = 3
    send_scheduled_message.max_retries = 3

    with patch(
        "app.tasks.messaging.run_async",
        side_effect=_run_async_raise(ExternalServiceError("timeout")),
    ), patch(
        "app.tasks.messaging.get_db_session", return_value=_db_session(db)
    ), patch("app.services.dlq.service.DLQService.add_to_dlq") as add_to_dlq:
        send_scheduled_message.run(str(message.id))

    payload = add_to_dlq.call_args.kwargs["payload"]
    assert payload["flow_context"] == {"flow_type": "quiz"}
