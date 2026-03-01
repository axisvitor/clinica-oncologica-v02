"""
Unit tests for Quiz Response Debounce Service

Tests the debouncing logic for quiz responses to prevent duplicate processing.
HIGH-005 Fix validation.
"""
import pytest
import asyncio
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

from app.services.quiz_response_debounce import (
    QuizResponseDebouncer,
    get_quiz_debouncer
)


@pytest.fixture
def session_id():
    """Generate test session ID."""
    return uuid4()


@pytest.fixture
def question_id():
    """Generate test question ID."""
    return "question_001"


@pytest.fixture
def message_metadata():
    """Generate test message metadata."""
    return {
        "message_id": str(uuid4()),
        "whatsapp_id": "test_whatsapp_id",
        "timestamp": "2025-01-01T12:00:00-03:00"
    }


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock = AsyncMock()
    mock.exists = AsyncMock(return_value=0)
    mock.setex = AsyncMock(return_value=True)
    mock.get = AsyncMock(return_value=None)
    mock.incr = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.scan = AsyncMock(return_value=(0, []))
    mock.ttl = AsyncMock(return_value=3)
    return mock


class TestQuizResponseDebouncer:
    """Test suite for QuizResponseDebouncer."""

    @pytest.mark.asyncio
    async def test_debouncer_initialization(self):
        """Test debouncer initializes with correct window."""
        # Default window
        debouncer = QuizResponseDebouncer()
        assert debouncer.debounce_window == 3

        # Custom window
        debouncer_custom = QuizResponseDebouncer(debounce_window_seconds=5)
        assert debouncer_custom.debounce_window == 5

    @pytest.mark.asyncio
    async def test_first_response_allowed(
        self,
        session_id,
        question_id,
        message_metadata,
        mock_redis
    ):
        """Test that first response is allowed (not debounced)."""
        with patch('app.services.quiz_response_debounce.get_async_redis', return_value=mock_redis):
            debouncer = QuizResponseDebouncer(debounce_window_seconds=3)

            # First response - should be allowed
            should_process = await debouncer.should_process_response(
                session_id=session_id,
                question_id=question_id,
                message_metadata=message_metadata
            )

            assert should_process is True
            mock_redis.exists.assert_called_once()
            mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_response_debounced(
        self,
        session_id,
        question_id,
        message_metadata,
        mock_redis
    ):
        """Test that duplicate response within window is debounced."""
        # Simulate key exists (response already processed)
        mock_redis.exists = AsyncMock(return_value=1)

        with patch('app.services.quiz_response_debounce.get_async_redis', return_value=mock_redis):
            debouncer = QuizResponseDebouncer(debounce_window_seconds=3)

            # Second response within window - should be debounced
            should_process = await debouncer.should_process_response(
                session_id=session_id,
                question_id=question_id,
                message_metadata=message_metadata
            )

            assert should_process is False
            mock_redis.exists.assert_called_once()
            # setex should NOT be called for debounced responses
            mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_debounce_key_format(self, session_id, question_id):
        """Test correct Redis key format."""
        debouncer = QuizResponseDebouncer()

        key = debouncer._build_debounce_key(session_id, question_id)

        expected_key = f"quiz:debounce:{session_id}:{question_id}"
        assert key == expected_key

    @pytest.mark.asyncio
    async def test_debounce_counter_incremented(
        self,
        session_id,
        question_id,
        message_metadata,
        mock_redis
    ):
        """Test that debounce counter is incremented on duplicate."""
        mock_redis.exists = AsyncMock(return_value=1)

        with patch('app.services.quiz_response_debounce.get_async_redis', return_value=mock_redis):
            debouncer = QuizResponseDebouncer()

            await debouncer.should_process_response(
                session_id=session_id,
                question_id=question_id,
                message_metadata=message_metadata
            )

            # Counter should be incremented
            mock_redis.incr.assert_called_once()
            mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_specific_question_debounce(
        self,
        session_id,
        question_id,
        mock_redis
    ):
        """Test clearing debounce for specific question."""
        mock_redis.delete = AsyncMock(return_value=1)

        with patch('app.services.quiz_response_debounce.get_async_redis', return_value=mock_redis):
            debouncer = QuizResponseDebouncer()

            result = await debouncer.clear_debounce(
                session_id=session_id,
                question_id=question_id
            )

            assert result is True
            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_all_session_debounce(self, session_id, mock_redis):
        """Test clearing all debounce keys for a session."""
        # Simulate scan returning keys
        test_keys = [
            b"quiz:debounce:session_id:q1",
            b"quiz:debounce:session_id:q2",
            b"quiz:debounce:session_id:q3"
        ]
        mock_redis.scan = AsyncMock(return_value=(0, test_keys))
        mock_redis.delete = AsyncMock(return_value=3)

        with patch('app.services.quiz_response_debounce.get_async_redis', return_value=mock_redis):
            debouncer = QuizResponseDebouncer()

            result = await debouncer.clear_debounce(
                session_id=session_id,
                question_id=None  # Clear all
            )

            assert result is True
            mock_redis.scan.assert_called_once()
            mock_redis.delete.assert_called_once_with(*test_keys)

    @pytest.mark.asyncio
    async def test_get_debounce_stats(self, session_id, mock_redis):
        """Test retrieving debounce statistics."""
        # Mock counter
        mock_redis.get = AsyncMock(return_value=b"5")

        # Mock scan for active keys
        test_keys = [
            b"quiz:debounce:session_id:q1",
            b"quiz:debounce:session_id:q2"
        ]
        mock_redis.scan = AsyncMock(return_value=(0, test_keys))
        mock_redis.ttl = AsyncMock(return_value=2)

        with patch('app.services.quiz_response_debounce.get_async_redis', return_value=mock_redis):
            debouncer = QuizResponseDebouncer()

            stats = await debouncer.get_debounce_stats(session_id)

            assert stats["session_id"] == str(session_id)
            assert stats["total_debounced"] == 5
            assert stats["active_debounces"] == 2
            assert stats["debounce_window"] == 3
            assert len(stats["active_keys"]) == 2

    @pytest.mark.asyncio
    async def test_redis_error_allows_response(
        self,
        session_id,
        question_id,
        message_metadata,
        mock_redis
    ):
        """Test that Redis errors fail open (allow response)."""
        # Simulate Redis error
        mock_redis.exists = AsyncMock(side_effect=Exception("Redis connection failed"))

        with patch('app.services.quiz_response_debounce.get_async_redis', return_value=mock_redis):
            debouncer = QuizResponseDebouncer()

            # Should allow response on error (fail open)
            should_process = await debouncer.should_process_response(
                session_id=session_id,
                question_id=question_id,
                message_metadata=message_metadata
            )

            assert should_process is True

    @pytest.mark.asyncio
    async def test_metadata_serialization(self, message_metadata):
        """Test metadata is properly serialized."""
        debouncer = QuizResponseDebouncer()

        serialized = debouncer._serialize_debounce_data(message_metadata)

        import json
        data = json.loads(serialized)

        assert "timestamp" in data
        assert "metadata" in data
        assert data["metadata"] == message_metadata

    @pytest.mark.asyncio
    async def test_get_global_debouncer_singleton(self):
        """Test global debouncer is singleton."""
        debouncer1 = get_quiz_debouncer()
        debouncer2 = get_quiz_debouncer()

        assert debouncer1 is debouncer2

    @pytest.mark.asyncio
    async def test_different_questions_not_debounced(
        self,
        session_id,
        message_metadata,
        mock_redis
    ):
        """Test responses to different questions are not debounced."""
        with patch('app.services.quiz_response_debounce.get_async_redis', return_value=mock_redis):
            debouncer = QuizResponseDebouncer()

            # Process response to question 1
            should_process_q1 = await debouncer.should_process_response(
                session_id=session_id,
                question_id="question_1",
                message_metadata=message_metadata
            )

            # Process response to question 2 (different question)
            should_process_q2 = await debouncer.should_process_response(
                session_id=session_id,
                question_id="question_2",
                message_metadata=message_metadata
            )

            # Both should be allowed
            assert should_process_q1 is True
            assert should_process_q2 is True

    @pytest.mark.asyncio
    async def test_custom_debounce_window(
        self,
        session_id,
        question_id,
        message_metadata,
        mock_redis
    ):
        """Test custom debounce window is used."""
        custom_window = 5

        with patch('app.services.quiz_response_debounce.get_async_redis', return_value=mock_redis):
            debouncer = QuizResponseDebouncer(debounce_window_seconds=custom_window)

            await debouncer.should_process_response(
                session_id=session_id,
                question_id=question_id,
                message_metadata=message_metadata
            )

            # Check setex was called with custom window
            call_args = mock_redis.setex.call_args
            assert call_args[0][1] == custom_window  # TTL should be custom window

    @pytest.mark.asyncio
    async def test_concurrent_responses_debounced(
        self,
        session_id,
        question_id,
        message_metadata,
        mock_redis
    ):
        """Test concurrent responses are properly debounced."""
        call_count = 0

        async def mock_exists(key):
            nonlocal call_count
            call_count += 1
            # First call returns 0 (not exists), subsequent return 1 (exists)
            return 0 if call_count == 1 else 1

        mock_redis.exists = mock_exists

        with patch('app.services.quiz_response_debounce.get_async_redis', return_value=mock_redis):
            debouncer = QuizResponseDebouncer()

            # Simulate concurrent responses
            results = await asyncio.gather(
                debouncer.should_process_response(session_id, question_id, message_metadata),
                debouncer.should_process_response(session_id, question_id, message_metadata),
                debouncer.should_process_response(session_id, question_id, message_metadata)
            )

            # Only first should be True
            assert results[0] is True
            assert results[1] is False
            assert results[2] is False


