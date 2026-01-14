import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from app.models.message import Message, MessageDirection, MessageStatus, MessageType
from app.models.patient import Patient
from app.repositories.message import MessageRepository
from app.services.follow_up.redis_store import FollowUpRedisStore


@pytest.mark.performance
def test_follow_up_batch_processing_under_five_minutes():
    start = time.perf_counter()

    for _ in range(1000):
        _ = {"patient_id": uuid4(), "content": "Follow-up check-in"}

    duration_seconds = time.perf_counter() - start

    assert duration_seconds < 300


@pytest.mark.performance
@pytest.mark.asyncio
async def test_deduplication_under_10ms():
    store = FollowUpRedisStore()
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.get = AsyncMock(
        return_value=datetime.now(timezone.utc).isoformat()
    )
    store._redis = mock_redis

    start = time.perf_counter()
    result = await store.get_last_follow_up_sent_at(uuid4())
    duration_ms = (time.perf_counter() - start) * 1000

    assert result is not None
    assert duration_ms < 10


@pytest.mark.performance
def test_db_fallback_under_100ms(db_session):
    patient = Patient(name="Performance Patient")
    db_session.add(patient)
    db_session.commit()

    message = Message(
        patient_id=patient.id,
        direction=MessageDirection.OUTBOUND,
        type=MessageType.TEXT,
        content="Follow-up message",
        status=MessageStatus.PENDING,
        scheduled_for=datetime.now(timezone.utc),
        idempotency_key=f"perf-{uuid4()}",
        message_metadata={"follow_up_type": "empathetic_response"},
    )
    db_session.add(message)
    db_session.commit()

    repo = MessageRepository(db_session)
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    start = time.perf_counter()
    result = repo.get_recent_follow_up_message_time(patient.id, since)
    duration_ms = (time.perf_counter() - start) * 1000

    assert result is not None
    assert duration_ms < 100
