import asyncio
from uuid import uuid4

import fakeredis.aioredis
import pytest

import app.services.follow_up_system.message_deduplication_service as service_module
from app.monitoring.metrics import (
    follow_up_dedup_misses_total,
    follow_up_messages_deduplicated_total,
)
from app.services.follow_up_system.message_deduplication_service import (
    MessageDeduplicationService,
)


@pytest.fixture
async def fake_redis():
    redis = fakeredis.aioredis.FakeRedis()
    await redis.flushall()
    yield redis
    await redis.flushall()


@pytest.fixture
async def dedup_service(monkeypatch: pytest.MonkeyPatch, fake_redis):
    async def _get_redis():
        return fake_redis

    monkeypatch.setattr(service_module, "get_async_redis_client", _get_redis)
    monkeypatch.setenv("FOLLOW_UP_DEDUP_WINDOW_SECONDS", "86400")
    return MessageDeduplicationService()


@pytest.mark.asyncio
async def test_generate_dedup_key_consistency(dedup_service):
    patient_id = uuid4()
    content = "Hello there"
    follow_up_type = "empathetic_response"

    key_one = dedup_service._generate_dedup_key(patient_id, content, follow_up_type)
    key_two = dedup_service._generate_dedup_key(patient_id, content, follow_up_type)

    assert key_one == key_two


@pytest.mark.asyncio
async def test_generate_dedup_key_uniqueness(dedup_service):
    patient_id = uuid4()
    follow_up_type = "medical_clarification"

    key_one = dedup_service._generate_dedup_key(patient_id, "Message A", follow_up_type)
    key_two = dedup_service._generate_dedup_key(patient_id, "Message B", follow_up_type)
    key_three = dedup_service._generate_dedup_key(uuid4(), "Message A", follow_up_type)

    assert key_one != key_two
    assert key_one != key_three


@pytest.mark.asyncio
async def test_check_duplicate_not_exists(dedup_service):
    metric = follow_up_dedup_misses_total.labels(
        message_type="empathetic_response", source="deduplication_service"
    )
    start_value = metric._value.get()

    is_duplicate = await dedup_service.check_duplicate(
        patient_id=uuid4(),
        message_content="First message",
        follow_up_type="empathetic_response",
    )

    assert is_duplicate is False
    assert metric._value.get() == start_value + 1


@pytest.mark.asyncio
async def test_check_duplicate_exists(dedup_service):
    patient_id = uuid4()
    content = "Repeat message"
    follow_up_type = "medical_clarification"

    await dedup_service.mark_as_sent(patient_id, content, follow_up_type)
    is_duplicate = await dedup_service.check_duplicate(
        patient_id=patient_id,
        message_content=content,
        follow_up_type=follow_up_type,
    )

    assert is_duplicate is True


@pytest.mark.asyncio
async def test_mark_as_sent_success(dedup_service, fake_redis):
    patient_id = uuid4()
    content = "Mark this message"
    follow_up_type = "emotional_support"

    success = await dedup_service.mark_as_sent(patient_id, content, follow_up_type)
    dedup_key = dedup_service._generate_dedup_key(
        patient_id, content, follow_up_type
    )

    assert success is True
    assert await fake_redis.get(dedup_key) is not None


@pytest.mark.asyncio
async def test_mark_as_sent_ttl_verification(dedup_service, fake_redis):
    patient_id = uuid4()
    content = "TTL check"
    follow_up_type = "treatment_encouragement"

    await dedup_service.mark_as_sent(patient_id, content, follow_up_type)
    dedup_key = dedup_service._generate_dedup_key(
        patient_id, content, follow_up_type
    )
    ttl = await fake_redis.ttl(dedup_key)

    assert 86390 <= ttl <= 86400


@pytest.mark.asyncio
async def test_deduplication_window_24h(dedup_service):
    patient_id = uuid4()
    content = "Window check"
    follow_up_type = "appointment_scheduling"

    await dedup_service.mark_as_sent(patient_id, content, follow_up_type)
    is_duplicate = await dedup_service.check_duplicate(
        patient_id=patient_id,
        message_content=content,
        follow_up_type=follow_up_type,
    )

    assert is_duplicate is True


@pytest.mark.asyncio
async def test_deduplication_expires_after_24h(monkeypatch: pytest.MonkeyPatch):
    redis = fakeredis.aioredis.FakeRedis()
    await redis.flushall()

    async def _get_redis():
        return redis

    monkeypatch.setattr(service_module, "get_async_redis_client", _get_redis)

    # Use a short window to simulate 24h expiry without slowing tests.
    dedup_service = MessageDeduplicationService(window_seconds=1)
    patient_id = uuid4()
    content = "Expire check"
    follow_up_type = "information_request"

    await dedup_service.mark_as_sent(patient_id, content, follow_up_type)
    await asyncio.sleep(1.1)

    is_duplicate = await dedup_service.check_duplicate(
        patient_id=patient_id,
        message_content=content,
        follow_up_type=follow_up_type,
    )

    assert is_duplicate is False


@pytest.mark.asyncio
async def test_redis_failure_graceful(monkeypatch: pytest.MonkeyPatch):
    class FailingRedis:
        async def get(self, key):
            raise Exception("Redis connection failed")

    async def _get_redis():
        return FailingRedis()

    monkeypatch.setattr(service_module, "get_async_redis_client", _get_redis)
    dedup_service = MessageDeduplicationService()

    is_duplicate = await dedup_service.check_duplicate(
        patient_id=uuid4(),
        message_content="Failure check",
        follow_up_type="conversation_continuation",
    )

    assert is_duplicate is False


@pytest.mark.asyncio
async def test_metrics_increment(dedup_service):
    patient_id = uuid4()
    content = "Metrics check"
    follow_up_type = "provider_alert"

    metric = follow_up_messages_deduplicated_total.labels(
        message_type=follow_up_type, source="deduplication_service"
    )
    start_value = metric._value.get()

    await dedup_service.mark_as_sent(patient_id, content, follow_up_type)
    await dedup_service.check_duplicate(
        patient_id=patient_id,
        message_content=content,
        follow_up_type=follow_up_type,
    )

    assert metric._value.get() == start_value + 1
