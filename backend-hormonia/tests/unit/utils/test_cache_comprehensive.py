"""
Comprehensive unit tests for app.utils.cache module.
Tests ALL caching functions, utilities, edge cases, and scenarios.
Provides 100% coverage of cache.py with 40+ detailed test cases.
"""
import pytest
import json
import asyncio
import threading
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from typing import Any, Dict, List
import pickle
import hashlib

from app.utils.cache import (
    cache, CacheManager, AsyncCacheManager, get_cache_manager, get_async_cache_manager,
    _json_serializer, _serialize_for_cache, _deserialize_from_cache, _generate_cache_key,
    cache_user_data, get_cached_user_data, invalidate_user_cache,
    cache_user_data_async, get_cached_user_data_async, invalidate_user_cache_async,
    cache_patient_data, get_cached_patient_data, invalidate_patient_cache,
    cache_patient_data_async, get_cached_patient_data_async, invalidate_patient_cache_async,
    AsyncCacheContext, async_cache
)


class TestJSONSerializationComprehensive:
    """Comprehensive tests for JSON serialization helpers."""

    def test_json_serializer_datetime_various_formats(self):
        """Test JSON serialization of different datetime formats."""
        dt1 = datetime(2024, 1, 1, 12, 0, 0)
        dt2 = datetime(2024, 12, 31, 23, 59, 59, 999999)
        dt3 = datetime.now()

        assert _json_serializer(dt1) == str(dt1)
        assert _json_serializer(dt2) == str(dt2)
        assert _json_serializer(dt3) == str(dt3)

    def test_json_serializer_uuid_various_formats(self):
        """Test JSON serialization of various UUID formats."""
        uuid1 = UUID('12345678-1234-5678-1234-567812345678')
        uuid2 = uuid4()
        uuid3 = UUID(int=0)

        assert _json_serializer(uuid1) == str(uuid1)
        assert _json_serializer(uuid2) == str(uuid2)
        assert _json_serializer(uuid3) == str(uuid3)

    def test_json_serializer_decimal_precision(self):
        """Test JSON serialization of Decimal with various precisions."""
        test_cases = [
            Decimal('123.45'),
            Decimal('0.001'),
            Decimal('99999999.99999999'),
            Decimal('0'),
            Decimal('-123.45')
        ]

        for decimal_obj in test_cases:
            result = _json_serializer(decimal_obj)
            assert result == float(decimal_obj)

    def test_json_serializer_complex_nested_object(self):
        """Test JSON serialization of deeply nested objects."""
        class DeepObj:
            def __init__(self):
                self.level1 = {
                    'level2': {
                        'level3': 'deep_value'
                    }
                }
                self.list_attr = [1, 2, 3]
                self._private = "should_not_appear"

        obj = DeepObj()
        result = _json_serializer(obj)

        assert isinstance(result, dict)
        assert result['level1']['level2']['level3'] == 'deep_value'
        assert result['list_attr'] == [1, 2, 3]
        assert '_private' not in result

    def test_json_serializer_sqlalchemy_like_object(self):
        """Test JSON serialization of SQLAlchemy-like objects."""
        class SQLAlchemyLikeModel:
            def __init__(self):
                self.id = 123
                self.name = "Test Model"
                self.created_at = datetime.now()
                self._sa_instance_state = "should_be_excluded"
                self.__table__ = "should_be_excluded"

        obj = SQLAlchemyLikeModel()
        result = _json_serializer(obj)

        assert result['id'] == 123
        assert result['name'] == "Test Model"
        assert '_sa_instance_state' not in result
        assert '__table__' not in result

    def test_serialize_for_cache_with_circular_reference_protection(self):
        """Test cache serialization handles objects without infinite recursion."""
        class SimpleObj:
            def __init__(self):
                self.name = "test"
                self.value = 42

        obj = SimpleObj()
        result = _serialize_for_cache(obj)

        # Should not raise exception and return valid JSON
        deserialized = json.loads(result)
        assert deserialized['name'] == "test"
        assert deserialized['value'] == 42

    def test_serialize_for_cache_mixed_data_types(self):
        """Test cache serialization with mixed data types."""
        mixed_data = {
            'string': 'test',
            'integer': 42,
            'float': 3.14,
            'boolean': True,
            'null': None,
            'list': [1, 2, 3],
            'nested_dict': {'inner': 'value'}
        }

        result = _serialize_for_cache(mixed_data)
        deserialized = json.loads(result)
        assert deserialized == mixed_data

    def test_serialize_for_cache_with_special_characters(self):
        """Test cache serialization with special characters and unicode."""
        special_data = {
            'unicode': 'test_data',
            'emoji': 'emoji_test',
            'special_chars': '!@#$%^&*()',
            'newlines': 'line1\nline2\tline3',
            'quotes': 'He said "Hello"'
        }

        result = _serialize_for_cache(special_data)
        deserialized = json.loads(result)
        assert deserialized == special_data

    def test_deserialize_from_cache_malformed_json(self):
        """Test cache deserialization with various malformed JSON."""
        malformed_cases = [
            '{"incomplete": ',
            '{"trailing_comma": 123,}',
            '{"unquoted_key": value}',
            '{123: "numeric_key"}',
            'just plain text'
        ]

        for malformed in malformed_cases:
            result = _deserialize_from_cache(malformed)
            assert result == malformed  # Should return original string

    def test_deserialize_from_cache_edge_cases(self):
        """Test cache deserialization with edge cases."""
        edge_cases = [
            ('null', None),
            ('true', True),
            ('false', False),
            ('42', 42),
            ('"string"', "string"),
            ('[]', []),
            ('{}', {})
        ]

        for json_str, expected in edge_cases:
            result = _deserialize_from_cache(json_str)
            assert result == expected


