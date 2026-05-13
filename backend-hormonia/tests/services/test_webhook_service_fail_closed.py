from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.v2.webhooks import WebhookInboundEvent
from app.services.webhook_service import WebhookService


@pytest.mark.asyncio
async def test_check_idempotency_fails_closed_when_backends_error():
    db = MagicMock()
    db.execute.side_effect = RuntimeError("db unavailable")
    service = WebhookService(db)

    redis_client = AsyncMock()
    redis_client.set.side_effect = RuntimeError("redis unavailable")

    with patch.object(
        service, "_get_idempotency_service", new=AsyncMock(return_value=None)
    ), patch.object(
        service, "_get_redis", new=AsyncMock(return_value=redis_client)
    ), patch(
        "app.services.webhook_service.logger"
    ) as mock_logger:
        should_process = await service.check_idempotency(
            webhook_id="evt-123", event_type="message.received"
        )

    assert should_process is False
    assert mock_logger.error.called
    assert "fail-closed" in mock_logger.error.call_args.args[0]
    assert mock_logger.error.call_args.kwargs["extra"]["webhook_id_hash"].startswith(
        "webhook_id_"
    )


@pytest.mark.asyncio
async def test_process_inbound_webhook_duplicate_raises_409_before_processor():
    service = WebhookService(MagicMock())
    event = WebhookInboundEvent(
        event="message.received",
        data={"message_id": "msg-1", "from": "+5511999999999", "text": "oi"},
    )

    with patch.object(
        service, "check_idempotency", new=AsyncMock(return_value=False)
    ), patch("app.services.webhook_service.WebhookProcessor") as processor_cls:
        with pytest.raises(HTTPException) as exc_info:
            await service.process_inbound_webhook(
                event,
                verification={"webhook_id": "evt-duplicate"},
            )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Duplicate webhook event"
    processor_cls.assert_not_called()


@pytest.mark.asyncio
async def test_process_inbound_webhook_idempotency_infra_failure_raises_503_before_processor():
    db = MagicMock()
    db.execute.side_effect = RuntimeError("db unavailable")
    service = WebhookService(db)
    event = WebhookInboundEvent(
        event="message.received",
        data={"message_id": "msg-2", "from": "+5511888888888", "text": "oi"},
    )

    redis_client = AsyncMock()
    redis_client.set.side_effect = RuntimeError("redis unavailable")

    with patch.object(
        service, "_get_idempotency_service", new=AsyncMock(return_value=None)
    ), patch.object(
        service, "_get_redis", new=AsyncMock(return_value=redis_client)
    ), patch("app.services.webhook_service.WebhookProcessor") as processor_cls:
        with pytest.raises(HTTPException) as exc_info:
            await service.process_inbound_webhook(
                event,
                verification={"webhook_id": "evt-infra"},
            )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Webhook idempotency unavailable"
    processor_cls.assert_not_called()
