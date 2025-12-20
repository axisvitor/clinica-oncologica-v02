"""
Unit tests for webhook rate limiting (HIGH-001 FIX).

Tests multi-layer rate limiting functionality:
- Global rate limiting (1000 req/min)
- Per-phone rate limiting (100 req/min)
- Redis integration
- Error responses
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request, HTTPException
from app.utils.rate_limiter import (
    multi_layer_rate_limit,
    check_rate_limit_redis,
)


class TestRedisRateLimiting:
    """Test Redis-based rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_check_rate_limit_redis_under_limit(self):
        """Test rate limit check when under the limit."""
        # Mock Redis client
        redis_client = AsyncMock()
        redis_client.pipeline.return_value = redis_pipeline = AsyncMock()
        redis_pipeline.execute.return_value = [None, None, 5, None]  # 5 requests

        allowed, retry_after = await check_rate_limit_redis(
            key="test:key",
            max_requests=10,
            window_seconds=60,
            redis_client=redis_client
        )

        assert allowed is True
        assert retry_after == 0
        redis_client.pipeline.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_rate_limit_redis_over_limit(self):
        """Test rate limit check when over the limit."""
        # Mock Redis client
        redis_client = AsyncMock()
        redis_client.pipeline.return_value = redis_pipeline = AsyncMock()
        redis_pipeline.execute.return_value = [None, None, 15, None]  # 15 requests

        allowed, retry_after = await check_rate_limit_redis(
            key="test:key",
            max_requests=10,
            window_seconds=60,
            redis_client=redis_client
        )

        assert allowed is False
        assert retry_after == 60

    @pytest.mark.asyncio
    async def test_check_rate_limit_redis_unavailable(self):
        """Test rate limit fails open when Redis is unavailable."""
        allowed, retry_after = await check_rate_limit_redis(
            key="test:key",
            max_requests=10,
            window_seconds=60,
            redis_client=None
        )

        # Should fail open (allow request)
        assert allowed is True
        assert retry_after == 0

    @pytest.mark.asyncio
    async def test_check_rate_limit_redis_error(self):
        """Test rate limit fails open on Redis error."""
        # Mock Redis client that raises error
        redis_client = AsyncMock()
        redis_client.pipeline.side_effect = Exception("Redis error")

        allowed, retry_after = await check_rate_limit_redis(
            key="test:key",
            max_requests=10,
            window_seconds=60,
            redis_client=redis_client
        )

        # Should fail open (allow request)
        assert allowed is True
        assert retry_after == 0


