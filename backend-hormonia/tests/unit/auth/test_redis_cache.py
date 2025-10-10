"""
Unit tests for Redis cache functionality.

Tests the FirebaseRedisCache class including session management,
user caching, token validation, and all cache layers.
"""

import pytest
import json
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, Optional

from app.core.redis_manager import FirebaseRedisCache, RedisManager
from app.models.user import User, UserRole


class TestFirebaseRedisCache:
    """Test suite for FirebaseRedisCache class."""

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client."""
        client = Mock()
        client.ping.return_value = True
        return client

    @pytest.fixture
    def cache_instance(self, mock_redis_client):
        """Create FirebaseRedisCache instance with mocked Redis."""
        return FirebaseRedisCache(mock_redis_client)

    @pytest.fixture
    def sample_user_data(self):
        """Sample user data for testing."""
        return {
            "firebase_uid": "test-firebase-uid",
            "email": "test@example.com",
            "full_name": "Test User",
            "role": "doctor",
            "is_active": True,
            "id": "test-user-id"
        }

    @pytest.fixture
    def sample_firebase_data(self):
        """Sample Firebase user data."""
        return {
            "uid": "test-firebase-uid",
            "email": "test@example.com",
            "name": "Test User",
            "role": "doctor"
        }


class TestTokenCache:
    """Test Layer 1: Token validation cache."""

    def test_cache_validated_token(self, cache_instance, mock_redis_client, sample_firebase_data):
        """Test caching validated Firebase token."""
        token = "firebase-id-token"

        cache_instance.cache_validated_token(token, sample_firebase_data)

        # Verify Redis setex was called
        mock_redis_client.setex.assert_called_once()
        args = mock_redis_client.setex.call_args

        # Check key format
        key = args[0][0]
        assert key.startswith("firebase:token:")

        # Check TTL
        ttl = args[0][1]
        assert ttl == cache_instance.token_ttl

        # Check cached data
        cached_data = json.loads(args[0][2])
        assert cached_data["firebase_uid"] == sample_firebase_data["uid"]
        assert cached_data["email"] == sample_firebase_data["email"]

    def test_get_cached_token_hit(self, cache_instance, mock_redis_client, sample_firebase_data):
        """Test successful token cache retrieval."""
        token = "firebase-id-token"
        cached_data = {
            "firebase_uid": "test-firebase-uid",
            "email": "test@example.com",
            "validated_at": datetime.utcnow().isoformat()
        }

        mock_redis_client.get.return_value = json.dumps(cached_data)

        result = cache_instance.get_cached_token(token)

        assert result == cached_data
        mock_redis_client.get.assert_called_once()

    def test_get_cached_token_miss(self, cache_instance, mock_redis_client):
        """Test token cache miss."""
        token = "firebase-id-token"
        mock_redis_client.get.return_value = None

        result = cache_instance.get_cached_token(token)

        assert result is None
        mock_redis_client.get.assert_called_once()

    def test_invalidate_token(self, cache_instance, mock_redis_client):
        """Test token cache invalidation."""
        token = "firebase-id-token"

        cache_instance.invalidate_token(token)

        mock_redis_client.delete.assert_called_once()
        key = mock_redis_client.delete.call_args[0][0]
        assert key.startswith("firebase:token:")


class TestUserCache:
    """Test Layer 2: User object cache."""

    def test_cache_user(self, cache_instance, mock_redis_client, sample_user_data):
        """Test caching user data."""
        firebase_uid = "test-firebase-uid"

        cache_instance.cache_user(firebase_uid, sample_user_data)

        mock_redis_client.setex.assert_called_once()
        args = mock_redis_client.setex.call_args

        # Check key format
        key = args[0][0]
        assert key == f"user:firebase_uid:{firebase_uid}"

        # Check TTL
        ttl = args[0][1]
        assert ttl == cache_instance.user_ttl

        # Check cached data includes original data + timestamp
        cached_data = json.loads(args[0][2])
        assert cached_data["firebase_uid"] == sample_user_data["firebase_uid"]
        assert cached_data["email"] == sample_user_data["email"]
        assert "cached_at" in cached_data

    def test_get_cached_user_hit(self, cache_instance, mock_redis_client, sample_user_data):
        """Test successful user cache retrieval."""
        firebase_uid = "test-firebase-uid"
        cached_data = {**sample_user_data, "cached_at": datetime.utcnow().isoformat()}

        mock_redis_client.get.return_value = json.dumps(cached_data)

        result = cache_instance.get_cached_user(firebase_uid)

        assert result == cached_data
        mock_redis_client.get.assert_called_once()

    def test_get_cached_user_miss(self, cache_instance, mock_redis_client):
        """Test user cache miss."""
        firebase_uid = "test-firebase-uid"
        mock_redis_client.get.return_value = None

        result = cache_instance.get_cached_user(firebase_uid)

        assert result is None
        mock_redis_client.get.assert_called_once()

    def test_invalidate_user_cache(self, cache_instance, mock_redis_client):
        """Test user cache invalidation."""
        firebase_uid = "test-firebase-uid"

        cache_instance.invalidate_user_cache(firebase_uid)

        mock_redis_client.delete.assert_called_once()
        key = mock_redis_client.delete.call_args[0][0]
        assert key == f"user:firebase_uid:{firebase_uid}"


class TestSessionManagement:
    """Test Layer 3: Session management."""

    @pytest.mark.asyncio
    async def test_create_session(self, cache_instance, mock_redis_client):
        """Test session creation."""
        session_id = "test-session-id"
        user_id = "test-user-id"
        firebase_uid = "test-firebase-uid"
        metadata = {"device": "iPhone", "ip": "192.168.1.1"}

        # Mock asyncio.to_thread for sync Redis operations
        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = True

            result = await cache_instance.create_session(
                session_id=session_id,
                user_id=user_id,
                firebase_uid=firebase_uid,
                metadata=metadata,
                ttl=3600
            )

            assert result is True
            mock_to_thread.assert_called()

    @pytest.mark.asyncio
    async def test_get_session_success(self, cache_instance, mock_redis_client):
        """Test successful session retrieval."""
        session_id = "test-session-id"
        session_data = {
            "user_id": "test-user-id",
            "firebase_uid": "test-firebase-uid",
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": (datetime.utcnow() - timedelta(minutes=5)).isoformat()
        }

        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            # First call returns session data, second call for setex
            mock_to_thread.side_effect = [json.dumps(session_data), True]

            result = await cache_instance.get_session(session_id)

            assert result is not None
            assert result["user_id"] == session_data["user_id"]
            assert result["firebase_uid"] == session_data["firebase_uid"]
            # last_activity should be updated
            assert result["last_activity"] != session_data["last_activity"]

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, cache_instance, mock_redis_client):
        """Test session retrieval when session doesn't exist."""
        session_id = "non-existent-session"

        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = None

            result = await cache_instance.get_session(session_id)

            assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_session_success(self, cache_instance, mock_redis_client):
        """Test successful session invalidation."""
        session_id = "test-session-id"

        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = 1  # 1 key deleted

            result = await cache_instance.invalidate_session(session_id)

            assert result is True

    @pytest.mark.asyncio
    async def test_invalidate_session_not_found(self, cache_instance, mock_redis_client):
        """Test session invalidation when session doesn't exist."""
        session_id = "non-existent-session"

        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = 0  # 0 keys deleted

            result = await cache_instance.invalidate_session(session_id)

            assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_all_user_sessions(self, cache_instance, mock_redis_client):
        """Test invalidating all sessions for a user."""
        firebase_uid = "test-firebase-uid"

        # Mock scan_iter to return some session keys
        session_keys = [
            b"session:session1",
            b"session:session2",
            b"session:session3"
        ]

        # Mock session data for sessions belonging to the user
        session_data_1 = {"firebase_uid": firebase_uid, "user_id": "user1"}
        session_data_2 = {"firebase_uid": "other-uid", "user_id": "user2"}
        session_data_3 = {"firebase_uid": firebase_uid, "user_id": "user3"}

        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            # Setup return values for asyncio.to_thread calls
            mock_to_thread.side_effect = [
                session_keys,  # scan_iter result
                json.dumps(session_data_1),  # get session1 data
                True,  # delete session1
                json.dumps(session_data_2),  # get session2 data (different user)
                json.dumps(session_data_3),  # get session3 data
                True   # delete session3
            ]

            result = await cache_instance.invalidate_all_user_sessions(firebase_uid)

            # Should delete 2 sessions (session1 and session3)
            assert result == 2

    def test_list_user_sessions(self, cache_instance, mock_redis_client):
        """Test listing all sessions for a user."""
        firebase_uid = "test-firebase-uid"

        # Mock scan_iter to return session keys
        session_keys = [
            "session:session1",
            "session:session2",
            "session:session3"
        ]
        mock_redis_client.scan_iter.return_value = session_keys

        # Mock session data
        session_data_1 = {"firebase_uid": firebase_uid, "user_id": "user1"}
        session_data_2 = {"firebase_uid": "other-uid", "user_id": "user2"}
        session_data_3 = {"firebase_uid": firebase_uid, "user_id": "user3"}

        # Setup get method to return different data for each key
        def mock_get(key):
            if key == "session:session1":
                return json.dumps(session_data_1)
            elif key == "session:session2":
                return json.dumps(session_data_2)
            elif key == "session:session3":
                return json.dumps(session_data_3)
            return None

        mock_redis_client.get.side_effect = mock_get

        result = cache_instance.list_user_sessions(firebase_uid)

        # Should return 2 sessions (session1 and session3)
        assert len(result) == 2
        assert all(session["firebase_uid"] == firebase_uid for session in result)
        assert any(session["session_id"] == "session1" for session in result)
        assert any(session["session_id"] == "session3" for session in result)


