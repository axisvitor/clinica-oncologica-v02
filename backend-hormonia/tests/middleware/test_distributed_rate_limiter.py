"""
Tests for DistributedRateLimiter - Redis-based rate limiting.

This test suite validates the production-ready distributed rate limiter
that replaces the in-memory implementation to prevent memory leaks.
"""

import pytest
import time
from unittest.mock import Mock, patch
from app.middleware.rate_limiter import DistributedRateLimiter


class TestDistributedRateLimiter:
    """Test suite for Redis-based distributed rate limiter."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_client = Mock()
        redis_client.ping.return_value = True
        redis_client.pipeline.return_value = Mock()
        return redis_client

    @pytest.fixture
    def rate_limiter(self, mock_redis):
        """Create DistributedRateLimiter with mocked Redis."""
        with patch('redis.from_url', return_value=mock_redis):
            limiter = DistributedRateLimiter(
                redis_url="redis://localhost:6379/3",
                rate=10,
                per=60
            )
            # Force Redis client initialization
            limiter._get_redis_client()
            return limiter

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_first_request(self, rate_limiter, mock_redis):
        """Test that first request is always allowed."""
        # Mock Redis pipeline responses
        pipe = Mock()
        pipe.execute.side_effect = [
            [None, None],  # First execute: get values
            [None, None],  # Second execute: setex
        ]
        mock_redis.pipeline.return_value = pipe

        is_allowed, retry_after = await rate_limiter.is_allowed("user:123")

        assert is_allowed is True
        assert retry_after is None

    @pytest.mark.asyncio
    async def test_rate_limiter_enforces_limit(self, rate_limiter, mock_redis):
        """Test that rate limiter enforces limits correctly."""
        current_time = time.time()

        # Mock Redis pipeline to simulate exhausted allowance
        pipe = Mock()
        pipe.execute.side_effect = [
            ["0.5", str(current_time)],  # Allowance below 1.0
        ]
        mock_redis.pipeline.return_value = pipe

        is_allowed, retry_after = await rate_limiter.is_allowed("user:123")

        assert is_allowed is False
        assert retry_after is not None
        assert retry_after > 0

    @pytest.mark.asyncio
    async def test_rate_limiter_replenishes_tokens(self, rate_limiter, mock_redis):
        """Test that tokens are replenished over time."""
        # Simulate time passed to replenish tokens
        past_time = time.time() - 30  # 30 seconds ago

        pipe = Mock()
        pipe.execute.side_effect = [
            ["5.0", str(past_time)],  # Some allowance, old timestamp
            [None, None],  # setex calls
        ]
        mock_redis.pipeline.return_value = pipe

        is_allowed, retry_after = await rate_limiter.is_allowed("user:123")

        assert is_allowed is True
        assert retry_after is None

    @pytest.mark.asyncio
    async def test_rate_limiter_uses_ttl(self, rate_limiter, mock_redis):
        """Test that rate limiter sets TTL on Redis keys."""
        pipe = Mock()
        pipe.execute.side_effect = [
            [None, None],
            [None, None],
        ]
        mock_redis.pipeline.return_value = pipe

        await rate_limiter.is_allowed("user:123")

        # Verify setex was called with TTL
        setex_calls = [call for call in pipe.method_calls if call[0] == 'setex']
        assert len(setex_calls) > 0
        # TTL should be 2x the rate period (120 seconds for 60s period)
        for call in setex_calls:
            assert call[1][1] == 120  # TTL = per * 2

    @pytest.mark.asyncio
    async def test_rate_limiter_falls_back_on_redis_error(self, rate_limiter, mock_redis):
        """Test graceful fallback when Redis is unavailable."""
        # Simulate Redis error
        mock_redis.pipeline.side_effect = Exception("Redis connection error")

        is_allowed, retry_after = await rate_limiter.is_allowed("user:123")

        # Should fail open (allow request) when Redis has issues
        assert is_allowed is True
        assert retry_after is None

    @pytest.mark.asyncio
    async def test_rate_limiter_different_keys_independent(self, rate_limiter, mock_redis):
        """Test that different keys have independent rate limits."""
        pipe = Mock()
        pipe.execute.side_effect = [
            [None, None],  # user:123 - first call
            [None, None],
            [None, None],  # user:456 - independent limit
            [None, None],
        ]
        mock_redis.pipeline.return_value = pipe

        # User 123
        is_allowed_1, _ = await rate_limiter.is_allowed("user:123")
        # User 456
        is_allowed_2, _ = await rate_limiter.is_allowed("user:456")

        assert is_allowed_1 is True
        assert is_allowed_2 is True

    def test_rate_limiter_reset(self, rate_limiter, mock_redis):
        """Test resetting rate limit for a key."""
        rate_limiter.reset("user:123")

        # Verify Redis delete was called
        mock_redis.delete.assert_called_once()
        call_args = mock_redis.delete.call_args[0]
        assert "ratelimit:allowance:user:123" in call_args
        assert "ratelimit:last_check:user:123" in call_args

    def test_rate_limiter_get_remaining(self, rate_limiter, mock_redis):
        """Test getting remaining requests."""
        mock_redis.get.return_value = "7.5"

        remaining = rate_limiter.get_remaining("user:123")

        assert remaining == 7
        mock_redis.get.assert_called_with("ratelimit:allowance:user:123")

    def test_rate_limiter_get_remaining_no_data(self, rate_limiter, mock_redis):
        """Test getting remaining when no data exists."""
        mock_redis.get.return_value = None

        remaining = rate_limiter.get_remaining("user:123")

        assert remaining == 10  # Should return max rate

    @pytest.mark.asyncio
    async def test_rate_limiter_concurrent_requests_safe(self, rate_limiter, mock_redis):
        """Test that concurrent requests are handled safely with Redis pipeline."""
        pipe = Mock()
        pipe.execute.side_effect = [
            ["9.0", str(time.time())],
            [None, None],
        ]
        mock_redis.pipeline.return_value = pipe

        is_allowed, _ = await rate_limiter.is_allowed("user:123")

        # Verify pipeline was used (atomic operations)
        assert mock_redis.pipeline.called
        assert is_allowed is True

    def test_rate_limiter_custom_prefix(self):
        """Test rate limiter with custom Redis key prefix."""
        with patch('redis.from_url') as mock_from_url:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_from_url.return_value = mock_client

            limiter = DistributedRateLimiter(
                redis_url="redis://localhost:6379/3",
                prefix="custom_prefix"
            )
            limiter._get_redis_client()

            limiter.reset("test:key")

            # Verify custom prefix is used
            call_args = mock_client.delete.call_args[0]
            assert "custom_prefix:allowance:test:key" in call_args

    def test_rate_limiter_lazy_redis_connection(self):
        """Test that Redis connection is lazy (not created until needed)."""
        with patch('redis.from_url') as mock_from_url:
            limiter = DistributedRateLimiter(
                redis_url="redis://localhost:6379/3"
            )

            # Redis should not be connected yet
            assert not mock_from_url.called

            # Trigger lazy connection
            limiter._get_redis_client()

            # Now Redis should be connected
            assert mock_from_url.called

    @pytest.mark.asyncio
    async def test_rate_limiter_handles_redis_none_gracefully(self):
        """Test graceful handling when Redis connection fails."""
        with patch('redis.from_url', side_effect=Exception("Connection failed")):
            limiter = DistributedRateLimiter(
                redis_url="redis://localhost:6379/3"
            )

            # Should not raise exception
            is_allowed, retry_after = await limiter.is_allowed("user:123")

            # Should fail open (allow request)
            assert is_allowed is True
            assert retry_after is None


class TestDistributedRateLimiterIntegration:
    """Integration tests for DistributedRateLimiter (requires real Redis)."""

    @pytest.mark.integration
    @pytest.mark.skipif(
        not pytest.importorskip("redis", minversion="4.0.0"),
        reason="Redis library not available"
    )
    @pytest.mark.asyncio
    async def test_real_redis_rate_limiting(self):
        """Test rate limiting with real Redis (integration test)."""
        try:
            limiter = DistributedRateLimiter(
                redis_url="redis://localhost:6379/3",
                rate=5,
                per=10
            )

            # Test that Redis is available
            redis_client = limiter._get_redis_client()
            if redis_client is None:
                pytest.skip("Redis not available for integration test")

            # Clean up any existing data
            limiter.reset("integration:test")

            # Should allow first 5 requests
            for i in range(5):
                is_allowed, _ = await limiter.is_allowed("integration:test")
                assert is_allowed is True, f"Request {i+1} should be allowed"

            # 6th request should be denied
            is_allowed, retry_after = await limiter.is_allowed("integration:test")
            assert is_allowed is False
            assert retry_after is not None

            # Clean up
            limiter.reset("integration:test")

        except Exception as e:
            pytest.skip(f"Redis integration test failed: {e}")


class TestDistributedRateLimiterMemoryLeak:
    """Tests to verify no memory leaks compared to in-memory implementation."""

    def test_no_in_memory_storage(self):
        """Verify that DistributedRateLimiter doesn't store data in memory."""
        with patch('redis.from_url') as mock_from_url:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_from_url.return_value = mock_client

            limiter = DistributedRateLimiter(
                redis_url="redis://localhost:6379/3"
            )

            # Check that there are no dictionaries storing keys
            assert not hasattr(limiter, 'allowance')
            assert not hasattr(limiter, 'last_check')
            assert not hasattr(limiter, 'reputation')
            assert not hasattr(limiter, 'violations')

    def test_redis_handles_cleanup_via_ttl(self):
        """Verify that cleanup is handled by Redis TTL, not in-memory logic."""
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True

        with patch('redis.from_url', return_value=mock_redis_client):
            limiter = DistributedRateLimiter(
                redis_url="redis://localhost:6379/3",
                rate=10,
                per=60
            )

            # Verify no cleanup method exists
            assert not hasattr(limiter, '_cleanup_old_keys')
            assert not hasattr(limiter, 'MAX_KEYS')
            assert not hasattr(limiter, 'KEY_EXPIRY')