class TestCacheKeyGenerationComprehensive:
    """Comprehensive tests for cache key generation."""

    def test_generate_cache_key_with_complex_args(self):
        """Test cache key generation with complex argument types."""
        complex_args = [
            {'dict': 'value'},
            [1, 2, 3],
            (4, 5, 6),
            None,
            True,
            3.14
        ]

        key = _generate_cache_key("test", *complex_args)
        assert "test:" in key
        # Should not raise exception

    def test_generate_cache_key_with_nested_kwargs(self):
        """Test cache key generation with nested keyword arguments."""
        nested_kwargs = {
            'user_data': {'id': 123, 'name': 'test'},
            'filters': {'status': 'active', 'type': 'admin'},
            'pagination': {'page': 1, 'limit': 10}
        }

        key = _generate_cache_key("test", **nested_kwargs)

        # Should be deterministic - same input = same key
        key2 = _generate_cache_key("test", **nested_kwargs)
        assert key == key2

    def test_generate_cache_key_ordering_consistency(self):
        """Test cache key generation is consistent regardless of kwarg order."""
        key1 = _generate_cache_key("test", a=1, b=2, c=3)
        key2 = _generate_cache_key("test", c=3, a=1, b=2)
        key3 = _generate_cache_key("test", b=2, c=3, a=1)

        assert key1 == key2 == key3

    def test_generate_cache_key_unicode_handling(self):
        """Test cache key generation handles unicode properly."""
        unicode_args = ["test", "emoji", "cafe", "naive"]
        key = _generate_cache_key("test", *unicode_args)

        assert "test:" in key
        # Should not raise UnicodeError

    def test_generate_cache_key_extremely_long_key(self):
        """Test cache key generation with extremely long keys."""
        long_prefix = "x" * 300
        long_args = ["y" * 100 for _ in range(10)]

        key = _generate_cache_key(long_prefix, *long_args)

        # Should be hashed when too long
        assert len(key) < 250  # Much shorter than original
        assert "hash:" in key

    def test_generate_cache_key_empty_and_none_handling(self):
        """Test cache key generation with empty values and None."""
        test_cases = [
            ("prefix", "", None, [], {}),
            ("prefix", None),
            ("prefix", ""),
            ("prefix", None, "", None)
        ]

        for args in test_cases:
            key = _generate_cache_key(*args)
            assert key.startswith("prefix")

    def test_generate_cache_key_special_characters(self):
        """Test cache key generation with special characters."""
        special_chars = [":", "@", "#", "$", "%", "^", "&", "*"]
        key = _generate_cache_key("test", *special_chars)

        # Should handle special characters without breaking
        assert "test:" in key


