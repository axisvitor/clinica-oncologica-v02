"""
Comprehensive tests for Rate Limiting Middleware.
"""
import pytest
import time
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request, HTTPException, status
from starlette.types import ASGIApp

from app.middleware.rate_limit import RateLimitMiddleware


@pytest.fixture
def mock_app():
    """Mock ASGI application."""
    return Mock(spec=ASGIApp)


@pytest.fixture
def mock_request():
    """Mock HTTP request."""
    request = Mock(spec=Request)
    request.headers = {}
    request.client = Mock()
    request.client.host = "127.0.0.1"
    return request


@pytest.fixture
def mock_response():
    """Mock HTTP response."""
    response = Mock()
    response.headers = {}
    return response


@pytest.fixture
async def mock_call_next(mock_response):
    """Mock call_next function."""
    async def call_next(request):
        return mock_response
    return call_next


class TestRateLimitMiddleware:
    """Test RateLimitMiddleware functionality."""

    def test_init_default_values(self, mock_app):
        """Test middleware initialization with default values."""
        middleware = RateLimitMiddleware(mock_app)

        assert middleware.app == mock_app
        assert middleware.requests_per_minute == 60
        assert middleware.window_seconds == 60
        assert middleware.request_store == {}

    def test_init_custom_values(self, mock_app):
        """Test middleware initialization with custom values."""
        middleware = RateLimitMiddleware(
            mock_app,
            requests_per_minute=100,
            window_seconds=120
        )

        assert middleware.requests_per_minute == 100
        assert middleware.window_seconds == 120
        assert middleware.request_store == {}

    def test_get_client_ip_from_client(self, mock_app, mock_request):
        """Test getting client IP from request.client."""
        middleware = RateLimitMiddleware(mock_app)
        mock_request.client.host = "192.168.1.100"

        ip = middleware._get_client_ip(mock_request)
        assert ip == "192.168.1.100"

    def test_get_client_ip_x_forwarded_for(self, mock_app, mock_request):
        """Test getting client IP from X-Forwarded-For header."""
        middleware = RateLimitMiddleware(mock_app)
        mock_request.headers = {"X-Forwarded-For": "203.0.113.1, 198.51.100.2"}

        ip = middleware._get_client_ip(mock_request)
        assert ip == "203.0.113.1"

    def test_get_client_ip_x_real_ip(self, mock_app, mock_request):
        """Test getting client IP from X-Real-IP header."""
        middleware = RateLimitMiddleware(mock_app)
        mock_request.headers = {"X-Real-IP": "203.0.113.2"}

        ip = middleware._get_client_ip(mock_request)
        assert ip == "203.0.113.2"

    def test_get_client_ip_forwarded_for_priority(self, mock_app, mock_request):
        """Test X-Forwarded-For takes priority over X-Real-IP."""
        middleware = RateLimitMiddleware(mock_app)
        mock_request.headers = {
            "X-Forwarded-For": "203.0.113.1",
            "X-Real-IP": "203.0.113.2"
        }

        ip = middleware._get_client_ip(mock_request)
        assert ip == "203.0.113.1"

    def test_get_client_ip_no_client(self, mock_app, mock_request):
        """Test getting client IP when request.client is None."""
        middleware = RateLimitMiddleware(mock_app)
        mock_request.client = None

        ip = middleware._get_client_ip(mock_request)
        assert ip == "unknown"

    def test_get_client_ip_forwarded_for_whitespace(self, mock_app, mock_request):
        """Test X-Forwarded-For header with whitespace."""
        middleware = RateLimitMiddleware(mock_app)
        mock_request.headers = {"X-Forwarded-For": " 203.0.113.1 , 198.51.100.2 "}

        ip = middleware._get_client_ip(mock_request)
        assert ip == "203.0.113.1"

    def test_is_request_allowed_new_ip(self, mock_app):
        """Test request allowed for new IP."""
        middleware = RateLimitMiddleware(mock_app)

        assert middleware._is_request_allowed("127.0.0.1") is True

    def test_is_request_allowed_under_limit(self, mock_app):
        """Test request allowed when under limit."""
        middleware = RateLimitMiddleware(mock_app, requests_per_minute=5)
        ip = "127.0.0.1"

        # Add some requests but stay under limit
        middleware.request_store[ip] = [time.time()] * 4

        assert middleware._is_request_allowed(ip) is True

    def test_is_request_allowed_at_limit(self, mock_app):
        """Test request blocked when at limit."""
        middleware = RateLimitMiddleware(mock_app, requests_per_minute=5)
        ip = "127.0.0.1"

        # Add requests at the limit
        middleware.request_store[ip] = [time.time()] * 5

        assert middleware._is_request_allowed(ip) is False

    def test_is_request_allowed_over_limit(self, mock_app):
        """Test request blocked when over limit."""
        middleware = RateLimitMiddleware(mock_app, requests_per_minute=5)
        ip = "127.0.0.1"

        # Add requests over the limit
        middleware.request_store[ip] = [time.time()] * 6

        assert middleware._is_request_allowed(ip) is False

    def test_record_request_new_ip(self, mock_app):
        """Test recording request for new IP."""
        middleware = RateLimitMiddleware(mock_app)
        ip = "127.0.0.1"

        middleware._record_request(ip)

        assert ip in middleware.request_store
        assert len(middleware.request_store[ip]) == 1
        assert isinstance(middleware.request_store[ip][0], float)

    def test_record_request_existing_ip(self, mock_app):
        """Test recording request for existing IP."""
        middleware = RateLimitMiddleware(mock_app)
        ip = "127.0.0.1"

        # Add initial request
        middleware.request_store[ip] = [time.time() - 10]

        middleware._record_request(ip)

        assert len(middleware.request_store[ip]) == 2

    def test_cleanup_old_requests_no_ip(self, mock_app):
        """Test cleanup with IP not in store."""
        middleware = RateLimitMiddleware(mock_app)

        # Should not raise exception
        middleware._cleanup_old_requests("127.0.0.1")

    def test_cleanup_old_requests_recent(self, mock_app):
        """Test cleanup keeps recent requests."""
        middleware = RateLimitMiddleware(mock_app, window_seconds=60)
        ip = "127.0.0.1"
        current_time = time.time()

        # Add recent requests
        middleware.request_store[ip] = [
            current_time - 10,  # 10 seconds ago
            current_time - 30,  # 30 seconds ago
            current_time - 50   # 50 seconds ago
        ]

        middleware._cleanup_old_requests(ip)

        assert len(middleware.request_store[ip]) == 3

    def test_cleanup_old_requests_expired(self, mock_app):
        """Test cleanup removes expired requests."""
        middleware = RateLimitMiddleware(mock_app, window_seconds=60)
        ip = "127.0.0.1"
        current_time = time.time()

        # Add mix of recent and old requests
        middleware.request_store[ip] = [
            current_time - 10,  # 10 seconds ago (keep)
            current_time - 70,  # 70 seconds ago (remove)
            current_time - 30,  # 30 seconds ago (keep)
            current_time - 90   # 90 seconds ago (remove)
        ]

        middleware._cleanup_old_requests(ip)

        assert len(middleware.request_store[ip]) == 2

    def test_cleanup_old_requests_all_expired(self, mock_app):
        """Test cleanup removes IP when all requests expired."""
        middleware = RateLimitMiddleware(mock_app, window_seconds=60)
        ip = "127.0.0.1"
        current_time = time.time()

        # Add only old requests
        middleware.request_store[ip] = [
            current_time - 70,  # 70 seconds ago
            current_time - 90   # 90 seconds ago
        ]

        middleware._cleanup_old_requests(ip)

        assert ip not in middleware.request_store

    @pytest.mark.asyncio
    async def test_dispatch_first_request(self, mock_app, mock_request, mock_call_next):
        """Test first request for an IP is allowed."""
        middleware = RateLimitMiddleware(mock_app)

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response is not None
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_dispatch_rate_limit_headers(self, mock_app, mock_request, mock_call_next):
        """Test rate limit headers are added to response."""
        middleware = RateLimitMiddleware(mock_app, requests_per_minute=10)

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["X-RateLimit-Limit"] == "10"
        assert response.headers["X-RateLimit-Remaining"] == "9"  # After first request
        assert int(response.headers["X-RateLimit-Reset"]) > time.time()

    @pytest.mark.asyncio
    async def test_dispatch_rate_limit_exceeded(self, mock_app, mock_request, mock_call_next):
        """Test rate limit exceeded raises HTTPException."""
        middleware = RateLimitMiddleware(mock_app, requests_per_minute=2)
        ip = "127.0.0.1"

        # Pre-populate with requests at limit
        middleware.request_store[ip] = [time.time()] * 2

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(mock_request, mock_call_next)

        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "Rate limit exceeded" in exc_info.value.detail
        assert exc_info.value.headers["Retry-After"] == "60"

    @pytest.mark.asyncio
    async def test_dispatch_remaining_count_decreases(self, mock_app, mock_request, mock_call_next):
        """Test remaining count decreases with each request."""
        middleware = RateLimitMiddleware(mock_app, requests_per_minute=5)

        # First request
        response1 = await middleware.dispatch(mock_request, mock_call_next)
        assert response1.headers["X-RateLimit-Remaining"] == "4"

        # Second request
        response2 = await middleware.dispatch(mock_request, mock_call_next)
        assert response2.headers["X-RateLimit-Remaining"] == "3"

    @pytest.mark.asyncio
    async def test_dispatch_cleanup_called(self, mock_app, mock_request, mock_call_next):
        """Test cleanup is called during dispatch."""
        middleware = RateLimitMiddleware(mock_app)

        with patch.object(middleware, '_cleanup_old_requests') as mock_cleanup:
            await middleware.dispatch(mock_request, mock_call_next)
            mock_cleanup.assert_called_once_with("127.0.0.1")

    @pytest.mark.asyncio
    async def test_dispatch_different_ips_independent(self, mock_app, mock_call_next):
        """Test different IPs have independent rate limits."""
        middleware = RateLimitMiddleware(mock_app, requests_per_minute=2)

        # Create requests from different IPs
        request1 = Mock(spec=Request)
        request1.headers = {}
        request1.client = Mock()
        request1.client.host = "127.0.0.1"

        request2 = Mock(spec=Request)
        request2.headers = {}
        request2.client = Mock()
        request2.client.host = "192.168.1.100"

        # Both should be allowed initially
        response1 = await middleware.dispatch(request1, mock_call_next)
        response2 = await middleware.dispatch(request2, mock_call_next)

        assert response1 is not None
        assert response2 is not None

    @pytest.mark.asyncio
    @patch('app.middleware.rate_limit.logger')
    async def test_dispatch_logs_rate_limit_exceeded(self, mock_logger, mock_app, mock_request, mock_call_next):
        """Test that rate limit exceeded is logged."""
        middleware = RateLimitMiddleware(mock_app, requests_per_minute=1)
        ip = "127.0.0.1"

        # Pre-populate with request at limit
        middleware.request_store[ip] = [time.time()]

        with pytest.raises(HTTPException):
            await middleware.dispatch(mock_request, mock_call_next)

        mock_logger.warning.assert_called_once()
        assert "Rate limit exceeded for IP: 127.0.0.1" in mock_logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_dispatch_preserves_response_content(self, mock_app, mock_request):
        """Test that response content is preserved."""
        middleware = RateLimitMiddleware(mock_app)
        original_content = {"message": "success"}

        async def call_next_with_content(request):
            response = Mock()
            response.headers = {}
            response.content = original_content
            return response

        response = await middleware.dispatch(mock_request, call_next_with_content)

        assert response.content == original_content
        assert "X-RateLimit-Limit" in response.headers

    def test_window_seconds_configuration(self, mock_app):
        """Test custom window seconds configuration."""
        middleware = RateLimitMiddleware(mock_app, window_seconds=120)
        ip = "127.0.0.1"
        current_time = time.time()

        # Add request just within custom window
        middleware.request_store[ip] = [current_time - 110]

        middleware._cleanup_old_requests(ip)

        # Should still be there with 120 second window
        assert len(middleware.request_store[ip]) == 1

        # Add request just outside custom window
        middleware.request_store[ip] = [current_time - 130]

        middleware._cleanup_old_requests(ip)

        # Should be removed
        assert ip not in middleware.request_store

    @pytest.mark.asyncio
    async def test_reset_header_accuracy(self, mock_app, mock_request, mock_call_next):
        """Test that reset header has reasonable accuracy."""
        middleware = RateLimitMiddleware(mock_app, window_seconds=60)
        current_time = time.time()

        with patch('time.time', return_value=current_time):
            response = await middleware.dispatch(mock_request, mock_call_next)

        reset_time = int(response.headers["X-RateLimit-Reset"])
        expected_reset = current_time + 60

        # Should be within 1 second of expected
        assert abs(reset_time - expected_reset) <= 1

    def test_remaining_calculation_edge_cases(self, mock_app):
        """Test remaining count calculation edge cases."""
        middleware = RateLimitMiddleware(mock_app, requests_per_minute=5)
        ip = "127.0.0.1"

        # Empty store
        assert ip not in middleware.request_store
        remaining = max(0, middleware.requests_per_minute - len(middleware.request_store.get(ip, [])))
        assert remaining == 5

        # At limit
        middleware.request_store[ip] = [time.time()] * 5
        remaining = max(0, middleware.requests_per_minute - len(middleware.request_store.get(ip, [])))
        assert remaining == 0

        # Over limit (shouldn't happen in normal operation, but test defensive programming)
        middleware.request_store[ip] = [time.time()] * 6
        remaining = max(0, middleware.requests_per_minute - len(middleware.request_store.get(ip, [])))
        assert remaining == 0  # max(0, -1) = 0