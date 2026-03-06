from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from starlette.requests import Request

from app.integrations.wuzapi.webhook import wuzapi_webhook
from app.utils.structured_logger import correlation_id as correlation_id_var


def _build_request(
    payload: dict[str, object],
    *,
    correlation_id: str | None = None,
) -> Request:
    body = json.dumps(payload).encode("utf-8")
    headers = [(b"content-type", b"application/json")]
    if correlation_id is not None:
        headers.append((b"x-correlation-id", correlation_id.encode("utf-8")))

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/webhooks/wuzapi",
        "headers": headers,
    }
    return Request(scope, receive)


def _message_payload(event_id: str) -> dict[str, object]:
    return {
        "type": "Message",
        "event": {
            "Info": {"ID": event_id, "Sender": "5511999999999@s.whatsapp.net"},
            "Message": {"Conversation": "oi"},
        },
    }


@pytest.fixture(autouse=True)
def clear_correlation_context() -> None:
    correlation_id_var.set("")


@pytest.mark.asyncio
async def test_wuzapi_webhook_uses_incoming_correlation_id_header() -> None:
    request = _build_request(_message_payload("CID-HEADER-1"), correlation_id="cid-header")
    db = AsyncMock()
    message = SimpleNamespace(
        is_lid=False,
        text="oi",
        phone="5511999999999",
        message_id="CID-HEADER-1",
    )

    with (
        patch(
            "app.integrations.wuzapi.webhook.get_async_redis_client",
            new=AsyncMock(return_value=AsyncMock()),
        ),
        patch(
            "app.integrations.wuzapi.webhook.AtomicWebhookIdempotency.try_acquire",
            new=AsyncMock(return_value=(True, "acquired")),
        ),
        patch(
            "app.integrations.wuzapi.webhook.WuzAPIMessageExtractor.extract_message",
            return_value=message,
        ),
    ):
        result = await wuzapi_webhook(request, db=db)

    assert result["correlation_id"] == "cid-header"
    assert correlation_id_var.get() == "cid-header"


@pytest.mark.asyncio
async def test_wuzapi_webhook_generates_correlation_id_when_missing_header() -> None:
    request = _build_request(_message_payload("CID-GENERATED-1"))
    db = AsyncMock()
    message = SimpleNamespace(
        is_lid=False,
        text="oi",
        phone="5511999999999",
        message_id="CID-GENERATED-1",
    )
    generated_uuid = UUID("12345678-1234-5678-1234-567812345678")

    with (
        patch(
            "app.integrations.wuzapi.webhook.get_async_redis_client",
            new=AsyncMock(return_value=AsyncMock()),
        ),
        patch(
            "app.integrations.wuzapi.webhook.AtomicWebhookIdempotency.try_acquire",
            new=AsyncMock(return_value=(True, "acquired")),
        ),
        patch(
            "app.integrations.wuzapi.webhook.WuzAPIMessageExtractor.extract_message",
            return_value=message,
        ),
        patch(
            "app.integrations.wuzapi.webhook.uuid4",
            return_value=generated_uuid,
        ),
    ):
        result = await wuzapi_webhook(request, db=db)

    assert result["correlation_id"] == str(generated_uuid)
    assert correlation_id_var.get() == str(generated_uuid)