class TestMultiLayerRateLimiting:
    """Test multi-layer rate limiting decorator."""

    @pytest.mark.asyncio
    async def test_multi_layer_under_global_limit(self):
        """Test request passes when under global limit."""
        # Mock function to decorate
        async def mock_endpoint(request: Request):
            return {"status": "ok"}

        # Mock request
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/webhooks/inbound"
        mock_request.json = AsyncMock(return_value={
            "data": {"key": {"remoteJid": "5511999999999@s.whatsapp.net"}}
        })

        # Apply decorator
        decorated = multi_layer_rate_limit(
            global_limit=1000,
            identifier_limit=100
        )(mock_endpoint)

        # Mock Redis to allow request
        with patch('app.utils.rate_limiter.get_redis_client') as mock_redis:
            redis_client = AsyncMock()
            redis_client.pipeline.return_value = redis_pipeline = AsyncMock()
            # Global: 5 requests, Phone: 2 requests (both under limit)
            redis_pipeline.execute.side_effect = [
                [None, None, 5, None],    # Global check
                [None, None, 2, None],    # Phone check
            ]
            redis_client.close = AsyncMock()
            mock_redis.return_value = redis_client

            result = await decorated(mock_request)

        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_multi_layer_over_global_limit(self):
        """Test request blocked when over global limit."""
        async def mock_endpoint(request: Request):
            return {"status": "ok"}

        mock_request = Mock(spec=Request)
        mock_request.url.path = "/webhooks/inbound"
        mock_request.json = AsyncMock(return_value={
            "data": {"key": {"remoteJid": "5511999999999@s.whatsapp.net"}}
        })

        decorated = multi_layer_rate_limit(
            global_limit=1000,
            identifier_limit=100
        )(mock_endpoint)

        with patch('app.utils.rate_limiter.get_redis_client') as mock_redis:
            redis_client = AsyncMock()
            redis_client.pipeline.return_value = redis_pipeline = AsyncMock()
            # Global: 1500 requests (over limit)
            redis_pipeline.execute.return_value = [None, None, 1500, None]
            redis_client.close = AsyncMock()
            mock_redis.return_value = redis_client

            with pytest.raises(HTTPException) as exc_info:
                await decorated(mock_request)

        assert exc_info.value.status_code == 429
        assert "Global rate limit exceeded" in str(exc_info.value.detail)
        assert "Retry-After" in exc_info.value.headers

    @pytest.mark.asyncio
    async def test_multi_layer_over_phone_limit(self):
        """Test request blocked when over per-phone limit."""
        async def mock_endpoint(request: Request):
            return {"status": "ok"}

        mock_request = Mock(spec=Request)
        mock_request.url.path = "/webhooks/inbound"
        mock_request.json = AsyncMock(return_value={
            "data": {"key": {"remoteJid": "5511999999999@s.whatsapp.net"}}
        })

        decorated = multi_layer_rate_limit(
            global_limit=1000,
            identifier_limit=100
        )(mock_endpoint)

        with patch('app.utils.rate_limiter.get_redis_client') as mock_redis:
            redis_client = AsyncMock()
            redis_client.pipeline.return_value = redis_pipeline = AsyncMock()
            # Global: 500 requests (under), Phone: 150 requests (over)
            redis_pipeline.execute.side_effect = [
                [None, None, 500, None],   # Global check (pass)
                [None, None, 150, None],   # Phone check (fail)
            ]
            redis_client.close = AsyncMock()
            mock_redis.return_value = redis_client

            with pytest.raises(HTTPException) as exc_info:
                await decorated(mock_request)

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded for this phone number" in str(exc_info.value.detail)
        assert exc_info.value.headers["X-RateLimit-Scope"] == "phone"

    @pytest.mark.asyncio
    async def test_multi_layer_phone_extraction(self):
        """Test phone number extraction from different webhook formats."""
        async def mock_endpoint(request: Request):
            return {"status": "ok"}

        # Test various webhook payload formats
        test_cases = [
            {
                "data": {"key": {"remoteJid": "5511999999999@s.whatsapp.net"}},
                "expected_phone": "5511999999999"
            },
            {
                "phone": "5511888888888",
                "expected_phone": "5511888888888"
            },
            {
                "data": {"phone": "5511777777777"},
                "expected_phone": None  # Not in expected path
            },
        ]

        for test_case in test_cases:
            mock_request = Mock(spec=Request)
            mock_request.url.path = "/webhooks/inbound"
            mock_request.json = AsyncMock(return_value=test_case)

            decorated = multi_layer_rate_limit(
                global_limit=1000,
                identifier_limit=100,
                identifier_key="data.key.remoteJid"
            )(mock_endpoint)

            with patch('app.utils.rate_limiter.get_redis_client') as mock_redis:
                redis_client = AsyncMock()
                redis_client.pipeline.return_value = redis_pipeline = AsyncMock()
                redis_pipeline.execute.return_value = [None, None, 5, None]
                redis_client.close = AsyncMock()
                mock_redis.return_value = redis_client

                result = await decorated(mock_request)

            assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_multi_layer_no_redis(self):
        """Test decorator fails open when Redis unavailable."""
        async def mock_endpoint(request: Request):
            return {"status": "ok"}

        mock_request = Mock(spec=Request)
        mock_request.url.path = "/webhooks/inbound"
        mock_request.json = AsyncMock(return_value={
            "data": {"key": {"remoteJid": "5511999999999@s.whatsapp.net"}}
        })

        decorated = multi_layer_rate_limit()(mock_endpoint)

        with patch('app.utils.rate_limiter.get_redis_client', return_value=None):
            result = await decorated(mock_request)

        # Should fail open (allow request)
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_multi_layer_malformed_payload(self):
        """Test decorator handles malformed payloads gracefully."""
        async def mock_endpoint(request: Request):
            return {"status": "ok"}

        mock_request = Mock(spec=Request)
        mock_request.url.path = "/webhooks/inbound"
        mock_request.json = AsyncMock(side_effect=Exception("Invalid JSON"))

        decorated = multi_layer_rate_limit()(mock_endpoint)

        with patch('app.utils.rate_limiter.get_redis_client') as mock_redis:
            redis_client = AsyncMock()
            redis_client.pipeline.return_value = redis_pipeline = AsyncMock()
            redis_pipeline.execute.return_value = [None, None, 5, None]
            redis_client.close = AsyncMock()
            mock_redis.return_value = redis_client

            result = await decorated(mock_request)

        # Should allow request (only global limit checked)
        assert result == {"status": "ok"}


