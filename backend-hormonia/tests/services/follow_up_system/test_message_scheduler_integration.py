import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
import redis.asyncio as redis_async

import app.services.follow_up_system.message_deduplication_service as dedup_module
from app.monitoring.metrics import follow_up_messages_deduplicated_total
from app.services.follow_up_system.enums import FollowUpType
from app.services.follow_up_system.models import FollowUpAction
from app.services.follow_up_system.scheduling.message import MessageScheduler


from app.utils.timezone import now_sao_paulo
DEDUP_KEY_PREFIX = "follow_up:dedup:test:"


class FakeDB:
    def __init__(self) -> None:
        self.added = []
        self.commit_count = 0
        self.refresh_count = 0
        self.rollback_count = 0

    def add(self, message) -> None:
        self.added.append(message)

    def commit(self) -> None:
        self.commit_count += 1

    def refresh(self, message) -> None:
        self.refresh_count += 1
        if getattr(message, "id", None) is None:
            message.id = uuid4()

    def rollback(self) -> None:
        self.rollback_count += 1


def _build_action(patient_id, content, follow_up_type: FollowUpType) -> FollowUpAction:
    return FollowUpAction(
        action_id=uuid4(),
        patient_id=patient_id,
        follow_up_type=follow_up_type,
        priority="normal",
        scheduled_for=now_sao_paulo(),
        parameters={"message_content": content},
    )


async def _clear_dedup_keys(redis_client) -> None:
    keys = [key async for key in redis_client.scan_iter(match=f"{DEDUP_KEY_PREFIX}*")]
    if keys:
        await redis_client.delete(*keys)


@pytest.fixture
def dedup_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Use a short window to keep time-based tests fast.
    monkeypatch.setenv("FOLLOW_UP_DEDUP_WINDOW_SECONDS", "2")


@pytest.fixture
async def redis_client():
    redis_url = (
        os.getenv("TEST_REDIS_URL")
        or os.getenv("REDIS_URL")
        or "redis://localhost:6379/0"
    )
    client = redis_async.from_url(redis_url, decode_responses=True)

    try:
        await client.ping()
    except Exception:
        await client.close()
        pytest.skip("Redis server not available for integration tests")

    await _clear_dedup_keys(client)
    yield client
    await _clear_dedup_keys(client)
    await client.close()


@pytest.fixture
async def scheduler_setup(
    monkeypatch: pytest.MonkeyPatch, redis_client, dedup_env
):
    async def _get_redis():
        return redis_client

    monkeypatch.setattr(dedup_module, "DEDUP_KEY_PREFIX", DEDUP_KEY_PREFIX)
    monkeypatch.setattr(dedup_module, "get_async_redis_client", _get_redis)
    db = FakeDB()
    message_scheduler = AsyncMock()
    message_scheduler.task_scheduler = AsyncMock()
    message_scheduler.task_scheduler.schedule_task = AsyncMock()
    scheduler = MessageScheduler(db, message_scheduler)
    return scheduler, db, message_scheduler


@pytest.mark.integration
@pytest.mark.asyncio
async def test_schedule_message_action_deduplication(scheduler_setup):
    scheduler, db, message_scheduler = scheduler_setup
    patient_id = uuid4()

    action_one = _build_action(
        patient_id, "Hello patient", FollowUpType.EMPATHETIC_RESPONSE
    )
    action_two = _build_action(
        patient_id, "Hello patient", FollowUpType.EMPATHETIC_RESPONSE
    )

    await scheduler.schedule_message_action(action_one)
    await scheduler.schedule_message_action(action_two)

    assert len(db.added) == 1
    assert message_scheduler.task_scheduler.schedule_task.call_count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_schedule_different_messages_allowed(scheduler_setup):
    scheduler, db, message_scheduler = scheduler_setup
    patient_id = uuid4()

    action_one = _build_action(
        patient_id, "First follow-up", FollowUpType.MEDICAL_CLARIFICATION
    )
    action_two = _build_action(
        patient_id, "Second follow-up", FollowUpType.MEDICAL_CLARIFICATION
    )

    await scheduler.schedule_message_action(action_one)
    await scheduler.schedule_message_action(action_two)

    assert len(db.added) == 2
    assert message_scheduler.task_scheduler.schedule_task.call_count == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_schedule_same_message_different_patients(scheduler_setup):
    scheduler, db, message_scheduler = scheduler_setup
    patient_one = uuid4()
    patient_two = uuid4()

    action_one = _build_action(
        patient_one, "Shared content", FollowUpType.TREATMENT_ENCOURAGEMENT
    )
    action_two = _build_action(
        patient_two, "Shared content", FollowUpType.TREATMENT_ENCOURAGEMENT
    )

    await scheduler.schedule_message_action(action_one)
    await scheduler.schedule_message_action(action_two)

    assert len(db.added) == 2
    assert message_scheduler.task_scheduler.schedule_task.call_count == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deduplication_after_23h(scheduler_setup):
    scheduler, db, message_scheduler = scheduler_setup
    patient_id = uuid4()
    follow_up_type = FollowUpType.EMOTIONAL_SUPPORT

    action_one = _build_action(patient_id, "Check-in", follow_up_type)
    action_two = _build_action(patient_id, "Check-in", follow_up_type)

    await scheduler.schedule_message_action(action_one)
    await asyncio.sleep(1)
    await scheduler.schedule_message_action(action_two)

    assert len(db.added) == 1
    assert message_scheduler.task_scheduler.schedule_task.call_count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deduplication_after_25h(scheduler_setup):
    scheduler, db, message_scheduler = scheduler_setup
    patient_id = uuid4()
    follow_up_type = FollowUpType.INFORMATION_REQUEST

    action_one = _build_action(patient_id, "Reminder", follow_up_type)
    action_two = _build_action(patient_id, "Reminder", follow_up_type)

    await scheduler.schedule_message_action(action_one)
    await asyncio.sleep(3)
    await scheduler.schedule_message_action(action_two)

    assert len(db.added) == 2
    assert message_scheduler.task_scheduler.schedule_task.call_count == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_metrics_tracking(scheduler_setup):
    scheduler, db, message_scheduler = scheduler_setup
    patient_id = uuid4()
    follow_up_type = FollowUpType.CONVERSATION_CONTINUATION

    metric = follow_up_messages_deduplicated_total.labels(
        message_type=follow_up_type.value, source="deduplication_service"
    )
    start_value = metric._value.get()

    action_one = _build_action(patient_id, "Metrics", follow_up_type)
    action_two = _build_action(patient_id, "Metrics", follow_up_type)

    await scheduler.schedule_message_action(action_one)
    await scheduler.schedule_message_action(action_two)

    assert metric._value.get() == start_value + 1
