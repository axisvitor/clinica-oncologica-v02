from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    assert mock_logger.error.call_args.kwargs["extra"]["webhook_id"] == "evt-123"