class TestRateLimitHeaders:
    """Test rate limit response headers."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers_global(self):
        """Test global rate limit headers are correct."""
        async def mock_endpoint(request: Request):
            return {"status": "ok"}

        mock_request = Mock(spec=Request)
        mock_request.url.path = "/webhooks/inbound"
        mock_request.json = AsyncMock(return_value={})

        decorated = multi_layer_rate_limit(
            global_limit=1000,
            global_window=60
        )(mock_endpoint)

        with patch('app.utils.rate_limiter.get_redis_client') as mock_redis:
            redis_client = AsyncMock()
            redis_client.pipeline.return_value = redis_pipeline = AsyncMock()
            redis_pipeline.execute.return_value = [None, None, 1500, None]
            redis_client.close = AsyncMock()
            mock_redis.return_value = redis_client

            with pytest.raises(HTTPException) as exc_info:
                await decorated(mock_request)

        headers = exc_info.value.headers
        assert headers["X-RateLimit-Limit"] == "1000"
        assert headers["X-RateLimit-Remaining"] == "0"
        assert headers["X-RateLimit-Scope"] == "global"
        assert "X-RateLimit-Reset" in headers
        assert headers["Retry-After"] == "60"

    @pytest.mark.asyncio
    async def test_rate_limit_headers_phone(self):
        """Test per-phone rate limit headers are correct."""
        async def mock_endpoint(request: Request):
            return {"status": "ok"}

        mock_request = Mock(spec=Request)
        mock_request.url.path = "/webhooks/inbound"
        mock_request.json = AsyncMock(return_value={
            "data": {"key": {"remoteJid": "5511999999999@s.whatsapp.net"}}
        })

        decorated = multi_layer_rate_limit(
            global_limit=1000,
            identifier_limit=100,
            identifier_window=60
        )(mock_endpoint)

        with patch('app.utils.rate_limiter.get_redis_client') as mock_redis:
            redis_client = AsyncMock()
            redis_client.pipeline.return_value = redis_pipeline = AsyncMock()
            redis_pipeline.execute.side_effect = [
                [None, None, 500, None],   # Global (pass)
                [None, None, 150, None],   # Phone (fail)
            ]
            redis_client.close = AsyncMock()
            mock_redis.return_value = redis_client

            with pytest.raises(HTTPException) as exc_info:
                await decorated(mock_request)

        headers = exc_info.value.headers
        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Remaining"] == "0"
        assert headers["X-RateLimit-Scope"] == "phone"
        assert headers["Retry-After"] == "60"


class TestRateLimitIntegration:
    """Integration tests for rate limiting."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_global_limit(self):
        """Test concurrent requests respect global limit."""
        async def mock_endpoint(request: Request):
            return {"status": "ok"}

        decorated = multi_layer_rate_limit(
            global_limit=10,  # Low limit for testing
            identifier_limit=5
        )(mock_endpoint)

        # Simulate multiple concurrent requests
        with patch('app.utils.rate_limiter.get_redis_client') as mock_redis:
            redis_client = AsyncMock()
            redis_client.pipeline.return_value = redis_pipeline = AsyncMock()
            redis_client.close = AsyncMock()

            request_count = 0

            async def mock_execute():
                nonlocal request_count
                request_count += 1
                return [None, None, request_count, None]

            redis_pipeline.execute = mock_execute
            mock_redis.return_value = redis_client

            # First 10 requests should succeed
            for i in range(10):
                mock_request = Mock(spec=Request)
                mock_request.url.path = f"/webhooks/test/{i}"
                mock_request.json = AsyncMock(return_value={})

                result = await decorated(mock_request)
                assert result == {"status": "ok"}

            # 11th request should fail
            mock_request = Mock(spec=Request)
            mock_request.url.path = "/webhooks/test/11"
            mock_request.json = AsyncMock(return_value={})

            with pytest.raises(HTTPException) as exc_info:
                await decorated(mock_request)

            assert exc_info.value.status_code == 429


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
