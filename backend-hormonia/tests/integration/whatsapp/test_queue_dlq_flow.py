"""
Integration tests for WhatsApp queue manager and DLQ flow.
"""

import asyncio
import json
from datetime import datetime, timezone

import pytest
from unittest.mock import AsyncMock

from app.integrations.whatsapp.queue.manager import QueueManager
from app.integrations.whatsapp.queue.schemas import MessageRequest, MessageResponse


from app.utils.timezone import now_sao_paulo
class FakeRedis:
    def __init__(self):
        self.lists = {}
        self.values = {}
        self.zsets = {}

    async def lpush(self, key, value):
        self.lists.setdefault(key, [])
        self.lists[key].insert(0, value)
        return len(self.lists[key])

    async def rpoplpush(self, source, dest):
        if source not in self.lists or not self.lists[source]:
            return None
        value = self.lists[source].pop()
        self.lists.setdefault(dest, []).insert(0, value)
        return value

    async def lrem(self, key, count, value):
        if key not in self.lists:
            return 0
        removed = 0
        new_list = []
        for item in self.lists[key]:
            if (count == 0 or removed < count) and item == value:
                removed += 1
                continue
            new_list.append(item)
        self.lists[key] = new_list
        return removed

    async def lrange(self, key, start, end):
        items = self.lists.get(key, [])
        if end == -1:
            end = len(items) - 1
        return items[start : end + 1]

    async def llen(self, key):
        return len(self.lists.get(key, []))

    async def set(self, key, value, ex=None):
        self.values[key] = value
        return True

    async def exists(self, key):
        return 1 if key in self.values else 0

    async def eval(self, script, numkeys, queue_key, processing_key, processing_started_at):
        moved = await self.rpoplpush(queue_key, processing_key)
        if moved is None:
            return None

        payload = json.loads(moved)
        payload["processing_started_at"] = processing_started_at
        updated = json.dumps(payload, default=str)
        self.lists[processing_key][0] = updated
        return updated

    async def zadd(self, key, mapping):
        zset = self.zsets.setdefault(key, {})
        for member, score in mapping.items():
            zset[member] = float(score)
        return len(mapping)

    async def zpopmin(self, key, count=1):
        zset = self.zsets.get(key, {})
        if not zset:
            return []

        ordered = sorted(zset.items(), key=lambda item: item[1])[:count]
        for member, _ in ordered:
            zset.pop(member, None)
        return ordered


async def _wait_for_queue_size(redis_client: FakeRedis, key: str, expected: int, attempts: int = 50):
    for _ in range(attempts):
        if await redis_client.llen(key) >= expected:
            return
        await asyncio.sleep(0)
    pytest.fail(f"Queue {key} did not reach size {expected}")


@pytest.mark.asyncio
async def test_fifo_processing_order(monkeypatch):
    redis_client = FakeRedis()
    processed = []

    async def sender(request: MessageRequest) -> MessageResponse:
        processed.append(request.message_id)
        return MessageResponse(
            success=True,
            message_id=request.message_id,
            timestamp=now_sao_paulo(),
            instance_name=request.instance_name,
        )

    manager = QueueManager(
        default_instance="primary",
        redis_client=redis_client,
        message_sender=sender,
    )

    for idx in range(10):
        await manager.queue_message(
            MessageRequest(
                instance_name="primary",
                message_id=f"msg-{idx}",
                to="5511999999999",
                text="hello",
            )
        )

    batch = await manager._dequeue_batch("primary", 10)
    for item in batch:
        await manager._process_payload("primary", item)

    assert processed == [f"msg-{i}" for i in range(10)]


@pytest.mark.asyncio
async def test_retry_requeues_message(monkeypatch):
    redis_client = FakeRedis()

    async def sender(request: MessageRequest) -> MessageResponse:
        raise Exception("timeout")

    manager = QueueManager(
        default_instance="primary",
        redis_client=redis_client,
        message_sender=sender,
    )
    monkeypatch.setattr(manager, "_calculate_retry_backoff", lambda _: 0)

    await manager.queue_message(
        MessageRequest(
            instance_name="primary",
            message_id="msg-retry",
            to="5511999999999",
            text="hello",
        )
    )

    batch = await manager._dequeue_batch("primary", 1)
    await manager._process_payload("primary", batch[0])
    await manager._drain_due_retries("primary")

    assert await redis_client.llen("whatsapp:queue:primary") == 1


@pytest.mark.asyncio
async def test_dlq_after_max_retries(monkeypatch):
    redis_client = FakeRedis()

    async def sender(request: MessageRequest) -> MessageResponse:
        raise Exception("api_error")

    manager = QueueManager(
        default_instance="primary",
        redis_client=redis_client,
        message_sender=sender,
    )
    manager.dlq_handler = AsyncMock()
    monkeypatch.setattr(manager, "_calculate_retry_backoff", lambda _: 0)

    await manager.queue_message(
        MessageRequest(
            instance_name="primary",
            message_id="msg-dlq",
            to="5511999999999",
            text="hello",
            metadata={"patient_id": "00000000-0000-0000-0000-000000000001"},
        )
    )

    for attempt in range(3):
        await manager._drain_due_retries("primary")
        await _wait_for_queue_size(redis_client, "whatsapp:queue:primary", 1)
        batch = await manager._dequeue_batch("primary", 1)
        assert batch, f"Expected payload on retry attempt {attempt + 1}"
        await manager._process_payload("primary", batch[0])

    assert await redis_client.llen("whatsapp:failed:primary") == 1
    assert manager.dlq_handler.route_to_dlq.called


@pytest.mark.asyncio
async def test_manual_requeue_from_failed_payload():
    redis_client = FakeRedis()
    manager = QueueManager(
        default_instance="primary",
        redis_client=redis_client,
    )

    failed_payload = {
        "message_id": "msg-requeue",
        "instance_name": "primary",
        "request": {
            "instance_name": "primary",
            "message_id": "msg-requeue",
            "to": "5511999999999",
            "text": "hello",
            "message_type": "text",
            "retry_count": 0,
        },
        "retry_count": 3,
        "retry_timestamps": [],
        "created_at": now_sao_paulo().isoformat(),
    }

    await redis_client.lpush(
        "whatsapp:failed:primary", json.dumps(failed_payload, default=str)
    )

    failed_entries = await redis_client.lrange("whatsapp:failed:primary", 0, -1)
    payload = json.loads(failed_entries[0])
    await manager.queue_message(MessageRequest(**payload["request"]))

    assert await redis_client.llen("whatsapp:queue:primary") == 1
