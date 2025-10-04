"""
Tests for rate limiting on authentication endpoints.

Verifies that rate limiting is properly configured and enforced
to prevent brute force attacks.
"""
import pytest
from fastapi.testclient import TestClient
from app.core.application_factory import create_application


@pytest.fixture
def client():
    """Create test client with rate limiting enabled."""
    app = create_application(
        enable_monitoring=False,
        enable_debug_endpoints=False,
        deployment_mode="development"
    )
    return TestClient(app)


class TestLoginRateLimit:
    """Test rate limiting on login endpoints."""

    def test_login_rate_limit_exceeded(self, client):
        """Test that login endpoint enforces rate limit (5/minute)."""
        # Attempt 6 login requests rapidly
        responses = []
        for i in range(6):
            response = client.post(
                "/api/v1/auth/login",
                data={"username": f"user{i}@example.com", "password": "test123"}
            )
            responses.append(response)

        # First 5 should succeed (or return 410 for disabled login)
        for response in responses[:5]:
            assert response.status_code in [200, 410]

        # 6th should be rate limited
        assert responses[5].status_code == 429
        assert "too_many_requests" in responses[5].json()["error"]

    def test_login_json_rate_limit(self, client):
        """Test rate limiting on JSON login endpoint."""
        responses = []
        for i in range(6):
            response = client.post(
                "/api/v1/auth/login-json",
                json={"email": f"user{i}@example.com", "password": "test123"}
            )
            responses.append(response)

        # 6th request should be rate limited
        assert responses[5].status_code == 429


class TestTokenRefreshRateLimit:
    """Test rate limiting on token refresh endpoint."""

    def test_refresh_rate_limit(self, client):
        """Test that token refresh has higher limit (20/minute)."""
        responses = []
        for i in range(21):
            response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "fake-token"}
            )
            responses.append(response)

        # First 20 should succeed (or return 410 for disabled refresh)
        for response in responses[:20]:
            assert response.status_code in [200, 410]

        # 21st should be rate limited
        assert responses[20].status_code == 429


class TestPasswordChangeRateLimit:
    """Test rate limiting on password change endpoint."""

    def test_password_change_rate_limit(self, client):
        """Test that password change is limited (3/hour)."""
        # Note: This test would need authentication, so we test the rate limit config
        # In a real scenario, you'd need to authenticate first
        pass  # Placeholder for authenticated tests


class TestAvatarUploadRateLimit:
    """Test rate limiting on avatar upload endpoint."""

    def test_avatar_upload_rate_limit(self, client):
        """Test that avatar uploads are limited (10/hour)."""
        # Note: This test would need authentication and file upload
        # In a real scenario, you'd need to authenticate first
        pass  # Placeholder for authenticated tests


class TestProfileUpdateRateLimit:
    """Test rate limiting on profile update endpoint."""

    def test_profile_update_rate_limit(self, client):
        """Test that profile updates are limited (20/hour)."""
        # Note: This test would need authentication
        # In a real scenario, you'd need to authenticate first
        pass  # Placeholder for authenticated tests


class TestRateLimitErrorFormat:
    """Test rate limit error response format."""

    def test_rate_limit_error_format(self, client):
        """Test that rate limit errors return proper format."""
        # Trigger rate limit
        for i in range(6):
            response = client.post(
                "/api/v1/auth/login",
                data={"username": f"user{i}@example.com", "password": "test123"}
            )

        # Check last response format
        assert response.status_code == 429
        error_data = response.json()
        assert "error" in error_data
        assert error_data["error"] == "too_many_requests"
        assert "message" in error_data
        assert "retry_after" in error_data


class TestRateLimitByIP:
    """Test that rate limiting is per IP address."""

    def test_different_ips_independent_limits(self, client):
        """Test that different IPs have independent rate limits."""
        # Note: In a real scenario, you'd simulate different IPs
        # using X-Forwarded-For header
        headers_ip1 = {"X-Forwarded-For": "192.168.1.1"}
        headers_ip2 = {"X-Forwarded-For": "192.168.1.2"}

        # Make 5 requests from IP1
        for i in range(5):
            response = client.post(
                "/api/v1/auth/login",
                data={"username": f"user{i}@example.com", "password": "test123"},
                headers=headers_ip1
            )
            assert response.status_code in [200, 410]

        # IP2 should still be able to make requests
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "test123"},
            headers=headers_ip2
        )
        assert response.status_code in [200, 410]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
