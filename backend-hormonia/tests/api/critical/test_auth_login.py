"""
Critical API Tests: Authentication Login Flow
Tests user authentication including login, token generation, and session management.

NOTE: This application uses Firebase Authentication, not traditional email/password login.
These tests are skipped as the /api/v2/auth/login endpoint does not exist.
Authentication flow:
1. Client authenticates with Firebase directly
2. Client sends Firebase ID token to /api/v2/auth/session
3. Server validates token and creates Redis session

For Firebase auth tests, see test_firebase_auth.py
"""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.skip(reason="App uses Firebase Auth - no /api/v2/auth/login endpoint exists")
@pytest.mark.api
@pytest.mark.auth
@pytest.mark.security
class TestAuthLogin:
    """Test authentication login functionality."""

    def test_login_success(self, client: TestClient, test_user: dict):
        """Test successful login with valid credentials."""
        # First create the user (normally done via registration)
        # For this test, assume user exists in fixture

        response = client.post(
            "/api/v2/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == test_user["email"]

    def test_login_invalid_email(self, client: TestClient):
        """Test login with non-existent email."""
        response = client.post(
            "/api/v2/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "SomePassword123",
            }
        )

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_invalid_password(self, client: TestClient, test_user: dict):
        """Test login with incorrect password."""
        response = client.post(
            "/api/v2/auth/login",
            json={
                "email": test_user["email"],
                "password": "WrongPassword123",
            }
        )

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_missing_fields(self, client: TestClient):
        """Test login with missing required fields."""
        # Missing password
        response = client.post(
            "/api/v2/auth/login",
            json={"email": "test@example.com"}
        )
        assert response.status_code == 422

        # Missing email
        response = client.post(
            "/api/v2/auth/login",
            json={"password": "Test123"}
        )
        assert response.status_code == 422

    def test_login_invalid_email_format(self, client: TestClient):
        """Test login with invalid email format."""
        response = client.post(
            "/api/v2/auth/login",
            json={
                "email": "not-an-email",
                "password": "Test123",
            }
        )

        assert response.status_code == 422

    @pytest.mark.slow
    def test_login_rate_limiting(self, client: TestClient):
        """Test that login attempts are rate limited."""
        # Attempt multiple failed logins
        for _ in range(10):
            client.post(
                "/api/v2/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "wrong",
                }
            )

        # Next attempt should be rate limited
        response = client.post(
            "/api/v2/auth/login",
            json={
                "email": "test@example.com",
                "password": "wrong",
            }
        )

        assert response.status_code == 429  # Too Many Requests

    def test_login_inactive_user(self, client: TestClient, test_user: dict):
        """Test login with inactive user account."""
        # This test assumes there's a way to create an inactive user
        inactive_user = test_user.copy()
        inactive_user["is_active"] = False

        response = client.post(
            "/api/v2/auth/login",
            json={
                "email": inactive_user["email"],
                "password": inactive_user["password"],
            }
        )

        assert response.status_code == 403
        assert "inactive" in response.json()["detail"].lower()

    def test_login_token_expiration(self, client: TestClient, test_user: dict):
        """Test that tokens have proper expiration."""
        response = client.post(
            "/api/v2/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "expires_in" in data or "exp" in data
        # Token should expire in reasonable time (e.g., 24 hours)

    def test_login_case_insensitive_email(self, client: TestClient, test_user: dict):
        """Test that email login is case insensitive."""
        # Login with uppercase email
        response = client.post(
            "/api/v2/auth/login",
            json={
                "email": test_user["email"].upper(),
                "password": test_user["password"],
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"].lower() == test_user["email"].lower()

    @pytest.mark.security
    def test_login_sql_injection_protection(self, client: TestClient):
        """Test protection against SQL injection attacks."""
        malicious_inputs = [
            "admin@example.com'; DROP TABLE users; --",
            "' OR '1'='1",
            "admin@example.com' UNION SELECT * FROM users --",
        ]

        for malicious_input in malicious_inputs:
            response = client.post(
                "/api/v2/auth/login",
                json={
                    "email": malicious_input,
                    "password": "test",
                }
            )

            # Should not execute malicious query
            assert response.status_code in [401, 422]
