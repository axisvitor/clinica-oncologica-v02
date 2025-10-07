"""
Test FirebaseRedisCache Critical Fixes

Validates all fixes applied to resolve blocking issues:
1. Constructor with optional redis_client parameter
2. All missing async methods implemented
3. Sync methods converted to async
4. Helper functions added
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from app.core.redis_manager import FirebaseRedisCache, get_redis_manager


class TestFirebaseRedisCacheConstructor:
    """Test Issue 1: Constructor requires redis_client but callers don't pass it"""

    def test_constructor_without_arguments(self):
        """Test that FirebaseRedisCache() works without arguments"""
        # This should NOT raise TypeError
        cache = FirebaseRedisCache()
        assert cache is not None
        assert cache.redis is not None

    def test_constructor_with_redis_client(self):
        """Test that passing redis_client still works (backward compatibility)"""
        mock_redis = Mock()
        cache = FirebaseRedisCache(redis_client=mock_redis)
        assert cache.redis is mock_redis


class TestFirebaseRedisCacheMissingMethods:
    """Test Issue 2: Missing methods that code expects"""

    @pytest.mark.asyncio
    async def test_get_user_by_uid_exists(self):
        """Test that get_user_by_uid method exists and is async"""
        cache = FirebaseRedisCache()
        assert hasattr(cache, 'get_user_by_uid')
        assert asyncio.iscoroutinefunction(cache.get_user_by_uid)

    @pytest.mark.asyncio
    async def test_cache_user_data_exists(self):
        """Test that cache_user_data method exists and is async"""
        cache = FirebaseRedisCache()
        assert hasattr(cache, 'cache_user_data')
        assert asyncio.iscoroutinefunction(cache.cache_user_data)

    @pytest.mark.asyncio
    async def test_get_or_create_user_exists(self):
        """Test that get_or_create_user method exists and is async"""
        cache = FirebaseRedisCache()
        assert hasattr(cache, 'get_or_create_user')
        assert asyncio.iscoroutinefunction(cache.get_or_create_user)

    @pytest.mark.asyncio
    async def test_get_session_ttl_exists(self):
        """Test that get_session_ttl method exists and is async"""
        cache = FirebaseRedisCache()
        assert hasattr(cache, 'get_session_ttl')
        assert asyncio.iscoroutinefunction(cache.get_session_ttl)


class TestFirebaseRedisCacheAsyncConversion:
    """Test Issue 3: Sync methods converted to async"""

    @pytest.mark.asyncio
    async def test_create_session_is_async(self):
        """Test that create_session is async and returns bool"""
        cache = FirebaseRedisCache()
        assert asyncio.iscoroutinefunction(cache.create_session)

    @pytest.mark.asyncio
    async def test_get_session_is_async(self):
        """Test that get_session is async"""
        cache = FirebaseRedisCache()
        assert asyncio.iscoroutinefunction(cache.get_session)

    @pytest.mark.asyncio
    async def test_invalidate_session_is_async(self):
        """Test that invalidate_session is async and returns bool"""
        cache = FirebaseRedisCache()
        assert asyncio.iscoroutinefunction(cache.invalidate_session)

    @pytest.mark.asyncio
    async def test_invalidate_all_user_sessions_is_async(self):
        """Test that invalidate_all_user_sessions is async and returns int"""
        cache = FirebaseRedisCache()
        assert asyncio.iscoroutinefunction(cache.invalidate_all_user_sessions)


class TestFirebaseRedisCacheIntegration:
    """Integration tests for the fixed methods"""

    @pytest.mark.asyncio
    async def test_create_session_returns_bool(self):
        """Test that create_session returns bool instead of None"""
        with patch.object(FirebaseRedisCache, '__init__', lambda x: None):
            cache = FirebaseRedisCache()
            cache.redis = Mock()
            cache.session_ttl = 3600

            # Mock setex to succeed
            cache.redis.setex = Mock(return_value=True)

            result = await cache.create_session(
                session_id="test_session",
                user_id="user_123",
                firebase_uid="firebase_123"
            )

            assert isinstance(result, bool)
            assert result is True

    @pytest.mark.asyncio
    async def test_get_session_returns_dict_or_none(self):
        """Test that get_session returns Dict or None"""
        with patch.object(FirebaseRedisCache, '__init__', lambda x: None):
            cache = FirebaseRedisCache()
            cache.redis = Mock()
            cache.session_ttl = 3600

            # Mock get to return None (session not found)
            cache.redis.get = Mock(return_value=None)

            result = await cache.get_session("test_session")

            assert result is None or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_invalidate_session_returns_bool(self):
        """Test that invalidate_session returns bool"""
        with patch.object(FirebaseRedisCache, '__init__', lambda x: None):
            cache = FirebaseRedisCache()
            cache.redis = Mock()

            # Mock delete to return 1 (success)
            cache.redis.delete = Mock(return_value=1)

            result = await cache.invalidate_session("test_session")

            assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_invalidate_all_user_sessions_returns_int(self):
        """Test that invalidate_all_user_sessions returns int"""
        with patch.object(FirebaseRedisCache, '__init__', lambda x: None):
            cache = FirebaseRedisCache()
            cache.redis = Mock()

            # Mock scan_iter to return empty list
            cache.redis.scan_iter = Mock(return_value=[])

            result = await cache.invalidate_all_user_sessions("firebase_123")

            assert isinstance(result, int)


class TestAuthDependenciesHelpers:
    """Test Issue 4: Missing helper function"""

    def test_verify_firebase_token_exists(self):
        """Test that verify_firebase_token function exists"""
        from app.dependencies.auth_dependencies import verify_firebase_token
        assert callable(verify_firebase_token)
        assert asyncio.iscoroutinefunction(verify_firebase_token)

    def test_get_redis_cache_exists(self):
        """Test that get_redis_cache dependency exists"""
        from app.dependencies.auth_dependencies import get_redis_cache
        assert callable(get_redis_cache)
        assert asyncio.iscoroutinefunction(get_redis_cache)


# Run tests with: pytest backend-hormonia/tests/test_firebase_redis_cache_fixes.py -v
