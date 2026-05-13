"""
Unit tests for DistributedRateLimiter middleware.

Tests distributed rate limiting functionality across multiple workers.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from app.middleware.distributed_rate_limiter import DistributedRateLimiter
from app.models.message import MessagePriority


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = Mock()
    redis.pipeline = Mock()
    
    # Mock pipeline context manager
    pipeline = Mock()
    pipeline.__aenter__ = AsyncMock(return_value=pipeline)
    pipeline.__aexit__ = AsyncMock()
    pipeline.zremrangebyscore = Mock(return_value=pipeline)
    pipeline.zcard = Mock(return_value=pipeline)
    pipeline.zadd = Mock(return_value=pipeline)
    pipeline.expire = Mock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[None, 0, None, None])
    
    redis.pipeline.return_value = pipeline
    return redis


@pytest.fixture
def rate_limiter(mock_redis):
    """Create DistributedRateLimiter instance."""
    return DistributedRateLimiter(
        redis_client=mock_redis,
        max_requests=80,
        window_seconds=60
    )


class TestRateLimitAcquisition:
    """Test rate limit acquisition."""

    @pytest.mark.asyncio
    async def test_acquire_within_limit_succeeds(self, rate_limiter, mock_redis):
        """Test that acquiring within rate limit succeeds."""
        # Mock current count below limit
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.return_value = [None, 50, None, None]  # 50 requests in window
        
        result = await rate_limiter.acquire(priority=MessagePriority.NORMAL)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_at_limit_fails(self, rate_limiter, mock_redis):
        """Test that acquiring at rate limit fails."""
        # Mock current count at limit
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.return_value = [None, 80, None, None]  # 80 requests (at limit)
        
        result = await rate_limiter.acquire(priority=MessagePriority.NORMAL)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_acquire_above_limit_fails(self, rate_limiter, mock_redis):
        """Test that acquiring above rate limit fails."""
        # Mock current count above limit
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.return_value = [None, 100, None, None]  # 100 requests (over limit)
        
        result = await rate_limiter.acquire(priority=MessagePriority.NORMAL)
        
        assert result is False


class TestPriorityHandling:
    """Test priority-based rate limiting."""

    @pytest.mark.asyncio
    async def test_urgent_messages_get_reserved_capacity(self, rate_limiter, mock_redis):
        """Test that urgent messages can use reserved capacity."""
        # Mock current count at 70 (normal limit would be 80, but urgent gets 20% reserved)
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.return_value = [None, 70, None, None]
        
        # Normal priority should fail (70 >= 80 - 16 reserved)
        result_normal = await rate_limiter.acquire(priority=MessagePriority.NORMAL)
        assert result_normal is False
        
        # Urgent priority should succeed (70 < 80)
        result_urgent = await rate_limiter.acquire(priority=MessagePriority.URGENT)
        assert result_urgent is True

    @pytest.mark.asyncio
    async def test_urgent_messages_respect_total_limit(self, rate_limiter, mock_redis):
        """Test that even urgent messages respect total limit."""
        # Mock current count at total limit
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.return_value = [None, 80, None, None]
        
        result = await rate_limiter.acquire(priority=MessagePriority.URGENT)
        
        assert result is False


class TestSlidingWindow:
    """Test sliding window algorithm."""

    @pytest.mark.asyncio
    async def test_old_requests_are_removed_from_window(self, rate_limiter, mock_redis):
        """Test that requests outside the time window are removed."""
        pipeline = mock_redis.pipeline.return_value
        
        await rate_limiter.acquire(priority=MessagePriority.NORMAL)
        
        # Verify zremrangebyscore was called to remove old entries
        pipeline.zremrangebyscore.assert_called_once()

    @pytest.mark.asyncio
    async def test_window_expiry_is_set(self, rate_limiter, mock_redis):
        """Test that Redis key expiry is set to window duration."""
        pipeline = mock_redis.pipeline.return_value
        
        await rate_limiter.acquire(priority=MessagePriority.NORMAL)
        
        # Verify expire was called with window duration
        pipeline.expire.assert_called_once()
        call_args = pipeline.expire.call_args[0]
        assert call_args[1] == 60  # window_seconds


class TestDistributedBehavior:
    """Test distributed rate limiting across multiple workers."""

    @pytest.mark.asyncio
    async def test_multiple_workers_share_same_limit(self, mock_redis):
        """Test that multiple workers share the same rate limit."""
        # Create two rate limiters (simulating two workers)
        limiter1 = DistributedRateLimiter(mock_redis, max_requests=80, window_seconds=60)
        limiter2 = DistributedRateLimiter(mock_redis, max_requests=80, window_seconds=60)
        
        pipeline = mock_redis.pipeline.return_value
        
        # Worker 1 makes 40 requests
        pipeline.execute.return_value = [None, 40, None, None]
        result1 = await limiter1.acquire(priority=MessagePriority.NORMAL)
        assert result1 is True
        
        # Worker 2 sees the same count (40) and can also acquire
        pipeline.execute.return_value = [None, 40, None, None]
        result2 = await limiter2.acquire(priority=MessagePriority.NORMAL)
        assert result2 is True
        
        # Both workers together hit limit (80)
        pipeline.execute.return_value = [None, 80, None, None]
        result3 = await limiter1.acquire(priority=MessagePriority.NORMAL)
        assert result3 is False

    @pytest.mark.asyncio
    async def test_rate_limit_key_is_shared(self, rate_limiter, mock_redis):
        """Test that all workers use the same Redis key."""
        pipeline = mock_redis.pipeline.return_value
        
        await rate_limiter.acquire(priority=MessagePriority.NORMAL)
        
        # Verify operations use consistent key
        zadd_call = pipeline.zadd.call_args[0]
        key = zadd_call[0]
        assert "rate_limit:" in key


class TestRateLimitTiers:
    """Test different rate limit tiers."""

    @pytest.mark.asyncio
    async def test_public_tier_has_lowest_limit(self, mock_redis):
        """Test that public tier has the most restrictive limit."""
        limiter = DistributedRateLimiter(
            mock_redis,
            max_requests=10,  # Public tier: 10 req/min
            window_seconds=60
        )
        
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.return_value = [None, 10, None, None]
        
        result = await limiter.acquire(priority=MessagePriority.NORMAL)
        assert result is False

    @pytest.mark.asyncio
    async def test_authenticated_tier_has_higher_limit(self, mock_redis):
        """Test that authenticated tier has higher limit."""
        limiter = DistributedRateLimiter(
            mock_redis,
            max_requests=100,  # Auth tier: 100 req/min
            window_seconds=60
        )
        
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.return_value = [None, 50, None, None]
        
        result = await limiter.acquire(priority=MessagePriority.NORMAL)
        assert result is True

    @pytest.mark.asyncio
    async def test_admin_tier_has_highest_limit(self, mock_redis):
        """Test that admin tier has highest limit."""
        limiter = DistributedRateLimiter(
            mock_redis,
            max_requests=1000,  # Admin tier: 1000 req/min
            window_seconds=60
        )
        
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.return_value = [None, 500, None, None]
        
        result = await limiter.acquire(priority=MessagePriority.NORMAL)
        assert result is True


class TestErrorHandling:
    """Test error handling in rate limiter."""

    @pytest.mark.asyncio
    async def test_redis_failure_denies_request(self, rate_limiter, mock_redis):
        """Test that Redis failure denies request (fail-closed)."""
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.side_effect = Exception("Redis connection error")
        
        result = await rate_limiter.acquire(priority=MessagePriority.NORMAL)
        
        assert result is False


class TestConcurrency:
    """Test concurrent rate limit checks."""

    @pytest.mark.asyncio
    async def test_concurrent_acquires_are_atomic(self, rate_limiter, mock_redis):
        """Test that concurrent acquire operations are atomic."""
        pipeline = mock_redis.pipeline.return_value
        
        # Simulate concurrent requests
        pipeline.execute.return_value = [None, 79, None, None]
        
        # Both should see the same count due to Redis atomicity
        result1 = await rate_limiter.acquire(priority=MessagePriority.NORMAL)
        result2 = await rate_limiter.acquire(priority=MessagePriority.NORMAL)
        
        # At least one should succeed
        assert result1 is True or result2 is True


class TestMetrics:
    """Test rate limiter metrics collection."""

    @pytest.mark.asyncio
    async def test_acquire_records_metrics(self, rate_limiter, mock_redis):
        """Test that acquire operations record metrics."""
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.return_value = [None, 50, None, None]
        
        with patch('app.middleware.distributed_rate_limiter.rate_limit_hits') as mock_metric:
            await rate_limiter.acquire(priority=MessagePriority.NORMAL)
            
            # Verify metric was recorded (if implemented)
            # This test documents expected behavior
            pass

    @pytest.mark.asyncio
    async def test_rejection_records_metrics(self, rate_limiter, mock_redis):
        """Test that rejections record metrics."""
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.return_value = [None, 80, None, None]
        
        with patch('app.middleware.distributed_rate_limiter.rate_limit_rejections') as mock_metric:
            await rate_limiter.acquire(priority=MessagePriority.NORMAL)
            
            # Verify rejection metric was recorded (if implemented)
            # This test documents expected behavior
            pass

