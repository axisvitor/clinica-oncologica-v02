import hashlib
import hmac
import json
from unittest.mock import ANY, AsyncMock, Mock, patch

import fakeredis.aioredis
import httpx
import pytest
from fastapi import FastAPI

from app.core.database.async_engine import get_async_db
from app.integrations.wuzapi.webhook import router


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/webhooks")

    async def _override_db():
        yield AsyncMock()

    app.dependency_overrides[get_async_db] = _override_db
    return app


@pytest.fixture
def secret() -> str:
    return "test-webhook-secret"


@pytest.fixture
async def fake_redis():
    redis = fakeredis.aioredis.FakeRedis()
    yield redis
    await redis.flushall()
    await redis.close()


def compute_hmac(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def message_payload(
    *,
    event_id: str | None = "MSG-1",
    sender: str = "5511999999999@s.whatsapp.net",
    text: str = "oi",
) -> dict:
    info = {"Sender": sender}
    if event_id is not None:
        info["ID"] = event_id
    return {
        "type": "Message",
        "event": {
            "Info": info,
            "Message": {"Conversation": text},
        },
    }


def receipt_payload(*, event_id: str = "RCT-1", sender: str = "5511999999999@s.whatsapp.net", receipt_type: str = "read") -> dict:
    return {
        "type": "ReadReceipt",
        "event": {
            "Info": {"ID": event_id, "Sender": sender},
            "Receipt": {"Type": receipt_type, "MessageIDs": [event_id]},
        },
    }


async def post_payload(client: httpx.AsyncClient, payload: dict, secret: str | None = None) -> httpx.Response:
    body = json.dumps(payload).encode()
    headers = {"content-type": "application/json"}
    if secret is not None:
        headers["x-hmac-signature"] = compute_hmac(body, secret)
    return await client.post("/webhooks/wuzapi", content=body, headers=headers)


@pytest.mark.asyncio
async def test_valid_hmac_returns_200(app: FastAPI, secret: str):
    payload = message_payload(event_id="X1")
    with patch("app.integrations.wuzapi.webhook.os.environ.get", return_value=secret):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload, secret=secret)
    assert response.status_code == 200


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
async def test_duplicate_event_returns_200_duplicate(app: FastAPI, fake_redis):
    payload = message_payload(event_id="DUP-1", text="hello")
    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            first = await post_payload(client, payload)
            second = await post_payload(client, payload)

    assert first.status_code == 200
    assert first.json()["status"] == "processed"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert second.json()["event_id"] == "DUP-1"


@pytest.mark.asyncio
async def test_missing_event_id_uses_body_hash(app: FastAPI, fake_redis):
    payload = message_payload(event_id=None, text="hello")
    body = json.dumps(payload).encode()
    expected_hash = hashlib.sha256(body).hexdigest()

    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            first = await client.post("/webhooks/wuzapi", content=body, headers={"content-type": "application/json"})
            second = await client.post("/webhooks/wuzapi", content=body, headers={"content-type": "application/json"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == {"status": "duplicate", "event_id": expected_hash}


@pytest.mark.asyncio
async def test_opt_out_stop_sets_messaging_stopped_at(app: FastAPI, fake_redis):
    payload = message_payload(event_id="STOP-1", text="STOP")
    patient = AsyncMock(id="patient-1")
    handle_opt_out_mock = AsyncMock()

    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)), patch(
        "app.integrations.wuzapi.webhook.PhoneNormalizer.find_patient_by_phone", return_value=patient
    ), patch("app.integrations.wuzapi.webhook.handle_opt_out", new=handle_opt_out_mock):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "opt_out_processed"
    assert response.json()["message_id"] == "STOP-1"
    handle_opt_out_mock.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["PARAR", "CANCELAR"])
