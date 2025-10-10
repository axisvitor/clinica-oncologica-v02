"""
Comprehensive unit tests for app.utils.cache module.
Tests caching decorators, cache managers, and Redis integration.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import timedelta, datetime
from decimal import Decimal
from uuid import UUID
import json

from app.utils.cache import (
    cache, CacheManager, AsyncCacheManager, get_cache_manager, get_async_cache_manager,
    _json_serializer, _serialize_for_cache, _deserialize_from_cache, _generate_cache_key,
    cache_user_data, get_cached_user_data, invalidate_user_cache,
    cache_user_data_async, get_cached_user_data_async, invalidate_user_cache_async,
    cache_patient_data, get_cached_patient_data, invalidate_patient_cache,
    cache_patient_data_async, get_cached_patient_data_async, invalidate_patient_cache_async,
    AsyncCacheContext, async_cache
)


class TestJSONSerialization:
    """Test JSON serialization helpers."""

    def test_json_serializer_datetime(self):
        """Test JSON serialization of datetime objects."""
        dt = datetime(2024, 1, 1, 12, 0, 0)
        result = _json_serializer(dt)
        assert result == str(dt)

    def test_json_serializer_uuid(self):
        """Test JSON serialization of UUID objects."""
        uuid_obj = UUID('12345678-1234-5678-1234-567812345678')
        result = _json_serializer(uuid_obj)
        assert result == str(uuid_obj)

    def test_json_serializer_decimal(self):
        """Test JSON serialization of Decimal objects."""
        decimal_obj = Decimal('123.45')
        result = _json_serializer(decimal_obj)
        assert result == 123.45

    def test_json_serializer_complex_object(self):
        """Test JSON serialization of objects with __dict__."""
        class TestObj:
            def __init__(self):
                self.name = "test"
                self.value = 42
                self._private = "hidden"

        obj = TestObj()
        result = _json_serializer(obj)

        assert isinstance(result, dict)
        assert result["name"] == "test"
        assert result["value"] == 42
        assert "_private" not in result

    def test_json_serializer_simple_object(self):
        """Test JSON serialization of simple objects."""
        result = _json_serializer(42)
        assert result == "42"

    def test_serialize_for_cache_complex_object(self):
        """Test cache serialization of complex objects."""
        class TestModel:
            def __init__(self):
                self.id = 1
                self.name = "test"
                self._internal = "hidden"

        obj = TestModel()
        result = _serialize_for_cache(obj)

        # Should be valid JSON
        deserialized = json.loads(result)
        assert deserialized["id"] == 1
        assert deserialized["name"] == "test"
        assert "_internal" not in deserialized

    def test_serialize_for_cache_simple_object(self):
        """Test cache serialization of simple objects."""
        data = {"key": "value", "number": 42}
        result = _serialize_for_cache(data)

        deserialized = json.loads(result)
        assert deserialized == data

    def test_serialize_for_cache_invalid_object(self):
        """Test cache serialization of objects that can't be JSON serialized."""
        class UnserializableObj:
            def __init__(self):
                self.func = lambda x: x  # Functions can't be serialized

        obj = UnserializableObj()
        result = _serialize_for_cache(obj)

        # Should fall back to string representation
        assert isinstance(result, str)

    def test_deserialize_from_cache_valid_json(self):
        """Test cache deserialization of valid JSON."""
        data = {"key": "value", "number": 42}
        json_str = json.dumps(data)

        result = _deserialize_from_cache(json_str)
        assert result == data

    def test_deserialize_from_cache_invalid_json(self):
        """Test cache deserialization of invalid JSON."""
        invalid_json = "not valid json"

        result = _deserialize_from_cache(invalid_json)
        assert result == invalid_json  # Returns original string


