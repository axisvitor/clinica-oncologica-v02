"""
Integration Tests for Firebase/Redis Authentication Flow

Tests the complete authentication workflow:
1. Firebase token validation → Session creation
2. Session validation via Redis
3. Session logout (single and all)
4. Proper async/await usage
5. Error handling (invalid tokens, Redis failures, network errors)

These tests validate all fixes applied to resolve blocking issues.
"""

import pytest
import asyncio
import uuid
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any

from app.core.redis_manager import FirebaseRedisCache, get_redis_manager
from app.dependencies.auth_dependencies import verify_firebase_token, get_redis_cache
from app.models.user import User, UserRole


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
async def mock_redis_manager():
    """Create mock Redis manager for testing"""
    manager = Mock()

    # Mock sync Redis client
    sync_client = Mock()
    sync_client.setex = Mock(return_value=True)
    sync_client.get = Mock(return_value=None)
    sync_client.delete = Mock(return_value=1)
    sync_client.scan_iter = Mock(return_value=[])
    sync_client.ttl = Mock(return_value=3600)
    sync_client.ping = Mock(return_value=True)

    manager.get_compatible_client = Mock(return_value=sync_client)
    return manager


@pytest.fixture
async def firebase_cache(mock_redis_manager):
    """Create FirebaseRedisCache instance with mocked Redis"""
    with patch('app.core.redis_manager.get_redis_manager', return_value=mock_redis_manager):
        cache = FirebaseRedisCache()
        return cache


@pytest.fixture
def mock_firebase_token():
    """Generate mock Firebase ID token"""
    return "eyJhbGciOiJSUzI1NiIsImtpZCI6InRlc3Qta2V5In0.eyJ1aWQiOiJ0ZXN0X3VpZF8xMjMiLCJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJuYW1lIjoiVGVzdCBVc2VyIiwicm9sZSI6ImRvY3RvciIsImlhdCI6MTYwMDAwMDAwMCwiZXhwIjoxNjAwMDAzNjAwfQ.signature"


@pytest.fixture
def mock_firebase_user_data():
    """Mock Firebase user data returned from token verification"""
    return {
        "uid": "test_firebase_uid_123",
        "email": "test@example.com",
        "name": "Test User",
        "role": "doctor",
        "email_verified": True
    }


@pytest.fixture
async def mock_db_session():
    """Create mock database session"""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = Mock()
    return session


# =============================================================================
# TEST SESSION CREATION (POST /api/v1/auth/session)
# =============================================================================

