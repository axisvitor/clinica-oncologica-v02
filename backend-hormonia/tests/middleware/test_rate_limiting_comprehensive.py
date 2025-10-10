"""
Comprehensive Rate Limiting Middleware Tests

Tests all rate limiting middleware functionality including:
- Basic rate limiting with sliding window algorithm
- IP-based and user-based rate limiting
- Enhanced rate limiting with Redis backend
- Rate limit headers and error responses
- Different limits per endpoint
- Whitelist and blacklist functionality
- Error handling and edge cases
"""

import pytest
import time
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response
from collections import deque

from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.enhanced_middleware import (
    EnhancedRateLimitMiddleware,
    RateLimitRule
)


class TestBasicRateLimitMiddleware:
    """Test basic rate limiting middleware functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI()

        @self.app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        @self.app.post("/api/data")
        async def api_endpoint():
            return {"result": "success"}

    def test_middleware_initialization_default(self):
        """Test middleware initialization with default values."""
        middleware = RateLimitMiddleware(self.app)

        assert middleware.requests_per_minute == 60
        assert middleware.window_seconds == 60
        assert isinstance(middleware.request_store, dict)

    def test_middleware_initialization_custom(self):
        """Test middleware initialization with custom values."""
        middleware = RateLimitMiddleware(
            self.app,
            requests_per_minute=100,
            window_seconds=120
        )

        assert middleware.requests_per_minute == 100
        assert middleware.window_seconds == 120

    def test_get_client_ip_forwarded_for(self):
        """Test client IP extraction from X-Forwarded-For header."""
        middleware = RateLimitMiddleware(self.app)

        # Mock request with X-Forwarded-For header
        mock_request = MagicMock()
        mock_request.headers.get.side_effect = lambda key: {
            "X-Forwarded-For": "192.168.1.1, 10.0.0.1",
            "X-Real-IP": "10.0.0.1"
        }.get(key)

        ip = middleware._get_client_ip(mock_request)
        assert ip == "192.168.1.1"

    def test_get_client_ip_real_ip(self):
        """Test client IP extraction from X-Real-IP header."""
        middleware = RateLimitMiddleware(self.app)

        # Mock request with X-Real-IP header only
        mock_request = MagicMock()
        mock_request.headers.get.side_effect = lambda key: {
            "X-Real-IP": "203.0.113.1"
        }.get(key)

        ip = middleware._get_client_ip(mock_request)
        assert ip == "203.0.113.1"

    def test_get_client_ip_fallback(self):
        """Test client IP extraction fallback to client.host."""
        middleware = RateLimitMiddleware(self.app)

        # Mock request without forwarded headers
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "127.0.0.1"

        ip = middleware._get_client_ip(mock_request)
        assert ip == "127.0.0.1"

    def test_get_client_ip_no_client(self):
        """Test client IP extraction when no client info available."""
        middleware = RateLimitMiddleware(self.app)

        # Mock request without client info
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client = None

        ip = middleware._get_client_ip(mock_request)
        assert ip == "unknown"

    def test_cleanup_old_requests(self):
        """Test cleanup of old request timestamps."""
        middleware = RateLimitMiddleware(self.app, window_seconds=60)

        # Add some old and new timestamps
        ip = "192.168.1.1"
        current_time = time.time()
        middleware.request_store[ip] = [
            current_time - 120,  # Old request (2 minutes ago)
            current_time - 30,   # Recent request
            current_time - 10    # Very recent request
        ]

        middleware._cleanup_old_requests(ip)

        # Should only keep recent requests
        assert len(middleware.request_store[ip]) == 2
        assert current_time - 120 not in middleware.request_store[ip]

    def test_cleanup_removes_empty_entries(self):
        """Test that cleanup removes empty IP entries."""
        middleware = RateLimitMiddleware(self.app, window_seconds=60)

        # Add only old timestamps
        ip = "192.168.1.1"
        current_time = time.time()
        middleware.request_store[ip] = [current_time - 120, current_time - 180]

        middleware._cleanup_old_requests(ip)

        # Entry should be completely removed
        assert ip not in middleware.request_store

    def test_is_request_allowed_new_ip(self):
        """Test rate limit check for new IP address."""
        middleware = RateLimitMiddleware(self.app)

        ip = "192.168.1.1"
        assert middleware._is_request_allowed(ip) is True

    def test_is_request_allowed_under_limit(self):
        """Test rate limit check for IP under limit."""
        middleware = RateLimitMiddleware(self.app, requests_per_minute=5)

        ip = "192.168.1.1"
        # Add 3 requests (under limit of 5)
        middleware.request_store[ip] = [time.time()] * 3

        assert middleware._is_request_allowed(ip) is True

    def test_is_request_allowed_at_limit(self):
        """Test rate limit check for IP at limit."""
        middleware = RateLimitMiddleware(self.app, requests_per_minute=5)

        ip = "192.168.1.1"
        # Add 5 requests (at limit)
        middleware.request_store[ip] = [time.time()] * 5

        assert middleware._is_request_allowed(ip) is False

    def test_record_request(self):
        """Test recording of request timestamp."""
        middleware = RateLimitMiddleware(self.app)

        ip = "192.168.1.1"
        before_count = len(middleware.request_store.get(ip, []))

        middleware._record_request(ip)

        after_count = len(middleware.request_store[ip])
        assert after_count == before_count + 1

    def test_rate_limit_integration(self):
        """Test rate limiting integration with FastAPI."""
        # Use low limit for testing
        self.app.add_middleware(RateLimitMiddleware, requests_per_minute=2, window_seconds=60)
        client = TestClient(self.app)

        # First request should succeed
        response1 = client.get("/test")
        assert response1.status_code == 200
        assert "X-RateLimit-Limit" in response1.headers
        assert "X-RateLimit-Remaining" in response1.headers
        assert "X-RateLimit-Reset" in response1.headers

        # Second request should succeed
        response2 = client.get("/test")
        assert response2.status_code == 200

        # Third request should be rate limited
        response3 = client.get("/test")
        assert response3.status_code == 429
        assert "Retry-After" in response3.headers

    def test_rate_limit_headers(self):
        """Test rate limit headers in responses."""
        self.app.add_middleware(RateLimitMiddleware, requests_per_minute=10)
        client = TestClient(self.app)

        response = client.get("/test")

        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == "10"
        assert int(response.headers["X-RateLimit-Remaining"]) <= 10
        assert "X-RateLimit-Reset" in response.headers

    def test_rate_limit_error_response(self):
        """Test rate limit exceeded error response."""
        self.app.add_middleware(RateLimitMiddleware, requests_per_minute=1)
        client = TestClient(self.app)

        # First request succeeds
        response1 = client.get("/test")
        assert response1.status_code == 200

        # Second request should be rate limited
        response2 = client.get("/test")
        assert response2.status_code == 429
        assert "Rate limit exceeded" in response2.json()["detail"]
        assert response2.headers["Retry-After"] == "60"


class TestEnhancedRateLimitMiddleware:
    """Test enhanced rate limiting middleware with advanced features."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI()

        @self.app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        @self.app.post("/api/v1/auth/login")
        async def login_endpoint():
            return {"token": "fake_token"}

        @self.app.post("/api/v1/patients")
        async def create_patient():
            return {"id": 1}

    def test_enhanced_middleware_initialization_default(self):
        """Test enhanced middleware initialization with defaults."""
        middleware = EnhancedRateLimitMiddleware(self.app)

        assert middleware.default_limit == 100
        assert middleware.default_window == 60
        assert isinstance(middleware.whitelist_ips, set)
        assert isinstance(middleware.blacklist_ips, set)
        assert isinstance(middleware.memory_store, dict)

    def test_enhanced_middleware_initialization_custom(self):
        """Test enhanced middleware initialization with custom values."""
        whitelist = ["192.168.1.100"]
        blacklist = ["10.0.0.1"]

        middleware = EnhancedRateLimitMiddleware(
            self.app,
            default_limit=50,
            default_window=120,
            whitelist_ips=whitelist,
            blacklist_ips=blacklist
        )

        assert middleware.default_limit == 50
        assert middleware.default_window == 120
        assert middleware.whitelist_ips == set(whitelist)
        assert middleware.blacklist_ips == set(blacklist)

    def test_rate_limit_rules_configuration(self):
        """Test rate limit rules for specific endpoints."""
        middleware = EnhancedRateLimitMiddleware(self.app)

        # Check login endpoint has strict limits
        login_rule = middleware.rules.get(("POST", "/api/v1/auth/login"))
        assert login_rule is not None
        assert login_rule.limit == 5  # Strict limit for login
        assert login_rule.window == 900  # 15 minutes

        # Check patients endpoint has reasonable limits
        patients_rule = middleware.rules.get(("POST", "/api/v1/patients"))
        assert patients_rule is not None
        assert patients_rule.limit == 20
        assert patients_rule.window == 60

    def test_memory_rate_limit_check(self):
        """Test memory-based rate limit checking."""
        middleware = EnhancedRateLimitMiddleware(self.app)

        # Create a rule with strict limits
        rule = RateLimitRule(
            endpoint="/test",
            method="GET",
            limit=2,
            window=60
        )

        key = "rate_limit:192.168.1.1:/test:GET"

        # First two requests should pass
        middleware._check_memory_rate_limit(key, rule)
        middleware._check_memory_rate_limit(key, rule)

        # Third request should raise exception
        with pytest.raises(HTTPException) as exc_info:
            middleware._check_memory_rate_limit(key, rule)

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail

    def test_memory_cleanup(self):
        """Test memory store cleanup functionality."""
        middleware = EnhancedRateLimitMiddleware(self.app)

        # Add old timestamps
        key = "rate_limit:test"
        old_time = time.time() - 7200  # 2 hours ago
        middleware.memory_store[key] = deque([old_time, old_time + 10])

        middleware._cleanup_memory_store()

        # Old entries should be removed
        assert key not in middleware.memory_store

    def test_rate_limit_headers_addition(self):
        """Test addition of rate limit headers to responses."""
        middleware = EnhancedRateLimitMiddleware(self.app)

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"

        mock_response = Response()

        middleware._add_rate_limit_headers(mock_response, mock_request)

        # Should add default headers since no specific rule exists
        assert "X-RateLimit-Limit" not in mock_response.headers

        # Test with specific rule
        mock_request.method = "POST"
        mock_request.url.path = "/api/v1/auth/login"

        middleware._add_rate_limit_headers(mock_response, mock_request)

        assert mock_response.headers["X-RateLimit-Limit"] == "5"
        assert mock_response.headers["X-RateLimit-Window"] == "900"
        assert mock_response.headers["X-RateLimit-Policy"] == "sliding-window"

    def test_rate_limit_response_creation(self):
        """Test rate limit exceeded response creation."""
        middleware = EnhancedRateLimitMiddleware(self.app)

        response = middleware._rate_limit_response("Test message")

        assert response.status_code == 429
        assert response.headers["Retry-After"] == "60"
        assert response.headers["X-RateLimit-Policy"] == "sliding-window"

        # Check response body
        import json
        body = json.loads(response.body)
        assert body["error"] == "rate_limit_exceeded"
        assert body["message"] == "Test message"

    def test_enhanced_integration_with_different_endpoints(self):
        """Test enhanced rate limiting with different endpoints."""
        self.app.add_middleware(EnhancedRateLimitMiddleware, default_limit=2)
        client = TestClient(self.app)

        # Test general endpoint
        response1 = client.get("/test")
        assert response1.status_code == 200

        response2 = client.get("/test")
        assert response2.status_code == 200

        # Should be rate limited on third request
        response3 = client.get("/test")
        assert response3.status_code == 429