class TestCacheKeyGeneration:
    """Test cache key generation functionality."""

    def test_generate_cache_key_simple(self):
        """Test cache key generation with simple arguments."""
        key = _generate_cache_key("test", "arg1", "arg2")
        assert key == "test:arg1:arg2"

    def test_generate_cache_key_with_kwargs(self):
        """Test cache key generation with keyword arguments."""
        key = _generate_cache_key("test", "arg1", name="value", id=123)
        assert "test:arg1" in key
        assert "name=value" in key
        assert "id=123" in key

    def test_generate_cache_key_sorted_kwargs(self):
        """Test cache key generation sorts kwargs for consistency."""
        key1 = _generate_cache_key("test", name="value", id=123)
        key2 = _generate_cache_key("test", id=123, name="value")
        assert key1 == key2

    def test_generate_cache_key_long_key_hashing(self):
        """Test cache key generation hashes long keys."""
        long_prefix = "a" * 200
        key = _generate_cache_key(long_prefix, "arg")

        # Should be hashed when too long
        assert len(key) < len(long_prefix) + 10
        assert "hash:" in key

    def test_generate_cache_key_empty_args(self):
        """Test cache key generation with no arguments."""
        key = _generate_cache_key("test")
        assert key == "test"

    def test_generate_cache_key_none_values(self):
        """Test cache key generation with None values."""
        key = _generate_cache_key("test", None, value=None)
        assert "test:None" in key
        assert "value=None" in key