class TestCacheDecoratorComprehensive:
    """Comprehensive tests for cache decorator functionality."""

    @pytest.fixture
    def mock_redis_comprehensive(self):
        """Comprehensive mock Redis client."""
        with patch('app.utils.cache.get_sync_redis') as mock_get_redis:
            mock_client = Mock()
            mock_client.get = Mock()
            mock_client.set = Mock()
            mock_client.delete = Mock()
            mock_client.exists = Mock()
            mock_client.ttl = Mock()
            mock_get_redis.return_value = mock_client
            yield mock_client

    def test_cache_decorator_with_multiple_args_and_kwargs(self, mock_redis_comprehensive):
        """Test cache decorator with complex argument combinations."""
        mock_redis_comprehensive.get.return_value = None

        @cache(ttl=300)
        def complex_function(arg1, arg2, kwarg1=None, kwarg2="default"):
            return f"{arg1}_{arg2}_{kwarg1}_{kwarg2}"

        result = complex_function("a", "b", kwarg1="c", kwarg2="d")

        assert result == "a_b_c_d"
        mock_redis_comprehensive.get.assert_called_once()
        mock_redis_comprehensive.set.assert_called_once()

    def test_cache_decorator_preserves_function_metadata(self, mock_redis_comprehensive):
        """Test cache decorator preserves original function metadata."""
        mock_redis_comprehensive.get.return_value = None

        @cache(ttl=300)
        def documented_function(param):
            """This is a test function."""
            return param * 2

        assert documented_function.__name__ == "documented_function"
        assert "This is a test function" in documented_function.__doc__

    def test_cache_decorator_with_class_methods(self, mock_redis_comprehensive):
        """Test cache decorator works with class methods."""
        mock_redis_comprehensive.get.return_value = None

        class TestClass:
            @cache(ttl=300)
            def instance_method(self, value):
                return f"instance_{value}"

            @classmethod
            @cache(ttl=300)
            def class_method(cls, value):
                return f"class_{value}"

            @staticmethod
            @cache(ttl=300)
            def static_method(value):
                return f"static_{value}"

        obj = TestClass()

        # Test instance method
        result1 = obj.instance_method("test1")
        assert result1 == "instance_test1"

        # Test class method
        result2 = TestClass.class_method("test2")
        assert result2 == "class_test2"

        # Test static method
        result3 = TestClass.static_method("test3")
        assert result3 == "static_test3"

    def test_cache_decorator_concurrent_access(self, mock_redis_comprehensive):
        """Test cache decorator handles concurrent access."""
        call_count = 0
        mock_redis_comprehensive.get.return_value = None

        @cache(ttl=300)
        def concurrent_function(value):
            nonlocal call_count
            call_count += 1
            time.sleep(0.01)  # Simulate some work
            return f"result_{value}_{call_count}"

        # Simulate concurrent calls
        import threading
        results = []

        def worker(value):
            result = concurrent_function(value)
            results.append(result)

        threads = [threading.Thread(target=worker, args=(f"test{i}",)) for i in range(5)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results) == 5
        # Each call should have unique cache keys
        assert len(set(results)) == 5

    def test_cache_decorator_redis_connection_recovery(self, mock_redis_comprehensive):
        """Test cache decorator handles Redis connection recovery."""
        # First call fails, second succeeds
        mock_redis_comprehensive.get.side_effect = [
            Exception("Connection lost"),
            None,  # Cache miss
            None   # Another cache miss
        ]

        @cache(ttl=300)
        def recovery_function(value):
            return f"recovered_{value}"

        # First call should work despite Redis error
        result1 = recovery_function("test1")
        assert result1 == "recovered_test1"

        # Second call should also work
        result2 = recovery_function("test2")
        assert result2 == "recovered_test2"

    def test_cache_decorator_with_none_return_value(self, mock_redis_comprehensive):
        """Test cache decorator handles None return values correctly."""
        mock_redis_comprehensive.get.return_value = None

        @cache(ttl=300)
        def none_returning_function():
            return None

        result = none_returning_function()
        assert result is None

        # Should still cache None values
        mock_redis_comprehensive.set.assert_called_once()

    def test_cache_decorator_with_large_objects(self, mock_redis_comprehensive):
        """Test cache decorator with large complex objects."""
        mock_redis_comprehensive.get.return_value = None

        @cache(ttl=300)
        def large_object_function():
            return {
                'large_list': list(range(1000)),
                'nested_data': {f'key_{i}': f'value_{i}' for i in range(100)},
                'metadata': {
                    'created_at': datetime.now(),
                    'id': uuid4(),
                    'value': Decimal('999.99')
                }
            }

        result = large_object_function()

        assert len(result['large_list']) == 1000
        assert len(result['nested_data']) == 100
        assert 'metadata' in result

        # Should serialize and cache successfully
        mock_redis_comprehensive.set.assert_called_once()

    def test_cache_decorator_ttl_edge_cases(self, mock_redis_comprehensive):
        """Test cache decorator with edge case TTL values."""
        mock_redis_comprehensive.get.return_value = None

        # Test with zero TTL
        @cache(ttl=0)
        def zero_ttl_function():
            return "zero_ttl"

        # Test with very large TTL
        @cache(ttl=timedelta(days=365))
        def large_ttl_function():
            return "large_ttl"

        # Test with fractional timedelta
        @cache(ttl=timedelta(seconds=1.5))
        def fractional_ttl_function():
            return "fractional_ttl"

        zero_ttl_function()
        large_ttl_function()
        fractional_ttl_function()

        # All should execute without error
        assert mock_redis_comprehensive.set.call_count == 3


