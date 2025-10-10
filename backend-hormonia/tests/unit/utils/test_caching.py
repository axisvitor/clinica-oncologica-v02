"""
Comprehensive unit tests for app.utils.caching module.
Tests Redis-based caching utilities, cache manager, and decorators.
"""
import pytest
import json
import pickle
import hashlib
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi import Request

from app.utils.caching import (
    CacheConfig,
    CacheManager,
    CACHE_CONFIGS,
    get_cache_manager,
    cache_result,
    invalidate_cache,
    generate_request_cache_key,
    generate_user_cache_key,
    cache_response
)


class TestCacheConfig:
    """Test the CacheConfig dataclass."""

    def test_cache_config_creation(self):
        """Test CacheConfig creation with defaults."""
        config = CacheConfig(ttl=300, key_prefix="test")
        assert config.ttl == 300
        assert config.key_prefix == "test"
        assert config.serialize_method == "json"
        assert config.compress is False

    def test_cache_config_custom_values(self):
        """Test CacheConfig with custom values."""
        config = CacheConfig(
            ttl=600,
            key_prefix="custom",
            serialize_method="pickle",
            compress=True
        )
        assert config.ttl == 600
        assert config.key_prefix == "custom"
        assert config.serialize_method == "pickle"
        assert config.compress is True


class TestCacheConfigs:
    """Test predefined cache configurations."""

    def test_cache_configs_exist(self):
        """Test that all expected cache configurations exist."""
        expected_configs = [
            "patient_list", "patient_detail", "user_profile", "quiz_templates",
            "flow_templates", "analytics_dashboard", "system_metrics",
            "message_stats", "report_data"
        ]

        for config_name in expected_configs:
            assert config_name in CACHE_CONFIGS
            config = CACHE_CONFIGS[config_name]
            assert isinstance(config, CacheConfig)
            assert config.ttl > 0
            assert config.key_prefix

    def test_cache_configs_ttl_values(self):
        """Test TTL values are reasonable."""
        # Quick access data should have shorter TTL
        assert CACHE_CONFIGS["system_metrics"].ttl == 60  # 1 minute
        assert CACHE_CONFIGS["patient_list"].ttl == 300  # 5 minutes

        # Stable data can have longer TTL
        assert CACHE_CONFIGS["quiz_templates"].ttl == 3600  # 1 hour
        assert CACHE_CONFIGS["user_profile"].ttl == 1800  # 30 minutes


