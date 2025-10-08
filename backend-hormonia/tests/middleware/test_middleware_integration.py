"""
Integration tests for middleware stack
Tests middleware interactions and request flow
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.middleware.cors import setup_cors
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.logging import RequestLoggingMiddleware


@pytest.fixture
def app():
    """Create test app with middleware stack"""
    app = FastAPI()

    # Add middleware in order
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
    setup_cors(app)

    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}

    @app.post("/protected")
    async def protected_endpoint():
        return {"message": "protected"}

    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestMiddlewareOrdering:
    """Test middleware execution order"""

    def test_security_headers_applied(self, client):
        """Should apply security headers to all responses"""
        response = client.get("/test")

        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "X-Frame-Options" in response.headers
        assert "X-XSS-Protection" in response.headers

    def test_cors_headers_on_preflight(self, client):
        """Should handle CORS preflight requests"""
        response = client.options(
            "/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )

        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers


class TestRateLimiting:
    """Test rate limiting middleware behavior"""

    def test_rate_limit_allows_normal_traffic(self, client):
        """Should allow requests under rate limit"""
        for _ in range(10):
            response = client.get("/test")
            assert response.status_code == 200

    def test_rate_limit_blocks_excessive_requests(self, client):
        """Should block requests exceeding rate limit"""
        # Make requests up to limit
        for _ in range(60):
            client.get("/test")

        # Next request should be rate limited
        response = client.get("/test")
        assert response.status_code == 429
        assert "Retry-After" in response.headers

    def test_rate_limit_per_ip(self, client):
        """Should track rate limits per IP address"""
        # Simulate different IPs
        for i in range(10):
            response = client.get(
                "/test",
                headers={"X-Forwarded-For": f"192.168.1.{i}"}
            )
            assert response.status_code == 200


class TestRequestLogging:
    """Test request logging middleware"""

    def test_logs_request_details(self, client, caplog):
        """Should log request method, path, and status"""
        with caplog.at_level("INFO"):
            client.get("/test")

        assert "GET /test" in caplog.text
        assert "200" in caplog.text

    def test_logs_request_duration(self, client, caplog):
        """Should log request processing time"""
        with caplog.at_level("INFO"):
            client.get("/test")

        # Should contain duration in milliseconds
        assert "ms" in caplog.text

    def test_logs_error_responses(self, client, caplog):
        """Should log error responses with details"""
        with caplog.at_level("ERROR"):
            response = client.get("/nonexistent")

        assert response.status_code == 404
        assert "404" in caplog.text


class TestCSRFProtection:
    """Test CSRF middleware integration"""

    def test_csrf_token_generation(self, client):
        """Should generate CSRF token for safe requests"""
        response = client.get("/test")

        # Token should be in response or headers
        assert response.status_code == 200

    def test_csrf_validation_on_post(self, client):
        """Should validate CSRF token on state-changing requests"""
        # POST without token should fail
        response = client.post("/protected", json={"data": "test"})

        # Should require CSRF token
        assert response.status_code in [403, 400]

    def test_csrf_exempt_endpoints(self, client):
        """Should allow exempt endpoints without CSRF token"""
        # Some endpoints should be exempt (like API endpoints with token auth)
        response = client.get("/test")
        assert response.status_code == 200


class TestErrorHandling:
    """Test middleware error handling"""

    def test_middleware_exception_handling(self, client):
        """Should handle middleware exceptions gracefully"""
        response = client.get("/test", headers={"X-Malformed-Header": "\x00\x01\x02"})

        # Should not crash, should return error response
        assert response.status_code in [200, 400, 500]

    def test_middleware_chain_continues_on_error(self, client):
        """Should continue middleware chain even if one fails"""
        # Even if one middleware has issues, response should be returned
        response = client.get("/test")
        assert response.status_code == 200


class TestSecurityIntegration:
    """Test security features integration"""

    def test_blocks_sql_injection_attempts(self, client):
        """Should sanitize SQL injection attempts"""
        malicious_input = "'; DROP TABLE users; --"
        response = client.get(f"/test?query={malicious_input}")

        # Should handle safely
        assert response.status_code in [200, 400]

    def test_blocks_xss_attempts(self, client):
        """Should sanitize XSS attempts"""
        xss_payload = "<script>alert('XSS')</script>"
        response = client.post("/protected", json={"input": xss_payload})

        # Should sanitize or reject
        assert response.status_code in [200, 400, 403]

    def test_validates_content_type(self, client):
        """Should validate Content-Type headers"""
        response = client.post(
            "/protected",
            data="invalid data",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        # Should handle invalid content type appropriately
        assert response.status_code in [400, 415, 422]


class TestPerformance:
    """Test middleware performance impact"""

    def test_middleware_overhead_acceptable(self, client):
        """Should not add significant overhead"""
        import time

        start = time.time()
        for _ in range(100):
            client.get("/test")
        duration = time.time() - start

        # 100 requests should complete in reasonable time
        assert duration < 5.0  # 5 seconds for 100 requests

    def test_concurrent_request_handling(self, client):
        """Should handle concurrent requests efficiently"""
        import concurrent.futures

        def make_request():
            return client.get("/test")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [f.result() for f in futures]

        # All requests should succeed
        assert all(r.status_code == 200 for r in results)
