"""
Critical API Tests: Token Refresh
Tests token refresh mechanism for maintaining user sessions.
"""
import pytest
from fastapi.testclient import TestClient
import time


@pytest.mark.api
@pytest.mark.auth
class TestAuthRefresh:
    """Test token refresh functionality."""

    def test_refresh_token_success(self, authenticated_client: TestClient):
        """Test successful token refresh."""
        # Get current token
        current_token = authenticated_client.headers.get("Authorization")

        response = authenticated_client.post("/api/v2/auth/refresh")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

        # New token should be different
        new_token = data["access_token"]
        assert new_token != current_token.replace("Bearer ", "")

    def test_refresh_without_auth(self, client: TestClient):
        """Test that refresh requires authentication."""
        response = client.post("/api/v2/auth/refresh")

        assert response.status_code == 401

    def test_refresh_with_expired_token(self, client: TestClient):
        """Test refresh with expired token."""
        # Create an expired token (this might need special fixture)
        expired_token = "expired.jwt.token"

        response = client.post(
            "/api/v2/auth/refresh",
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_refresh_with_invalid_token(self, client: TestClient):
        """Test refresh with malformed token."""
        invalid_token = "invalid.token.format"

        response = client.post(
            "/api/v2/auth/refresh",
            headers={"Authorization": f"Bearer {invalid_token}"}
        )

        assert response.status_code == 401

    def test_refresh_token_rotation(self, authenticated_client: TestClient):
        """Test that refresh implements token rotation."""
        # Get first token
        response1 = authenticated_client.post("/api/v2/auth/refresh")
        token1 = response1.json()["access_token"]

        # Update client with new token
        authenticated_client.headers["Authorization"] = f"Bearer {token1}"

        # Get second token
        response2 = authenticated_client.post("/api/v2/auth/refresh")
        token2 = response2.json()["access_token"]

        # Tokens should be different (rotation)
        assert token1 != token2

    def test_refresh_preserves_user_claims(self, authenticated_client: TestClient, test_user: dict):
        """Test that refresh maintains user claims."""
        response = authenticated_client.post("/api/v2/auth/refresh")

        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == test_user["email"]

    def test_refresh_token_blacklisting(self, authenticated_client: TestClient):
        """Test that old tokens are blacklisted after refresh."""
        # Get old token
        old_token = authenticated_client.headers.get("Authorization").replace("Bearer ", "")

        # Refresh to get new token
        response = authenticated_client.post("/api/v2/auth/refresh")
        new_token = response.json()["access_token"]

        # Try to use old token
        response = authenticated_client.get(
            "/api/v2/auth/me",
            headers={"Authorization": f"Bearer {old_token}"}
        )

        # Old token should be invalid
        assert response.status_code == 401

    def test_refresh_rate_limiting(self, authenticated_client: TestClient):
        """Test that token refresh has rate limiting."""
        # Attempt multiple refreshes in quick succession
        for _ in range(5):
            authenticated_client.post("/api/v2/auth/refresh")
            time.sleep(0.1)

        # Next refresh might be rate limited
        response = authenticated_client.post("/api/v2/auth/refresh")

        # Should succeed but with rate limit headers
        assert "X-RateLimit-Remaining" in response.headers or response.status_code == 429
