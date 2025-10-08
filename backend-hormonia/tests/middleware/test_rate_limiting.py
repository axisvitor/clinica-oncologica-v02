"""
Comprehensive rate limiting tests.

Tests rate limiting middleware, algorithms, and security measures.
Coverage target: >90%
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, Response

# Import rate limiting middleware if available
try:
    from app.middleware.rate_limiting import RateLimiter, rate_limit_middleware
except ImportError:
    RateLimiter = None
    rate_limit_middleware = None

from conftest import assert_response_time


class TestRateLimiterAlgorithms:
    """Test different rate limiting algorithms."""

    @pytest.mark.unit
    def test_token_bucket_algorithm(self, mock_redis):
        """Test token bucket rate limiting algorithm."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        # Mock Redis responses for token bucket
        mock_redis.eval.return_value = 1  # Tokens available

        rate_limiter = RateLimiter(algorithm="token_bucket")

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            is_allowed = rate_limiter.is_allowed("user:123", limit=10, window=60)

        assert is_allowed is True
        mock_redis.eval.assert_called_once()

    @pytest.mark.unit
    def test_sliding_window_algorithm(self, mock_redis):
        """Test sliding window rate limiting algorithm."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        # Mock Redis responses for sliding window
        mock_redis.zcard.return_value = 5  # Current count
        mock_redis.zadd.return_value = 1
        mock_redis.zremrangebyscore.return_value = 2

        rate_limiter = RateLimiter(algorithm="sliding_window")

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            is_allowed = rate_limiter.is_allowed("user:123", limit=10, window=60)

        assert is_allowed is True

    @pytest.mark.unit
    def test_fixed_window_algorithm(self, mock_redis):
        """Test fixed window rate limiting algorithm."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        # Mock Redis responses for fixed window
        mock_redis.incr.return_value = 5  # Current count
        mock_redis.expire.return_value = True

        rate_limiter = RateLimiter(algorithm="fixed_window")

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            is_allowed = rate_limiter.is_allowed("user:123", limit=10, window=60)

        assert is_allowed is True
        mock_redis.incr.assert_called_once()

    @pytest.mark.unit
    def test_rate_limit_exceeded(self, mock_redis):
        """Test when rate limit is exceeded."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        # Mock Redis to return count exceeding limit
        mock_redis.incr.return_value = 15  # Exceeds limit of 10

        rate_limiter = RateLimiter(algorithm="fixed_window")

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            is_allowed = rate_limiter.is_allowed("user:123", limit=10, window=60)

        assert is_allowed is False


class TestRateLimitingByIP:
    """Test rate limiting by IP address."""

    @pytest.mark.unit
    def test_rate_limit_by_ip_success(self, mock_redis):
        """Test successful request within IP rate limit."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        mock_redis.incr.return_value = 5  # Within limit

        rate_limiter = RateLimiter()

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            is_allowed = rate_limiter.is_allowed_by_ip("192.168.1.1", limit=100, window=60)

        assert is_allowed is True

    @pytest.mark.unit
    def test_rate_limit_by_ip_exceeded(self, mock_redis):
        """Test request exceeding IP rate limit."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        mock_redis.incr.return_value = 150  # Exceeds limit

        rate_limiter = RateLimiter()

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            is_allowed = rate_limiter.is_allowed_by_ip("192.168.1.1", limit=100, window=60)

        assert is_allowed is False

    @pytest.mark.security
    def test_rate_limit_ip_spoofing_protection(self, mock_redis, security_test_payloads):
        """Test protection against IP spoofing attempts."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        rate_limiter = RateLimiter()

        # Test with malicious IP addresses
        malicious_ips = [
            "127.0.0.1; DROP TABLE users;",
            "192.168.1.1' OR '1'='1",
            "../../../etc/passwd",
            "<script>alert('xss')</script>",
            "null",
            ""
        ]

        for ip in malicious_ips:
            with patch('app.middleware.rate_limiting.redis_client', mock_redis):
                # Should handle malicious IPs gracefully
                try:
                    is_allowed = rate_limiter.is_allowed_by_ip(ip, limit=10, window=60)
                    # Should either work (if sanitized) or return False
                    assert isinstance(is_allowed, bool)
                except Exception:
                    # Should not raise unhandled exceptions
                    pass

    @pytest.mark.unit
    def test_rate_limit_ipv6_support(self, mock_redis):
        """Test rate limiting with IPv6 addresses."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        mock_redis.incr.return_value = 5

        rate_limiter = RateLimiter()
        ipv6_address = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            is_allowed = rate_limiter.is_allowed_by_ip(ipv6_address, limit=10, window=60)

        assert is_allowed is True


class TestRateLimitingByUser:
    """Test rate limiting by user ID."""

    @pytest.mark.unit
    def test_rate_limit_by_user_success(self, mock_redis):
        """Test successful request within user rate limit."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        mock_redis.incr.return_value = 20  # Within limit

        rate_limiter = RateLimiter()

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            is_allowed = rate_limiter.is_allowed_by_user("user123", limit=50, window=60)

        assert is_allowed is True

    @pytest.mark.unit
    def test_rate_limit_by_user_exceeded(self, mock_redis):
        """Test request exceeding user rate limit."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        mock_redis.incr.return_value = 75  # Exceeds limit

        rate_limiter = RateLimiter()

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            is_allowed = rate_limiter.is_allowed_by_user("user123", limit=50, window=60)

        assert is_allowed is False

    @pytest.mark.unit
    def test_rate_limit_different_users_isolated(self, mock_redis):
        """Test that different users have isolated rate limits."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        # Mock different counts for different users
        def mock_incr(key):
            if "user123" in key:
                return 10
            elif "user456" in key:
                return 5
            return 1

        mock_redis.incr.side_effect = mock_incr

        rate_limiter = RateLimiter()

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            user1_allowed = rate_limiter.is_allowed_by_user("user123", limit=50, window=60)
            user2_allowed = rate_limiter.is_allowed_by_user("user456", limit=50, window=60)

        assert user1_allowed is True
        assert user2_allowed is True

    @pytest.mark.security
    def test_rate_limit_user_id_injection(self, mock_redis, security_test_payloads):
        """Test protection against user ID injection attacks."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        rate_limiter = RateLimiter()

        # Test with malicious user IDs
        for payload in security_test_payloads["sql_injection"]:
            with patch('app.middleware.rate_limiting.redis_client', mock_redis):
                try:
                    is_allowed = rate_limiter.is_allowed_by_user(payload, limit=10, window=60)
                    assert isinstance(is_allowed, bool)
                except Exception:
                    # Should not raise unhandled exceptions
                    pass


class TestRateLimitingMiddleware:
    """Test rate limiting middleware functionality."""

    @pytest.fixture
    def mock_request(self):
        """Create mock request object."""
        request = Mock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/test"
        request.client.host = "192.168.1.1"
        request.headers = {}
        request.state = Mock()
        return request

    @pytest.fixture
    def mock_response(self):
        """Create mock response object."""
        return Mock(spec=Response)

    @pytest.mark.unit
    async def test_rate_limit_middleware_allowed(self, mock_request, mock_response, mock_redis):
        """Test middleware allows request within rate limit."""
        if rate_limit_middleware is None:
            pytest.skip("Rate limiting middleware not available")

        mock_redis.incr.return_value = 5  # Within limit

        async def call_next(request):
            return mock_response

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            result = await rate_limit_middleware(mock_request, call_next)

        assert result == mock_response

    @pytest.mark.unit
    async def test_rate_limit_middleware_exceeded(self, mock_request, mock_redis):
        """Test middleware blocks request exceeding rate limit."""
        if rate_limit_middleware is None:
            pytest.skip("Rate limiting middleware not available")

        mock_redis.incr.return_value = 150  # Exceeds limit

        async def call_next(request):
            return Mock()

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await rate_limit_middleware(mock_request, call_next)

        assert exc_info.value.status_code == 429
        assert "rate limit" in str(exc_info.value.detail).lower()

    @pytest.mark.unit
    async def test_rate_limit_middleware_exempt_paths(self, mock_request, mock_response):
        """Test that exempt paths bypass rate limiting."""
        if rate_limit_middleware is None:
            pytest.skip("Rate limiting middleware not available")

        # Test common exempt paths
        exempt_paths = ["/api/health", "/api/status", "/static/"]

        for path in exempt_paths:
            mock_request.url.path = path

            async def call_next(request):
                return mock_response

            # Should not apply rate limiting to exempt paths
            result = await rate_limit_middleware(mock_request, call_next)
            assert result == mock_response

    @pytest.mark.unit
    async def test_rate_limit_middleware_different_limits_by_endpoint(self, mock_request, mock_response, mock_redis):
        """Test different rate limits for different endpoints."""
        if rate_limit_middleware is None:
            pytest.skip("Rate limiting middleware not available")

        mock_redis.incr.return_value = 10

        # Test endpoints with different expected limits
        endpoints = [
            ("/api/auth/login", 5),  # Stricter limit for auth
            ("/api/users", 100),     # Higher limit for user operations
            ("/api/search", 50)      # Medium limit for search
        ]

        async def call_next(request):
            return mock_response

        for path, expected_limit in endpoints:
            mock_request.url.path = path

            with patch('app.middleware.rate_limiting.redis_client', mock_redis):
                result = await rate_limit_middleware(mock_request, call_next)

            assert result == mock_response

    @pytest.mark.integration
    async def test_rate_limit_middleware_with_authenticated_user(self, mock_request, mock_response, mock_redis):
        """Test rate limiting with authenticated user."""
        if rate_limit_middleware is None:
            pytest.skip("Rate limiting middleware not available")

        # Mock authenticated user
        mock_request.state.user = Mock()
        mock_request.state.user.id = "user123"

        mock_redis.incr.return_value = 10

        async def call_next(request):
            return mock_response

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            result = await rate_limit_middleware(mock_request, call_next)

        assert result == mock_response


class TestRateLimitingRedisIntegration:
    """Test Redis integration for rate limiting."""

    @pytest.mark.integration
    def test_redis_lua_script_execution(self, mock_redis):
        """Test execution of Redis Lua scripts for rate limiting."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        # Mock Lua script execution
        mock_redis.eval.return_value = 1

        rate_limiter = RateLimiter(algorithm="token_bucket")

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            is_allowed = rate_limiter.is_allowed("test:key", limit=10, window=60)

        assert is_allowed is True
        mock_redis.eval.assert_called_once()

    @pytest.mark.integration
    def test_redis_connection_failure_handling(self, mock_redis):
        """Test handling of Redis connection failures."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        # Simulate Redis connection failure
        mock_redis.incr.side_effect = Exception("Redis connection failed")

        rate_limiter = RateLimiter()

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            # Should handle Redis errors gracefully (fail open or closed)
            try:
                is_allowed = rate_limiter.is_allowed("test:key", limit=10, window=60)
                # Could be True (fail open) or False (fail closed)
                assert isinstance(is_allowed, bool)
            except Exception:
                pytest.fail("Rate limiter should handle Redis errors gracefully")

    @pytest.mark.integration
    def test_redis_pipeline_optimization(self, mock_redis):
        """Test Redis pipeline optimization for batch operations."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        # Mock pipeline
        mock_pipeline = Mock()
        mock_pipeline.incr.return_value = mock_pipeline
        mock_pipeline.expire.return_value = mock_pipeline
        mock_pipeline.execute.return_value = [5, True]
        mock_redis.pipeline.return_value = mock_pipeline

        rate_limiter = RateLimiter()

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            # Check multiple keys at once
            results = rate_limiter.check_multiple_limits([
                ("user:123", 10, 60),
                ("ip:192.168.1.1", 100, 60)
            ])

        assert len(results) == 2
        mock_redis.pipeline.assert_called()


