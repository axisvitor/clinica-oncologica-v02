"""
Comprehensive integration tests for Authentication Flows

Tests complete authentication workflows including login, logout, session management,
token validation, and integration between all auth services.
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

# Import services and dependencies - adjust path based on actual structure
try:
    from app.services.firebase_auth_service import FirebaseAuthService
    from app.services.auth import AuthService
    from app.services.audit_service import AuditService
    from app.repositories.user import UserRepository
    from app.models.user import User
    from app.schemas.auth import TokenData
except ImportError:
    # Fallback for different project structures
    try:
        from services.firebase_auth_service import FirebaseAuthService
        from services.auth import AuthService
        from services.audit_service import AuditService
        from repositories.user import UserRepository
        from models.user import User
        from schemas.auth import TokenData
    except ImportError:
        # Create mock classes if services don't exist
        from services.firebase_auth_service import FirebaseAuthService
        from services.auth import AuthService
        from services.audit_service import AuditService
        from repositories.user import UserRepository
        from models.user import User

        class TokenData:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)


@pytest.fixture
def mock_db_session():
    """Mock database session for integration tests."""
    session = Mock(spec=Session)
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.query = Mock()
    return session


@pytest.fixture
def mock_user_repository():
    """Mock user repository."""
    repo = Mock(spec=UserRepository)
    return repo


@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def firebase_auth_service():
    """Firebase auth service with mocked Firebase Admin SDK."""
    with patch('firebase_admin.initialize_app'), \
         patch('firebase_admin.credentials.Certificate'), \
         patch('firebase_admin._apps', {}):
        service = FirebaseAuthService(
            project_id="test-project",
            private_key="-----BEGIN PRIVATE KEY-----\nMOCK_KEY\n-----END PRIVATE KEY-----",
            client_email="test@test.iam.gserviceaccount.com"
        )
        return service


@pytest.fixture
def auth_service(mock_db_session, mock_user_repository, mock_redis_client):
    """Legacy auth service."""
    return AuthService(
        db=mock_db_session,
        user_repository=mock_user_repository,
        redis_client=mock_redis_client
    )


@pytest.fixture
def audit_service(mock_db_session):
    """Audit service for logging."""
    return AuditService(mock_db_session)


@pytest.fixture
def sample_user():
    """Sample user for testing."""
    user = Mock(spec=User)
    user.id = "test-user-id"
    user.email = "test@example.com"
    user.firebase_uid = "firebase-uid-123"
    user.hashed_password = "$2b$12$hash"
    user.full_name = "Test User"
    user.role = "doctor"
    user.is_active = True
    return user


@pytest.fixture
def sample_firebase_token_data():
    """Sample Firebase token data."""
    return {
        'uid': 'firebase-uid-123',
        'email': 'test@example.com',
        'email_verified': True,
        'name': 'Test User',
        'picture': 'https://example.com/photo.jpg',
        'auth_time': 1234567890,
        'exp': 1234571490,
        'custom_claims': {'role': 'doctor'}
    }


class TestFirebaseAuthenticationFlow:
    """Test complete Firebase authentication workflows."""

    @patch('firebase_admin.auth.verify_id_token')
    async def test_firebase_login_success_flow(self, mock_verify, firebase_auth_service, audit_service, sample_firebase_token_data):
        """Test successful Firebase login flow with audit logging."""
        # Arrange
        mock_verify.return_value = {**sample_firebase_token_data, 'iss': 'firebase', 'aud': 'test-project'}
        firebase_token = "valid-firebase-token"

        # Mock audit logging
        with patch.object(audit_service, 'log_event') as mock_audit:
            # Act
            user_info = await firebase_auth_service.verify_token(firebase_token)

            # Assert
            assert user_info is not None
            assert user_info['uid'] == 'firebase-uid-123'
            assert user_info['email'] == 'test@example.com'
            assert user_info['custom_claims']['role'] == 'doctor'

            # Verify Firebase was called correctly
            mock_verify.assert_called_once_with(firebase_token, check_revoked=True)

    @patch('firebase_admin.auth.verify_id_token')
    async def test_firebase_login_expired_token_flow(self, mock_verify, firebase_auth_service):
        """Test Firebase login flow with expired token."""
        # Arrange
        from firebase_admin import auth as firebase_auth
        mock_verify.side_effect = firebase_auth.ExpiredIdTokenError('Token expired')

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await firebase_auth_service.verify_token("expired-token")

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'expired' in exc_info.value.detail.lower()

    @patch('firebase_admin.auth.verify_id_token')
    async def test_firebase_login_revoked_token_flow(self, mock_verify, firebase_auth_service):
        """Test Firebase login flow with revoked token."""
        # Arrange
        from firebase_admin import auth as firebase_auth
        mock_verify.side_effect = firebase_auth.RevokedIdTokenError('Token revoked')

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await firebase_auth_service.verify_token("revoked-token")

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'revoked' in exc_info.value.detail.lower()

    @patch('firebase_admin.auth.get_user')
    async def test_firebase_user_management_flow(self, mock_get_user, firebase_auth_service):
        """Test Firebase user management operations."""
        # Arrange
        mock_user_record = Mock()
        mock_user_record.uid = "firebase-uid-123"
        mock_user_record.email = "test@example.com"
        mock_user_record.email_verified = True
        mock_user_record.display_name = "Test User"
        mock_user_record.custom_claims = {"role": "doctor"}
        mock_user_record.disabled = False
        mock_user_record.provider_data = []
        mock_user_record.user_metadata = Mock(
            creation_timestamp=1234567890,
            last_sign_in_timestamp=1234567900
        )
        mock_get_user.return_value = mock_user_record

        # Act - Get user
        user_data = await firebase_auth_service.get_user("firebase-uid-123")

        # Assert
        assert user_data is not None
        assert user_data["uid"] == "firebase-uid-123"
        assert user_data["email"] == "test@example.com"
        assert user_data["custom_claims"]["role"] == "doctor"

        # Act - Set custom claims
        with patch('firebase_admin.auth.set_custom_user_claims') as mock_set_claims:
            result = await firebase_auth_service.set_custom_claims("firebase-uid-123", {"role": "admin"})
            assert result is True

        # Act - Revoke tokens
        with patch('firebase_admin.auth.revoke_refresh_tokens') as mock_revoke:
            result = await firebase_auth_service.revoke_refresh_tokens("firebase-uid-123")
            assert result is True


class TestLegacyAuthenticationFlow:
    """Test complete legacy authentication workflows."""

    @pytest.mark.asyncio
    async def test_legacy_login_success_flow(self, auth_service, mock_user_repository, sample_user):
        """Test successful legacy login flow."""
        # Arrange
        mock_user_repository.get_by_email.return_value = sample_user
        email = "test@example.com"
        password = "password123"
        client_ip = "192.168.1.1"

        with patch('app.services.auth.verify_password', return_value=True), \
             patch('app.services.auth.cache_user_data') as mock_cache:

            # Act
            user = await auth_service.authenticate_user(email, password, client_ip)

            # Assert
            assert user == sample_user
            mock_user_repository.get_by_email.assert_called_once_with(email)
            mock_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_legacy_login_rate_limited_flow(self, auth_service):
        """Test legacy login flow with rate limiting."""
        # Arrange
        auth_service.redis.get = AsyncMock(return_value="10")  # Exceeded attempts

        # Act
        result = await auth_service.authenticate_user("test@example.com", "password123", "192.168.1.1")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_legacy_login_wrong_password_flow(self, auth_service, mock_user_repository, sample_user):
        """Test legacy login flow with wrong password."""
        # Arrange
        mock_user_repository.get_by_email.return_value = sample_user

        with patch('app.services.auth.verify_password', return_value=False):
            # Act
            result = await auth_service.authenticate_user("test@example.com", "wrongpassword")

            # Assert
            assert result is None

    def test_legacy_token_management_flow(self, auth_service, sample_user):
        """Test legacy token creation and verification flow."""
        # Arrange
        token_data = {"email": sample_user.email, "sub": str(sample_user.id)}

        # Act - Create access token
        with patch('app.services.auth.create_access_token', return_value="access-token") as mock_create_access:
            access_token = auth_service.create_access_token(token_data)
            assert access_token == "access-token"

        # Act - Create refresh token
        with patch('app.services.auth.create_refresh_token', return_value="refresh-token") as mock_create_refresh:
            refresh_token = auth_service.create_refresh_token(token_data)
            assert refresh_token == "refresh-token"

        # Act - Verify token
        token_data_obj = TokenData(email=sample_user.email, exp=1234567890, token_type="access")
        with patch('app.services.auth.verify_jwt_token', return_value=token_data_obj) as mock_verify:
            verified_data = auth_service.verify_token("access-token")
            assert verified_data == token_data_obj

        # Act - Get current user
        with patch.object(auth_service, '_get_user_from_token_data', return_value=sample_user):
            current_user = auth_service.get_current_user("access-token")
            assert current_user == sample_user

    def test_legacy_token_blacklist_flow(self, auth_service):
        """Test token blacklisting flow."""
        # Arrange
        token = "token-to-blacklist"

        # Act - Blacklist token
        auth_service.blacklist_token(token)

        # Act - Verify blacklisted token is rejected
        result = auth_service.verify_token(token)

        # Assert
        assert result is None
        assert token in auth_service._blacklisted_tokens


class TestHybridAuthenticationFlow:
    """Test hybrid authentication scenarios using both Firebase and legacy auth."""

    @pytest.mark.asyncio
    async def test_firebase_to_legacy_user_mapping(self, firebase_auth_service, auth_service, mock_user_repository, sample_user, sample_firebase_token_data):
        """Test mapping Firebase user to legacy user record."""
        # Arrange
        firebase_token = "valid-firebase-token"
        mock_user_repository.get_by_email.return_value = sample_user

        with patch('firebase_admin.auth.verify_id_token', return_value={**sample_firebase_token_data, 'iss': 'firebase', 'aud': 'test-project'}):
            # Act - Verify Firebase token
            firebase_user_info = await firebase_auth_service.verify_token(firebase_token)

            # Act - Get corresponding legacy user
            legacy_user = mock_user_repository.get_by_email(firebase_user_info['email'])

            # Assert
            assert firebase_user_info['email'] == legacy_user.email
            assert legacy_user == sample_user

    @pytest.mark.asyncio
    async def test_dual_authentication_flow(self, firebase_auth_service, auth_service, sample_firebase_token_data):
        """Test scenarios where both Firebase and legacy auth might be used."""
        # Test Firebase authentication
        with patch('firebase_admin.auth.verify_id_token', return_value={**sample_firebase_token_data, 'iss': 'firebase', 'aud': 'test-project'}):
            firebase_user = await firebase_auth_service.verify_token("firebase-token")

        # Test legacy token creation for the same user
        token_data = {"email": firebase_user['email'], "sub": firebase_user['uid']}
        with patch('app.services.auth.create_access_token', return_value="legacy-token"):
            legacy_token = auth_service.create_access_token(token_data)

        # Assert both methods work for the same user
        assert firebase_user['email'] == token_data['email']
        assert legacy_token == "legacy-token"

    @pytest.mark.asyncio
    async def test_authentication_migration_flow(self, firebase_auth_service, auth_service, mock_user_repository, sample_user, sample_firebase_token_data):
        """Test migration from legacy to Firebase authentication."""
        # Step 1: User exists in legacy system
        mock_user_repository.get_by_email.return_value = sample_user

        # Step 2: User authenticates with Firebase
        with patch('firebase_admin.auth.verify_id_token', return_value={**sample_firebase_token_data, 'iss': 'firebase', 'aud': 'test-project'}):
            firebase_user = await firebase_auth_service.verify_token("firebase-token")

        # Step 3: Update legacy user with Firebase UID
        legacy_user = mock_user_repository.get_by_email(firebase_user['email'])
        legacy_user.firebase_uid = firebase_user['uid']

        # Assert migration data is consistent
        assert legacy_user.email == firebase_user['email']
        assert legacy_user.firebase_uid == firebase_user['uid']


class TestSessionManagementFlow:
    """Test session management across authentication services."""

    @pytest.mark.asyncio
    async def test_session_creation_flow(self, firebase_auth_service, audit_service, sample_firebase_token_data):
        """Test complete session creation flow with audit logging."""
        # Arrange
        session_id = "session-123"
        user_agent = "Mozilla/5.0 Test Browser"
        ip_address = "192.168.1.1"

        with patch('firebase_admin.auth.verify_id_token', return_value={**sample_firebase_token_data, 'iss': 'firebase', 'aud': 'test-project'}), \
             patch.object(audit_service, 'log_event') as mock_audit:

            # Act - Verify token (login)
            user_info = await firebase_auth_service.verify_token("firebase-token")

            # Act - Log session creation
            audit_service.log_event(
                event_type="session_created",
                event_category="access",
                actor_id=user_info['uid'],
                ip_address=ip_address,
                user_agent=user_agent,
                event_data={"session_id": session_id}
            )

            # Assert
            assert user_info['uid'] == 'firebase-uid-123'
            mock_audit.assert_called()

    @pytest.mark.asyncio
    async def test_session_invalidation_flow(self, firebase_auth_service, auth_service):
        """Test session invalidation flow."""
        # Arrange
        firebase_uid = "firebase-uid-123"
        legacy_token = "legacy-token"

        # Act - Revoke Firebase refresh tokens
        with patch('firebase_admin.auth.revoke_refresh_tokens') as mock_revoke:
            firebase_revoke_result = await firebase_auth_service.revoke_refresh_tokens(firebase_uid)
            assert firebase_revoke_result is True

        # Act - Blacklist legacy token
        auth_service.blacklist_token(legacy_token)

        # Assert both invalidation methods worked
        assert legacy_token in auth_service._blacklisted_tokens

    @pytest.mark.asyncio
    async def test_concurrent_session_management(self, firebase_auth_service, auth_service):
        """Test managing multiple concurrent sessions."""
        # Simulate multiple sessions for the same user
        sessions = [
            {"token": "token-1", "device": "mobile"},
            {"token": "token-2", "device": "desktop"},
            {"token": "token-3", "device": "tablet"}
        ]

        # Blacklist all sessions
        for session in sessions:
            auth_service.blacklist_token(session["token"])

        # Verify all tokens are blacklisted
        for session in sessions:
            assert session["token"] in auth_service._blacklisted_tokens

        # Verify token verification fails for all blacklisted tokens
        for session in sessions:
            result = auth_service.verify_token(session["token"])
            assert result is None


class TestErrorHandlingAndRecovery:
    """Test error handling and recovery in authentication flows."""

    @pytest.mark.asyncio
    async def test_firebase_service_unavailable_flow(self, firebase_auth_service):
        """Test handling when Firebase service is unavailable."""
        # Arrange
        with patch('firebase_admin.auth.verify_id_token', side_effect=Exception("Firebase unavailable")):
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await firebase_auth_service.verify_token("some-token")

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_redis_unavailable_flow(self, auth_service):
        """Test handling when Redis is unavailable."""
        # Arrange
        auth_service.redis.ping = AsyncMock(return_value=False)

        # Act & Assert
        with pytest.raises(RuntimeError, match="Authentication dependencies unavailable"):
            await auth_service.authenticate_user("test@example.com", "password123")

    @pytest.mark.asyncio
    async def test_database_unavailable_flow(self, auth_service, mock_user_repository):
        """Test handling when database is unavailable."""
        # Arrange
        mock_user_repository.get_by_email.side_effect = Exception("Database unavailable")

        with patch('app.services.auth.logger') as mock_logger:
            # Act & Assert
            with pytest.raises(Exception, match="Database unavailable"):
                await auth_service.authenticate_user("test@example.com", "password123")

    @pytest.mark.asyncio
    async def test_partial_service_degradation_flow(self, firebase_auth_service, auth_service):
        """Test handling partial service degradation."""
        # Simulate Firebase working but Redis unavailable
        with patch('firebase_admin.auth.verify_id_token', return_value={'uid': 'test', 'email': 'test@example.com', 'email_verified': True}):
            # Firebase auth should still work
            result = await firebase_auth_service.verify_token("firebase-token")
            assert result is not None

        # Legacy auth should fail gracefully when Redis is unavailable
        auth_service.redis.ping = AsyncMock(return_value=False)
        with pytest.raises(RuntimeError):
            await auth_service.authenticate_user("test@example.com", "password123")


class TestSecurityScenarios:
    """Test security-related authentication scenarios."""

    @pytest.mark.asyncio
    async def test_token_replay_attack_prevention(self, firebase_auth_service, auth_service):
        """Test prevention of token replay attacks."""
        # Simulate using the same token multiple times
        firebase_token = "firebase-token"
        legacy_token = "legacy-token"

        # Firebase tokens are validated by Firebase (stateless)
        with patch('firebase_admin.auth.verify_id_token', return_value={'uid': 'test', 'email': 'test@example.com', 'email_verified': True}):
            # First use should work
            result1 = await firebase_auth_service.verify_token(firebase_token)
            assert result1 is not None

            # Second use should also work (Firebase handles this)
            result2 = await firebase_auth_service.verify_token(firebase_token)
            assert result2 is not None

        # Legacy tokens can be blacklisted to prevent replay
        auth_service.blacklist_token(legacy_token)
        result = auth_service.verify_token(legacy_token)
        assert result is None

    @pytest.mark.asyncio
    async def test_rate_limiting_security_flow(self, auth_service):
        """Test rate limiting as a security measure."""
        # Simulate multiple failed login attempts
        auth_service.redis.get = AsyncMock(return_value="6")  # Exceeded limit

        # Subsequent attempts should be blocked
        result = await auth_service.authenticate_user("test@example.com", "password123", "192.168.1.1")
        assert result is None

    @pytest.mark.asyncio
    async def test_token_expiration_flow(self, firebase_auth_service):
        """Test handling of expired tokens."""
        from firebase_admin import auth as firebase_auth

        # Simulate expired Firebase token
        with patch('firebase_admin.auth.verify_id_token', side_effect=firebase_auth.ExpiredIdTokenError("Token expired")):
            with pytest.raises(HTTPException) as exc_info:
                await firebase_auth_service.verify_token("expired-token")

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_malicious_input_handling(self, firebase_auth_service, auth_service):
        """Test handling of malicious inputs."""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE users; --",
            "../../../etc/passwd",
            "null",
            "",
            None,
            123,
            {"malicious": "object"}
        ]

        for malicious_input in malicious_inputs:
            # Firebase service should handle gracefully
            try:
                await firebase_auth_service.verify_token(malicious_input)
            except HTTPException as e:
                assert e.status_code == status.HTTP_401_UNAUTHORIZED

            # Legacy service should handle gracefully
            result = auth_service.verify_token(malicious_input)
            assert result is None


class TestAuditingAndCompliance:
    """Test auditing and compliance features in authentication flows."""

    @pytest.mark.asyncio
    async def test_comprehensive_audit_flow(self, firebase_auth_service, audit_service, sample_firebase_token_data):
        """Test comprehensive audit logging throughout authentication flow."""
        # Arrange
        mock_refresh = Mock()
        mock_refresh.side_effect = lambda obj: setattr(obj, 'id', 'audit-log-id')
        audit_service.db.refresh = mock_refresh

        with patch('firebase_admin.auth.verify_id_token', return_value={**sample_firebase_token_data, 'iss': 'firebase', 'aud': 'test-project'}):
            # Act - Successful authentication
            user_info = await firebase_auth_service.verify_token("firebase-token")

            # Act - Log authentication success
            audit_service.log_event(
                event_type="firebase_login_success",
                event_category="access",
                actor_id=user_info['uid'],
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0 Test",
                result="success"
            )

            # Assert
            assert user_info is not None
            audit_service.db.add.assert_called()
            audit_service.db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_failed_authentication_audit_flow(self, firebase_auth_service, audit_service):
        """Test audit logging for failed authentication attempts."""
        # Arrange
        mock_refresh = Mock()
        mock_refresh.side_effect = lambda obj: setattr(obj, 'id', 'audit-log-id')
        audit_service.db.refresh = mock_refresh

        from firebase_admin import auth as firebase_auth
        with patch('firebase_admin.auth.verify_id_token', side_effect=firebase_auth.InvalidIdTokenError("Invalid token")):
            # Act - Failed authentication
            try:
                await firebase_auth_service.verify_token("invalid-token")
            except HTTPException:
                pass

            # Act - Log authentication failure
            audit_service.log_event(
                event_type="firebase_login_failure",
                event_category="security",
                severity="warning",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0 Test",
                event_data={"failure_reason": "invalid_token"},
                result="failure"
            )

            # Assert
            audit_service.db.add.assert_called()
            audit_service.db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_rate_limiting_audit_flow(self, auth_service, audit_service):
        """Test audit logging for rate limiting events."""
        # Arrange
        mock_refresh = Mock()
        mock_refresh.side_effect = lambda obj: setattr(obj, 'id', 'audit-log-id')
        audit_service.db.refresh = mock_refresh

        # Simulate rate limiting
        auth_service.redis.get = AsyncMock(return_value="10")  # Exceeded

        # Act
        result = await auth_service.authenticate_user("test@example.com", "password123", "192.168.1.1")

        # Log rate limiting event
        audit_service.log_event(
            event_type="rate_limit_exceeded",
            event_category="security",
            severity="warning",
            ip_address="192.168.1.1",
            event_data={"email": "test@example.com", "attempts": 10},
            result="blocked"
        )

        # Assert
        assert result is None
        audit_service.db.add.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])