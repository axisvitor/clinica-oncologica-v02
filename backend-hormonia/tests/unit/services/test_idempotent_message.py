"""
Unit tests for IdempotentMessageSender service.

Tests idempotency functionality to ensure messages are not sent multiple times.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timedelta

from app.services.idempotent_message_sender import IdempotentMessageSender
from app.models.message import Message, MessageStatus


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    db.query = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    return db


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = Mock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    redis.exists = AsyncMock(return_value=False)
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def mock_evolution_client():
    """Mock Evolution API client."""
    client = Mock()
    client.send_text_message = AsyncMock(return_value={"id": "whatsapp_123"})
    return client


@pytest.fixture
def sender(mock_db, mock_redis, mock_evolution_client):
    """Create IdempotentMessageSender instance."""
    return IdempotentMessageSender(
        db=mock_db,
        redis_client=mock_redis,
        evolution_client=mock_evolution_client
    )


@pytest.fixture
def sample_message():
    """Create a sample message for testing."""
    return Message(
        id=uuid4(),
        patient_id=uuid4(),
        content="Test message",
        phone="+5511987654321",
        status=MessageStatus.PENDING,
        idempotency_key=None
    )


class TestIdempotencyKeyGeneration:
    """Test idempotency key generation."""

    def test_generate_idempotency_key_is_unique(self, sender, sample_message):
        """Test that generated idempotency keys are unique."""
        key1 = sender.generate_idempotency_key(sample_message)
        key2 = sender.generate_idempotency_key(sample_message)
        
        # Keys should be deterministic for same message
        assert key1 == key2
        assert key1.startswith("msg:")

    def test_idempotency_key_includes_message_id(self, sender, sample_message):
        """Test that idempotency key includes message ID."""
        key = sender.generate_idempotency_key(sample_message)
        
        assert str(sample_message.id) in key


class TestMessageSendingWithIdempotency:
    """Test message sending with idempotency checks."""

    @pytest.mark.asyncio
    async def test_send_message_first_time_succeeds(self, sender, mock_redis, mock_evolution_client, sample_message, mock_db):
        """Test that sending a message for the first time succeeds."""
        mock_redis.exists.return_value = False
        mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = sample_message
        
        result = await sender.send_message(sample_message.id)
        
        assert result["status"] == "sent"
        assert result["whatsapp_id"] == "whatsapp_123"
        mock_evolution_client.send_text_message.assert_called_once()
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_already_processed_skips_sending(self, sender, mock_redis, mock_evolution_client, sample_message):
        """Test that already processed messages are not sent again."""
        mock_redis.exists.return_value = True
        
        result = await sender.send_message(sample_message.id)
        
        assert result["status"] == "already_sent"
        mock_evolution_client.send_text_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_message_already_sent_status_skips_sending(self, sender, mock_db, mock_evolution_client, sample_message):
        """Test that messages with SENT status are not sent again."""
        sample_message.status = MessageStatus.SENT
        mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = sample_message
        
        result = await sender.send_message(sample_message.id)
        
        assert result["status"] == "already_sent"
        mock_evolution_client.send_text_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_message_updates_status_on_success(self, sender, mock_db, mock_redis, mock_evolution_client, sample_message):
        """Test that message status is updated to SENT on success."""
        mock_redis.exists.return_value = False
        mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = sample_message
        
        await sender.send_message(sample_message.id)
        
        assert sample_message.status == MessageStatus.SENT
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_stores_idempotency_key_in_redis(self, sender, mock_db, mock_redis, mock_evolution_client, sample_message):
        """Test that idempotency key is stored in Redis after sending."""
        mock_redis.exists.return_value = False
        mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = sample_message
        
        await sender.send_message(sample_message.id)
        
        # Verify Redis setex was called with 24h TTL
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 86400  # 24 hours in seconds


class TestConcurrentSending:
    """Test concurrent message sending scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_sends_only_one_succeeds(self, sender, mock_db, mock_redis, mock_evolution_client, sample_message):
        """Test that concurrent sends of same message only result in one actual send."""
        # First call: not in cache
        mock_redis.exists.side_effect = [False, True]
        mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = sample_message
        
        # First send
        result1 = await sender.send_message(sample_message.id)
        
        # Second send (concurrent)
        result2 = await sender.send_message(sample_message.id)
        
        assert result1["status"] == "sent"
        assert result2["status"] == "already_sent"
        assert mock_evolution_client.send_text_message.call_count == 1


class TestErrorHandling:
    """Test error handling in message sending."""

    @pytest.mark.asyncio
    async def test_send_message_evolution_api_failure_rolls_back(self, sender, mock_db, mock_redis, mock_evolution_client, sample_message):
        """Test that Evolution API failure rolls back transaction."""
        mock_redis.exists.return_value = False
        mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = sample_message
        mock_evolution_client.send_text_message.side_effect = Exception("API Error")
        
        with pytest.raises(Exception, match="API Error"):
            await sender.send_message(sample_message.id)
        
        mock_db.rollback.assert_called_once()
        # Idempotency key should not be stored on failure
        mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_message_nonexistent_message_raises_error(self, sender, mock_db):
        """Test that sending nonexistent message raises error."""
        mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = None
        
        with pytest.raises(ValueError, match="Message not found"):
            await sender.send_message(uuid4())


class TestIdempotencyKeyExpiration:
    """Test idempotency key expiration behavior."""

    @pytest.mark.asyncio
    async def test_expired_idempotency_key_allows_resend(self, sender, mock_db, mock_redis, mock_evolution_client, sample_message):
        """Test that expired idempotency keys allow message to be resent."""
        # Simulate expired key (not in Redis)
        mock_redis.exists.return_value = False
        mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = sample_message
        
        result = await sender.send_message(sample_message.id)
        
        assert result["status"] == "sent"
        mock_evolution_client.send_text_message.assert_called_once()


class TestBatchSending:
    """Test batch message sending with idempotency."""

    @pytest.mark.asyncio
    async def test_send_batch_processes_all_messages(self, sender, mock_db, mock_redis, mock_evolution_client):
        """Test that batch sending processes all messages."""
        messages = [
            Message(id=uuid4(), content=f"Message {i}", phone="+5511987654321", status=MessageStatus.PENDING)
            for i in range(5)
        ]
        
        mock_redis.exists.return_value = False
        mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.side_effect = messages
        
        message_ids = [msg.id for msg in messages]
        results = await sender.send_batch(message_ids)
        
        assert len(results) == 5
        assert all(r["status"] == "sent" for r in results)
        assert mock_evolution_client.send_text_message.call_count == 5

    @pytest.mark.asyncio
    async def test_send_batch_skips_already_sent_messages(self, sender, mock_db, mock_redis, mock_evolution_client):
        """Test that batch sending skips already sent messages."""
        messages = [
            Message(id=uuid4(), content="Message 1", phone="+5511987654321", status=MessageStatus.PENDING),
            Message(id=uuid4(), content="Message 2", phone="+5511987654321", status=MessageStatus.SENT),
            Message(id=uuid4(), content="Message 3", phone="+5511987654321", status=MessageStatus.PENDING),
        ]
        
        mock_redis.exists.side_effect = [False, True, False]
        mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.side_effect = messages
        
        message_ids = [msg.id for msg in messages]
        results = await sender.send_batch(message_ids)
        
        assert len(results) == 3
        assert results[0]["status"] == "sent"
        assert results[1]["status"] == "already_sent"
        assert results[2]["status"] == "sent"
        assert mock_evolution_client.send_text_message.call_count == 2  # Only 2 actually sent

