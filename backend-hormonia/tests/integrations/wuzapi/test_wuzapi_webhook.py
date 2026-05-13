import hashlib
import hmac
import json
from pathlib import Path
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch

import fakeredis.aioredis
import httpx
import pytest
from fastapi import FastAPI

from app.core.database.async_engine import get_async_db
from app.integrations.wuzapi.webhook import router


FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "wuzapi"


def load_fixture(name: str) -> dict:
    """Load a captured WuzAPI JSON fixture by filename."""
    return json.loads((FIXTURE_DIR / name).read_text())


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/webhooks")

    async def _override_db():
        mock_db = AsyncMock()
        # run_sync bridge: call the function with a mock sync session
        mock_sync_session = MagicMock()
        async def _run_sync(fn):
            return fn(mock_sync_session)
        mock_db.run_sync = _run_sync
        yield mock_db

    app.dependency_overrides[get_async_db] = _override_db
    return app


@pytest.fixture
def secret() -> str:
    return "test-webhook-secret"


@pytest.fixture(autouse=True)
def _no_hmac_by_default():
    """Disable HMAC validation by default so tests without explicit HMAC work.

    Tests that need HMAC validation explicitly patch settings with their own secret.
    """
    mock_settings = MagicMock()
    mock_settings.WHATSAPP_WEBHOOK_HMAC_ENABLED = False
    mock_settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET = ""
    mock_settings.WHATSAPP_WEBHOOK_TIMESTAMP_REQUIRED = False
    mock_settings.WHATSAPP_WEBHOOK_MAX_TIMESTAMP_AGE_SECONDS = 300
    with patch("app.integrations.wuzapi.webhook.settings", mock_settings):
        yield


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
async def test_valid_hmac_returns_200(app: FastAPI, secret: str, fake_redis):
    payload = message_payload(event_id="X1")
    mock_settings = MagicMock()
    mock_settings.WHATSAPP_WEBHOOK_HMAC_ENABLED = True
    mock_settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET = secret
    mock_settings.WHATSAPP_WEBHOOK_TIMESTAMP_REQUIRED = False
    mock_settings.WHATSAPP_WEBHOOK_MAX_TIMESTAMP_AGE_SECONDS = 300
    with patch("app.integrations.wuzapi.webhook.settings", mock_settings), patch(
        "app.integrations.wuzapi.webhook.get_async_redis_client",
        new=AsyncMock(return_value=fake_redis),
    ):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload, secret=secret)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_invalid_hmac_returns_403(app: FastAPI, secret: str):
    body = b'{"type":"Message","event":{"Info":{"ID":"X2"}}}'
    mock_settings = MagicMock()
    mock_settings.WHATSAPP_WEBHOOK_HMAC_ENABLED = True
    mock_settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET = secret
    mock_settings.WHATSAPP_WEBHOOK_TIMESTAMP_REQUIRED = False
    mock_settings.WHATSAPP_WEBHOOK_MAX_TIMESTAMP_AGE_SECONDS = 300
    with patch("app.integrations.wuzapi.webhook.settings", mock_settings):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/webhooks/wuzapi",
                content=body,
                headers={"x-hmac-signature": "bad-signature", "content-type": "application/json"},
            )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unknown_event_type_returns_ignored(app: FastAPI, fake_redis):
    payload = {"type": "PresenceUpdate", "event": {"Info": {"ID": "UNK-1"}}}

    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert response.json()["type"] == "PresenceUpdate"


@pytest.mark.asyncio
async def test_missing_hmac_header_returns_403(app: FastAPI, secret: str):
    body = json.dumps({"type": "Message", "event": {"Info": {"ID": "HMAC-MISS-1"}}}).encode()

    mock_settings = MagicMock()
    mock_settings.WHATSAPP_WEBHOOK_HMAC_ENABLED = True
    mock_settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET = secret
    mock_settings.WHATSAPP_WEBHOOK_TIMESTAMP_REQUIRED = False
    mock_settings.WHATSAPP_WEBHOOK_MAX_TIMESTAMP_AGE_SECONDS = 300
    with patch("app.integrations.wuzapi.webhook.settings", mock_settings):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/webhooks/wuzapi",
                content=body,
                headers={"content-type": "application/json"},
            )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_event_returns_409_duplicate(app: FastAPI, fake_redis):
    payload = message_payload(event_id="DUP-1", text="hello")
    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            first = await post_payload(client, payload)
            second = await post_payload(client, payload)

    assert first.status_code == 200
    assert first.json()["status"] == "processed"
    assert second.status_code == 409
    assert second.json()["detail"] == "Duplicate webhook event"


