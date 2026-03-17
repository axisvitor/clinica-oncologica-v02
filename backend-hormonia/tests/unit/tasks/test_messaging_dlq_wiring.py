"""DLQ wiring tests for Taskiq send_scheduled_message.

Taskiq migration: Imports from app.tasks.messaging_taskiq instead of app.tasks.messaging.
Task is async; tested via await task.fn(). Context provides retry count.
DLQ routing uses _route_to_dlq helper (sync DLQService under the hood).
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.exceptions import ExternalServiceError
from app.models.message import MessageStatus
from app.services.dlq.base import FlowMessageRetryConfig
from app.tasks.messaging_taskiq import send_scheduled_message


def _fake_context(retries: int = 0):
    """Build a minimal fake Taskiq context with retry labels."""
    ctx = MagicMock()
    ctx.message.labels = {"_retries": str(retries)}
    return ctx


def _mock_message(patient_phone: str = "+5511999000001", patient_deleted: bool = False):
    """Build a minimal Message with patient relationship for the async path."""
    msg = MagicMock()
    msg.id = uuid4()
    msg.patient_id = uuid4()
    msg.type = SimpleNamespace(value="text")
    msg.status = MessageStatus.SENDING
    msg.delivery_status = None
    msg.retry_count = 0
    msg.failure_reason = None
    msg.message_metadata = {"flow_context": {"flow_type": "quiz"}}

    patient = MagicMock()
    patient.phone = patient_phone
    patient.deleted_at = "2025-01-01" if patient_deleted else None
    msg.patient = patient

    return msg


@pytest.mark.asyncio
async def test_send_scheduled_message_routes_to_dlq_on_non_retriable_failure():
    """Non-retriable errors (no phone) route to DLQ via _route_to_dlq."""
    msg = _mock_message(patient_phone=None)
    msg.patient.phone = None

    db = AsyncMock()

    # Claim succeeds (1 row updated)
    claim_result = MagicMock()
    claim_result.rowcount = 1
    db.execute = AsyncMock(side_effect=[
        claim_result,  # claim UPDATE
        MagicMock(scalar_one_or_none=MagicMock(return_value=msg)),  # SELECT with patient
    ])

    with patch(
        "app.tasks.messaging_taskiq._route_to_dlq",
    ) as dlq_mock:
        result = await send_scheduled_message.fn(
            message_id=str(msg.id),
            db=db,
            context=_fake_context(0),
        )

    assert result["success"] is False
    dlq_mock.assert_called_once()


@pytest.mark.asyncio
async def test_send_scheduled_message_retries_on_transient_whatsapp_failure():
    """Transient WhatsApp errors raise to trigger SmartRetryMiddleware retry."""
    msg = _mock_message()

    db = AsyncMock()
    claim_result = MagicMock()
    claim_result.rowcount = 1
    db.execute = AsyncMock(side_effect=[
        claim_result,  # claim UPDATE
        MagicMock(scalar_one_or_none=MagicMock(return_value=msg)),  # SELECT with patient
    ])

    service = MagicMock()
    service.send_message = AsyncMock(side_effect=Exception("WhatsApp down"))

    with patch(
        "app.tasks.messaging_taskiq.create_unified_whatsapp_service",
        return_value=service,
    ):
        # retries=0 < max → task should raise to trigger retry
        with pytest.raises(Exception, match="WhatsApp down"):
            await send_scheduled_message.fn(
                message_id=str(msg.id),
                db=db,
                context=_fake_context(0),
            )


def test_flow_message_retry_config_values():
    cfg = FlowMessageRetryConfig()

    assert cfg.MAX_RETRY_ATTEMPTS == 3
    assert cfg.RETRY_DELAYS == [30, 120, 600]
