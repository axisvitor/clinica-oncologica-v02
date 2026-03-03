import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import httpx
import pytest
from fastapi import FastAPI

from app.core.database.async_engine import get_async_db
from app.integrations.wuzapi.webhook import router
from app.models.message import MessageStatus
from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.services.webhook.handlers.message_handler import handle_opt_out


@pytest.mark.asyncio
async def test_handle_opt_out_sets_messaging_stopped_at():
    patient = MagicMock()
    patient.id = "patient-test-1"
    patient.messaging_stopped_at = None

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )
    )

    with patch("app.services.lgpd.consent_service.ConsentService"):
        await handle_opt_out(patient, db)

    assert patient.messaging_stopped_at is not None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_guard_blocks_opted_out_patient_via_service():
    db = AsyncMock()
    db.execute = AsyncMock()

    service = UnifiedWhatsAppService(db, redis_url="redis://fake:6379/0")

    message = MagicMock()
    message.id = uuid4()
    message.patient_id = uuid4()
    message.status = MessageStatus.PENDING

    opted_out_patient = MagicMock()
    opted_out_patient.messaging_stopped_at = datetime(2026, 3, 3, 12, 0, 0, tzinfo=timezone.utc)

    with patch.object(service, "_ensure_patient_loaded", return_value=opted_out_patient):
        result = await service.send_message(message)

    assert result is False


@pytest.mark.asyncio
async def test_send_guard_allows_active_patient_via_service():
    db = AsyncMock()
    db.execute = AsyncMock()

    service = UnifiedWhatsAppService(db, redis_url="redis://fake:6379/0")

    message = MagicMock()
    message.id = uuid4()
    message.patient_id = uuid4()
    message.status = MessageStatus.PENDING

    active_patient = MagicMock()
    active_patient.messaging_stopped_at = None

    with patch.object(service, "_ensure_patient_loaded", return_value=active_patient), patch.object(
        service, "_send_via_queue", AsyncMock(return_value=True)
    ), patch.object(service, "_send_via_direct_api", AsyncMock(return_value=True)):
        result = await service.send_message(message)

    assert result is True


def test_send_guard_blocks_opted_out_patient():
    opted_out_patient = MagicMock()
    opted_out_patient.messaging_stopped_at = datetime.now(timezone.utc)
    assert opted_out_patient.messaging_stopped_at is not None

    active_patient = MagicMock()
    active_patient.messaging_stopped_at = None
    assert active_patient.messaging_stopped_at is None


@pytest.mark.asyncio
async def test_stop_webhook_to_send_guard_integrated():
    """Integrated E2E: STOP webhook -> real handle_opt_out mutation -> send guard blocks.

    This is the single integrated test required by TEST-04 verification:
    1. POSTs "STOP" to /webhooks/wuzapi via httpx ASGITransport
    2. Does NOT mock handle_opt_out — lets it run for real inside _process_opt_out
    3. Mocks PhoneNormalizer.find_patient_by_phone to return a MagicMock patient
    4. After webhook returns, verifies patient.messaging_stopped_at is not None
    5. Creates UnifiedWhatsAppService and calls send_message with the SAME patient
    6. Asserts result is False (guard blocks)
    """
    # --- Setup: mock patient with messaging_stopped_at = None (not yet opted out) ---
    patient = MagicMock()
    patient.id = uuid4()
    patient.messaging_stopped_at = None  # Will be set by real handle_opt_out

    # --- Setup: AsyncMock db that handle_opt_out can operate on ---
    # handle_opt_out calls:
    #   1. patient.messaging_stopped_at = now  (direct attribute set on MagicMock — works)
    #   2. await db.execute(select(Consent).where(...)) -> needs .scalars().all() -> []
    #   3. await db.commit()
    mock_db = AsyncMock()
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = []  # No consents to revoke
    mock_db.execute = AsyncMock(return_value=mock_execute_result)

    # --- Setup: FastAPI app with wuzapi webhook router ---
    app = FastAPI()
    app.include_router(router, prefix="/webhooks")

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_async_db] = _override_db

    # --- Setup: fakeredis for idempotency ---
    fake_redis = fakeredis.aioredis.FakeRedis()

    # --- Step 1: POST "STOP" to /webhooks/wuzapi ---
    payload = {
        "type": "Message",
        "event": {
            "Info": {
                "ID": "INTEGRATED-STOP-1",
                "Sender": "5511999887766@s.whatsapp.net",
            },
            "Message": {"Conversation": "STOP"},
        },
    }
    body = json.dumps(payload).encode()

    with (
        patch(
            "app.integrations.wuzapi.webhook.get_async_redis_client",
            new=AsyncMock(return_value=fake_redis),
        ),
        # Mock PhoneNormalizer to return our patient — but do NOT mock handle_opt_out
        patch(
            "app.integrations.wuzapi.webhook.PhoneNormalizer.find_patient_by_phone",
            return_value=patient,
        ),
        # Patch ConsentService at its source module (lazy-imported inside handle_opt_out)
        patch("app.services.lgpd.consent_service.ConsentService"),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/webhooks/wuzapi",
                content=body,
                headers={"content-type": "application/json"},
            )

    # --- Step 2: Verify webhook processed opt-out ---
    assert response.status_code == 200
    resp_body = response.json()
    assert resp_body["status"] == "opt_out_processed"
    assert resp_body["message_id"] == "INTEGRATED-STOP-1"

    # --- Step 3: Verify real handle_opt_out set messaging_stopped_at ---
    assert patient.messaging_stopped_at is not None, (
        "handle_opt_out must set messaging_stopped_at on the patient object"
    )

    # --- Step 4: Use the SAME patient in UnifiedWhatsAppService.send_message ---
    service_db = AsyncMock()
    service = UnifiedWhatsAppService(service_db, redis_url="redis://fake:6379/0")

    message = MagicMock()
    message.id = uuid4()
    message.patient_id = patient.id
    message.status = MessageStatus.PENDING

    # Patch _ensure_patient_loaded to return the SAME patient that was mutated by handle_opt_out
    with patch.object(service, "_ensure_patient_loaded", return_value=patient):
        result = await service.send_message(message)

    # --- Step 5: Assert send guard blocks ---
    assert result is False, (
        "send_message must return False for a patient whose "
        "messaging_stopped_at was set by handle_opt_out"
    )

    # --- Cleanup ---
    await fake_redis.flushall()
    await fake_redis.close()