class TestAsyncMethods:
    """Test async methods for compatibility."""

    @pytest.mark.asyncio
    async def test_get_user_by_uid_async(self, cache_instance, mock_redis_client, sample_user_data):
        """Test async user retrieval by UID."""
        firebase_uid = "test-firebase-uid"
        cached_data = {**sample_user_data, "cached_at": datetime.utcnow().isoformat()}

        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = json.dumps(cached_data)

            result = await cache_instance.get_user_by_uid(firebase_uid)

            assert result == cached_data

    @pytest.mark.asyncio
    async def test_cache_user_data_async(self, cache_instance, mock_redis_client, sample_user_data):
        """Test async user data caching."""
        firebase_uid = "test-firebase-uid"

        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = True

            await cache_instance.cache_user_data(firebase_uid, sample_user_data, ttl=900)

            mock_to_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_user_cache_hit(self, cache_instance, mock_redis_client, sample_user_data):
        """Test get_or_create_user with cache hit."""
        firebase_uid = "test-firebase-uid"
        mock_db = AsyncMock()

        with patch.object(cache_instance, 'get_user_by_uid', return_value=sample_user_data):
            result = await cache_instance.get_or_create_user(
                db=mock_db,
                firebase_uid=firebase_uid,
                email="test@example.com"
            )

            assert isinstance(result, User)
            assert result.firebase_uid == firebase_uid

    @pytest.mark.asyncio
    async def test_get_or_create_user_database_fallback(self, cache_instance, mock_redis_client):
        """Test get_or_create_user with cache miss and database fallback."""
        firebase_uid = "test-firebase-uid"
        email = "test@example.com"

        # Mock database user
        mock_user = Mock(spec=User)
        mock_user.id = "test-user-id"
        mock_user.firebase_uid = firebase_uid
        mock_user.email = email
        mock_user.full_name = "Test User"
        mock_user.role = UserRole.DOCTOR
        mock_user.is_active = True

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch.object(cache_instance, 'get_user_by_uid', return_value=None):
            with patch.object(cache_instance, 'cache_user_data', new_callable=AsyncMock):
                result = await cache_instance.get_or_create_user(
                    db=mock_db,
                    firebase_uid=firebase_uid,
                    email=email
                )

                assert result == mock_user
                mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_user_create_new(self, cache_instance, mock_redis_client):
        """Test get_or_create_user with new user creation."""
        firebase_uid = "test-firebase-uid"
        email = "test@example.com"
        display_name = "Test User"

        # Mock empty database result
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.add = Mock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        with patch.object(cache_instance, 'get_user_by_uid', return_value=None):
            with patch.object(cache_instance, 'cache_user_data', new_callable=AsyncMock):
                with patch('app.core.redis_manager.User') as MockUser:
                    mock_new_user = Mock(spec=User)
                    mock_new_user.id = "new-user-id"
                    mock_new_user.firebase_uid = firebase_uid
                    mock_new_user.email = email
                    mock_new_user.full_name = display_name
                    mock_new_user.role = UserRole.DOCTOR
                    mock_new_user.is_active = True
                    MockUser.return_value = mock_new_user

                    result = await cache_instance.get_or_create_user(
                        db=mock_db,
                        firebase_uid=firebase_uid,
                        email=email,
                        display_name=display_name
                    )

                    assert result == mock_new_user
                    mock_db.add.assert_called_once()
                    mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session_ttl(self, cache_instance, mock_redis_client):
        """Test getting session TTL."""
        session_id = "test-session-id"
        expected_ttl = 3600

        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = expected_ttl

            result = await cache_instance.get_session_ttl(session_id)

            assert result == expected_ttl