@pytest.mark.asyncio
async def test_missing_event_id_uses_body_hash(app: FastAPI, fake_redis):
    payload = message_payload(event_id=None, text="hello")
    body = json.dumps(payload).encode()

    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            first = await client.post("/webhooks/wuzapi", content=body, headers={"content-type": "application/json"})
            second = await client.post("/webhooks/wuzapi", content=body, headers={"content-type": "application/json"})

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"] == "Duplicate webhook event"


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
async def test_idempotency_failure_returns_503(app: FastAPI):
    payload = message_payload(event_id="FAIL-CLOSED-1", text="hello")

    with patch(
        "app.integrations.wuzapi.webhook.get_async_redis_client",
        new=AsyncMock(side_effect=ConnectionError("redis down")),
    ):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)

    assert response.status_code == 503
    assert response.json()["detail"] == "Webhook idempotency unavailable"


@pytest.mark.asyncio
async def test_message_from_fixture_processes_successfully(app: FastAPI, fake_redis):
    """Webhook processes a captured WuzAPI Message fixture payload."""
    payload = load_fixture("message_inbound.json")
    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["message_id"] == "3EB0A618C4E77B6E5A3D"


@pytest.mark.asyncio
async def test_receipt_from_fixture_maps_status(app: FastAPI, fake_redis):
    """Webhook processes a captured WuzAPI ReadReceipt fixture payload."""
    payload = load_fixture("read_receipt.json")
    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["internal_status"] == "read"
    assert "3EB0A618C4E77B6E5A3D" in body["message_ids"]


@pytest.mark.asyncio
async def test_unknown_event_from_fixture_returns_ignored(app: FastAPI, fake_redis):
    """Webhook returns ignored for a captured PresenceUpdate fixture payload."""
    payload = load_fixture("presence_update.json")
    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ignored"
    assert body["type"] == "PresenceUpdate"


@pytest.mark.asyncio
async def test_message_routes_to_patient_flow_processing(app: FastAPI, fake_redis):
    """Normal inbound message finds patient and creates inbound message + flow response."""
    payload = message_payload(event_id="FLOW-1", text="Estou me sentindo bem")

    mock_patient = MagicMock()
    mock_patient.id = "patient-flow-1"

    mock_flow_state = MagicMock()
    mock_flow_state.id = "flow-state-1"
    mock_flow_state.flow_type = "onboarding"
    mock_flow_state.current_step = 3
    mock_flow_state.step_data = {
        "flow_kind": "onboarding",
        "current_flow_day": 5,
        "current_day_message_index": 2,
        "awaiting_response": True,
    }

    mock_message = MagicMock()
    mock_message.id = "msg-inbound-1"

    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)), \
         patch("app.integrations.wuzapi.webhook.PhoneNormalizer.find_patient_by_phone", return_value=mock_patient), \
         patch("app.integrations.wuzapi.webhook.FlowStateRepository") as mock_flow_repo_cls, \
         patch("app.integrations.wuzapi.webhook.PatientRepository"), \
         patch("app.domain.messaging.core.MessageService.process_inbound_message", return_value=mock_message), \
         patch("app.integrations.wuzapi.webhook.PatientFlowResponse") as mock_response_cls, \
         patch("app.integrations.wuzapi.webhook.flag_modified"), \
         patch("app.services.flow.sequential_message_handler.SequentialMessageHandler") as mock_handler_cls:

        mock_flow_repo_cls.return_value.get_active_flow.return_value = mock_flow_state
        mock_handler_instance = AsyncMock()
        mock_handler_instance.handle_response_and_continue = AsyncMock(return_value={"status": "waiting"})
        mock_handler_cls.return_value = mock_handler_instance

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["patient_id"] == "patient-flow-1"
    assert body["context"] == "flow"
    assert body["internal_message_id"] == "msg-inbound-1"


@pytest.mark.asyncio
async def test_message_patient_not_found_returns_skipped(app: FastAPI, fake_redis):
    """When patient is not found by phone, message is skipped."""
    payload = message_payload(event_id="NF-1", text="hello")

    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)), \
         patch("app.integrations.wuzapi.webhook.PhoneNormalizer.find_patient_by_phone", return_value=None):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "skipped"
    assert body["reason"] == "patient_not_found"


@pytest.mark.asyncio
async def test_message_no_active_flow_stores_as_general_chat(app: FastAPI, fake_redis):
    """Message for patient without active flow is stored as general_chat."""
    payload = message_payload(event_id="GC-1", text="pergunta geral")

    mock_patient = MagicMock()
    mock_patient.id = "patient-gc-1"

    mock_message = MagicMock()
    mock_message.id = "msg-gc-1"

    with patch("app.integrations.wuzapi.webhook.get_async_redis_client", new=AsyncMock(return_value=fake_redis)), \
         patch("app.integrations.wuzapi.webhook.PhoneNormalizer.find_patient_by_phone", return_value=mock_patient), \
         patch("app.integrations.wuzapi.webhook.FlowStateRepository") as mock_flow_repo_cls, \
         patch("app.integrations.wuzapi.webhook.PatientRepository"), \
         patch("app.domain.messaging.core.MessageService.process_inbound_message", return_value=mock_message):

        mock_flow_repo_cls.return_value.get_active_flow.return_value = None

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await post_payload(client, payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["context"] == "general_chat"
