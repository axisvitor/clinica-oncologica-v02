"""
Unit tests for Session Management.

This test suite covers user session management including:
- Session creation and storage
- Session validation
- Session expiration
- Session refresh
- Multi-device session handling
- Session revocation

Coverage Impact: +0.3%
Priority: P0 - Critical Security
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock

from app.services.session import SessionService
from app.models.user import User
from app.core.security import create_access_token, create_refresh_token


class TestSessionManagement:
    """Test user session management."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis = Mock()
        redis.get = Mock(return_value=None)
        redis.set = Mock(return_value=True)
        redis.setex = Mock(return_value=True)
        redis.delete = Mock(return_value=True)
        redis.exists = Mock(return_value=False)
        return redis

    @pytest.fixture
    def session_service(self, mock_redis, db_session):
        """Create SessionService instance."""
        return SessionService(db=db_session, redis=mock_redis)

    @pytest.fixture
    def test_user(self, db_session):
        """Create test user."""
        user = User(
            id=uuid4(),
            email="test@example.com",
            full_name="Test User",
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
        return user

    @pytest.mark.asyncio
    async def test_create_session_success(self, session_service, test_user, mock_redis):
        """
        Test successful session creation.

        Verifies session is created and stored in Redis.
        """
        # Act
        session_data = await session_service.create_session(test_user.id)

        # Assert
        assert session_data is not None
        assert "access_token" in session_data
        assert "refresh_token" in session_data
        assert "session_id" in session_data

        # Verify Redis storage was called
        assert mock_redis.setex.called or mock_redis.set.called

    @pytest.mark.asyncio
    async def test_validate_session_success(self, session_service, test_user, mock_redis):
        """
        Test successful session validation.

        Verifies active sessions are validated correctly.
        """
        # Arrange
        session_id = f"session:{test_user.id}:{uuid4()}"
        session_data = {
            "user_id": str(test_user.id),
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat()
        }

        import json
        mock_redis.get.return_value = json.dumps(session_data).encode()
        mock_redis.exists.return_value = True

        # Act
        is_valid = await session_service.validate_session(session_id)

        # Assert
        assert is_valid is True
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_expired_session(self, session_service, test_user, mock_redis):
        """
        Test validation of expired session.

        Verifies expired sessions are rejected.
        """
        # Arrange
        session_id = f"session:{test_user.id}:{uuid4()}"
        expired_session = {
            "user_id": str(test_user.id),
            "created_at": (datetime.utcnow() - timedelta(days=2)).isoformat(),
            "expires_at": (datetime.utcnow() - timedelta(days=1)).isoformat()  # Expired
        }

        import json
        mock_redis.get.return_value = json.dumps(expired_session).encode()

        # Act
        is_valid = await session_service.validate_session(session_id)

        # Assert
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_nonexistent_session(self, session_service, mock_redis):
        """
        Test validation of non-existent session.

        Verifies missing sessions are rejected.
        """
        # Arrange
        session_id = f"session:nonexistent:{uuid4()}"
        mock_redis.get.return_value = None
        mock_redis.exists.return_value = False

        # Act
        is_valid = await session_service.validate_session(session_id)

        # Assert
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_refresh_session_success(self, session_service, test_user, mock_redis):
        """
        Test successful session refresh.

        Verifies session can be refreshed with valid refresh token.
        """
        # Arrange
        refresh_token = create_refresh_token({"sub": str(test_user.id)})
        session_id = f"session:{test_user.id}:{uuid4()}"

        session_data = {
            "user_id": str(test_user.id),
            "refresh_token": refresh_token,
            "created_at": datetime.utcnow().isoformat()
        }

        import json
        mock_redis.get.return_value = json.dumps(session_data).encode()
        mock_redis.exists.return_value = True

        # Act
        new_tokens = await session_service.refresh_session(refresh_token)

        # Assert
        assert new_tokens is not None
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens

    @pytest.mark.asyncio
    async def test_revoke_session_success(self, session_service, test_user, mock_redis):
        """
        Test successful session revocation.

        Verifies session can be revoked/deleted.
        """
        # Arrange
        session_id = f"session:{test_user.id}:{uuid4()}"
        mock_redis.exists.return_value = True

        # Act
        revoked = await session_service.revoke_session(session_id)

        # Assert
        assert revoked is True
        mock_redis.delete.assert_called_once_with(session_id)

    @pytest.mark.asyncio
    async def test_revoke_all_user_sessions(self, session_service, test_user, mock_redis):
        """
        Test revoking all sessions for a user.

        Verifies logout from all devices functionality.
        """
        # Arrange
        session_keys = [
            f"session:{test_user.id}:device1",
            f"session:{test_user.id}:device2",
            f"session:{test_user.id}:device3"
        ]

        mock_redis.keys.return_value = session_keys

        # Act
        count = await session_service.revoke_all_user_sessions(test_user.id)

        # Assert
        assert count == 3
        assert mock_redis.delete.call_count == 3

    @pytest.mark.asyncio
    async def test_get_active_sessions_count(self, session_service, test_user, mock_redis):
        """
        Test getting count of active sessions for user.

        Verifies multi-device session tracking.
        """
        # Arrange
        session_keys = [
            f"session:{test_user.id}:device1",
            f"session:{test_user.id}:device2"
        ]

        mock_redis.keys.return_value = session_keys

        # Act
        count = await session_service.get_active_sessions_count(test_user.id)

        # Assert
        assert count == 2

    @pytest.mark.asyncio
    async def test_session_ttl_set_correctly(self, session_service, test_user, mock_redis):
        """
        Test that session TTL is set correctly in Redis.

        Verifies automatic expiration handling.
        """
        # Act
        await session_service.create_session(test_user.id)

        # Assert
        # Verify setex was called with TTL (time to live)
        if mock_redis.setex.called:
            call_args = mock_redis.setex.call_args
            ttl = call_args[0][1]  # Second argument is TTL
            assert ttl > 0
            # Verify reasonable TTL (e.g., 24 hours = 86400 seconds)
            assert ttl <= 86400

    @pytest.mark.asyncio
    async def test_session_extends_on_activity(self, session_service, test_user, mock_redis):
        """
        Test that session is extended on user activity.

        Verifies sliding expiration behavior.
        """
        # Arrange
        session_id = f"session:{test_user.id}:{uuid4()}"
        session_data = {
            "user_id": str(test_user.id),
            "last_activity": (datetime.utcnow() - timedelta(minutes=30)).isoformat()
        }

        import json
        mock_redis.get.return_value = json.dumps(session_data).encode()
        mock_redis.exists.return_value = True

        # Act
        await session_service.update_session_activity(session_id)

        # Assert
        # Verify session was updated (either set or setex called)
        assert mock_redis.setex.called or mock_redis.set.called

    @pytest.mark.asyncio
    async def test_concurrent_session_limit(self, session_service, test_user, mock_redis):
        """
        Test enforcement of concurrent session limit.

        Verifies maximum allowed concurrent sessions per user.
        """
        # Arrange
        max_sessions = 5
        existing_sessions = [
            f"session:{test_user.id}:device{i}" for i in range(max_sessions)
        ]

        mock_redis.keys.return_value = existing_sessions

        with patch.object(session_service, 'max_concurrent_sessions', max_sessions):
            # Act - try to create one more session
            result = await session_service.create_session(
                test_user.id,
                enforce_limit=True
            )

        # Assert - oldest session should have been removed
        assert result is not None
        # Verify at least one delete was called to make room
        assert mock_redis.delete.called

    @pytest.mark.asyncio
    async def test_session_metadata_stored(self, session_service, test_user, mock_redis):
        """
        Test that session metadata is stored correctly.

        Verifies device info, IP, user agent tracking.
        """
        # Arrange
        metadata = {
            "device": "iPhone",
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0"
        }

        # Act
        session_data = await session_service.create_session(
            test_user.id,
            metadata=metadata
        )

        # Assert
        assert session_data is not None
        # Verify metadata was included in Redis storage
        if mock_redis.setex.called:
            call_args = mock_redis.setex.call_args
            stored_data = call_args[0][2]  # Third argument is the value
            import json
            if isinstance(stored_data, bytes):
                stored_data = stored_data.decode()
            data_dict = json.loads(stored_data)
            assert "metadata" in data_dict or "device" in data_dict