class TestCacheStats:
    """Test cache statistics and monitoring."""

    def test_get_cache_stats(self, cache_instance, mock_redis_client):
        """Test cache statistics retrieval."""
        # Mock active sessions
        session_keys = ["session:1", "session:2", "session:3"]
        mock_redis_client.scan_iter.return_value = session_keys

        stats = cache_instance.get_cache_stats()

        assert stats["token_cache_ttl"] == cache_instance.token_ttl
        assert stats["user_cache_ttl"] == cache_instance.user_ttl
        assert stats["session_ttl"] == cache_instance.session_ttl
        assert stats["redis_connection"] == "healthy"
        assert stats["active_sessions"] == 3

    def test_get_cache_stats_unhealthy_redis(self, cache_instance, mock_redis_client):
        """Test cache statistics with unhealthy Redis."""
        mock_redis_client.ping.return_value = False
        mock_redis_client.scan_iter.return_value = []

        stats = cache_instance.get_cache_stats()

        assert stats["redis_connection"] == "unhealthy"
        assert stats["active_sessions"] == 0


class TestErrorHandling:
    """Test error handling in cache operations."""

    @pytest.mark.asyncio
    async def test_create_session_redis_error(self, cache_instance, mock_redis_client):
        """Test session creation with Redis error."""
        session_id = "test-session-id"

        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = Exception("Redis connection error")

            result = await cache_instance.create_session(
                session_id=session_id,
                user_id="user-id",
                firebase_uid="firebase-uid"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_get_session_redis_error(self, cache_instance, mock_redis_client):
        """Test session retrieval with Redis error."""
        session_id = "test-session-id"

        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = Exception("Redis connection error")

            result = await cache_instance.get_session(session_id)

            assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_session_redis_error(self, cache_instance, mock_redis_client):
        """Test session invalidation with Redis error."""
        session_id = "test-session-id"

        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = Exception("Redis connection error")

            result = await cache_instance.invalidate_session(session_id)

            assert result is False


class TestCompatibilityMethods:
    """Test methods for backward compatibility."""

    def test_custom_ttl_parameters(self, cache_instance, mock_redis_client):
        """Test custom TTL parameter handling."""
        # Test both ttl_seconds and ttl parameters
        cache_instance.cache_validated_token(
            "token",
            {"uid": "test"},
            ttl_seconds=1800
        )

        args = mock_redis_client.setex.call_args
        assert args[0][1] == 1800  # Custom TTL used


if __name__ == "__main__":
    pytest.main([__file__, "-v"])