class TestCacheManager:
    """Test the CacheManager class."""

    def test_cache_manager_initialization(self):
        """Test CacheManager initialization."""
        manager = CacheManager()
        assert manager.redis_client is None
        assert manager._local_cache == {}
        assert manager._cache_stats["hits"] == 0
        assert manager._cache_stats["misses"] == 0
        assert manager._cache_stats["errors"] == 0

    def test_cache_manager_with_redis_client(self):
        """Test CacheManager with provided Redis client."""
        mock_client = AsyncMock()
        manager = CacheManager(redis_client=mock_client)
        assert manager.redis_client == mock_client

    @pytest.mark.asyncio
    async def test_get_redis_client_success(self):
        """Test successful Redis client retrieval."""
        manager = CacheManager()

        with patch('app.utils.caching.get_async_redis') as mock_get_redis:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock()
            mock_get_redis.return_value = mock_client

            result = await manager._get_redis_client()

            assert result == mock_client
            mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_redis_client_failure(self):
        """Test Redis client retrieval failure."""
        manager = CacheManager()

        with patch('app.utils.caching.get_async_redis') as mock_get_redis:
            mock_get_redis.side_effect = Exception("Redis connection failed")

            result = await manager._get_redis_client()

            assert result is None

    def test_generate_cache_key_short(self):
        """Test cache key generation for short keys."""
        manager = CacheManager()
        config = CacheConfig(ttl=300, key_prefix="test")
        key_parts = ["user", "123", "profile"]

        result = manager._generate_cache_key(config, key_parts)

        assert result == "test:user:123:profile"

    def test_generate_cache_key_long(self):
        """Test cache key generation for long keys (hashed)."""
        manager = CacheManager()
        config = CacheConfig(ttl=300, key_prefix="test")
        # Create a very long key
        key_parts = ["very_long_key_part"] * 20

        result = manager._generate_cache_key(config, key_parts)

        # Should be hashed when key is too long
        assert result.startswith("test:")
        assert len(result) == 37  # "test:" + 32-char MD5 hash

    def test_serialize_data_json(self):
        """Test JSON serialization."""
        manager = CacheManager()
        data = {"key": "value", "number": 42}

        result = manager._serialize_data(data, "json")

        assert isinstance(result, bytes)
        assert json.loads(result.decode()) == data

    def test_serialize_data_pickle(self):
        """Test pickle serialization."""
        manager = CacheManager()
        data = {"key": "value", "complex": {"nested": [1, 2, 3]}}

        result = manager._serialize_data(data, "pickle")

        assert isinstance(result, bytes)
        assert pickle.loads(result) == data

    def test_serialize_data_unknown_method(self):
        """Test serialization with unknown method."""
        manager = CacheManager()

        with pytest.raises(ValueError, match="Unknown serialization method"):
            manager._serialize_data({"test": "data"}, "unknown")

    def test_deserialize_data_json(self):
        """Test JSON deserialization."""
        manager = CacheManager()
        data = {"key": "value", "number": 42}
        serialized = json.dumps(data).encode()

        result = manager._deserialize_data(serialized, "json")

        assert result == data

    def test_deserialize_data_pickle(self):
        """Test pickle deserialization."""
        manager = CacheManager()
        data = {"key": "value", "complex": {"nested": [1, 2, 3]}}
        serialized = pickle.dumps(data)

        result = manager._deserialize_data(serialized, "pickle")

        assert result == data

    def test_deserialize_data_unknown_method(self):
        """Test deserialization with unknown method."""
        manager = CacheManager()

        with pytest.raises(ValueError, match="Unknown serialization method"):
            manager._deserialize_data(b"test data", "unknown")

    @pytest.mark.asyncio
    async def test_get_redis_cache_hit(self):
        """Test cache get with Redis hit."""
        mock_client = AsyncMock()
        cached_data = json.dumps({"cached": "data"}).encode()
        mock_client.get.return_value = cached_data

        manager = CacheManager()

        with patch.object(manager, '_get_redis_client', return_value=mock_client):
            result = await manager.get("patient_list", ["user123", "page1"])

            assert result == {"cached": "data"}
            assert manager._cache_stats["hits"] == 1
            assert manager._cache_stats["misses"] == 0

    @pytest.mark.asyncio
    async def test_get_redis_cache_miss(self):
        """Test cache get with Redis miss."""
        mock_client = AsyncMock()
        mock_client.get.return_value = None

        manager = CacheManager()

        with patch.object(manager, '_get_redis_client', return_value=mock_client):
            result = await manager.get("patient_list", ["user123", "page1"], default="default_value")

            assert result == "default_value"
            assert manager._cache_stats["hits"] == 0
            assert manager._cache_stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_get_local_cache_hit(self):
        """Test cache get with local cache hit."""
        manager = CacheManager()

        # Pre-populate local cache
        cache_key = "patients:list:user123:page1"
        manager._local_cache[cache_key] = {
            "data": {"local": "cached"},
            "expires_at": datetime.utcnow() + timedelta(seconds=300)
        }

        with patch.object(manager, '_get_redis_client', return_value=None):
            result = await manager.get("patient_list", ["user123", "page1"])

            assert result == {"local": "cached"}
            assert manager._cache_stats["hits"] == 1

    @pytest.mark.asyncio
    async def test_get_local_cache_expired(self):
        """Test cache get with expired local cache."""
        manager = CacheManager()

        # Pre-populate local cache with expired entry
        cache_key = "patients:list:user123:page1"
        manager._local_cache[cache_key] = {
            "data": {"expired": "data"},
            "expires_at": datetime.utcnow() - timedelta(seconds=60)  # Expired
        }

        with patch.object(manager, '_get_redis_client', return_value=None):
            result = await manager.get("patient_list", ["user123", "page1"], default="default")

            assert result == "default"
            assert cache_key not in manager._local_cache  # Should be removed
            assert manager._cache_stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_get_unknown_cache_type(self):
        """Test cache get with unknown cache type."""
        manager = CacheManager()

        result = await manager.get("unknown_type", ["key"], default="default")

        assert result == "default"

    @pytest.mark.asyncio
    async def test_get_error_handling(self):
        """Test cache get error handling."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Redis error")

        manager = CacheManager()

        with patch.object(manager, '_get_redis_client', return_value=mock_client):
            result = await manager.get("patient_list", ["user123"], default="default")

            assert result == "default"
            assert manager._cache_stats["errors"] == 1

    @pytest.mark.asyncio
    async def test_set_redis_success(self):
        """Test cache set with Redis success."""
        mock_client = AsyncMock()
        mock_client.setex = AsyncMock()

        manager = CacheManager()

        with patch.object(manager, '_get_redis_client', return_value=mock_client):
            result = await manager.set("patient_list", ["user123"], {"data": "test"})

            assert result is True
            mock_client.setex.assert_called_once()
            # Check local cache was also updated
            assert len(manager._local_cache) == 1

    @pytest.mark.asyncio
    async def test_set_ttl_override(self):
        """Test cache set with TTL override."""
        mock_client = AsyncMock()

        manager = CacheManager()

        with patch.object(manager, '_get_redis_client', return_value=mock_client):
            await manager.set("patient_list", ["user123"], {"data": "test"}, ttl_override=600)

            # Check Redis setex was called with custom TTL
            call_args = mock_client.setex.call_args
            assert call_args[0][1] == 600  # TTL argument

    @pytest.mark.asyncio
    async def test_set_no_redis(self):
        """Test cache set when Redis is unavailable."""
        manager = CacheManager()

        with patch.object(manager, '_get_redis_client', return_value=None):
            result = await manager.set("patient_list", ["user123"], {"data": "test"})

            assert result is True
            # Should still store in local cache
            assert len(manager._local_cache) == 1

    @pytest.mark.asyncio
    async def test_set_unknown_cache_type(self):
        """Test cache set with unknown cache type."""
        manager = CacheManager()

        result = await manager.set("unknown_type", ["key"], {"data": "test"})

        assert result is False

    @pytest.mark.asyncio
    async def test_set_error_handling(self):
        """Test cache set error handling."""
        manager = CacheManager()

        with patch.object(manager, '_serialize_data', side_effect=Exception("Serialization error")):
            result = await manager.set("patient_list", ["user123"], {"data": "test"})

            assert result is False
            assert manager._cache_stats["errors"] == 1

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """Test cache delete success."""
        mock_client = AsyncMock()

        manager = CacheManager()
        # Pre-populate local cache
        cache_key = "patients:list:user123"
        manager._local_cache[cache_key] = {"data": "test", "expires_at": datetime.utcnow()}

        with patch.object(manager, '_get_redis_client', return_value=mock_client):
            result = await manager.delete("patient_list", ["user123"])

            assert result is True
            mock_client.delete.assert_called_once()
            assert cache_key not in manager._local_cache

    @pytest.mark.asyncio
    async def test_delete_unknown_cache_type(self):
        """Test cache delete with unknown cache type."""
        manager = CacheManager()

        result = await manager.delete("unknown_type", ["key"])

        assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_pattern_redis(self):
        """Test cache pattern invalidation with Redis."""
        mock_client = AsyncMock()
        mock_client.keys.return_value = ["key1", "key2", "key3"]
        mock_client.delete = AsyncMock()

        manager = CacheManager()

        with patch.object(manager, '_get_redis_client', return_value=mock_client):
            result = await manager.invalidate_pattern("patients:*")

            assert result == 3
            mock_client.keys.assert_called_once_with("patients:*")
            mock_client.delete.assert_called_once_with("key1", "key2", "key3")

    @pytest.mark.asyncio
    async def test_invalidate_pattern_local_only(self):
        """Test cache pattern invalidation with local cache only."""
        manager = CacheManager()

        # Pre-populate local cache
        manager._local_cache = {
            "patients:list:user1": {"data": "test1"},
            "patients:list:user2": {"data": "test2"},
            "users:profile:user1": {"data": "test3"}
        }

        with patch.object(manager, '_get_redis_client', return_value=None):
            result = await manager.invalidate_pattern("patients:")

            assert result == 2
            # Only the matching keys should be removed
            assert "users:profile:user1" in manager._local_cache
            assert "patients:list:user1" not in manager._local_cache

    def test_get_stats(self):
        """Test cache statistics calculation."""
        manager = CacheManager()
        manager._cache_stats = {"hits": 80, "misses": 20, "errors": 5}
        manager._local_cache = {"key1": {}, "key2": {}}

        stats = manager.get_stats()

        assert stats["hits"] == 80
        assert stats["misses"] == 20
        assert stats["errors"] == 5
        assert stats["hit_rate_percent"] == 80.0
        assert stats["local_cache_size"] == 2

    def test_get_stats_no_requests(self):
        """Test cache statistics with no requests."""
        manager = CacheManager()

        stats = manager.get_stats()

        assert stats["hit_rate_percent"] == 0

    @pytest.mark.asyncio
    async def test_clear_all_success(self):
        """Test clearing all cache data."""
        mock_client = AsyncMock()
        mock_client.keys.return_value = ["key1", "key2"]
        mock_client.delete = AsyncMock()

        manager = CacheManager()
        manager._local_cache = {"key1": {}, "key2": {}}

        with patch.object(manager, '_get_redis_client', return_value=mock_client):
            result = await manager.clear_all()

            assert result is True
            assert len(manager._local_cache) == 0
            # Should call keys for each cache config
            assert mock_client.keys.call_count == len(CACHE_CONFIGS)

    @pytest.mark.asyncio
    async def test_clear_all_error(self):
        """Test clear all error handling."""
        manager = CacheManager()

        with patch.object(manager, '_get_redis_client', side_effect=Exception("Clear error")):
            result = await manager.clear_all()

            assert result is False


class TestCacheManagerGlobal:
    """Test global cache manager functions."""

    def test_get_cache_manager_singleton(self):
        """Test that get_cache_manager returns singleton."""
        # Reset global manager
        import app.utils.caching
        app.utils.caching._cache_manager = None

        manager1 = get_cache_manager()
        manager2 = get_cache_manager()

        assert manager1 is manager2
        assert isinstance(manager1, CacheManager)


class TestCacheResultDecorator:
    """Test the cache_result decorator."""

    @pytest.mark.asyncio
    async def test_cache_result_cache_miss(self):
        """Test cache_result decorator with cache miss."""
        def key_gen(user_id, page):
            return [user_id, str(page)]

        @cache_result("patient_list", key_gen)
        async def get_patients(user_id, page=1):
            return {"patients": f"data_for_{user_id}_page_{page}"}

        with patch('app.utils.caching.get_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get.return_value = None  # Cache miss
            mock_manager.set = AsyncMock()
            mock_get_manager.return_value = mock_manager

            result = await get_patients("user123", page=2)

            assert result == {"patients": "data_for_user123_page_2"}
            mock_manager.get.assert_called_once_with("patient_list", ["user123", "2"])
            mock_manager.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_result_cache_hit(self):
        """Test cache_result decorator with cache hit."""
        def key_gen(user_id):
            return [user_id]

        @cache_result("patient_list", key_gen)
        async def get_patients(user_id):
            return {"patients": "fresh_data"}  # Should not be called

        with patch('app.utils.caching.get_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get.return_value = {"patients": "cached_data"}
            mock_get_manager.return_value = mock_manager

            result = await get_patients("user123")

            assert result == {"patients": "cached_data"}
            mock_manager.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_result_key_generation_error(self):
        """Test cache_result decorator with key generation error."""
        def failing_key_gen(*args, **kwargs):
            raise ValueError("Key generation failed")

        @cache_result("patient_list", failing_key_gen)
        async def get_patients(user_id):
            return {"patients": "fallback_data"}

        result = await get_patients("user123")

        # Should execute function without caching
        assert result == {"patients": "fallback_data"}

    @pytest.mark.asyncio
    async def test_cache_result_ttl_override(self):
        """Test cache_result decorator with TTL override."""
        def key_gen(user_id):
            return [user_id]

        @cache_result("patient_list", key_gen, ttl_override=1200)
        async def get_patients(user_id):
            return {"patients": "data"}

        with patch('app.utils.caching.get_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get.return_value = None
            mock_get_manager.return_value = mock_manager

            await get_patients("user123")

            # Check TTL override was passed
            call_args = mock_manager.set.call_args
            assert call_args[0][3] == 1200  # ttl_override argument


class TestInvalidateCache:
    """Test cache invalidation functions."""

    @pytest.mark.asyncio
    async def test_invalidate_cache_function(self):
        """Test invalidate_cache function."""
        invalidate_func = invalidate_cache("patient_list", ["user123"])

        with patch('app.utils.caching.get_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_get_manager.return_value = mock_manager

            await invalidate_func()

            mock_manager.delete.assert_called_once_with("patient_list", ["user123"])


class TestCacheKeyGenerators:
    """Test cache key generation utilities."""

    def test_generate_request_cache_key(self):
        """Test request-based cache key generation."""
        mock_request = Mock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/api/patients"
        mock_request.query_params.items.return_value = [("page", "1"), ("limit", "10")]

        result = generate_request_cache_key(mock_request)

        expected = ["GET", "/api/patients", "[('limit', '10'), ('page', '1')]"]
        assert result == expected

    def test_generate_request_cache_key_with_additional_parts(self):
        """Test request cache key generation with additional parts."""
        mock_request = Mock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/api/data"
        mock_request.query_params.items.return_value = []

        result = generate_request_cache_key(mock_request, ["user123", "extra"])

        expected = ["POST", "/api/data", "[]", "user123", "extra"]
        assert result == expected

    def test_generate_user_cache_key(self):
        """Test user-based cache key generation."""
        result = generate_user_cache_key("user123")

        assert result == ["user123"]

    def test_generate_user_cache_key_with_additional_parts(self):
        """Test user cache key generation with additional parts."""
        result = generate_user_cache_key("user123", ["profile", "settings"])

        assert result == ["user123", "profile", "settings"]


class TestCacheResponseDecorator:
    """Test the cache_response decorator."""

    @pytest.mark.asyncio
    async def test_cache_response_cache_miss(self):
        """Test cache_response decorator with cache miss."""
        @cache_response(seconds=600)
        async def get_dashboard_data(user_id):
            return {"dashboard": f"data_for_{user_id}"}

        with patch('app.utils.caching.get_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get.return_value = None  # Cache miss
            mock_manager.set = AsyncMock()
            mock_get_manager.return_value = mock_manager

            result = await get_dashboard_data("user123")

            assert result == {"dashboard": "data_for_user123"}
            mock_manager.set.assert_called_once()
            # Check custom TTL was used
            call_args = mock_manager.set.call_args
            assert call_args[0][3] == 600

    @pytest.mark.asyncio
    async def test_cache_response_cache_hit(self):
        """Test cache_response decorator with cache hit."""
        @cache_response()
        async def get_dashboard_data():
            return {"dashboard": "fresh_data"}  # Should not be called

        with patch('app.utils.caching.get_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get.return_value = {"dashboard": "cached_data"}
            mock_get_manager.return_value = mock_manager

            result = await get_dashboard_data()

            assert result == {"dashboard": "cached_data"}
            mock_manager.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_response_key_generation(self):
        """Test cache_response key generation from function arguments."""
        @cache_response()
        async def get_data(param1, param2=None):
            return {"param1": param1, "param2": param2}

        with patch('app.utils.caching.get_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get.return_value = None
            mock_get_manager.return_value = mock_manager

            await get_data("value1", param2="value2")

            # Check that cache key was generated from function name and args hash
            call_args = mock_manager.get.call_args
            key_parts = call_args[0][1]
            assert key_parts[0] == "get_data"
            assert isinstance(key_parts[1], str)  # Hash of args/kwargs

    @pytest.mark.asyncio
    async def test_cache_response_preserves_metadata(self):
        """Test that cache_response preserves function metadata."""
        @cache_response()
        async def documented_function():
            """This function has documentation."""
            return {"data": "test"}

        assert documented_function.__name__ == "documented_function"
        assert "This function has documentation" in documented_function.__doc__


class TestCachingEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_cache_with_none_values(self):
        """Test caching None values."""
        manager = CacheManager()

        with patch.object(manager, '_get_redis_client', return_value=None):
            # Set None value
            result = await manager.set("patient_list", ["test"], None)
            assert result is True

            # Get None value
            cached = await manager.get("patient_list", ["test"])
            assert cached is None

    @pytest.mark.asyncio
    async def test_cache_with_complex_objects(self):
        """Test caching complex objects."""
        manager = CacheManager()
        complex_data = {
            "nested": {"deep": {"value": 42}},
            "list": [1, 2, {"inner": "value"}],
            "datetime_str": str(datetime.utcnow())
        }

        with patch.object(manager, '_get_redis_client', return_value=None):
            await manager.set("report_data", ["complex"], complex_data)
            cached = await manager.get("report_data", ["complex"])

            assert cached == complex_data

    def test_cache_key_generation_with_unicode(self):
        """Test cache key generation with unicode characters."""
        manager = CacheManager()
        config = CacheConfig(ttl=300, key_prefix="test")
        key_parts = ["user", "测试用户", "profile"]

        result = manager._generate_cache_key(config, key_parts)

        assert "test:" in result
        # Should handle unicode gracefully

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self):
        """Test concurrent cache operations."""
        manager = CacheManager()

        with patch.object(manager, '_get_redis_client', return_value=None):
            # Simulate concurrent operations
            tasks = []

            async def cache_operation(i):
                await manager.set("patient_list", [f"user{i}"], {"data": i})
                return await manager.get("patient_list", [f"user{i}"])

            import asyncio
            results = await asyncio.gather(*[cache_operation(i) for i in range(5)])

            assert len(results) == 5
            for i, result in enumerate(results):
                assert result["data"] == i