class TestCacheDecorator:
    """Test the cache decorator functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        with patch('app.utils.cache.get_sync_redis') as mock_get_redis:
            mock_client = Mock()
            mock_get_redis.return_value = mock_client
            yield mock_client

    def test_cache_decorator_hit(self, mock_redis):
        """Test cache decorator with cache hit."""
        mock_redis.get.return_value = '"cached_result"'

        @cache(ttl=300)
        def test_function(arg):
            return f"result_{arg}"

        result = test_function("test")

        assert result == "cached_result"
        mock_redis.get.assert_called_once()
        mock_redis.set.assert_not_called()

    def test_cache_decorator_miss(self, mock_redis):
        """Test cache decorator with cache miss."""
        mock_redis.get.return_value = None

        @cache(ttl=300)
        def test_function(arg):
            return f"result_{arg}"

        result = test_function("test")

        assert result == "result_test"
        mock_redis.get.assert_called_once()
        mock_redis.set.assert_called_once()

    def test_cache_decorator_with_timedelta(self, mock_redis):
        """Test cache decorator with timedelta TTL."""
        mock_redis.get.return_value = None
        ttl_delta = timedelta(hours=1)

        @cache(ttl=ttl_delta)
        def test_function():
            return "result"

        test_function()

        # Should convert timedelta to seconds (3600)
        mock_redis.set.assert_called_once()
        args = mock_redis.set.call_args
        assert args[1]['ex'] == 3600

    def test_cache_decorator_custom_prefix(self, mock_redis):
        """Test cache decorator with custom key prefix."""
        mock_redis.get.return_value = None

        @cache(ttl=300, key_prefix="custom")
        def test_function():
            return "result"

        test_function()

        # Check that custom prefix was used
        cache_key = mock_redis.get.call_args[0][0]
        assert cache_key.startswith("cache:custom:")

    def test_cache_decorator_custom_namespace(self, mock_redis):
        """Test cache decorator with custom namespace."""
        mock_redis.get.return_value = None

        @cache(ttl=300, namespace="custom_ns")
        def test_function():
            return "result"

        test_function()

        # Check that custom namespace was used
        cache_key = mock_redis.get.call_args[0][0]
        assert cache_key.startswith("custom_ns:")

    def test_cache_decorator_redis_get_error(self, mock_redis):
        """Test cache decorator handles Redis GET errors gracefully."""
        mock_redis.get.side_effect = Exception("Redis connection error")

        @cache(ttl=300)
        def test_function():
            return "result"

        with patch('app.utils.cache.logger') as mock_logger:
            result = test_function()

            assert result == "result"
            mock_logger.warning.assert_called()

    def test_cache_decorator_redis_set_error(self, mock_redis):
        """Test cache decorator handles Redis SET errors gracefully."""
        mock_redis.get.return_value = None
        mock_redis.set.side_effect = Exception("Redis connection error")

        @cache(ttl=300)
        def test_function():
            return "result"

        with patch('app.utils.cache.logger') as mock_logger:
            result = test_function()

            assert result == "result"
            mock_logger.warning.assert_called()

    def test_cache_decorator_complex_object(self, mock_redis):
        """Test cache decorator with complex object serialization."""
        mock_redis.get.return_value = None

        class TestModel:
            def __init__(self):
                self.id = 1
                self.name = "test"

        @cache(ttl=300)
        def test_function():
            return TestModel()

        result = test_function()

        assert result.id == 1
        assert result.name == "test"
        mock_redis.set.assert_called_once()

    def test_cache_decorator_string_return(self, mock_redis):
        """Test cache decorator with string return value."""
        mock_redis.get.return_value = None

        @cache(ttl=300)
        def test_function():
            return "simple string"

        result = test_function()

        assert result == "simple string"
        # String should be stored directly
        mock_redis.set.assert_called_once()
        set_args = mock_redis.set.call_args[0]
        assert set_args[1] == "simple string"


class TestCacheManager:
    """Test the CacheManager class."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        mock_client = Mock()
        return mock_client

    @pytest.fixture
    def cache_manager(self, mock_redis):
        """Create CacheManager with mocked Redis."""
        return CacheManager(mock_redis)

    def test_cache_manager_get_success(self, cache_manager, mock_redis):
        """Test CacheManager get operation success."""
        mock_redis.get.return_value = '"test_value"'

        result = cache_manager.get("test_key")

        assert result == "test_value"
        mock_redis.get.assert_called_once_with("cache:test_key")

    def test_cache_manager_get_not_found(self, cache_manager, mock_redis):
        """Test CacheManager get operation when key not found."""
        mock_redis.get.return_value = None

        result = cache_manager.get("test_key")

        assert result is None

    def test_cache_manager_get_error(self, cache_manager, mock_redis):
        """Test CacheManager get operation handles errors."""
        mock_redis.get.side_effect = Exception("Redis error")

        with patch('app.utils.cache.logger') as mock_logger:
            result = cache_manager.get("test_key")

            assert result is None
            mock_logger.error.assert_called()

    def test_cache_manager_set_success(self, cache_manager, mock_redis):
        """Test CacheManager set operation success."""
        mock_redis.set.return_value = True

        result = cache_manager.set("test_key", "test_value", ttl=300)

        assert result is True
        mock_redis.set.assert_called_once_with("cache:test_key", "test_value", ex=300)

    def test_cache_manager_set_with_timedelta(self, cache_manager, mock_redis):
        """Test CacheManager set operation with timedelta TTL."""
        mock_redis.set.return_value = True
        ttl = timedelta(minutes=5)

        result = cache_manager.set("test_key", "test_value", ttl=ttl)

        assert result is True
        mock_redis.set.assert_called_once_with("cache:test_key", "test_value", ex=300)

    def test_cache_manager_set_complex_object(self, cache_manager, mock_redis):
        """Test CacheManager set operation with complex object."""
        mock_redis.set.return_value = True

        class TestObj:
            def __init__(self):
                self.name = "test"
                self.value = 42

        obj = TestObj()
        result = cache_manager.set("test_key", obj)

        assert result is True
        # Should serialize the object
        set_call = mock_redis.set.call_args[0]
        assert '"name": "test"' in set_call[1]
        assert '"value": 42' in set_call[1]

    def test_cache_manager_set_error(self, cache_manager, mock_redis):
        """Test CacheManager set operation handles errors."""
        mock_redis.set.side_effect = Exception("Redis error")

        with patch('app.utils.cache.logger') as mock_logger:
            result = cache_manager.set("test_key", "test_value")

            assert result is False
            mock_logger.error.assert_called()

    def test_cache_manager_delete_success(self, cache_manager, mock_redis):
        """Test CacheManager delete operation success."""
        mock_redis.delete.return_value = 1

        result = cache_manager.delete("test_key")

        assert result == 1
        mock_redis.delete.assert_called_once_with("cache:test_key")

    def test_cache_manager_delete_error(self, cache_manager, mock_redis):
        """Test CacheManager delete operation handles errors."""
        mock_redis.delete.side_effect = Exception("Redis error")

        with patch('app.utils.cache.logger') as mock_logger:
            result = cache_manager.delete("test_key")

            assert result is False
            mock_logger.error.assert_called()

    def test_cache_manager_invalidate_pattern(self, cache_manager, mock_redis):
        """Test CacheManager pattern invalidation."""
        mock_redis.keys.return_value = ["cache:user:1", "cache:user:2"]
        mock_redis.delete.return_value = True

        result = cache_manager.invalidate_pattern("user:*")

        assert result == 2
        mock_redis.keys.assert_called_once_with("cache:user:*")
        assert mock_redis.delete.call_count == 2

    def test_cache_manager_invalidate_pattern_no_keys(self, cache_manager, mock_redis):
        """Test CacheManager pattern invalidation with no matching keys."""
        mock_redis.keys.return_value = []

        result = cache_manager.invalidate_pattern("user:*")

        assert result == 0
        mock_redis.delete.assert_not_called()

    def test_cache_manager_invalidate_namespace(self, cache_manager, mock_redis):
        """Test CacheManager namespace invalidation."""
        mock_redis.keys.return_value = ["test:key1", "test:key2"]
        mock_redis.delete.return_value = True

        result = cache_manager.invalidate_namespace("test")

        assert result == 2
        mock_redis.keys.assert_called_once_with("test:*")

    def test_cache_manager_exists(self, cache_manager, mock_redis):
        """Test CacheManager exists check."""
        mock_redis.exists.return_value = 1

        result = cache_manager.exists("test_key")

        assert result == 1
        mock_redis.exists.assert_called_once_with("cache:test_key")

    def test_cache_manager_get_ttl(self, cache_manager, mock_redis):
        """Test CacheManager TTL retrieval."""
        mock_redis.ttl.return_value = 300

        result = cache_manager.get_ttl("test_key")

        assert result == 300
        mock_redis.ttl.assert_called_once_with("cache:test_key")

    def test_cache_manager_get_ttl_no_ttl(self, cache_manager, mock_redis):
        """Test CacheManager TTL retrieval when no TTL is set."""
        mock_redis.ttl.return_value = -1

        result = cache_manager.get_ttl("test_key")

        assert result is None

    def test_cache_manager_custom_namespace(self, mock_redis):
        """Test CacheManager with custom namespace."""
        manager = CacheManager(mock_redis)
        manager.namespace = "custom"

        manager.get("test_key")

        mock_redis.get.assert_called_once_with("custom:test_key")


