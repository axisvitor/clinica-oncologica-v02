"""
Focused regression tests for WhatsApp queue batching and webhook hardening.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks

from app.config import settings
from app.integrations.whatsapp.api import webhooks as webhook_module
from app.integrations.whatsapp.models.message import MessageStatus, WebhookPayload
from app.integrations.whatsapp.services.message_service import (
    MessageQueue,
    WhatsAppMessageService,
)


@pytest.mark.asyncio
async def test_process_queue_batch_processes_and_retries_failed_messages():
    queue = MessageQueue(redis_url="redis://localhost:6379/0")
    queue.dequeue_message = AsyncMock(
        side_effect=[
            {"id": "evt-1", "data": {"message_id": "m-1", "action": "send_message"}},
            {"id": "evt-2", "data": {"message_id": "m-2", "action": "send_message"}},
            None,
        ]
    )
    queue.retry_message = AsyncMock(return_value=True)
    queue.get_queue_stats = AsyncMock(
        return_value={
            "pending": 3,
            "scheduled": 1,
            "retry_scheduled": 2,
            "dead_letter": 0,
        }
    )

    service = WhatsAppMessageService(
        evolution_client=AsyncMock(),
        db_session=AsyncMock(),
        message_queue=queue,
    )

    async def _process(payload):
        if payload["id"] == "evt-2":
            raise RuntimeError("processing error")

    service._process_message = AsyncMock(side_effect=_process)

    result = await service.process_queue_batch(max_messages=10)

    assert result["processed"] == 1
    assert result["failed"] == 1
    assert result["retried"] == 1
    assert result["queue_pending"] == 3
    assert result["queue_scheduled"] == 1
    assert result["queue_retry_scheduled"] == 2
    assert result["queue_dead_letter"] == 0


@pytest.mark.asyncio
async def test_process_webhook_event_propagates_handler_failures(monkeypatch):
    async def _boom(*_args, **_kwargs):
        raise RuntimeError("handler failed")

    monkeypatch.setattr(webhook_module, "handle_message_upsert", _boom)

    payload = WebhookPayload(
        instance="test-instance",
        event="MESSAGES_UPSERT",
        data={"key": {"id": "msg-123"}},
    )

    with pytest.raises(RuntimeError, match="handler failed"):
        await webhook_module.process_webhook_event(payload, BackgroundTasks(), None)


def test_get_client_ip_respects_proxy_trust_flag(monkeypatch):
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.10, 10.0.0.1", "x-real-ip": "198.51.100.9"},
        client=SimpleNamespace(host="127.0.0.1"),
    )

    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_TRUST_PROXY_HEADERS", False)
    assert webhook_module._get_client_ip(request) == "127.0.0.1"

    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_TRUST_PROXY_HEADERS", True)
    assert webhook_module._get_client_ip(request) == "203.0.113.10"


@pytest.mark.asyncio
async def test_handle_send_message_skips_ambiguous_candidates_without_commit():
    class _ScalarResult:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class _Scalars:
        def __init__(self, values):
            self._values = values

        def all(self):
            return self._values

    class _ListResult:
        def __init__(self, values):
            self._values = values

        def scalars(self):
            return _Scalars(self._values)

    class _FakeDB:
        def __init__(self, candidates):
            self._candidates = candidates
            self._call_count = 0
            self.commit_calls = 0

        def execute(self, _stmt):
            self._call_count += 1
            if self._call_count == 1:
                return _ScalarResult(None)  # existing external_id check
            return _ListResult(self._candidates)  # candidate lookup

        def commit(self):
            self.commit_calls += 1

    created_at = datetime(2026, 1, 1, 12, 0, 0)
    candidate_a = SimpleNamespace(
        id="msg-a",
        created_at=created_at,
        external_id=None,
        status=MessageStatus.PENDING,
        sent_at=None,
        updated_at=None,
    )
    candidate_b = SimpleNamespace(
        id="msg-b",
        created_at=created_at,
        external_id=None,
        status=MessageStatus.PENDING,
        sent_at=None,
        updated_at=None,
    )

    db = _FakeDB([candidate_a, candidate_b])
    payload = {
        "key": {
            "id": "evo-123",
            "remoteJid": "5511999999999@s.whatsapp.net",
        },
        "messageTimestamp": 1735743600,  # 2026-01-01 12:00:00-03
    }

    await webhook_module.handle_send_message("test-instance", payload, db)

    assert db.commit_calls == 0
    assert candidate_a.external_id is None
    assert candidate_b.external_id is None


@pytest.mark.asyncio
async def test_handle_contact_upsert_rolls_back_and_raises_on_db_error():
    class _FailingDB:
        def execute(self, _stmt):
            raise RuntimeError("db boom")

        def rollback(self):
            self.rolled_back = True

    db = _FailingDB()
    db.rolled_back = False

    with pytest.raises(RuntimeError, match="db boom"):
        await webhook_module.handle_contact_upsert(
            "test-instance",
            {"id": "5511999999999@s.whatsapp.net", "pushName": "Test"},
            db,
        )

    assert db.rolled_back is True