class TestSessionCreation:
    """Test POST /api/v1/auth/session endpoint"""

    @pytest.mark.asyncio
    async def test_create_session_success(
        self,
        firebase_cache,
        mock_firebase_user_data,
        mock_db_session
    ):
        """Test successful session creation from Firebase token"""

        # Mock Firebase token verification
        with patch('app.dependencies.auth_dependencies.verify_firebase_token') as mock_verify:
            mock_verify.return_value = mock_firebase_user_data

            # Create session
            session_id = str(uuid.uuid4())
            user_id = "user_123"
            firebase_uid = mock_firebase_user_data["uid"]

            # CRITICAL TEST: Verify create_session returns bool, not coroutine
            result = await firebase_cache.create_session(
                session_id=session_id,
                user_id=user_id,
                firebase_uid=firebase_uid,
                ttl=3600
            )

            # Assert proper return type
            assert isinstance(result, bool), "create_session must return bool, not coroutine"
            assert result is True, "Session creation should succeed"

    @pytest.mark.asyncio
    async def test_create_session_stores_in_redis(
        self,
        firebase_cache,
        mock_firebase_user_data
    ):
        """Test that session is actually stored in Redis"""

        session_id = str(uuid.uuid4())
        user_id = "user_123"
        firebase_uid = mock_firebase_user_data["uid"]

        # Mock Redis setex to track calls
        with patch.object(firebase_cache.redis, 'setex') as mock_setex:
            await firebase_cache.create_session(
                session_id=session_id,
                user_id=user_id,
                firebase_uid=firebase_uid,
                ttl=3600
            )

            # Verify Redis setex was called
            assert mock_setex.called, "Session should be stored in Redis"

            # Verify key format
            call_args = mock_setex.call_args[0]
            assert call_args[0] == f"session:{session_id}", "Redis key should use correct format"
            assert call_args[1] == 3600, "TTL should be 3600 seconds"

    @pytest.mark.asyncio
    async def test_create_session_with_metadata(
        self,
        firebase_cache,
        mock_firebase_user_data
    ):
        """Test session creation with device metadata"""

        session_id = str(uuid.uuid4())
        user_id = "user_123"
        firebase_uid = mock_firebase_user_data["uid"]
        metadata = {
            "device_type": "mobile",
            "os": "iOS 17",
            "browser": "Safari",
            "ip_address": "192.168.1.100"
        }

        result = await firebase_cache.create_session(
            session_id=session_id,
            user_id=user_id,
            firebase_uid=firebase_uid,
            metadata=metadata,
            ttl=3600
        )

        assert result is True, "Session with metadata should be created"

    @pytest.mark.asyncio
    async def test_create_session_with_invalid_firebase_token(
        self,
        firebase_cache,
        mock_firebase_token
    ):
        """Test session creation with invalid Firebase token"""

        # Mock Firebase verification failure
        with patch('app.dependencies.auth_dependencies.verify_firebase_token') as mock_verify:
            mock_verify.side_effect = Exception("Invalid Firebase token")

            # Should raise exception
            with pytest.raises(Exception, match="Invalid Firebase token"):
                await verify_firebase_token(mock_firebase_token)

    @pytest.mark.asyncio
    async def test_create_session_redis_failure(
        self,
        firebase_cache,
        mock_firebase_user_data
    ):
        """Test session creation when Redis is unavailable"""

        session_id = str(uuid.uuid4())
        user_id = "user_123"
        firebase_uid = mock_firebase_user_data["uid"]

        # Mock Redis failure
        with patch.object(firebase_cache.redis, 'setex', side_effect=Exception("Redis connection error")):
            result = await firebase_cache.create_session(
                session_id=session_id,
                user_id=user_id,
                firebase_uid=firebase_uid,
                ttl=3600
            )

            # Should return False on Redis failure
            assert result is False, "Session creation should fail gracefully when Redis is down"


# =============================================================================
# TEST SESSION VALIDATION (GET /api/v1/auth/session/validate)
# =============================================================================

class TestSessionValidation:
    """Test GET /api/v1/auth/session/validate endpoint"""

    @pytest.mark.asyncio
    async def test_validate_valid_session(
        self,
        firebase_cache,
        mock_firebase_user_data
    ):
        """Test validation of valid session"""

        session_id = str(uuid.uuid4())
        session_data = {
            "user_id": "user_123",
            "firebase_uid": mock_firebase_user_data["uid"],
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat()
        }

        # Mock Redis to return session data
        import json
        with patch.object(firebase_cache.redis, 'get', return_value=json.dumps(session_data)):
            result = await firebase_cache.get_session(session_id)

            # CRITICAL TEST: Verify result is dict, not coroutine
            assert isinstance(result, dict), "get_session must return dict, not coroutine"
            assert result["firebase_uid"] == mock_firebase_user_data["uid"]
            assert "last_activity" in result

    @pytest.mark.asyncio
    async def test_validate_invalid_session(
        self,
        firebase_cache
    ):
        """Test validation of invalid/expired session"""

        session_id = str(uuid.uuid4())

        # Mock Redis to return None (session not found)
        with patch.object(firebase_cache.redis, 'get', return_value=None):
            result = await firebase_cache.get_session(session_id)

            # Should return None for invalid session
            assert result is None, "Invalid session should return None"

    @pytest.mark.asyncio
    async def test_validate_session_updates_last_activity(
        self,
        firebase_cache,
        mock_firebase_user_data
    ):
        """Test that session validation updates last_activity timestamp"""

        session_id = str(uuid.uuid4())
        old_timestamp = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
        session_data = {
            "user_id": "user_123",
            "firebase_uid": mock_firebase_user_data["uid"],
            "created_at": old_timestamp,
            "last_activity": old_timestamp
        }

        import json
        with patch.object(firebase_cache.redis, 'get', return_value=json.dumps(session_data)):
            with patch.object(firebase_cache.redis, 'setex') as mock_setex:
                result = await firebase_cache.get_session(session_id)

                # Verify last_activity was updated
                assert result["last_activity"] != old_timestamp, "last_activity should be updated"

                # Verify Redis was updated
                assert mock_setex.called, "Session should be updated in Redis"

    @pytest.mark.asyncio
    async def test_get_session_ttl(
        self,
        firebase_cache
    ):
        """Test getting remaining TTL for a session"""

        session_id = str(uuid.uuid4())

        # Mock Redis TTL command
        with patch.object(firebase_cache.redis, 'ttl', return_value=3600):
            ttl = await firebase_cache.get_session_ttl(session_id)

            # CRITICAL TEST: Verify result is int, not coroutine
            assert isinstance(ttl, int), "get_session_ttl must return int, not coroutine"
            assert ttl == 3600, "TTL should match Redis value"

    @pytest.mark.asyncio
    async def test_get_session_ttl_expired(
        self,
        firebase_cache
    ):
        """Test getting TTL for expired session"""

        session_id = str(uuid.uuid4())

        # Mock Redis TTL for expired key (-2)
        with patch.object(firebase_cache.redis, 'ttl', return_value=-2):
            ttl = await firebase_cache.get_session_ttl(session_id)

            # Should return -1 for expired/missing keys
            assert ttl == -1, "Expired session should return -1"