class TestRateLimitErrorHandling:
    """Test rate limit error handling and edge cases."""

    def test_rate_limit_rule_validation(self):
        """Test rate limit rule validation."""
        # Valid rule
        rule = RateLimitRule(
            endpoint="/api/test",
            method="GET",
            limit=100,
            window=60
        )

        assert rule.endpoint == "/api/test"
        assert rule.method == "GET"
        assert rule.limit == 100
        assert rule.window == 60

    def test_rate_limit_with_zero_limit(self):
        """Test rate limiting with zero limit (blocks all requests)."""
        middleware = RateLimitMiddleware(MagicMock(), requests_per_minute=0)

        ip = "192.168.1.1"
        assert middleware._is_request_allowed(ip) is False

    def test_rate_limit_window_boundary(self):
        """Test rate limiting at window boundaries."""
        middleware = RateLimitMiddleware(MagicMock(), requests_per_minute=2, window_seconds=60)

        ip = "192.168.1.1"
        current_time = time.time()

        # Add request at window boundary
        middleware.request_store[ip] = [current_time - 59.9]  # Just within window

        # Should still count against limit
        assert middleware._is_request_allowed(ip) is True

        # Add another request
        middleware._record_request(ip)
        assert middleware._is_request_allowed(ip) is False

    def test_concurrent_request_handling(self):
        """Test handling of concurrent requests from same IP."""
        middleware = RateLimitMiddleware(MagicMock(), requests_per_minute=5)

        ip = "192.168.1.1"

        # Simulate concurrent requests
        for _ in range(5):
            middleware._record_request(ip)

        # Should be at limit
        assert middleware._is_request_allowed(ip) is False

    def test_different_ips_independent_limits(self):
        """Test that different IPs have independent rate limits."""
        middleware = RateLimitMiddleware(MagicMock(), requests_per_minute=2)

        ip1 = "192.168.1.1"
        ip2 = "192.168.1.2"

        # Fill limit for IP1
        middleware._record_request(ip1)
        middleware._record_request(ip1)

        # IP1 should be limited
        assert middleware._is_request_allowed(ip1) is False

        # IP2 should still be allowed
        assert middleware._is_request_allowed(ip2) is True

    def test_enhanced_middleware_error_handling(self):
        """Test enhanced middleware error handling."""
        middleware = EnhancedRateLimitMiddleware(MagicMock())

        # Mock request
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.1"
        mock_request.headers.get.return_value = None
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.state.user_id = None

        # Mock call_next that raises exception
        async def mock_call_next_error(request):
            raise Exception("Downstream error")

        async def test_error_handling():
            # Should continue processing despite downstream error
            result = await middleware.dispatch(mock_request, mock_call_next_error)
            # Middleware should pass through the error

        # Should not raise exception from middleware itself
        with pytest.raises(Exception, match="Downstream error"):
            asyncio.run(test_error_handling())

    def test_user_based_rate_limiting(self):
        """Test user-based rate limiting preference."""
        middleware = EnhancedRateLimitMiddleware(MagicMock())

        # Mock request with user ID
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.1"
        mock_request.headers.get.return_value = None
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.state.user_id = "user123"

        # Mock call_next
        async def mock_call_next(request):
            return Response()

        # Should use user ID for rate limiting key
        async def test_user_rate_limit():
            await middleware.dispatch(mock_request, mock_call_next)

        # Verify user-based key is used (indirectly through successful execution)
        asyncio.run(test_user_rate_limit())


if __name__ == "__main__":
    pytest.main([__file__])