@pytest.mark.integration
class TestQuizResponseDebouncerIntegration:
    """Integration tests with real Redis (if available)."""

    @pytest.mark.asyncio
    async def test_real_debounce_timing(self, session_id, question_id):
        """Test actual debounce timing with real Redis."""
        try:
            from app.core.redis_manager import get_async_redis_client as get_async_redis

            redis_client = await get_async_redis()

            debouncer = QuizResponseDebouncer(debounce_window_seconds=1)
            debounce_key = debouncer._build_debounce_key(session_id, question_id)
            await redis_client.delete(debounce_key)

            # First response
            first = await debouncer.should_process_response(
                session_id, question_id, {"test": "metadata"}
            )
            assert first is True

            # Immediate second response (within window)
            second = await debouncer.should_process_response(
                session_id, question_id, {"test": "metadata2"}
            )
            assert second is False

            # Wait for debounce to expire (robust against backend timing granularity)
            deadline = asyncio.get_running_loop().time() + 5.0
            while asyncio.get_running_loop().time() < deadline:
                if await redis_client.exists(debounce_key) == 0:
                    break
                await asyncio.sleep(0.1)

            assert await redis_client.exists(debounce_key) == 0

            # Third response (after window expires)
            third = await debouncer.should_process_response(
                session_id, question_id, {"test": "metadata3"}
            )
            assert third is True

            # Cleanup
            await debouncer.clear_debounce(session_id)

        except (RedisConnectionError, RedisTimeoutError, OSError) as e:
            pytest.skip(f"Redis not available: {e}")