# =============================================================================
# TEST SESSION LOGOUT (POST /api/v1/auth/logout)
# =============================================================================

class TestSessionLogout:
    """Test POST /api/v1/auth/logout endpoint"""

    @pytest.mark.asyncio
    async def test_logout_valid_session(
        self,
        firebase_cache
    ):
        """Test logout with valid session"""

        session_id = str(uuid.uuid4())

        # Mock Redis delete to return 1 (key deleted)
        with patch.object(firebase_cache.redis, 'delete', return_value=1):
            result = await firebase_cache.invalidate_session(session_id)

            # CRITICAL TEST: Verify result is bool, not coroutine
            assert isinstance(result, bool), "invalidate_session must return bool, not coroutine"
            assert result is True, "Valid session should be deleted"

    @pytest.mark.asyncio
    async def test_logout_invalid_session(
        self,
        firebase_cache
    ):
        """Test logout with invalid/expired session"""

        session_id = str(uuid.uuid4())

        # Mock Redis delete to return 0 (key not found)
        with patch.object(firebase_cache.redis, 'delete', return_value=0):
            result = await firebase_cache.invalidate_session(session_id)

            assert result is False, "Invalid session logout should return False"

    @pytest.mark.asyncio
    async def test_logout_redis_error(
        self,
        firebase_cache
    ):
        """Test logout when Redis fails"""

        session_id = str(uuid.uuid4())

        # Mock Redis delete to raise exception
        with patch.object(firebase_cache.redis, 'delete', side_effect=Exception("Redis error")):
            result = await firebase_cache.invalidate_session(session_id)

            # Should return False on error (graceful failure)
            assert result is False, "Logout should fail gracefully on Redis error"


# =============================================================================
# TEST LOGOUT ALL SESSIONS (POST /api/v1/auth/logout-all)
# =============================================================================

