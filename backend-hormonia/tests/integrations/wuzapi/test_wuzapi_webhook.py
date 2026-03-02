import hashlib
import hmac
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI

from app.core.database.async_engine import get_async_db
from app.integrations.wuzapi.webhook import router


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def _override_db():
        yield AsyncMock()

    app.dependency_overrides[get_async_db] = _override_db
    return app


@pytest.fixture
def secret() -> str:
    return "test-webhook-secret"


def compute_hmac(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_valid_hmac_returns_200(app: FastAPI, secret: str):
    body = b'{"type":"Message","event":{"Info":{"ID":"X1"}}}'
    signature = compute_hmac(body, secret)

    with patch("app.integrations.wuzapi.webhook.os.environ.get", return_value=secret):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/webhooks/wuzapi",
                content=body,
                headers={"x-hmac-signature": signature, "content-type": "application/json"},
            )

    assert response.status_code == 200
    assert response.json()["status"] == "received"


@pytest.mark.asyncio
async def test_invalid_hmac_returns_403(app: FastAPI, secret: str):
    body = b'{"type":"Message","event":{"Info":{"ID":"X2"}}}'

    with patch("app.integrations.wuzapi.webhook.os.environ.get", return_value=secret):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/webhooks/wuzapi",
                content=body,
                headers={"x-hmac-signature": "bad-signature", "content-type": "application/json"},
            )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_missing_hmac_header_returns_403(app: FastAPI, secret: str):
    body = b'{"type":"Message","event":{"Info":{"ID":"X3"}}}'

    with patch("app.integrations.wuzapi.webhook.os.environ.get", return_value=secret):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/webhooks/wuzapi",
                content=body,
                headers={"content-type": "application/json"},
            )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_no_secret_configured_skips_hmac(app: FastAPI):
    body = b'{"type":"Message","event":{"Info":{"ID":"X4"}}}'

    with patch("app.integrations.wuzapi.webhook.os.environ.get", return_value=None):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/webhooks/wuzapi",
                content=body,
                headers={"content-type": "application/json"},
            )

    assert response.status_code == 200
    assert response.json()["status"] == "received"


@pytest.mark.asyncio
async def test_invalid_json_returns_400(app: FastAPI, secret: str):
    body = b'{"type": '
    signature = compute_hmac(body, secret)

    with patch("app.integrations.wuzapi.webhook.os.environ.get", return_value=secret):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/webhooks/wuzapi",
                content=body,
                headers={"x-hmac-signature": signature, "content-type": "application/json"},
            )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_message_event_routes_to_handler(app: FastAPI, secret: str):
    body = b'{"type":"Message","event":{"Info":{"ID":"X5"}}}'
    signature = compute_hmac(body, secret)

    with patch("app.integrations.wuzapi.webhook.os.environ.get", return_value=secret):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/webhooks/wuzapi",
                content=body,
                headers={"x-hmac-signature": signature, "content-type": "application/json"},
            )

    assert response.status_code == 200
    assert response.json() == {"status": "received", "message_id": "X5", "type": "Message"}


@pytest.mark.asyncio
async def test_receipt_event_routes_to_handler(app: FastAPI, secret: str):
    body = b'{"type":"ReadReceipt","event":{"Info":{"ID":"X6"},"Receipt":{"Type":"read"}}}'
    signature = compute_hmac(body, secret)

    with patch("app.integrations.wuzapi.webhook.os.environ.get", return_value=secret):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/webhooks/wuzapi",
                content=body,
                headers={"x-hmac-signature": signature, "content-type": "application/json"},
            )

    assert response.status_code == 200
    assert response.json()["status"] == "received"
    assert response.json()["type"] == "ReadReceipt"


@pytest.mark.asyncio
async def test_unknown_event_type_returns_ignored(app: FastAPI, secret: str):
    body = b'{"type":"FooBar","event":{"Info":{"ID":"X7"}}}'
    signature = compute_hmac(body, secret)

    with patch("app.integrations.wuzapi.webhook.os.environ.get", return_value=secret):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/webhooks/wuzapi",
                content=body,
                headers={"x-hmac-signature": signature, "content-type": "application/json"},
            )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "type": "FooBar"}


@pytest.mark.asyncio
async def test_raw_body_read_before_hmac(app: FastAPI, secret: str):
    body = b'{ "type" : "Message" , "event" : { "Info" : { "ID" : "X8" } } }'
    signature = compute_hmac(body, secret)

    with patch("app.integrations.wuzapi.webhook.os.environ.get", return_value=secret):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/webhooks/wuzapi",
                content=body,
                headers={"x-hmac-signature": signature, "content-type": "application/json"},
            )

    assert response.status_code == 200
    assert response.json()["message_id"] == "X8"


@pytest.mark.asyncio
async def test_missing_event_id_uses_hash_fallback(app: FastAPI, secret: str):
    body = b'{"type":"Message","event":{"Info":{},"Message":{"Conversation":"hi"}}}'
    signature = compute_hmac(body, secret)

    with patch("app.integrations.wuzapi.webhook.os.environ.get", return_value=secret):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/webhooks/wuzapi",
                content=body,
                headers={"x-hmac-signature": signature, "content-type": "application/json"},
            )

    assert response.status_code == 200
    assert response.json()["status"] == "received"
    assert len(response.json()["message_id"]) == 32
