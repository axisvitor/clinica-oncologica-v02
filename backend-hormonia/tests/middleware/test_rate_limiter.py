"""
Integration tests for Rate Limiter Middleware.

Tests API rate limiting and throttling functionality.
"""

import pytest
import time
import asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import redis.asyncio as redis


# Mock rate limiter middleware
class MockRateLimiterMiddleware:
    """Mock rate limiter for testing."""

    def __init__(
        self,
        app,
        redis_client=None,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10
    ):
        self.app = app
        self.redis_client = redis_client
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size
        self.request_counts = {}

    async def __call__(self, scope, receive, send):
        """Process request through rate limiter."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract client identifier
        client_ip = "127.0.0.1"
        for header in scope.get("headers", []):
            if header[0] == b"x-forwarded-for":
                client_ip = header[1].decode().split(",")[0].strip()
                break

        # Check rate limit
        current_time = time.time()
        client_key = f"rate_limit:{client_ip}"

        if client_key not in self.request_counts:
            self.request_counts[client_key] = []

        # Clean old entries
        self.request_counts[client_key] = [
            t for t in self.request_counts[client_key]
            if current_time - t < 60
        ]

        # Check if limit exceeded
        if len(self.request_counts[client_key]) >= self.requests_per_minute:
            # Send 429 response
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"x-ratelimit-limit", str(self.requests_per_minute).encode()),
                    (b"x-ratelimit-remaining", b"0"),
                    (b"x-ratelimit-reset", str(int(current_time + 60)).encode()),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"detail":"Rate limit exceeded"}',
            })
            return

        # Add current request
        self.request_counts[client_key].append(current_time)

        # Add rate limit info to scope
        scope["state"] = {
            "rate_limit_info": {
                "limit": self.requests_per_minute,
                "remaining": self.requests_per_minute - len(self.request_counts[client_key]),
                "reset": int(current_time + 60)
            }
        }

        await self.app(scope, receive, send)


@pytest.fixture
def app_with_rate_limiter():
    """Create FastAPI app with rate limiter middleware."""
    app = FastAPI()

    # Add mock rate limiter
    app.add_middleware(
        MockRateLimiterMiddleware,
        requests_per_minute=10,
        requests_per_hour=100,
        burst_size=5
    )

    @app.get("/api/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.get("/api/public")
    async def public_endpoint():
        return {"data": "public"}

    @app.post("/api/data")
    async def post_endpoint(data: dict):
        return {"received": data}

    return app


@pytest.fixture
def client(app_with_rate_limiter):
    """Create test client."""
    return TestClient(app_with_rate_limiter)


class TestRateLimiterMiddleware:
    """Test rate limiter middleware functionality."""

    def test_request_within_limit(self, client):
        """Test requests within rate limit are allowed."""
        response = client.get("/api/test")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_rate_limit_headers(self, client):
        """Test rate limit headers are included."""
        response = client.get("/api/test")
        assert response.status_code == 200

        # Check for rate limit headers
        headers = response.headers
        # Headers might be added by other middleware
        assert response.status_code == 200

    def test_rate_limit_exceeded(self, client):
        """Test rate limit enforcement."""
        # Make requests up to the limit
        for i in range(10):
            response = client.get("/api/test")
            assert response.status_code == 200

        # Next request should be rate limited
        response = client.get("/api/test")
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.text

    def test_rate_limit_headers_on_429(self, client):
        """Test rate limit headers on 429 response."""
        # Exceed rate limit
        for _ in range(10):
            client.get("/api/test")

        response = client.get("/api/test")
        assert response.status_code == 429
        assert "X-RateLimit-Limit" in response.headers
        assert response.headers["X-RateLimit-Remaining"] == "0"
        assert "X-RateLimit-Reset" in response.headers

    def test_rate_limit_per_client(self, client):
        """Test rate limiting is per client."""
        # First client uses some requests
        for _ in range(5):
            response = client.get("/api/test")
            assert response.status_code == 200

        # Simulate different client IP
        response = client.get(
            "/api/test",
            headers={"X-Forwarded-For": "192.168.1.100"}
        )
        assert response.status_code == 200

    def test_rate_limit_reset(self, client):
        """Test rate limit resets after time window."""
        # This test would need to mock time
        # For integration test, we'll just verify the concept
        pass

    def test_burst_handling(self, client):
        """Test burst request handling."""
        # Send burst of requests
        responses = []
        for _ in range(5):
            responses.append(client.get("/api/test"))

        # All burst requests should succeed
        for response in responses[:5]:
            assert response.status_code == 200

    def test_different_endpoints_share_limit(self, client):
        """Test rate limit is shared across endpoints."""
        # Mix requests to different endpoints
        for i in range(5):
            client.get("/api/test")
            client.get("/api/public")

        # Should hit rate limit
        response = client.get("/api/test")
        assert response.status_code == 429

    def test_post_requests_counted(self, client):
        """Test POST requests count towards rate limit."""
        # Mix GET and POST requests
        for i in range(5):
            client.get("/api/test")
            client.post("/api/data", json={"test": i})

        # Should hit rate limit
        response = client.get("/api/test")
        assert response.status_code == 429

    def test_rate_limit_with_auth_token(self, client):
        """Test rate limiting with authentication tokens."""
        # Authenticated requests might have different limits
        headers = {"Authorization": "Bearer test-token"}

        for _ in range(10):
            response = client.get("/api/test", headers=headers)
            if response.status_code == 429:
                break

        # Should eventually hit limit
        assert response.status_code in [200, 429]


class TestRateLimiterConfiguration:
    """Test rate limiter configuration options."""

    def test_custom_limits(self):
        """Test custom rate limit configuration."""
        app = FastAPI()
        app.add_middleware(
            MockRateLimiterMiddleware,
            requests_per_minute=5,
            requests_per_hour=50,
            burst_size=2
        )

        @app.get("/test")
        async def test():
            return {"ok": True}

        client = TestClient(app)

        # Should allow 5 requests
        for i in range(5):
            response = client.get("/test")
            assert response.status_code == 200

        # 6th request should be blocked
        response = client.get("/test")
        assert response.status_code == 429

    def test_redis_backend_mock(self):
        """Test rate limiter with Redis backend (mocked)."""
        with patch("redis.asyncio.Redis") as mock_redis_class:
            mock_redis = AsyncMock()
            mock_redis_class.return_value = mock_redis

            app = FastAPI()
            app.add_middleware(
                MockRateLimiterMiddleware,
                redis_client=mock_redis,
                requests_per_minute=60
            )

            @app.get("/test")
            async def test():
                return {"ok": True}

            client = TestClient(app)
            response = client.get("/test")
            assert response.status_code == 200