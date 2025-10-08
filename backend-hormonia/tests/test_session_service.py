"""
Session Service Tests - Comprehensive test coverage for Redis session management
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import timedelta
from app.services.session_service import SessionService


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis_mock = MagicMock()
    redis_mock.hset = Mock(return_value=True)
    redis_mock.expire = Mock(return_value=True)
    redis_mock.hgetall = Mock(return_value={})
    redis_mock.ttl = Mock(return_value=86400)  # 1 day
    redis_mock.delete = Mock(return_value=1)
    redis_mock.exists = Mock(return_value=True)
    redis_mock.scan_iter = Mock(return_value=[])
    return redis_mock


@pytest.fixture
def session_service(mock_redis):
    """SessionService instance with mocked Redis"""
    return SessionService(mock_redis)


class TestSessionCreation:
    """Test session creation functionality"""

    def test_create_session_basic(self, session_service, mock_redis):
        """Should create session with user_id and return session_id"""
        session_id = session_service.create_session("user123")

        assert session_id is not None
        assert len(session_id) > 20  # URL-safe token
        mock_redis.hset.assert_called_once()
        mock_redis.expire.assert_called_once()

    def test_create_session_with_metadata(self, session_service, mock_redis):
        """Should create session with additional metadata"""
        metadata = {"device_id": "device123", "ip_address": "192.168.1.1"}
        session_id = session_service.create_session("user123", metadata)

        assert session_id is not None
        call_args = mock_redis.hset.call_args
        assert "device_id" in str(call_args)
        assert "ip_address" in str(call_args)

    def test_create_session_sets_ttl(self, session_service, mock_redis):
        """Should set 7-day TTL on session"""
        session_id = session_service.create_session("user123")

        expected_ttl = int(timedelta(days=7).total_seconds())
        mock_redis.expire.assert_called_once()
        actual_ttl = mock_redis.expire.call_args[0][1]
        assert actual_ttl == expected_ttl


class TestSessionRetrieval:
    """Test session retrieval functionality"""

    def test_get_session_existing(self, session_service, mock_redis):
        """Should retrieve existing session data"""
        mock_redis.hgetall.return_value = {
            b"user_id": b"user123",
            b"created_at": b"2025-01-01T00:00:00"
        }

        session_data = session_service.get_session("session123")

        assert session_data is not None
        assert session_data["user_id"] == "user123"
        assert "created_at" in session_data

    def test_get_session_nonexistent(self, session_service, mock_redis):
        """Should return None for nonexistent session"""
        mock_redis.hgetall.return_value = {}

        session_data = session_service.get_session("invalid_session")

        assert session_data is None

    def test_get_user_id_valid_session(self, session_service, mock_redis):
        """Should extract user_id from valid session"""
        mock_redis.hgetall.return_value = {
            b"user_id": b"user123",
            b"email": b"test@example.com"
        }

        user_id = session_service.get_user_id("session123")

        assert user_id == "user123"

    def test_get_user_id_invalid_session(self, session_service, mock_redis):
        """Should return None for invalid session"""
        mock_redis.hgetall.return_value = {}

        user_id = session_service.get_user_id("invalid_session")

        assert user_id is None


class TestSessionRefresh:
    """Test session refresh functionality"""

    def test_refresh_session_near_expiry(self, session_service, mock_redis):
        """Should refresh session TTL when near expiry"""
        # TTL < 1 day (threshold)
        mock_redis.ttl.return_value = int(timedelta(hours=12).total_seconds())

        refreshed = session_service.refresh_session("session123")

        assert refreshed is True
        mock_redis.expire.assert_called_once()

    def test_refresh_session_not_near_expiry(self, session_service, mock_redis):
        """Should NOT refresh session when TTL > threshold"""
        # TTL > 1 day (threshold)
        mock_redis.ttl.return_value = int(timedelta(days=5).total_seconds())

        refreshed = session_service.refresh_session("session123")

        assert refreshed is False
        mock_redis.expire.assert_not_called()

    def test_refresh_session_expired(self, session_service, mock_redis):
        """Should return False for expired session"""
        mock_redis.ttl.return_value = -2  # Key doesn't exist

        refreshed = session_service.refresh_session("expired_session")

        assert refreshed is False


class TestSessionDeletion:
    """Test session deletion functionality"""

    def test_delete_session_existing(self, session_service, mock_redis):
        """Should delete existing session"""
        mock_redis.delete.return_value = 1

        deleted = session_service.delete_session("session123")

        assert deleted is True
        mock_redis.delete.assert_called_once()

    def test_delete_session_nonexistent(self, session_service, mock_redis):
        """Should return False for nonexistent session"""
        mock_redis.delete.return_value = 0

        deleted = session_service.delete_session("invalid_session")

        assert deleted is False


class TestSessionUpdate:
    """Test session metadata update functionality"""

    def test_update_session_metadata_valid(self, session_service, mock_redis):
        """Should update metadata for valid session"""
        mock_redis.exists.return_value = True
        metadata = {"last_activity": "2025-01-01T12:00:00"}

        updated = session_service.update_session_metadata("session123", metadata)

        assert updated is True
        mock_redis.hset.assert_called_once()

    def test_update_session_metadata_invalid(self, session_service, mock_redis):
        """Should return False for invalid session"""
        mock_redis.exists.return_value = False

        updated = session_service.update_session_metadata("invalid_session", {})

        assert updated is False
        mock_redis.hset.assert_not_called()


class TestBulkSessionDeletion:
    """Test bulk session deletion for user"""

    def test_delete_all_user_sessions(self, session_service, mock_redis):
        """Should delete all sessions for a user"""
        # Mock scan_iter to return 3 session keys
        mock_redis.scan_iter.return_value = [
            b"session:sess1",
            b"session:sess2",
            b"session:sess3"
        ]

        # Mock hgetall to return user_id for 2 sessions
        def mock_hgetall(key):
            if key in [b"session:sess1", b"session:sess2"]:
                return {b"user_id": b"user123"}
            return {b"user_id": b"other_user"}

        mock_redis.hgetall.side_effect = mock_hgetall

        deleted_count = session_service.delete_all_user_sessions("user123")

        assert deleted_count == 2
        assert mock_redis.delete.call_count == 2


class TestSessionSecurity:
    """Test security aspects of session management"""

    def test_session_id_randomness(self, session_service):
        """Should generate unique session IDs"""
        session_ids = set()
        for _ in range(100):
            session_id = session_service.create_session("user123")
            session_ids.add(session_id)

        # All 100 should be unique
        assert len(session_ids) == 100

    def test_session_id_length(self, session_service):
        """Should generate sufficiently long session IDs"""
        session_id = session_service.create_session("user123")

        # secrets.token_urlsafe(32) produces ~43 characters
        assert len(session_id) >= 40