class TestLogoutAllSessions:
    """Test POST /api/v1/auth/logout-all endpoint"""

    @pytest.mark.asyncio
    async def test_logout_all_sessions_success(
        self,
        firebase_cache,
        mock_firebase_user_data
    ):
        """Test logout from all user sessions"""

        firebase_uid = mock_firebase_user_data["uid"]

        # Mock multiple sessions in Redis
        session_keys = [
            b"session:sess1",
            b"session:sess2",
            b"session:sess3"
        ]

        import json
        session_data = json.dumps({
            "firebase_uid": firebase_uid,
            "user_id": "user_123"
        })

        # Mock Redis scan and get operations
        with patch.object(firebase_cache.redis, 'scan_iter', return_value=session_keys):
            with patch.object(firebase_cache.redis, 'get', return_value=session_data):
                with patch.object(firebase_cache.redis, 'delete') as mock_delete:
                    result = await firebase_cache.invalidate_all_user_sessions(firebase_uid)

                    # CRITICAL TEST: Verify result is int, not coroutine
                    assert isinstance(result, int), "invalidate_all_user_sessions must return int, not coroutine"
                    assert result == 3, "Should delete all 3 sessions"
                    assert mock_delete.call_count == 3, "Redis delete should be called 3 times"

    @pytest.mark.asyncio
    async def test_logout_all_sessions_no_sessions(
        self,
        firebase_cache,
        mock_firebase_user_data
    ):
        """Test logout all when no sessions exist"""

        firebase_uid = mock_firebase_user_data["uid"]

        # Mock empty Redis scan
        with patch.object(firebase_cache.redis, 'scan_iter', return_value=[]):
            result = await firebase_cache.invalidate_all_user_sessions(firebase_uid)

            assert result == 0, "Should return 0 when no sessions found"

    @pytest.mark.asyncio
    async def test_logout_all_sessions_different_users(
        self,
        firebase_cache
    ):
        """Test logout all only deletes current user's sessions"""

        firebase_uid_a = "firebase_uid_a"
        firebase_uid_b = "firebase_uid_b"

        # Mock sessions from different users
        session_keys = [
            b"session:sess1",  # User A
            b"session:sess2",  # User B
            b"session:sess3"   # User A
        ]

        import json

        def mock_get(key):
            if key == b"session:sess1":
                return json.dumps({"firebase_uid": firebase_uid_a})
            elif key == b"session:sess2":
                return json.dumps({"firebase_uid": firebase_uid_b})
            elif key == b"session:sess3":
                return json.dumps({"firebase_uid": firebase_uid_a})
            return None

        with patch.object(firebase_cache.redis, 'scan_iter', return_value=session_keys):
            with patch.object(firebase_cache.redis, 'get', side_effect=mock_get):
                with patch.object(firebase_cache.redis, 'delete') as mock_delete:
                    result = await firebase_cache.invalidate_all_user_sessions(firebase_uid_a)

                    # Should only delete User A's sessions (2 sessions)
                    assert result == 2, "Should only delete User A's 2 sessions"
                    assert mock_delete.call_count == 2, "Should call delete twice"


# =============================================================================
# TEST ASYNC/AWAIT VALIDATION
# =============================================================================

class TestAsyncAwaitValidation:
    """Test that all firebase_cache methods are properly awaited"""

    @pytest.mark.asyncio
    async def test_all_async_methods_are_coroutines(
        self,
        firebase_cache
    ):
        """Test that all async methods are actual coroutines"""

        # List of async methods that MUST be coroutines
        async_methods = [
            'create_session',
            'get_session',
            'invalidate_session',
            'invalidate_all_user_sessions',
            'get_user_by_uid',
            'cache_user_data',
            'get_or_create_user',
            'get_session_ttl'
        ]

        for method_name in async_methods:
            method = getattr(firebase_cache, method_name)
            assert asyncio.iscoroutinefunction(method), \
                f"{method_name} must be an async coroutine function"

    @pytest.mark.asyncio
    async def test_no_coroutine_objects_returned(
        self,
        firebase_cache,
        mock_firebase_user_data
    ):
        """Test that methods return actual values, not coroutine objects"""

        session_id = str(uuid.uuid4())
        firebase_uid = mock_firebase_user_data["uid"]

        # Test create_session
        result = await firebase_cache.create_session(
            session_id=session_id,
            user_id="user_123",
            firebase_uid=firebase_uid
        )
        assert not asyncio.iscoroutine(result), "create_session should return bool, not coroutine"

        # Test invalidate_session
        result = await firebase_cache.invalidate_session(session_id)
        assert not asyncio.iscoroutine(result), "invalidate_session should return bool, not coroutine"

        # Test invalidate_all_user_sessions
        result = await firebase_cache.invalidate_all_user_sessions(firebase_uid)
        assert not asyncio.iscoroutine(result), "invalidate_all_user_sessions should return int, not coroutine"

        # Test get_session_ttl
        result = await firebase_cache.get_session_ttl(session_id)
        assert not asyncio.iscoroutine(result), "get_session_ttl should return int, not coroutine"


# =============================================================================
# TEST USER CACHE METHODS
# =============================================================================