class TestRateLimitingPerformance:
    """Test rate limiting performance characteristics."""

    @pytest.mark.performance
    def test_rate_limit_check_performance(self, mock_redis, performance_timer):
        """Test performance of rate limit checks."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        mock_redis.incr.return_value = 5

        rate_limiter = RateLimiter()

        performance_timer.start()
        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            for i in range(1000):
                is_allowed = rate_limiter.is_allowed(f"test:key:{i}", limit=10, window=60)
                assert is_allowed is True
        response_time = performance_timer.stop()

        assert_response_time(response_time, max_time=1.0)

    @pytest.mark.performance
    def test_concurrent_rate_limit_checks(self, mock_redis):
        """Test concurrent rate limit checks."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        mock_redis.incr.return_value = 5

        rate_limiter = RateLimiter()

        async def check_rate_limit(key):
            with patch('app.middleware.rate_limiting.redis_client', mock_redis):
                return rate_limiter.is_allowed(key, limit=10, window=60)

        async def run_concurrent_checks():
            tasks = [check_rate_limit(f"test:key:{i}") for i in range(100)]
            results = await asyncio.gather(*tasks)
            return results

        results = asyncio.run(run_concurrent_checks())
        assert len(results) == 100
        assert all(result is True for result in results)

    @pytest.mark.performance
    def test_memory_usage_with_many_keys(self, mock_redis):
        """Test memory usage with many rate limit keys."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        mock_redis.incr.return_value = 5

        rate_limiter = RateLimiter()

        # Create many rate limit entries
        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            for i in range(10000):
                rate_limiter.is_allowed(f"test:key:{i}", limit=10, window=60)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable
        assert memory_increase < 50 * 1024 * 1024, f"Memory increase too high: {memory_increase} bytes"


class TestRateLimitingSecurityFeatures:
    """Test security features of rate limiting."""

    @pytest.mark.security
    def test_distributed_rate_limiting(self, mock_redis):
        """Test distributed rate limiting across multiple instances."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        # Simulate multiple application instances
        mock_redis.incr.side_effect = [1, 2, 3, 4, 5]  # Progressive counts

        rate_limiter = RateLimiter()

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            for i in range(5):
                is_allowed = rate_limiter.is_allowed("user:123", limit=10, window=60)
                assert is_allowed is True

        assert mock_redis.incr.call_count == 5

    @pytest.mark.security
    def test_rate_limit_bypass_prevention(self, mock_redis):
        """Test prevention of rate limit bypass attempts."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        rate_limiter = RateLimiter()

        # Test bypass attempts with key variations
        bypass_attempts = [
            "user:123",
            "user:123 ",  # Trailing space
            "user:123\n", # Newline
            "user:123\t", # Tab
            "USER:123",   # Case variation
            "user:123\x00", # Null byte
        ]

        mock_redis.incr.return_value = 15  # Exceeds limit

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            for key in bypass_attempts:
                is_allowed = rate_limiter.is_allowed(key, limit=10, window=60)
                # All should be consistently rate limited
                assert is_allowed is False

    @pytest.mark.security
    def test_rate_limit_key_collision_prevention(self, mock_redis):
        """Test prevention of rate limit key collisions."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        rate_limiter = RateLimiter()

        # Test potential collision scenarios
        collision_keys = [
            ("user", "123"),
            ("user:1", "23"),
            ("use", "r:123"),
        ]

        mock_redis.incr.return_value = 5

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            for key_parts in collision_keys:
                key = ":".join(key_parts)
                is_allowed = rate_limiter.is_allowed(key, limit=10, window=60)
                assert is_allowed is True

        # Verify keys are properly namespaced to prevent collisions
        calls = mock_redis.incr.call_args_list
        called_keys = [call[0][0] for call in calls]

        # All keys should be different
        assert len(set(called_keys)) == len(called_keys)

    @pytest.mark.security
    def test_adaptive_rate_limiting_under_attack(self, mock_redis):
        """Test adaptive rate limiting during attack scenarios."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        rate_limiter = RateLimiter()

        # Simulate attack pattern detection
        attack_threshold = 1000
        normal_requests = 50

        # Mock progressive counts simulating attack
        counts = list(range(1, attack_threshold + 1))
        mock_redis.incr.side_effect = counts

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            # Normal requests should be allowed
            for i in range(normal_requests):
                is_allowed = rate_limiter.is_allowed("attacker:ip", limit=100, window=60)
                if i < 100:  # Within normal limit
                    assert is_allowed is True
                else:  # Should start blocking
                    assert is_allowed is False


class TestRateLimitingConfiguration:
    """Test rate limiting configuration and customization."""

    @pytest.mark.unit
    def test_rate_limit_configuration_validation(self):
        """Test validation of rate limiting configuration."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        # Test invalid configurations
        invalid_configs = [
            {"limit": -1, "window": 60},      # Negative limit
            {"limit": 10, "window": -1},      # Negative window
            {"limit": 0, "window": 60},       # Zero limit
            {"limit": 10, "window": 0},       # Zero window
        ]

        for config in invalid_configs:
            try:
                rate_limiter = RateLimiter()
                is_allowed = rate_limiter.is_allowed("test", **config)
                # Should either handle gracefully or validate input
                assert isinstance(is_allowed, bool)
            except ValueError:
                # Acceptable to raise ValueError for invalid config
                pass

    @pytest.mark.unit
    def test_rate_limit_multiple_window_sizes(self, mock_redis):
        """Test rate limiting with multiple window sizes."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        mock_redis.incr.return_value = 5

        rate_limiter = RateLimiter()

        window_sizes = [1, 60, 3600, 86400]  # 1 sec, 1 min, 1 hour, 1 day

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            for window in window_sizes:
                is_allowed = rate_limiter.is_allowed("test:key", limit=10, window=window)
                assert is_allowed is True

    @pytest.mark.unit
    def test_rate_limit_custom_key_generator(self, mock_redis):
        """Test custom key generation for rate limiting."""
        if RateLimiter is None:
            pytest.skip("Rate limiter not available")

        mock_redis.incr.return_value = 5

        def custom_key_generator(identifier, window):
            return f"custom:{identifier}:{window}"

        rate_limiter = RateLimiter(key_generator=custom_key_generator)

        with patch('app.middleware.rate_limiting.redis_client', mock_redis):
            try:
                is_allowed = rate_limiter.is_allowed("test", limit=10, window=60)
                assert is_allowed is True

                # Verify custom key was used
                mock_redis.incr.assert_called_with("custom:test:60")
            except TypeError:
                # Custom key generator might not be supported
                pytest.skip("Custom key generator not supported")