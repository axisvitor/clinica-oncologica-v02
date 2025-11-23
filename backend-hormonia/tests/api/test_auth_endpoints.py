"""
Test suite for Authentication API endpoints.

Tests cover:
- User login (POST /api/v2/auth/login)
- User logout (POST /api/v2/auth/logout)
- Session validation (GET /api/v2/auth/session)
- Token refresh (POST /api/v2/auth/refresh)
- Password reset (POST /api/v2/auth/reset-password)
- Session management
- Redis session storage
- Firebase authentication integration
"""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.core.security import create_access_token, hash_password


class TestAuthenticationEndpoints:
    """Test authentication and session management endpoints."""

    @pytest.fixture
    def test_user(self, db: Session):
        """Create a test user."""
        user = User(
            firebase_uid="test-firebase-uid",
            email="test@example.com",
            full_name="Test User",
            role=UserRole.DOCTOR,
            is_active=True,
            password_hash=hash_password("TestPassword123!")
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @pytest.mark.api
    @pytest.mark.security
    def test_login_success(
        self,
        client: TestClient,
        test_user: User,
        redis_cache
    ):
        """Test successful user login."""
        response = client.post(
            "/api/v2/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "session_id" in data
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == "test@example.com"

        # Verify session cookie is set
        assert "session_id" in response.cookies

        # Verify session in Redis
        session_data = redis_cache.get_session(data["session_id"])
        assert session_data is not None
        assert session_data["firebase_uid"] == test_user.firebase_uid

    @pytest.mark.api
    @pytest.mark.security
    def test_login_invalid_credentials(
        self,
        client: TestClient,
        test_user: User
    ):
        """Test login with invalid credentials."""
        response = client.post(
            "/api/v2/auth/login",
            json={
                "email": "test@example.com",
                "password": "WrongPassword"
            }
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "session_id" not in response.cookies

    @pytest.mark.api
    @pytest.mark.security
    def test_login_nonexistent_user(
        self,
        client: TestClient
    ):
        """Test login with non-existent user."""
        response = client.post(
            "/api/v2/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "Password123!"
            }
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.api
    @pytest.mark.security
    def test_login_inactive_user(
        self,
        client: TestClient,
        db: Session
    ):
        """Test login with inactive user account."""
        # Create inactive user
        inactive_user = User(
            firebase_uid="inactive-firebase-uid",
            email="inactive@example.com",
            full_name="Inactive User",
            role=UserRole.DOCTOR,
            is_active=False,
            password_hash=hash_password("Password123!")
        )
        db.add(inactive_user)
        db.commit()

        response = client.post(
            "/api/v2/auth/login",
            json={
                "email": "inactive@example.com",
                "password": "Password123!"
            }
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.api
    @pytest.mark.security
    def test_logout_success(
        self,
        client: TestClient,
        test_user: User,
        redis_cache
    ):
        """Test successful user logout."""
        # Login first
        login_response = client.post(
            "/api/v2/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )
        session_id = login_response.json()["session_id"]

        # Logout
        response = client.post(
            "/api/v2/auth/logout",
            headers={"X-Session-ID": session_id}
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify session removed from Redis
        session_data = redis_cache.get_session(session_id)
        assert session_data is None

    @pytest.mark.api
    @pytest.mark.security
    def test_logout_invalid_session(
        self,
        client: TestClient
    ):
        """Test logout with invalid session."""
        response = client.post(
            "/api/v2/auth/logout",
            headers={"X-Session-ID": "invalid-session-id"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.api
    @pytest.mark.security
    def test_validate_session_success(
        self,
        client: TestClient,
        test_user: User
    ):
        """Test session validation with valid session."""
        # Login first
        login_response = client.post(
            "/api/v2/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )
        session_id = login_response.json()["session_id"]

        # Validate session
        response = client.get(
            "/api/v2/auth/session",
            headers={"X-Session-ID": session_id}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["valid"] is True
        assert data["user"]["email"] == "test@example.com"

    @pytest.mark.api
    @pytest.mark.security
    def test_validate_session_expired(
        self,
        client: TestClient,
        redis_cache
    ):
        """Test session validation with expired session."""
        # Create expired session
        session_id = str(uuid4())
        redis_cache.set_session(
            session_id,
            {"firebase_uid": "test-uid"},
            ttl=0  # Expired
        )

        response = client.get(
            "/api/v2/auth/session",
            headers={"X-Session-ID": session_id}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.api
    @pytest.mark.security
    def test_refresh_token_success(
        self,
        client: TestClient,
        test_user: User
    ):
        """Test token refresh with valid session."""
        # Login first
        login_response = client.post(
            "/api/v2/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )
        session_id = login_response.json()["session_id"]
        old_token = login_response.json()["access_token"]

        # Refresh token
        response = client.post(
            "/api/v2/auth/refresh",
            headers={"X-Session-ID": session_id}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "access_token" in data
        assert data["access_token"] != old_token

    @pytest.mark.api
    @pytest.mark.security
    def test_password_reset_request_success(
        self,
        client: TestClient,
        test_user: User
    ):
        """Test password reset request."""
        response = client.post(
            "/api/v2/auth/reset-password",
            json={"email": "test@example.com"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["message"] == "Password reset email sent"

    @pytest.mark.api
    @pytest.mark.security
    def test_password_reset_nonexistent_user(
        self,
        client: TestClient
    ):
        """Test password reset for non-existent user."""
        response = client.post(
            "/api/v2/auth/reset-password",
            json={"email": "nonexistent@example.com"}
        )

        # Should return 200 to prevent user enumeration
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.api
    @pytest.mark.security
    def test_concurrent_sessions_allowed(
        self,
        client: TestClient,
        test_user: User,
        redis_cache
    ):
        """Test that multiple concurrent sessions are allowed."""
        # Login multiple times
        sessions = []
        for _ in range(3):
            response = client.post(
                "/api/v2/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "TestPassword123!"
                }
            )
            sessions.append(response.json()["session_id"])

        # Verify all sessions are valid
        for session_id in sessions:
            session_data = redis_cache.get_session(session_id)
            assert session_data is not None

    @pytest.mark.api
    @pytest.mark.security
    def test_session_ttl_extended_on_activity(
        self,
        client: TestClient,
        test_user: User,
        redis_cache
    ):
        """Test that session TTL is extended on activity."""
        # Login
        login_response = client.post(
            "/api/v2/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )
        session_id = login_response.json()["session_id"]

        # Get initial TTL
        initial_ttl = redis_cache.get_ttl(session_id)

        # Make authenticated request
        client.get(
            "/api/v2/auth/session",
            headers={"X-Session-ID": session_id}
        )

        # Verify TTL was extended
        new_ttl = redis_cache.get_ttl(session_id)
        assert new_ttl >= initial_ttl

    @pytest.mark.api
    @pytest.mark.security
    def test_login_rate_limiting(
        self,
        client: TestClient,
        test_user: User
    ):
        """Test that login attempts are rate limited."""
        # Make multiple failed login attempts
        for _ in range(10):
            client.post(
                "/api/v2/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "WrongPassword"
                }
            )

        # Next attempt should be rate limited
        response = client.post(
            "/api/v2/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.fixture
def redis_cache():
    """Mock Redis cache for testing."""
    # This should be implemented in conftest.py with actual Redis mock
    class MockRedisCache:
        def __init__(self):
            self.data = {}

        def get_session(self, session_id: str):
            return self.data.get(f"session:{session_id}")

        def set_session(self, session_id: str, data: dict, ttl: int = 3600):
            self.data[f"session:{session_id}"] = data

        def get_ttl(self, session_id: str):
            return 3600 if f"session:{session_id}" in self.data else 0

    return MockRedisCache()


@pytest.fixture
def authenticated_headers(client: TestClient, test_user: User):
    """Create authenticated headers for testing."""
    login_response = client.post(
        "/api/v2/auth/login",
        json={
            "email": "test@example.com",
            "password": "TestPassword123!"
        }
    )
    session_id = login_response.json()["session_id"]

    return {
        "X-Session-ID": session_id,
        "Authorization": f"Bearer {login_response.json()['access_token']}"
    }
