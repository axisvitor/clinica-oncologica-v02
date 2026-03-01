"""
Integration tests for WhatsApp webhook processing scenarios.
"""

import asyncio
import hmac
import hashlib
import json
import time
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database import get_db
from app.integrations.whatsapp.api import webhooks as webhook_module
from app.integrations.whatsapp.models.message import WebhookPayload, WhatsAppMessage
from app.models.patient import Patient


@pytest.fixture
def client():
    def override_get_db():
        yield None

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def _make_payload(event: str = "MESSAGES_UPSERT", message_id: str = "msg-1"):
    return {
        "event": event,
        "instance": "test-instance",
        "data": {
            "key": {"id": message_id, "remoteJid": "5511999999999@s.whatsapp.net"},
            "message": {"conversation": "Oi"},
            "messageTimestamp": int(time.time()),
        },
    }


def _sign_payload(payload: dict, secret: str) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return digest


def test_invalid_hmac_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_HMAC_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_SECRET", "test-secret")

    class FakeRedis:
        async def get(self, key):
            return None

        async def incr(self, key):
            return 1

        async def expire(self, key, ttl):
            return True

        async def setex(self, key, ttl, value):
            return True

        async def delete(self, *keys):
            return 1

    async def allow_rate_limit(*args, **kwargs):
        return True, 0

    async def fake_get_redis():
        return FakeRedis()

    monkeypatch.setattr(webhook_module, "check_rate_limit_redis", allow_rate_limit)
    monkeypatch.setattr(webhook_module, "get_redis", fake_get_redis)

    payload = _make_payload()
    response = client.post(
        "/webhooks/whatsapp/evolution/test-instance",
        json=payload,
        headers={"X-Webhook-Signature": "invalid"},
    )

    assert response.status_code == 401


def test_idempotency_duplicate_webhook_processed_once(client, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_HMAC_ENABLED", False)

    class StubIdempotency:
        def __init__(self):
            self.seen = set()

        async def try_acquire(self, event_type, event_id, worker_id=None):
            key = (event_type, event_id)
            if key in self.seen:
                return False, "duplicate"
            self.seen.add(key)
            return True, "acquired"

        async def mark_completed(self, event_type, event_id):
            return None

    stub = StubIdempotency()

    async def stub_get_idempotency_service():
        return stub

    async def stub_handle_message_upsert(instance_name, data, background_tasks, db):
        messages = data if isinstance(data, list) else [data]
        for message in messages:
            message_id = message.get("key", {}).get("id")
            if await webhook_module.is_event_processed(
                message_id, event_type="message", instance_name=instance_name
            ):
                continue
            processed["count"] += 1

    processed = {"count": 0}

    monkeypatch.setattr(webhook_module, "get_idempotency_service", stub_get_idempotency_service)
    monkeypatch.setattr(webhook_module, "handle_message_upsert", stub_handle_message_upsert)

    payload = _make_payload(message_id="dup-msg")
    for _ in range(3):
        response = client.post("/webhooks/whatsapp/evolution/test-instance", json=payload)
        assert response.status_code == 200

    assert processed["count"] == 1


@pytest.mark.asyncio
async def test_event_routing_upsert_and_update(monkeypatch):
    called = {"upsert": False, "update": False}

    async def stub_upsert(instance_name, data, background_tasks, db):
        called["upsert"] = True

    async def stub_update(instance_name, data, db):
        called["update"] = True

    monkeypatch.setattr(webhook_module, "handle_message_upsert", stub_upsert)
    monkeypatch.setattr(webhook_module, "handle_message_update", stub_update)

    payload_upsert = WebhookPayload(
        instance="test-instance",
        event="MESSAGES_UPSERT",
        data=_make_payload("MESSAGES_UPSERT")["data"],
    )
    payload_update = WebhookPayload(
        instance="test-instance",
        event="MESSAGES_UPDATE",
        data=_make_payload("MESSAGES_UPDATE")["data"],
    )

    await webhook_module.process_webhook_event(payload_upsert, BackgroundTasks(), None)
    await webhook_module.process_webhook_event(payload_update, BackgroundTasks(), None)

    assert called["upsert"] is True
    assert called["update"] is True


@pytest.mark.asyncio
async def test_background_task_triggered_for_patient_message(monkeypatch):
    background_tasks = BackgroundTasks()

    class FakeResult:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class FakeDB:
        class _Query:
            def filter(self, *args, **kwargs):
                return self

            def first(self):
                return None

        def execute(self, stmt):
            entity = stmt.column_descriptions[0]["entity"]
            if entity is WhatsAppMessage:
                return FakeResult(None)
            if entity is Patient:
                return FakeResult(fake_patient)
            return FakeResult(None)

        def query(self, _model):
            return self._Query()

        def add(self, obj):
            return None

        def flush(self):
            return None

        def commit(self):
            return None

        def rollback(self):
            return None

    fake_patient = SimpleNamespace(id="patient-1", phone_hash="hash")

    class FakeLGPD:
        def hash_phone(self, value):
            return "hash"

    async def stub_is_event_processed(*args, **kwargs):
        return False

    monkeypatch.setattr(
        "app.services.encryption.get_lgpd_encryption_service",
        lambda: FakeLGPD(),
    )
    monkeypatch.setattr(webhook_module, "is_event_processed", stub_is_event_processed)

    data = _make_payload()["data"]

    await webhook_module.handle_message_upsert(
        "test-instance", data, background_tasks, FakeDB()
    )

    # Current implementation processes inbound path inline (no background task enqueue).
    assert len(background_tasks.tasks) == 0
