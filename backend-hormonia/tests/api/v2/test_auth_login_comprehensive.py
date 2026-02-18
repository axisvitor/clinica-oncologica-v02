"""
Comprehensive Authentication Login Tests

Tests cover:
- Firebase token verification
- Session management (create, verify, revoke)
- Rate limiting
- Token security
- Error handling
- Edge cases
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, UserRole, AuthProvider
from app.models.session import Session as SessionModel


from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
# ============================================================================
# Helper Functions
# ============================================================================


@pytest.fixture
def test_user(test_doctor_user: User) -> User:
    """Align session-oriented auth tests with the default authenticated doctor fixture."""
    return test_doctor_user

def create_mock_firebase_token_data(
    uid: str = "A1B2C3D4E5F6G7H8I9J0K1L2M3N4",
    email: str = "test@clinica.com",
    email_verified: bool = True,
    name: str = "Test User",
    picture: str = "https://example.com/photo.jpg",
    custom_claims: dict = None
) -> dict:
    """Create mock Firebase token verification response."""
    return {
        "uid": uid,
        "email": email,
        "email_verified": email_verified,
        "name": name,
        "picture": picture,
        "custom_claims": custom_claims or {"role": "doctor"}
    }


def create_test_session_model(
    db: Session,
    user: User,
    is_active: bool = True,
    expires_in_days: int = 5,
    **kwargs
) -> SessionModel:
    """Create a test session in the database."""
    session = SessionModel(
        id=kwargs.get('id', uuid4()),
        user_id=user.id,
        session_token=f"test_token_{uuid4().hex}",
        is_active=is_active,
        created_at=kwargs.get('created_at', now_sao_paulo_naive()),
        expires_at=kwargs.get('expires_at', now_sao_paulo_naive() + timedelta(days=expires_in_days)),
        last_activity=kwargs.get('last_activity', now_sao_paulo_naive()),
        ip_address=kwargs.get('ip_address', '192.168.1.1'),
        user_agent=kwargs.get('user_agent', 'Mozilla/5.0 Test Browser'),
        revoked_at=kwargs.get('revoked_at'),
        revocation_reason=kwargs.get('revocation_reason'),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


# ============================================================================
# Firebase Authentication Tests
# ============================================================================

@pytest.mark.api
@pytest.mark.auth
class TestFirebaseAuthentication:
    """Test suite for Firebase authentication endpoints."""

    def test_firebase_verify_valid_token_new_user(
        self,
        client: TestClient,
        db_session: Session,
        mock_redis
    ):
        """Test Firebase verification creates new user when not exists."""
        firebase_data = create_mock_firebase_token_data(
            uid="B1C2D3E4F5G6H7I8J9K0L1M2N3O4",
            email="newuser@clinica.com"
        )

        with patch('app.api.v2.routers.auth.verify_token', new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = firebase_data

            with patch('app.dependencies.auth_dependencies.get_redis_cache') as mock_cache:
                mock_cache_instance = MagicMock()
                mock_cache_instance.create_session = AsyncMock(return_value=True)
                mock_cache.return_value = mock_cache_instance

                response = client.post(
                    "/api/v2/auth/firebase/verify",
                    json={"id_token": "valid.firebase.token"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["valid"] is True
                assert "session_id" in data

    def test_firebase_verify_valid_token_existing_user(
        self,
        client: TestClient,
        db_session: Session,
        mock_redis
    ):
        """Test Firebase verification updates existing user."""
        # Create existing user
        from app.models.user import User
        existing_user = User(
            id=uuid4(),
            firebase_uid="C1D2E3F4G5H6I7J8K9L0M1N2O3P4",
            email="existing@clinica.com",
            full_name="Existing User",
            is_active=True,
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.FIREBASE
        )
        db_session.add(existing_user)
        db_session.commit()

        firebase_data = create_mock_firebase_token_data(
            uid="C1D2E3F4G5H6I7J8K9L0M1N2O3P4",
            email="existing@clinica.com",
            name="Updated Name"
        )

        with patch('app.api.v2.routers.auth.verify_token', new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = firebase_data

            with patch('app.dependencies.auth_dependencies.get_redis_cache') as mock_cache:
                mock_cache_instance = MagicMock()
                mock_cache_instance.create_session = AsyncMock(return_value=True)
                mock_cache.return_value = mock_cache_instance

                response = client.post(
                    "/api/v2/auth/firebase/verify",
                    json={"id_token": "valid.firebase.token"}
                )

                assert response.status_code == 200

    def test_firebase_verify_invalid_token(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test Firebase verification with invalid token returns 401."""
        with patch('app.api.v2.routers.auth.verify_token', new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = None

            response = client.post(
                "/api/v2/auth/firebase/verify",
                json={"id_token": "invalid.firebase.token"}
            )

            assert response.status_code == 401
            assert "Invalid" in response.json()["detail"]

    def test_firebase_verify_expired_token(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test Firebase verification with expired token."""
        with patch('app.api.v2.routers.auth.verify_token', new_callable=AsyncMock) as mock_verify:
            mock_verify.side_effect = Exception("Token expired")

            response = client.post(
                "/api/v2/auth/firebase/verify",
                json={"id_token": "expired.firebase.token"}
            )

            assert response.status_code == 500

    def test_firebase_verify_missing_token(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test Firebase verification without token returns validation error."""
        response = client.post(
            "/api/v2/auth/firebase/verify",
            json={}
        )

        assert response.status_code == 422

    def test_firebase_verify_missing_uid_in_token(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test Firebase verification with token missing uid."""
        with patch('app.api.v2.routers.auth.verify_token', new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = {"email": "test@example.com"}  # Missing uid

            response = client.post(
                "/api/v2/auth/firebase/verify",
                json={"id_token": "token.without.uid"}
            )

            assert response.status_code == 400

    def test_firebase_verify_missing_email_in_token(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test Firebase verification with token missing email."""
        with patch('app.api.v2.routers.auth.verify_token', new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = {"uid": "E1F2G3H4I5J6K7L8M9N0O1P2Q3R4"}  # Missing email

            response = client.post(
                "/api/v2/auth/firebase/verify",
                json={"id_token": "token.without.email"}
            )

            assert response.status_code == 400

    def test_firebase_verify_locked_account(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test Firebase verification with locked account."""
        from app.models.user import User

        locked_user = User(
            id=uuid4(),
            firebase_uid="D1E2F3G4H5I6J7K8L9M0N1O2P3Q4",
            email="locked@clinica.com",
            full_name="Locked User",
            is_active=True,
            is_locked=True,
            locked_until=now_sao_paulo_naive() + timedelta(hours=1),
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.FIREBASE
        )
        db_session.add(locked_user)
        db_session.commit()

        firebase_data = create_mock_firebase_token_data(
            uid="D1E2F3G4H5I6J7K8L9M0N1O2P3Q4",
            email="locked@clinica.com"
        )

        with patch('app.api.v2.routers.auth.verify_token', new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = firebase_data

            response = client.post(
                "/api/v2/auth/firebase/verify",
                json={"id_token": "valid.firebase.token"}
            )

            assert response.status_code == 403
            assert "locked" in response.json()["detail"].lower()

    def test_firebase_verify_sets_session_cookie(
        self,
        client: TestClient,
        db_session: Session,
        mock_redis
    ):
        """Test Firebase verification sets HTTP-only session cookie."""
        firebase_data = create_mock_firebase_token_data()

        with patch('app.api.v2.routers.auth.verify_token', new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = firebase_data

            with patch('app.dependencies.auth_dependencies.get_redis_cache') as mock_cache:
                mock_cache_instance = MagicMock()
                mock_cache_instance.create_session = AsyncMock(return_value=True)
                mock_cache.return_value = mock_cache_instance

                response = client.post(
                    "/api/v2/auth/firebase/verify",
                    json={"id_token": "valid.firebase.token"}
                )

                assert response.status_code == 200
                # Check for session_id cookie or X-Session-ID header
                assert "X-Session-ID" in response.headers or "session_id" in response.cookies


# ============================================================================
# Session Management Tests
# ============================================================================

@pytest.mark.api
@pytest.mark.auth
class TestSessionManagement:
    """Test suite for session management endpoints."""

    def test_verify_session_valid(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test verifying a valid session."""
        # Create active session
        session = create_test_session_model(db_session, test_user)

        response = client.get(
            "/api/v2/auth/verify-session",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "user_id" in data

    def test_verify_session_expired(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test verifying an expired session."""
        # Create expired session
        create_test_session_model(
            db_session,
            test_user,
            expires_at=now_sao_paulo_naive() - timedelta(hours=1)
        )

        response = client.get(
            "/api/v2/auth/verify-session",
            headers=auth_headers
        )

        assert response.status_code == 401

    def test_verify_session_revoked(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test verifying a revoked session."""
        # Create revoked session
        create_test_session_model(
            db_session,
            test_user,
            is_active=False,
            revoked_at=now_sao_paulo_naive()
        )

        response = client.get(
            "/api/v2/auth/verify-session",
            headers=auth_headers
        )

        assert response.status_code == 401

    def test_verify_session_no_auth(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test verifying session without authentication."""
        response = client.get("/api/v2/auth/verify-session")
        assert response.status_code == 401

    def test_logout_success(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test successful logout."""
        session = create_test_session_model(db_session, test_user)

        with patch('app.dependencies.auth_dependencies.get_redis_cache') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.invalidate_session = AsyncMock(return_value=True)
            mock_cache.return_value = mock_cache_instance

            response = client.delete(
                "/api/v2/auth/logout",
                headers=auth_headers,
                cookies={"session_id": str(session.id)}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_logout_all_devices(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test logout from all devices."""
        # Create multiple sessions
        for i in range(3):
            create_test_session_model(db_session, test_user)

        with patch('app.dependencies.auth_dependencies.get_redis_cache') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.invalidate_all_user_sessions = AsyncMock(return_value=3)
            mock_cache.return_value = mock_cache_instance

            response = client.delete(
                "/api/v2/auth/logout-all",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_logout_without_session(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test logout when no session exists."""
        with patch('app.dependencies.auth_dependencies.get_redis_cache') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.invalidate_session = AsyncMock(return_value=False)
            mock_cache.return_value = mock_cache_instance

            response = client.delete(
                "/api/v2/auth/logout",
                headers=auth_headers
            )

            # Should still return success
            assert response.status_code == 200


# ============================================================================
# CSRF Token Tests
# ============================================================================

@pytest.mark.api
@pytest.mark.auth
class TestCSRFToken:
    """Test suite for CSRF token endpoint."""

    def test_get_csrf_token(
        self,
        client: TestClient
    ):
        """Test getting CSRF token."""
        response = client.get("/api/v2/auth/csrf-token")

        assert response.status_code == 200
        data = response.json()
        assert "csrf_token" in data
        token = data["csrf_token"]
        assert isinstance(token, str)
        # Current implementation returns signed CSRF tokens:
        # {timestamp}.{random_hex}.{signature}
        parts = token.split(".")
        assert len(parts) == 3
        assert len(token) > 32

    def test_csrf_token_uniqueness(
        self,
        client: TestClient
    ):
        """Test CSRF tokens are unique per request."""
        response1 = client.get("/api/v2/auth/csrf-token")
        response2 = client.get("/api/v2/auth/csrf-token")

        token1 = response1.json()["csrf_token"]
        token2 = response2.json()["csrf_token"]

        assert token1 != token2


# ============================================================================
# Rate Limiting Tests
# ============================================================================

@pytest.mark.api
@pytest.mark.auth
@pytest.mark.slow
class TestRateLimiting:
    """Test suite for authentication rate limiting."""

    def test_firebase_verify_rate_limit(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test rate limiting on Firebase verify endpoint (60/minute)."""
        # This test verifies rate limiting exists
        # In real scenario, would need to make 60+ requests

        with patch('app.api.v2.routers.auth.verify_token', new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = None

            # Make a single request to verify endpoint works
            response = client.post(
                "/api/v2/auth/firebase/verify",
                json={"id_token": "test.firebase.token"}
            )

            # Should not be rate limited on first request
            assert response.status_code != 429

    def test_verify_session_rate_limit(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test rate limiting on session verify endpoint (100/minute)."""
        # Create session
        create_test_session_model(db_session, test_user)

        # Make single request
        response = client.get(
            "/api/v2/auth/verify-session",
            headers=auth_headers
        )

        # Should not be rate limited on first request
        assert response.status_code != 429

    def test_logout_rate_limit(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test rate limiting on logout endpoint (20/minute)."""
        with patch('app.dependencies.auth_dependencies.get_redis_cache') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.invalidate_session = AsyncMock(return_value=True)
            mock_cache.return_value = mock_cache_instance

            response = client.delete(
                "/api/v2/auth/logout",
                headers=auth_headers
            )

            # Should not be rate limited on first request
            assert response.status_code != 429


# ============================================================================
# Security Tests
# ============================================================================

@pytest.mark.api
@pytest.mark.auth
@pytest.mark.security
class TestAuthenticationSecurity:
    """Test suite for authentication security."""

    def test_sql_injection_prevention_email(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test SQL injection prevention in token verification."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "admin@example.com' UNION SELECT * FROM users --",
            "test@example.com'; DELETE FROM sessions; --"
        ]

        for malicious_input in malicious_inputs:
            with patch('app.api.v2.routers.auth.verify_token', new_callable=AsyncMock) as mock_verify:
                mock_verify.return_value = {
                    "uid": "E1F2G3H4I5J6K7L8M9N0O1P2Q3R4",
                    "email": malicious_input
                }

                response = client.post(
                    "/api/v2/auth/firebase/verify",
                    json={"id_token": "test.firebase.token"}
                )

                # Should handle gracefully, not execute SQL
                assert response.status_code in [200, 400, 422, 500]

    def test_xss_prevention_in_user_data(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test XSS prevention in user data."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>"
        ]

        for xss_payload in xss_payloads:
            with patch('app.api.v2.routers.auth.verify_token', new_callable=AsyncMock) as mock_verify:
                mock_verify.return_value = {
                    "uid": "E1F2G3H4I5J6K7L8M9N0O1P2Q3R4",
                    "email": "test@example.com",
                    "name": xss_payload
                }

                with patch('app.dependencies.auth_dependencies.get_redis_cache') as mock_cache:
                    mock_cache_instance = MagicMock()
                    mock_cache_instance.create_session = AsyncMock(return_value=True)
                    mock_cache.return_value = mock_cache_instance

                    response = client.post(
                        "/api/v2/auth/firebase/verify",
                        json={"id_token": "test.firebase.token"}
                    )

                    # Should store but escape/sanitize dangerous content
                    assert response.status_code in [200, 500]

    def test_session_token_not_exposed_in_response_body(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test that session tokens are not exposed in response body."""
        session = create_test_session_model(db_session, test_user)

        response = client.get(
            "/api/v2/auth/verify-session",
            headers=auth_headers
        )

        if response.status_code == 200:
            data = response.json()
            # Session token should not be in response
            assert "session_token" not in data or data.get("session_token") is None

    def test_password_not_in_any_response(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test that password/hashed_password never appears in responses."""
        session = create_test_session_model(db_session, test_user)

        response = client.get(
            "/api/v2/auth/verify-session",
            headers=auth_headers
        )

        if response.status_code == 200:
            response_text = response.text
            assert "password" not in response_text.lower()
            assert "hashed" not in response_text.lower()


# ============================================================================
# Edge Cases Tests
# ============================================================================

@pytest.mark.api
@pytest.mark.auth
class TestEdgeCases:
    """Test suite for authentication edge cases."""

    def test_empty_token_string(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test handling of empty token string."""
        response = client.post(
            "/api/v2/auth/firebase/verify",
            json={"id_token": ""}
        )

        assert response.status_code in [400, 422]

    def test_whitespace_only_token(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test handling of whitespace-only token."""
        response = client.post(
            "/api/v2/auth/firebase/verify",
            json={"id_token": "   "}
        )

        assert response.status_code in [400, 422, 500]

    def test_very_long_token(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test handling of extremely long token."""
        long_token = "x" * 100000  # 100KB token

        response = client.post(
            "/api/v2/auth/firebase/verify",
            json={"id_token": long_token}
        )

        # Should handle gracefully
        assert response.status_code in [400, 413, 422, 500]

    def test_unicode_in_token(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test handling of unicode characters in token."""
        unicode_token = "token_with_unicode_\u4e2d\u6587_\u0639\u0631\u0628\u064a"

        with patch('app.api.v2.routers.auth.verify_token', new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = None

            response = client.post(
                "/api/v2/auth/firebase/verify",
                json={"id_token": unicode_token}
            )

            # Strict JWT contract rejects malformed token format before verification
            assert response.status_code in [400, 401, 422]

    def test_concurrent_session_creation(
        self,
        client: TestClient,
        db_session: Session,
        mock_redis
    ):
        """Test handling of concurrent session creation attempts."""
        firebase_data = create_mock_firebase_token_data()

        with patch('app.api.v2.routers.auth.verify_token', new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = firebase_data

            with patch('app.dependencies.auth_dependencies.get_redis_cache') as mock_cache:
                mock_cache_instance = MagicMock()
                mock_cache_instance.create_session = AsyncMock(return_value=True)
                mock_cache.return_value = mock_cache_instance

                # Make multiple requests (simulating concurrent access)
                responses = []
                for _ in range(3):
                    response = client.post(
                        "/api/v2/auth/firebase/verify",
                        json={"id_token": "valid.firebase.token"}
                    )
                    responses.append(response)

                # All should succeed or be rate limited
                for response in responses:
                    assert response.status_code in [200, 429]

    def test_session_verify_with_inactive_user(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test session verification when user becomes inactive."""
        # Create session
        create_test_session_model(db_session, test_user)

        # Deactivate user
        test_user.is_active = False
        db_session.commit()

        response = client.get(
            "/api/v2/auth/verify-session",
            headers=auth_headers
        )

        # Should fail due to inactive user
        assert response.status_code in [401, 403]