class TestAsyncCacheManager:
    """Test the AsyncCacheManager class."""

    @pytest.fixture
    def mock_async_redis(self):
        """Mock async Redis client."""
        mock_client = AsyncMock()
        return mock_client

    @pytest.fixture
    def async_cache_manager(self):
        """Create AsyncCacheManager."""
        return AsyncCacheManager()

    @pytest.mark.asyncio
    async def test_async_cache_manager_get_success(self, async_cache_manager, mock_async_redis):
        """Test AsyncCacheManager get operation success."""
        mock_async_redis.get.return_value = '"test_value"'

        with patch('app.utils.cache.get_async_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_async_redis

            result = await async_cache_manager.get("test_key")

            assert result == "test_value"
            mock_async_redis.get.assert_called_once_with("cache:test_key")

    @pytest.mark.asyncio
    async def test_async_cache_manager_get_not_found(self, async_cache_manager, mock_async_redis):
        """Test AsyncCacheManager get operation when key not found."""
        mock_async_redis.get.return_value = None

        with patch('app.utils.cache.get_async_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_async_redis

            result = await async_cache_manager.get("test_key")

            assert result is None

    @pytest.mark.asyncio
    async def test_async_cache_manager_set_success(self, async_cache_manager, mock_async_redis):
        """Test AsyncCacheManager set operation success."""
        mock_async_redis.set.return_value = True

        with patch('app.utils.cache.get_async_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_async_redis

            result = await async_cache_manager.set("test_key", "test_value", ttl=300)

            assert result is True
            mock_async_redis.set.assert_called_once_with("cache:test_key", "test_value", ex=300)

    @pytest.mark.asyncio
    async def test_async_cache_manager_delete_success(self, async_cache_manager, mock_async_redis):
        """Test AsyncCacheManager delete operation success."""
        mock_async_redis.delete.return_value = 1

        with patch('app.utils.cache.get_async_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_async_redis

            result = await async_cache_manager.delete("test_key")

            assert result == 1
            mock_async_redis.delete.assert_called_once_with("cache:test_key")


class TestCacheManagerSingletons:
    """Test cache manager singleton functionality."""

    def test_get_cache_manager_singleton(self):
        """Test get_cache_manager returns singleton."""
        with patch('app.utils.cache._cache_manager', None):
            manager1 = get_cache_manager()
            manager2 = get_cache_manager()

            assert manager1 is manager2

    def test_get_async_cache_manager_singleton(self):
        """Test get_async_cache_manager returns singleton."""
        with patch('app.utils.cache._async_cache_manager', None):
            manager1 = get_async_cache_manager()
            manager2 = get_async_cache_manager()

            assert manager1 is manager2


class TestConvenienceFunctions:
    """Test convenience functions for common caching patterns."""

    @pytest.fixture
    def mock_cache_manager(self):
        """Mock cache manager."""
        with patch('app.utils.cache.get_cache_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_get_manager.return_value = mock_manager
            yield mock_manager

    @pytest.fixture
    def mock_async_cache_manager(self):
        """Mock async cache manager."""
        with patch('app.utils.cache.get_async_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_get_manager.return_value = mock_manager
            yield mock_manager

    def test_cache_user_data(self, mock_cache_manager):
        """Test cache_user_data convenience function."""
        mock_cache_manager.set.return_value = True

        result = cache_user_data("user123", {"name": "John"}, ttl=1800)

        assert result is True
        mock_cache_manager.set.assert_called_once_with(
            "user:user123", {"name": "John"}, ttl=1800, namespace="users"
        )

    def test_get_cached_user_data(self, mock_cache_manager):
        """Test get_cached_user_data convenience function."""
        mock_cache_manager.get.return_value = {"name": "John"}

        result = get_cached_user_data("user123")

        assert result == {"name": "John"}
        mock_cache_manager.get.assert_called_once_with("user:user123", namespace="users")

    def test_invalidate_user_cache(self, mock_cache_manager):
        """Test invalidate_user_cache convenience function."""
        mock_cache_manager.delete.return_value = True

        result = invalidate_user_cache("user123")

        assert result is True
        mock_cache_manager.delete.assert_called_once_with("user:user123", namespace="users")

    @pytest.mark.asyncio
    async def test_cache_user_data_async(self, mock_async_cache_manager):
        """Test cache_user_data_async convenience function."""
        mock_async_cache_manager.set.return_value = True

        result = await cache_user_data_async("user123", {"name": "John"}, ttl=1800)

        assert result is True
        mock_async_cache_manager.set.assert_called_once_with(
            "user:user123", {"name": "John"}, ttl=1800, namespace="users"
        )

    @pytest.mark.asyncio
    async def test_get_cached_user_data_async(self, mock_async_cache_manager):
        """Test get_cached_user_data_async convenience function."""
        mock_async_cache_manager.get.return_value = {"name": "John"}

        result = await get_cached_user_data_async("user123")

        assert result == {"name": "John"}
        mock_async_cache_manager.get.assert_called_once_with("user:user123", namespace="users")

    @pytest.mark.asyncio
    async def test_invalidate_user_cache_async(self, mock_async_cache_manager):
        """Test invalidate_user_cache_async convenience function."""
        mock_async_cache_manager.delete.return_value = True

        result = await invalidate_user_cache_async("user123")

        assert result is True
        mock_async_cache_manager.delete.assert_called_once_with("user:user123", namespace="users")

    def test_cache_patient_data(self, mock_cache_manager):
        """Test cache_patient_data convenience function."""
        mock_cache_manager.set.return_value = True

        result = cache_patient_data("patient123", {"diagnosis": "Cancer"}, ttl=3600)

        assert result is True
        mock_cache_manager.set.assert_called_once_with(
            "patient:patient123", {"diagnosis": "Cancer"}, ttl=3600, namespace="patients"
        )

    def test_get_cached_patient_data(self, mock_cache_manager):
        """Test get_cached_patient_data convenience function."""
        mock_cache_manager.get.return_value = {"diagnosis": "Cancer"}

        result = get_cached_patient_data("patient123")

        assert result == {"diagnosis": "Cancer"}
        mock_cache_manager.get.assert_called_once_with("patient:patient123", namespace="patients")

    def test_invalidate_patient_cache(self, mock_cache_manager):
        """Test invalidate_patient_cache convenience function."""
        mock_cache_manager.delete.return_value = True

        result = invalidate_patient_cache("patient123")

        assert result is True
        mock_cache_manager.delete.assert_called_once_with("patient:patient123", namespace="patients")

    @pytest.mark.asyncio
    async def test_cache_patient_data_async(self, mock_async_cache_manager):
        """Test cache_patient_data_async convenience function."""
        mock_async_cache_manager.set.return_value = True

        result = await cache_patient_data_async("patient123", {"diagnosis": "Cancer"}, ttl=3600)

        assert result is True
        mock_async_cache_manager.set.assert_called_once_with(
            "patient:patient123", {"diagnosis": "Cancer"}, ttl=3600, namespace="patients"
        )

    @pytest.mark.asyncio
    async def test_get_cached_patient_data_async(self, mock_async_cache_manager):
        """Test get_cached_patient_data_async convenience function."""
        mock_async_cache_manager.get.return_value = {"diagnosis": "Cancer"}

        result = await get_cached_patient_data_async("patient123")

        assert result == {"diagnosis": "Cancer"}
        mock_async_cache_manager.get.assert_called_once_with("patient:patient123", namespace="patients")

    @pytest.mark.asyncio
    async def test_invalidate_patient_cache_async(self, mock_async_cache_manager):
        """Test invalidate_patient_cache_async convenience function."""
        mock_async_cache_manager.delete.return_value = True

        result = await invalidate_patient_cache_async("patient123")

        assert result is True
        mock_async_cache_manager.delete.assert_called_once_with("patient:patient123", namespace="patients")


class TestAsyncCacheContext:
    """Test async cache context manager."""

    @pytest.mark.asyncio
    async def test_async_cache_context_manager(self):
        """Test async cache context manager usage."""
        with patch('app.utils.cache.get_async_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_get_manager.return_value = mock_manager

            async with async_cache() as cache_mgr:
                assert cache_mgr is mock_manager

    @pytest.mark.asyncio
    async def test_async_cache_context_manager_operations(self):
        """Test async cache context manager with operations."""
        with patch('app.utils.cache.get_async_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.set.return_value = True
            mock_manager.get.return_value = "test_value"
            mock_get_manager.return_value = mock_manager

            async with async_cache() as cache_mgr:
                await cache_mgr.set("key", "value")
                result = await cache_mgr.get("key")

                assert result == "test_value"
                mock_manager.set.assert_called_once()
                mock_manager.get.assert_called_once()


class TestCacheEdgeCases:
    """Test edge cases and error scenarios."""

    def test_cache_decorator_with_none_redis(self):
        """Test cache decorator when Redis client is None."""
        with patch('app.utils.cache.get_sync_redis') as mock_get_redis:
            mock_get_redis.return_value = None

            @cache(ttl=300)
            def test_function():
                return "result"

            # Should not raise exception, just not cache
            result = test_function()
            assert result == "result"

    def test_serialize_for_cache_with_callable_attributes(self):
        """Test serialization of objects with callable attributes."""
        class TestObj:
            def __init__(self):
                self.name = "test"
                self.method = lambda x: x

        obj = TestObj()
        result = _serialize_for_cache(obj)

        # Should exclude callable attributes
        deserialized = json.loads(result)
        assert "name" in deserialized
        assert "method" not in deserialized

    def test_cache_manager_with_none_redis(self):
        """Test CacheManager operations with None redis client."""
        manager = CacheManager(None)

        # Should handle gracefully
        assert manager.get("key") is None
        assert manager.set("key", "value") is False
        assert manager.delete("key") is False