class TestUserCacheMethods:
    """Test user-related cache methods"""

    @pytest.mark.asyncio
    async def test_get_user_by_uid_cache_hit(
        self,
        firebase_cache,
        mock_firebase_user_data
    ):
        """Test get_user_by_uid with cache hit"""

        firebase_uid = mock_firebase_user_data["uid"]

        import json
        cached_user = json.dumps({
            "firebase_uid": firebase_uid,
            "email": "test@example.com",
            "role": "doctor"
        })

        with patch.object(firebase_cache.redis, 'get', return_value=cached_user):
            result = await firebase_cache.get_user_by_uid(firebase_uid)

            assert isinstance(result, dict), "get_user_by_uid must return dict"
            assert result["firebase_uid"] == firebase_uid
            assert not asyncio.iscoroutine(result), "Must return dict, not coroutine"

    @pytest.mark.asyncio
    async def test_get_user_by_uid_cache_miss(
        self,
        firebase_cache,
        mock_firebase_user_data
    ):
        """Test get_user_by_uid with cache miss"""

        firebase_uid = mock_firebase_user_data["uid"]

        with patch.object(firebase_cache.redis, 'get', return_value=None):
            result = await firebase_cache.get_user_by_uid(firebase_uid)

            assert result is None, "Cache miss should return None"

    @pytest.mark.asyncio
    async def test_cache_user_data(
        self,
        firebase_cache,
        mock_firebase_user_data
    ):
        """Test caching user data"""

        firebase_uid = mock_firebase_user_data["uid"]
        user_data = {
            "firebase_uid": firebase_uid,
            "email": "test@example.com",
            "role": "doctor"
        }

        with patch.object(firebase_cache.redis, 'setex') as mock_setex:
            await firebase_cache.cache_user_data(firebase_uid, user_data, ttl=900)

            # Verify setex was called with correct parameters
            assert mock_setex.called, "User data should be cached in Redis"
            call_args = mock_setex.call_args[0]
            assert call_args[0] == f"user:firebase_uid:{firebase_uid}"
            assert call_args[1] == 900  # TTL


# =============================================================================
# TEST ERROR HANDLING
# =============================================================================

class TestErrorHandling:
    """Test error handling for various failure scenarios"""

    @pytest.mark.asyncio
    async def test_redis_connection_timeout(
        self,
        firebase_cache
    ):
        """Test handling of Redis connection timeout"""

        session_id = str(uuid.uuid4())

        # Mock Redis timeout
        from redis.exceptions import TimeoutError as RedisTimeoutError
        with patch.object(firebase_cache.redis, 'get', side_effect=RedisTimeoutError("Connection timeout")):
            result = await firebase_cache.get_session(session_id)

            # Should return None on timeout
            assert result is None, "Should handle timeout gracefully"

    @pytest.mark.asyncio
    async def test_redis_connection_error(
        self,
        firebase_cache
    ):
        """Test handling of Redis connection error"""

        session_id = str(uuid.uuid4())

        # Mock Redis connection error
        from redis.exceptions import ConnectionError as RedisConnectionError
        with patch.object(firebase_cache.redis, 'setex', side_effect=RedisConnectionError("Connection refused")):
            result = await firebase_cache.create_session(
                session_id=session_id,
                user_id="user_123",
                firebase_uid="firebase_uid_123"
            )

            # Should return False on connection error
            assert result is False, "Should handle connection error gracefully"

    @pytest.mark.asyncio
    async def test_invalid_json_in_redis(
        self,
        firebase_cache
    ):
        """Test handling of corrupted/invalid JSON in Redis"""

        session_id = str(uuid.uuid4())

        # Mock Redis returning invalid JSON
        with patch.object(firebase_cache.redis, 'get', return_value="invalid json {"):
            result = await firebase_cache.get_session(session_id)

            # Should return None for invalid data
            assert result is None, "Should handle invalid JSON gracefully"

    @pytest.mark.asyncio
    async def test_network_failure_during_logout_all(
        self,
        firebase_cache
    ):
        """Test network failure during logout all operation"""

        firebase_uid = "firebase_uid_123"

        # Mock network failure during scan
        with patch.object(firebase_cache.redis, 'scan_iter', side_effect=Exception("Network error")):
            result = await firebase_cache.invalidate_all_user_sessions(firebase_uid)

            # Should return 0 on error
            assert result == 0, "Should return 0 on network failure"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
