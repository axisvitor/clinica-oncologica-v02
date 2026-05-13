"""M014/S01 webhook replay and idempotency fail-closed contract tests."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import httpx
import pytest
from fastapi import FastAPI

from app.core.database.async_engine import get_async_db
from app.integrations.wuzapi import webhook as wuzapi_webhook

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "wuzapi"
SECRET = "m014-s01-webhook-secret"


def _settings(
    *,
    hmac_enabled: bool = True,
    secret: str | None = SECRET,
    timestamp_required: bool = False,
    max_timestamp_age_seconds: int = 300,
):
    return SimpleNamespace(
        WHATSAPP_WEBHOOK_HMAC_ENABLED=hmac_enabled,
        WHATSAPP_WUZAPI_WEBHOOK_SECRET=secret,
        WHATSAPP_WEBHOOK_TIMESTAMP_REQUIRED=timestamp_required,
        WHATSAPP_WEBHOOK_MAX_TIMESTAMP_AGE_SECONDS=max_timestamp_age_seconds,
    )


def _body(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _signature(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _message_payload(*, event_id: str = "MSG-1", text: str = "oi") -> dict:
    return {
        "type": "Message",
        "event": {
            "Info": {
                "ID": event_id,
                "Sender": "5511999999999@s.whatsapp.net",
            },
            "Message": {"Conversation": text},
        },
    }


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(wuzapi_webhook.router, prefix="/webhooks")

    async def _override_db():
        yield AsyncMock()

    app.dependency_overrides[get_async_db] = _override_db
    return app


@pytest.fixture
async def fake_redis():
    redis = fakeredis.aioredis.FakeRedis()
    yield redis
    await redis.flushall()
    await redis.close()


async def _post_wuzapi(
    client: httpx.AsyncClient,
    payload: dict,
    *,
    secret: str | None = SECRET,
    timestamp: int | str | None = None,
    signature: str | None = None,
    correlation_id: str = "corr-m014-s01",
) -> httpx.Response:
    body = _body(payload)
    headers = {
        "content-type": "application/json",
        "x-correlation-id": correlation_id,
    }
    if signature is None and secret is not None:
        signature = _signature(body, secret)
    if signature is not None:
        headers["x-hmac-signature"] = signature
    if timestamp is not None:
        headers["x-webhook-timestamp"] = str(timestamp)
    return await client.post("/webhooks/wuzapi", content=body, headers=headers)


@pytest.mark.asyncio
async def test_invalid_hmac_denies_before_idempotency_or_processing(app: FastAPI, caplog):
    payload = _message_payload(
        event_id="BAD-HMAC-1",
        text="patient@example.com reset-token-secret 5511999999999",
    )
    get_redis = AsyncMock()
    handle_message = AsyncMock()

    with patch.object(wuzapi_webhook, "settings", _settings()), patch.object(
        wuzapi_webhook, "get_async_redis_client", new=get_redis
    ), patch.object(wuzapi_webhook, "_handle_message", new=handle_message), caplog.at_level(
        logging.WARNING, logger="app.integrations.wuzapi.webhook"
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await _post_wuzapi(
                client,
                payload,
                signature="sha256=definitely-not-valid",
                correlation_id="corr-invalid-hmac",
            )

    assert response.status_code == 403, response.text
    assert get_redis.await_count == 0
    handle_message.assert_not_awaited()

    denial_records = [
        record
        for record in caplog.records
        if getattr(record, "event_type", None) == "wuzapi_webhook_denied"
    ]
    assert len(denial_records) == 1
    record = denial_records[0]
    assert record.reason == "invalid_hmac_signature"
    assert record.path == "/webhooks/wuzapi"
    assert record.method == "POST"
    assert record.correlation_id == "corr-invalid-hmac"
    assert record.webhook_event_type == "unknown"
    assert isinstance(record.client_identity_hash, str)

    log_text = caplog.text
    assert "patient@example.com" not in log_text
    assert "reset-token-secret" not in log_text
    assert "5511999999999" not in log_text
    assert SECRET not in log_text
    assert "definitely-not-valid" not in log_text


@pytest.mark.asyncio
async def test_hmac_enabled_missing_secret_denies_before_parsing_or_processing(app: FastAPI):
    get_redis = AsyncMock()
    handle_message = AsyncMock()

    with patch.object(
        wuzapi_webhook,
        "settings",
        _settings(hmac_enabled=True, secret=""),
    ), patch.object(wuzapi_webhook, "get_async_redis_client", new=get_redis), patch.object(
        wuzapi_webhook, "_handle_message", new=handle_message
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/webhooks/wuzapi",
                content=b"not-json-and-must-not-be-parsed",
                headers={"content-type": "application/json"},
            )

    assert response.status_code == 503, response.text
    assert get_redis.await_count == 0
    handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_required_timestamp_denies_before_idempotency_or_processing(app: FastAPI):
    payload = _message_payload(event_id="STALE-1")
    stale_timestamp = int(time.time()) - 600
    get_redis = AsyncMock()
    handle_message = AsyncMock()

    with patch.object(
        wuzapi_webhook,
        "settings",
        _settings(timestamp_required=True, max_timestamp_age_seconds=30),
    ), patch.object(wuzapi_webhook, "get_async_redis_client", new=get_redis), patch.object(
        wuzapi_webhook, "_handle_message", new=handle_message
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await _post_wuzapi(
                client,
                payload,
                timestamp=stale_timestamp,
            )

    assert response.status_code == 403, response.text
    assert get_redis.await_count == 0
    handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_event_denies_409_before_second_processing(app: FastAPI, fake_redis):
    payload = _message_payload(event_id="DUP-M014-1")
    handle_message = AsyncMock(return_value={"status": "processed"})

    with patch.object(
        wuzapi_webhook,
        "settings",
        _settings(hmac_enabled=False, secret=None),
    ), patch.object(
        wuzapi_webhook, "get_async_redis_client", new=AsyncMock(return_value=fake_redis)
    ), patch.object(wuzapi_webhook, "_handle_message", new=handle_message):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            first = await _post_wuzapi(client, payload, secret=None)
            second = await _post_wuzapi(client, payload, secret=None)

    assert first.status_code == 200, first.text
    assert first.json()["status"] == "processed"
    assert second.status_code == 409, second.text
    assert second.json()["detail"] == "Duplicate webhook event"
    assert handle_message.await_count == 1


@pytest.mark.asyncio
async def test_idempotency_backend_failure_denies_503_before_processing(app: FastAPI):
    payload = _message_payload(event_id="REDIS-DOWN-1")
    handle_message = AsyncMock(return_value={"status": "processed"})

    with patch.object(
        wuzapi_webhook,
        "settings",
        _settings(hmac_enabled=False, secret=None),
    ), patch.object(
        wuzapi_webhook,
        "get_async_redis_client",
        new=AsyncMock(side_effect=ConnectionError("redis unavailable")),
    ), patch.object(wuzapi_webhook, "_handle_message", new=handle_message):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await _post_wuzapi(client, payload, secret=None)

    assert response.status_code == 503, response.text
    assert response.json()["detail"] == "Webhook idempotency unavailable"
    handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_valid_signed_fixture_with_fresh_timestamp_still_passes(app: FastAPI, fake_redis):
    payload = json.loads((FIXTURE_DIR / "presence_update.json").read_text())

    with patch.object(
        wuzapi_webhook,
        "settings",
        _settings(timestamp_required=True),
    ), patch.object(
        wuzapi_webhook, "get_async_redis_client", new=AsyncMock(return_value=fake_redis)
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await _post_wuzapi(
                client,
                payload,
                timestamp=int(time.time()),
            )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ignored"
    assert response.json()["type"] == "PresenceUpdate"