async def test_opt_out_keywords_process_opt_out(app: FastAPI, fake_redis, text: str):
    payload = message_payload(event_id=f"OPT-{text}", text=text)
    patient = AsyncMock(id="patient-2")
    handle_opt_out_mock = AsyncMock()

    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)), patch(
        "app.integrations.wuzapi.webhook.PhoneNormalizer.find_patient_by_phone", return_value=patient
    ), patch("app.integrations.wuzapi.webhook.handle_opt_out", new=handle_opt_out_mock):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "opt_out_processed"
    handle_opt_out_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_opt_out_revokes_communication_consent(app: FastAPI, fake_redis):
    payload = message_payload(event_id="STOP-2", text="STOP")
    patient = AsyncMock(id="patient-3")
    handle_opt_out_mock = AsyncMock()

    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)), patch(
        "app.integrations.wuzapi.webhook.PhoneNormalizer.find_patient_by_phone", return_value=patient
    ), patch("app.integrations.wuzapi.webhook.handle_opt_out", new=handle_opt_out_mock):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "opt_out_processed"
    handle_opt_out_mock.assert_awaited_once_with(patient, ANY)


@pytest.mark.asyncio
async def test_opt_out_unknown_phone_logs_warning(app: FastAPI, fake_redis, caplog):
    payload = message_payload(event_id="STOP-UNKNOWN", text="STOP")

    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)), patch(
        "app.integrations.wuzapi.webhook.PhoneNormalizer.find_patient_by_phone", return_value=None
    ):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "opt_out_processed"
    assert "no patient found for phone" in caplog.text.lower()


@pytest.mark.asyncio
async def test_opt_out_uses_phone_hash_lookup(app: FastAPI, fake_redis):
    payload = message_payload(event_id="STOP-HASH", text="STOP")
    patient = AsyncMock(id="patient-4")
    find_mock = Mock(return_value=patient)

    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)), patch(
        "app.integrations.wuzapi.webhook.PhoneNormalizer.find_patient_by_phone", new=find_mock
    ), patch("app.integrations.wuzapi.webhook.handle_opt_out", new=AsyncMock()):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "opt_out_processed"
    find_mock.assert_called_once()


@pytest.mark.asyncio
async def test_lid_sender_routes_to_dlq(app: FastAPI, fake_redis):
    payload = message_payload(event_id="LID-1", sender="12345@lid", text="oi")
    send_to_dlq_mock = AsyncMock(return_value=True)

    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)), patch(
        "app.services.webhook_dlq.WebhookDLQ.send_to_dlq", new=send_to_dlq_mock
    ):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "queued_for_review"
    assert response.json()["reason"] == "lid_sender"
    kwargs = send_to_dlq_mock.await_args.kwargs
    assert kwargs["event_type"] == "wuzapi:lid_sender"


@pytest.mark.asyncio
async def test_lid_sender_not_dropped(app: FastAPI, fake_redis):
    payload = message_payload(event_id="LID-2", sender="99999@lid", text="PARAR")
    send_to_dlq_mock = AsyncMock(return_value=True)

    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)), patch(
        "app.services.webhook_dlq.WebhookDLQ.send_to_dlq", new=send_to_dlq_mock
    ):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "queued_for_review"
    send_to_dlq_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_receipt_maps_to_internal_status(app: FastAPI, fake_redis):
    payload = receipt_payload(event_id="RCP-READ", receipt_type="read")

    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    assert response.json()["internal_status"] == "read"


@pytest.mark.asyncio
async def test_receipt_delivered_empty_type(app: FastAPI, fake_redis):
    payload = receipt_payload(event_id="RCP-DELIVERED", receipt_type="")

    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    assert response.json()["internal_status"] == "delivered"


@pytest.mark.asyncio
async def test_idempotency_fail_open(app: FastAPI):
    payload = message_payload(event_id="FAIL-OPEN-1", text="hello")

    with patch(
        "app.integrations.wuzapi.webhook.get_async_redis_client",
        new=AsyncMock(side_effect=ConnectionError("redis down")),
    ):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "processed"