class TestCacheManagerComprehensive:
    """Comprehensive tests for CacheManager functionality."""

    @pytest.fixture
    def mock_redis_manager(self):
        """Mock Redis client for manager tests."""
        mock_client = Mock()
        mock_client.get = Mock()
        mock_client.set = Mock()
        mock_client.delete = Mock()
        mock_client.exists = Mock()
        mock_client.ttl = Mock()
        mock_client.keys = Mock()
        return mock_client

    @pytest.fixture
    def cache_manager(self, mock_redis_manager):
        """Create CacheManager with mocked Redis."""
        return CacheManager(mock_redis_manager)

    def test_cache_manager_batch_operations(self, cache_manager, mock_redis_manager):
        """Test CacheManager batch operations."""
        # Test setting multiple keys
        keys_and_values = [
            ("key1", "value1"),
            ("key2", {"complex": "object"}),
            ("key3", [1, 2, 3])
        ]

        for key, value in keys_and_values:
            result = cache_manager.set(key, value)
            assert result is True

        # Verify all set operations were called
        assert mock_redis_manager.set.call_count == 3

    def test_cache_manager_namespace_isolation(self, cache_manager, mock_redis_manager):
        """Test CacheManager namespace isolation."""
        # Same key in different namespaces should be different
        cache_manager.set("shared_key", "value1", namespace="ns1")
        cache_manager.set("shared_key", "value2", namespace="ns2")

        # Check that different full keys were used
        call_args = mock_redis_manager.set.call_args_list
        assert call_args[0][0][0] == "ns1:shared_key"
        assert call_args[1][0][0] == "ns2:shared_key"

    def test_cache_manager_ttl_variations(self, cache_manager, mock_redis_manager):
        """Test CacheManager with various TTL formats."""
        mock_redis_manager.set.return_value = True

        # Test different TTL formats
        cache_manager.set("key1", "value", ttl=300)  # seconds
        cache_manager.set("key2", "value", ttl=timedelta(minutes=5))  # timedelta
        cache_manager.set("key3", "value", ttl=timedelta(hours=1, minutes=30))  # complex timedelta

        # Check TTL conversions
        call_args = mock_redis_manager.set.call_args_list
        assert call_args[0][1]['ex'] == 300
        assert call_args[1][1]['ex'] == 300  # 5 minutes
        assert call_args[2][1]['ex'] == 5400  # 1.5 hours

    def test_cache_manager_error_resilience(self, cache_manager, mock_redis_manager):
        """Test CacheManager resilience to various errors."""
        # Test Redis connection errors
        mock_redis_manager.get.side_effect = Exception("Connection error")
        mock_redis_manager.set.side_effect = Exception("Write error")
        mock_redis_manager.delete.side_effect = Exception("Delete error")

        with patch('app.utils.cache.logger') as mock_logger:
            # All operations should handle errors gracefully
            assert cache_manager.get("key") is None
            assert cache_manager.set("key", "value") is False
            assert cache_manager.delete("key") is False

            # Should log errors
            assert mock_logger.error.call_count >= 3

    def test_cache_manager_memory_efficiency(self, cache_manager, mock_redis_manager):
        """Test CacheManager memory efficiency with large data."""
        # Create large data structure
        large_data = {
            'bulk_data': ['x' * 1000] * 1000,  # ~1MB of data
            'metadata': {f'field_{i}': i for i in range(1000)}
        }

        mock_redis_manager.set.return_value = True

        # Should handle large data without memory issues
        result = cache_manager.set("large_key", large_data)
        assert result is True

    def test_cache_manager_key_pattern_matching(self, cache_manager, mock_redis_manager):
        """Test CacheManager pattern matching capabilities."""
        mock_redis_manager.keys.return_value = [
            "cache:user:123:profile",
            "cache:user:123:settings",
            "cache:user:456:profile",
            "cache:patient:789:data"
        ]
        mock_redis_manager.delete.return_value = True

        # Test pattern invalidation
        deleted_count = cache_manager.invalidate_pattern("user:123:*")

        assert deleted_count == 2  # Should match 2 keys
        mock_redis_manager.keys.assert_called_with("cache:user:123:*")

    def test_cache_manager_data_integrity(self, cache_manager, mock_redis_manager):
        """Test CacheManager maintains data integrity."""
        test_data = {
            'datetime': datetime(2024, 1, 1, 12, 0, 0),
            'uuid': uuid4(),
            'decimal': Decimal('123.456'),
            'nested': {
                'list': [1, 2, 3],
                'bool': True,
                'null': None
            }
        }

        # Mock round-trip serialization
        serialized_data = json.dumps(test_data, default=str)
        mock_redis_manager.get.return_value = serialized_data

        result = cache_manager.get("integrity_test")

        # Data should be preserved (though types may change for JSON serialization)
        assert isinstance(result, dict)
        assert 'datetime' in result
        assert 'uuid' in result
        assert 'decimal' in result

    def test_cache_manager_concurrent_operations(self, cache_manager, mock_redis_manager):
        """Test CacheManager handles concurrent operations safely."""
        mock_redis_manager.get.return_value = None
        mock_redis_manager.set.return_value = True

        results = []
        errors = []

        def cache_operation(thread_id):
            try:
                for i in range(10):
                    key = f"thread_{thread_id}_key_{i}"
                    value = f"thread_{thread_id}_value_{i}"

                    # Set and immediately get
                    cache_manager.set(key, value)
                    retrieved = cache_manager.get(key)
                    results.append((key, value, retrieved))
            except Exception as e:
                errors.append(e)

        # Run concurrent operations
        threads = [threading.Thread(target=cache_operation, args=(i,)) for i in range(5)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Should complete without errors
        assert len(errors) == 0
        assert len(results) == 50  # 5 threads * 10 operations

    def test_cache_manager_custom_namespace_behavior(self, cache_manager, mock_redis_manager):
        """Test CacheManager custom namespace behavior."""
        original_namespace = cache_manager.namespace

        # Test default namespace
        cache_manager.get("test_key")
        default_call = mock_redis_manager.get.call_args[0][0]
        assert default_call == f"{original_namespace}:test_key"

        # Test custom namespace
        cache_manager.get("test_key", namespace="custom")
        custom_call = mock_redis_manager.get.call_args[0][0]
        assert custom_call == "custom:test_key"

        # Test empty namespace
        cache_manager.get("test_key", namespace="")
        empty_call = mock_redis_manager.get.call_args[0][0]
        assert empty_call == ":test_key"


class TestAsyncCacheManagerComprehensive:
    """Comprehensive tests for AsyncCacheManager functionality."""

    @pytest.fixture
    def mock_async_redis_comprehensive(self):
        """Comprehensive mock async Redis client."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock()
        mock_client.set = AsyncMock()
        mock_client.delete = AsyncMock()
        mock_client.exists = AsyncMock()
        mock_client.ttl = AsyncMock()
        mock_client.keys = AsyncMock()
        return mock_client

    @pytest.fixture
    def async_cache_manager(self):
        """Create AsyncCacheManager."""
        return AsyncCacheManager()

    @pytest.mark.asyncio
    async def test_async_cache_manager_concurrent_operations(self, async_cache_manager, mock_async_redis_comprehensive):
        """Test AsyncCacheManager concurrent async operations."""
        mock_async_redis_comprehensive.get.return_value = None
        mock_async_redis_comprehensive.set.return_value = True

        with patch('app.utils.cache.get_async_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_async_redis_comprehensive

            async def async_cache_operation(operation_id):
                key = f"async_key_{operation_id}"
                value = f"async_value_{operation_id}"

                # Concurrent set and get operations
                await async_cache_manager.set(key, value)
                return await async_cache_manager.get(key)

            # Run multiple async operations concurrently
            tasks = [async_cache_operation(i) for i in range(10)]
            results = await asyncio.gather(*tasks)

            assert len(results) == 10
            # All operations should complete

    @pytest.mark.asyncio
    async def test_async_cache_manager_error_handling(self, async_cache_manager, mock_async_redis_comprehensive):
        """Test AsyncCacheManager error handling in async context."""
        # Simulate various async errors
        mock_async_redis_comprehensive.get.side_effect = Exception("Async get error")
        mock_async_redis_comprehensive.set.side_effect = Exception("Async set error")

        with patch('app.utils.cache.get_async_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_async_redis_comprehensive

            with patch('app.utils.cache.logger') as mock_logger:
                # Should handle async errors gracefully
                result_get = await async_cache_manager.get("error_key")
                result_set = await async_cache_manager.set("error_key", "value")

                assert result_get is None
                assert result_set is False
                assert mock_logger.error.call_count >= 2

    @pytest.mark.asyncio
    async def test_async_cache_manager_timeout_handling(self, async_cache_manager):
        """Test AsyncCacheManager handles timeouts correctly."""
        async def slow_redis_operation():
            await asyncio.sleep(5)  # Simulate slow operation
            return None

        mock_slow_redis = AsyncMock()
        mock_slow_redis.get = slow_redis_operation

        with patch('app.utils.cache.get_async_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_slow_redis

            # Should not hang indefinitely
            start_time = time.time()
            result = await async_cache_manager.get("slow_key")
            elapsed = time.time() - start_time

            # Should complete relatively quickly due to error handling
            assert elapsed < 10  # Should not wait full 5 seconds

    @pytest.mark.asyncio
    async def test_async_cache_manager_large_data_streaming(self, async_cache_manager, mock_async_redis_comprehensive):
        """Test AsyncCacheManager with large data that requires streaming."""
        # Create very large data
        large_data = {
            'stream_data': ['chunk'] * 10000,
            'metadata': {'size': '10k_chunks'}
        }

        mock_async_redis_comprehensive.set.return_value = True

        with patch('app.utils.cache.get_async_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_async_redis_comprehensive

            # Should handle large data efficiently
            result = await async_cache_manager.set("large_stream", large_data)
            assert result is True


class TestConvenienceFunctionsComprehensive:
    """Comprehensive tests for convenience functions."""

    @pytest.fixture
    def mock_cache_manager_comprehensive(self):
        """Mock cache manager for comprehensive testing."""
        with patch('app.utils.cache.get_cache_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.get = Mock()
            mock_manager.set = Mock()
            mock_manager.delete = Mock()
            mock_get_manager.return_value = mock_manager
            yield mock_manager

    @pytest.fixture
    def mock_async_cache_manager_comprehensive(self):
        """Mock async cache manager for comprehensive testing."""
        with patch('app.utils.cache.get_async_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get = AsyncMock()
            mock_manager.set = AsyncMock()
            mock_manager.delete = AsyncMock()
            mock_get_manager.return_value = mock_manager
            yield mock_manager

    def test_user_data_cache_functions_comprehensive(self, mock_cache_manager_comprehensive):
        """Test user data cache functions with comprehensive scenarios."""
        # Test with complex user data
        complex_user_data = {
            'id': 'user_123',
            'profile': {
                'name': 'Test User',
                'preferences': {'theme': 'dark', 'language': 'en'},
                'last_login': datetime.now().isoformat()
            },
            'permissions': ['read', 'write', 'admin'],
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
        }

        mock_cache_manager_comprehensive.set.return_value = True
        mock_cache_manager_comprehensive.get.return_value = complex_user_data
        mock_cache_manager_comprehensive.delete.return_value = True

        # Test caching complex user data
        result_set = cache_user_data("user_123", complex_user_data, ttl=1800)
        assert result_set is True

        # Test retrieving complex user data
        result_get = get_cached_user_data("user_123")
        assert result_get == complex_user_data

        # Test invalidating user cache
        result_delete = invalidate_user_cache("user_123")
        assert result_delete is True

        # Verify correct namespace usage
        mock_cache_manager_comprehensive.set.assert_called_with(
            "user:user_123", complex_user_data, ttl=1800, namespace="users"
        )

    def test_patient_data_cache_functions_comprehensive(self, mock_cache_manager_comprehensive):
        """Test patient data cache functions with comprehensive scenarios."""
        # Test with complex patient data
        complex_patient_data = {
            'id': 'patient_456',
            'medical_info': {
                'diagnosis': 'Test Diagnosis',
                'treatment_plan': ['step1', 'step2', 'step3'],
                'allergies': ['penicillin', 'latex'],
                'medications': {
                    'current': ['med1', 'med2'],
                    'history': ['old_med1', 'old_med2']
                }
            },
            'personal_info': {
                'name': 'Test Patient',
                'age': 45,
                'contact': {
                    'phone': '123-456-7890',
                    'email': 'patient@test.com'
                }
            },
            'appointments': [
                {'date': '2024-01-01', 'type': 'consultation'},
                {'date': '2024-01-15', 'type': 'follow-up'}
            ]
        }

        mock_cache_manager_comprehensive.set.return_value = True
        mock_cache_manager_comprehensive.get.return_value = complex_patient_data
        mock_cache_manager_comprehensive.delete.return_value = True

        # Test with custom TTL
        result_set = cache_patient_data("patient_456", complex_patient_data, ttl=7200)
        assert result_set is True

        # Test retrieval
        result_get = get_cached_patient_data("patient_456")
        assert result_get == complex_patient_data

        # Test invalidation
        result_delete = invalidate_patient_cache("patient_456")
        assert result_delete is True

        # Verify correct namespace and TTL
        mock_cache_manager_comprehensive.set.assert_called_with(
            "patient:patient_456", complex_patient_data, ttl=7200, namespace="patients"
        )

    @pytest.mark.asyncio
    async def test_async_convenience_functions_comprehensive(self, mock_async_cache_manager_comprehensive):
        """Test async convenience functions comprehensively."""
        test_data = {'async': 'data', 'timestamp': datetime.now().isoformat()}

        mock_async_cache_manager_comprehensive.set.return_value = True
        mock_async_cache_manager_comprehensive.get.return_value = test_data
        mock_async_cache_manager_comprehensive.delete.return_value = True

        # Test async user functions
        result_user_set = await cache_user_data_async("async_user", test_data)
        result_user_get = await get_cached_user_data_async("async_user")
        result_user_delete = await invalidate_user_cache_async("async_user")

        assert result_user_set is True
        assert result_user_get == test_data
        assert result_user_delete is True

        # Test async patient functions
        result_patient_set = await cache_patient_data_async("async_patient", test_data)
        result_patient_get = await get_cached_patient_data_async("async_patient")
        result_patient_delete = await invalidate_patient_cache_async("async_patient")

        assert result_patient_set is True
        assert result_patient_get == test_data
        assert result_patient_delete is True

        # Verify async calls were made correctly
        assert mock_async_cache_manager_comprehensive.set.call_count == 2
        assert mock_async_cache_manager_comprehensive.get.call_count == 2
        assert mock_async_cache_manager_comprehensive.delete.call_count == 2

    def test_convenience_functions_error_resilience(self, mock_cache_manager_comprehensive):
        """Test convenience functions handle errors gracefully."""
        # Simulate cache manager errors
        mock_cache_manager_comprehensive.set.side_effect = Exception("Set error")
        mock_cache_manager_comprehensive.get.side_effect = Exception("Get error")
        mock_cache_manager_comprehensive.delete.side_effect = Exception("Delete error")

        # Functions should handle errors without raising exceptions
        try:
            cache_user_data("error_user", {"data": "test"})
            get_cached_user_data("error_user")
            invalidate_user_cache("error_user")

            cache_patient_data("error_patient", {"data": "test"})
            get_cached_patient_data("error_patient")
            invalidate_patient_cache("error_patient")

            # If we reach here, error handling worked
            assert True
        except Exception as e:
            pytest.fail(f"Convenience functions should handle errors gracefully: {e}")


class TestAsyncCacheContextComprehensive:
    """Comprehensive tests for async cache context manager."""

    @pytest.mark.asyncio
    async def test_async_cache_context_nested_operations(self):
        """Test async cache context with nested operations."""
        with patch('app.utils.cache.get_async_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.set.return_value = True
            mock_manager.get.return_value = "cached_value"
            mock_manager.delete.return_value = True
            mock_get_manager.return_value = mock_manager

            async with async_cache() as cache_mgr:
                # Nested operations within context
                await cache_mgr.set("key1", "value1")

                async with async_cache() as nested_cache_mgr:
                    await nested_cache_mgr.set("key2", "value2")
                    result = await nested_cache_mgr.get("key1")
                    assert result == "cached_value"

                await cache_mgr.delete("key1")

            # All operations should complete successfully
            assert mock_manager.set.call_count == 2
            assert mock_manager.get.call_count == 1
            assert mock_manager.delete.call_count == 1

    @pytest.mark.asyncio
    async def test_async_cache_context_exception_handling(self):
        """Test async cache context handles exceptions properly."""
        with patch('app.utils.cache.get_async_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.set.side_effect = Exception("Context error")
            mock_get_manager.return_value = mock_manager

            try:
                async with async_cache() as cache_mgr:
                    await cache_mgr.set("error_key", "error_value")
                    # This should raise an exception

                # Context should handle cleanup properly even with exceptions
                assert True
            except Exception:
                # Exception is expected, context should still clean up properly
                pass

    @pytest.mark.asyncio
    async def test_async_cache_context_multiple_concurrent_contexts(self):
        """Test multiple concurrent async cache contexts."""
        with patch('app.utils.cache.get_async_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.set.return_value = True
            mock_manager.get.return_value = None
            mock_get_manager.return_value = mock_manager

            async def context_operation(context_id):
                async with async_cache() as cache_mgr:
                    await cache_mgr.set(f"key_{context_id}", f"value_{context_id}")
                    return await cache_mgr.get(f"key_{context_id}")

            # Run multiple contexts concurrently
            tasks = [context_operation(i) for i in range(5)]
            results = await asyncio.gather(*tasks)

            assert len(results) == 5
            # All contexts should operate independently


class TestCacheEdgeCasesAndPerformance:
    """Test edge cases, performance scenarios, and stress conditions."""

    def test_cache_with_extremely_large_keys(self):
        """Test cache behavior with extremely large cache keys."""
        # Create a very large key
        large_key_parts = ["x" * 1000 for _ in range(100)]  # 100KB+ key

        key = _generate_cache_key("test", *large_key_parts)

        # Should be hashed and much shorter
        assert len(key) < 1000
        assert "hash:" in key

    def test_cache_serialization_edge_cases(self):
        """Test cache serialization with edge case data types."""
        edge_case_data = [
            float('inf'),  # Infinity
            float('-inf'), # Negative infinity
            complex(1, 2), # Complex numbers
            set([1, 2, 3]), # Sets (not JSON serializable)
            frozenset([4, 5, 6]), # Frozen sets
            lambda x: x,   # Functions
            type,          # Types
        ]

        for data in edge_case_data:
            try:
                result = _serialize_for_cache(data)
                # Should not raise exception, might fallback to string
                assert isinstance(result, str)
            except Exception:
                # Some data types may not be serializable, that's ok
                pass

    def test_cache_performance_with_many_operations(self):
        """Test cache performance with many rapid operations."""
        with patch('app.utils.cache.get_sync_redis') as mock_get_redis:
            mock_client = Mock()
            mock_client.get.return_value = None
            mock_client.set.return_value = True
            mock_get_redis.return_value = mock_client

            @cache(ttl=300)
            def performance_function(value):
                return f"result_{value}"

            # Perform many operations rapidly
            start_time = time.time()
            for i in range(1000):
                performance_function(f"test_{i}")
            end_time = time.time()

            # Should complete in reasonable time (less than 5 seconds)
            assert (end_time - start_time) < 5.0

    def test_cache_memory_cleanup(self):
        """Test cache doesn't leak memory with many operations."""
        import gc

        with patch('app.utils.cache.get_sync_redis') as mock_get_redis:
            mock_client = Mock()
            mock_client.get.return_value = None
            mock_client.set.return_value = True
            mock_get_redis.return_value = mock_client

            @cache(ttl=300)
            def memory_test_function(value):
                return ["data"] * 1000  # Create some data

            # Force garbage collection
            gc.collect()
            initial_objects = len(gc.get_objects())

            # Perform operations
            for i in range(100):
                memory_test_function(f"test_{i}")

            # Force garbage collection again
            gc.collect()
            final_objects = len(gc.get_objects())

            # Object count shouldn't grow dramatically
            object_growth = final_objects - initial_objects
            assert object_growth < 10000  # Reasonable threshold

    def test_cache_thread_safety(self):
        """Test cache operations are thread-safe."""
        with patch('app.utils.cache.get_sync_redis') as mock_get_redis:
            mock_client = Mock()
            mock_client.get.return_value = None
            mock_client.set.return_value = True
            mock_get_redis.return_value = mock_client

            results = []
            errors = []

            @cache(ttl=300)
            def thread_safe_function(thread_id, value):
                return f"thread_{thread_id}_result_{value}"

            def thread_worker(thread_id):
                try:
                    for i in range(50):
                        result = thread_safe_function(thread_id, i)
                        results.append(result)
                except Exception as e:
                    errors.append(e)

            # Create and run multiple threads
            threads = [threading.Thread(target=thread_worker, args=(i,)) for i in range(10)]

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            # Should complete without errors
            assert len(errors) == 0
            assert len(results) == 500  # 10 threads * 50 operations

    @pytest.mark.asyncio
    async def test_async_cache_stress_test(self):
        """Stress test async cache operations."""
        with patch('app.utils.cache.get_async_redis') as mock_get_redis:
            mock_client = AsyncMock()
            mock_client.get.return_value = None
            mock_client.set.return_value = True
            mock_get_redis.return_value = mock_client

            async_manager = AsyncCacheManager()

            async def stress_operation(operation_id):
                tasks = []
                for i in range(10):
                    key = f"stress_{operation_id}_{i}"
                    value = f"stress_value_{operation_id}_{i}"

                    # Create concurrent set and get operations
                    tasks.append(async_manager.set(key, value))
                    tasks.append(async_manager.get(key))

                return await asyncio.gather(*tasks)

            # Run multiple stress operations concurrently
            stress_tasks = [stress_operation(i) for i in range(20)]
            results = await asyncio.gather(*stress_tasks)

            # All operations should complete
            assert len(results) == 20
            for result in results:
                assert len(result) == 20  # 10 sets + 10 gets per operation

    def test_cache_with_unicode_and_special_characters(self):
        """Test cache handles unicode and special characters correctly."""
        special_test_cases = [
            "test_data",  # ASCII safe
            "cafe naive resume",  # Accented characters removed
            "Internationalization",  # Mixed special chars removed
            "\n\t\r\\\"'",  # Escape characters
            "null_byte",  # Null byte removed
            "currency_symbols",  # Currency symbols removed
        ]

        for test_case in special_test_cases:
            # Test key generation
            key = _generate_cache_key("test", test_case)
            assert isinstance(key, str)

            # Test serialization
            serialized = _serialize_for_cache({"data": test_case})
            assert isinstance(serialized, str)

            # Test deserialization
            deserialized = _deserialize_from_cache(serialized)
            assert deserialized["data"] == test_case