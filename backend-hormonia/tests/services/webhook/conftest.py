"""
Pytest configuration and shared fixtures for webhook tests.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from app.models.message import Message, MessageStatus, MessageType


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = Mock()
    db.query = Mock()
    db.execute = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.close = Mock()
    db.refresh = Mock()
    return db


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = Mock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.setex = AsyncMock()
    redis.exists = AsyncMock(return_value=False)
    redis.delete = AsyncMock()
    redis.hget = AsyncMock(return_value=None)
    redis.hset = AsyncMock()
    redis.hdel = AsyncMock()
    redis.hgetall = AsyncMock(return_value={})
    redis.zadd = AsyncMock()
    redis.zrem = AsyncMock()
    redis.zrangebyscore = AsyncMock(return_value=[])
    redis.expire = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_evolution_client():
    """Create a mock Evolution API client."""
    client = Mock()
    client.send_text_message = AsyncMock(return_value={"id": "whatsapp_123", "status": "SENT"})
    client.send_media_message = AsyncMock(return_value={"id": "whatsapp_media_123", "status": "SENT"})
    return client


@pytest.fixture
def mock_connection_state_repo():
    """Create a mock connection state repository."""
    repo = Mock()
    repo.set_state = AsyncMock()
    repo.get_state = AsyncMock(return_value="open")
    return repo


@pytest.fixture
def sample_patient():
    """Create a sample patient for testing."""
    patient = Mock()
    patient.id = uuid4()
    patient.cpf = "12345678909"
    patient.full_name = "Test Patient"
    patient.phone = "+5511987654321"
    patient.is_active = True
    return patient


@pytest.fixture
def sample_message():
    """Create a sample message for testing."""
    return Message(
        id=uuid4(),
        patient_id=uuid4(),
        content="Test message content",
        phone="+5511987654321",
        status=MessageStatus.PENDING,
        message_type=MessageType.TEXT,
        direction="incoming"
    )


@pytest.fixture
def evolution_message_webhook():
    """Sample Evolution API message webhook payload."""
    return {
        "instance": "clinica-hormonia",
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "5511987654321@s.whatsapp.net",
                "fromMe": False,
                "id": "whatsapp_msg_123"
            },
            "message": {
                "conversation": "Hello, I need help with my treatment."
            },
            "messageTimestamp": 1699999999,
            "pushName": "Test Patient"
        }
    }


@pytest.fixture
def evolution_status_webhook():
    """Sample Evolution API status webhook payload."""
    return {
        "instance": "clinica-hormonia",
        "event": "messages.update",
        "data": {
            "key": {
                "remoteJid": "5511987654321@s.whatsapp.net",
                "id": "whatsapp_msg_123"
            },
            "status": "READ"
        }
    }


@pytest.fixture
def evolution_connection_webhook():
    """Sample Evolution API connection webhook payload."""
    return {
        "instance": "clinica-hormonia",
        "event": "connection.update",
        "state": "open"
    }


@pytest.fixture
def evolution_qrcode_webhook():
    """Sample Evolution API QR code webhook payload."""
    return {
        "instance": "clinica-hormonia",
        "event": "qrcode.updated",
        "qrcode": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
    }
