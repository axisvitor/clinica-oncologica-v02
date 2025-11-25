"""
Pytest configuration and shared fixtures for follow-up service tests.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from uuid import uuid4
from datetime import datetime, timedelta


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = Mock()
    redis.ping = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=0)
    redis.expire = AsyncMock(return_value=True)
    redis.hget = AsyncMock(return_value=None)
    redis.hset = AsyncMock(return_value=1)
    redis.hdel = AsyncMock(return_value=1)
    redis.hgetall = AsyncMock(return_value={})
    redis.hlen = AsyncMock(return_value=0)
    redis.zadd = AsyncMock(return_value=1)
    redis.zrem = AsyncMock(return_value=1)
    redis.zrangebyscore = AsyncMock(return_value=[])
    redis.zcard = AsyncMock(return_value=0)
    redis.pipeline = Mock(return_value=AsyncMock())
    return redis


@pytest.fixture
def sample_action():
    """Sample follow-up action."""
    return {
        "id": str(uuid4()),
        "patient_id": str(uuid4()),
        "action_type": "follow_up_call",
        "scheduled_for": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        "status": "pending",
        "priority": "medium",
        "metadata": {"reason": "Check treatment progress"}
    }


@pytest.fixture
def sample_alert():
    """Sample follow-up alert."""
    return {
        "id": str(uuid4()),
        "patient_id": str(uuid4()),
        "alert_type": "missed_appointment",
        "escalation_level": 1,
        "status": "active",
        "created_at": datetime.utcnow().isoformat(),
        "metadata": {"appointment_date": "2024-01-15"}
    }


@pytest.fixture
def sample_context():
    """Sample patient context."""
    return {
        "patient_id": str(uuid4()),
        "last_interaction": datetime.utcnow().isoformat(),
        "conversation_state": "awaiting_response",
        "pending_questions": ["How are you feeling?"],
        "metadata": {"flow_id": str(uuid4())}
    }
