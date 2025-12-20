"""
Comprehensive Unit Tests for RedisBackend

Tests Redis backend with serialization, local cache fallback, and operations.
"""
import pytest
import json
import pickle
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4, UUID


class TestRedisBackendInitialization:
    """Test RedisBackend initialization."""

    def test_initialization_default(self):
        """Test default initialization."""
        from app.infrastructure.cache.redis_backend import RedisBackend

        backend = RedisBackend()

        assert backend.redis_client is None
        assert backend.enable_local_fallback is True
        assert isinstance(backend._local_cache, dict)
        assert len(backend._local_cache) == 0

    def test_initialization_with_client(self):
        """Test initialization with provided client."""
        from app.infrastructure.cache.redis_backend import RedisBackend

        mock_client = Mock()
        backend = RedisBackend(redis_client=mock_client)

        assert backend.redis_client is mock_client

    def test_initialization_with_local_fallback_disabled(self):
        """Test initialization with local fallback disabled."""
        from app.infrastructure.cache.redis_backend import RedisBackend

        backend = RedisBackend(enable_local_fallback=False)

        assert backend.enable_local_fallback is False


class TestSerialization:
    """Test serialization methods."""

    @pytest.fixture
    def backend(self):
        """Create RedisBackend instance."""
        from app.infrastructure.cache.redis_backend import RedisBackend
        return RedisBackend()

    def test_serialize_string_json(self, backend):
        """Test serializing string to JSON."""
        from app.infrastructure.cache.redis_backend import SerializationMethod

        data = "test string"
        result = backend.serialize_for_cache(data, SerializationMethod.JSON)

        assert result == "test string"

    def test_serialize_dict_json(self, backend):
        """Test serializing dict to JSON."""
        from app.infrastructure.cache.redis_backend import SerializationMethod

        data = {"key": "value", "number": 42}
        result = backend.serialize_for_cache(data, SerializationMethod.JSON)

        parsed = json.loads(result)
        assert parsed["key"] == "value"
        assert parsed["number"] == 42

    def test_serialize_datetime_json(self, backend):
        """Test serializing datetime to JSON."""
        from app.infrastructure.cache.redis_backend import SerializationMethod

        now = datetime.utcnow()
        data = {"timestamp": now}
        result = backend.serialize_for_cache(data, SerializationMethod.JSON)

        parsed = json.loads(result)
        assert "timestamp" in parsed
        # Should be ISO format string
        assert isinstance(parsed["timestamp"], str)

    def test_serialize_uuid_json(self, backend):
        """Test serializing UUID to JSON."""
        from app.infrastructure.cache.redis_backend import SerializationMethod

        uid = uuid4()
        data = {"id": uid}
        result = backend.serialize_for_cache(data, SerializationMethod.JSON)

        parsed = json.loads(result)
        assert "id" in parsed
        # Should be string representation
        assert UUID(parsed["id"]) == uid

    def test_serialize_decimal_json(self, backend):
        """Test serializing Decimal to JSON."""
        from app.infrastructure.cache.redis_backend import SerializationMethod

        data = {"price": Decimal("19.99")}
        result = backend.serialize_for_cache(data, SerializationMethod.JSON)

        parsed = json.loads(result)
        assert "price" in parsed
        assert parsed["price"] == 19.99

    def test_serialize_object_with_dict_json(self, backend):
        """Test serializing object with __dict__ to JSON."""
        from app.infrastructure.cache.redis_backend import SerializationMethod

        class TestObject:
            def __init__(self):
                self.name = "test"
                self.value = 123
                self._private = "hidden"

        obj = TestObject()
        result = backend.serialize_for_cache(obj, SerializationMethod.JSON)

        parsed = json.loads(result)
        assert "name" in parsed
        assert "value" in parsed
        # Private attributes should be excluded
        assert "_private" not in parsed

    def test_serialize_pickle(self, backend):
        """Test serializing to pickle."""
        from app.infrastructure.cache.redis_backend import SerializationMethod

        data = {"key": "value", "number": 42}
        result = backend.serialize_for_cache(data, SerializationMethod.PICKLE)

        assert isinstance(result, bytes)
        deserialized = pickle.loads(result)
        assert deserialized == data

    def test_serialize_handles_error(self, backend):
        """Test serialization handles errors gracefully."""
        from app.infrastructure.cache.redis_backend import SerializationMethod

        # Create non-serializable object
        class NonSerializable:
            def __str__(self):
                raise Exception("Cannot serialize")

        obj = NonSerializable()
        # Should fall back to str() and handle the error
        result = backend.serialize_for_cache(obj, SerializationMethod.JSON)

        # Should return some string representation
        assert isinstance(result, str)


class TestDeserialization:
    """Test deserialization methods."""

    @pytest.fixture
    def backend(self):
        """Create RedisBackend instance."""
        from app.infrastructure.cache.redis_backend import RedisBackend
        return RedisBackend()

    def test_deserialize_json_string(self, backend):
        """Test deserializing JSON string."""
        from app.infrastructure.cache.redis_backend import SerializationMethod

        data = '{"key": "value", "number": 42}'
        result = backend.deserialize_from_cache(data, SerializationMethod.JSON)

        assert result["key"] == "value"
        assert result["number"] == 42

    def test_deserialize_json_bytes(self, backend):
        """Test deserializing JSON bytes."""
        from app.infrastructure.cache.redis_backend import SerializationMethod

        data = b'{"key": "value", "number": 42}'
        result = backend.deserialize_from_cache(data, SerializationMethod.JSON)

        assert result["key"] == "value"
        assert result["number"] == 42

    def test_deserialize_pickle_bytes(self, backend):
        """Test deserializing pickle bytes."""
        from app.infrastructure.cache.redis_backend import SerializationMethod

        original = {"key": "value", "number": 42}
        pickled = pickle.dumps(original)

        result = backend.deserialize_from_cache(pickled, SerializationMethod.PICKLE)

        assert result == original

    def test_deserialize_handles_error(self, backend):
        """Test deserialization handles errors gracefully."""
        from app.infrastructure.cache.redis_backend import SerializationMethod

        # Invalid JSON
        data = "not valid json {"
        result = backend.deserialize_from_cache(data, SerializationMethod.JSON)

        # Should return the original data on error
        assert result == data


class TestLocalCache:
    """Test local cache functionality."""

    @pytest.fixture
    def backend(self):
        """Create RedisBackend instance with local cache enabled."""
        from app.infrastructure.cache.redis_backend import RedisBackend
        return RedisBackend(enable_local_fallback=True)

    def test_set_in_local_cache(self, backend):
        """Test setting value in local cache."""
        backend.set_in_local_cache("test_key", "test_value", 60)

        assert "test_key" in backend._local_cache
        assert backend._local_cache["test_key"]["data"] == "test_value"

    def test_get_from_local_cache_valid(self, backend):
        """Test getting value from local cache (not expired)."""
        backend.set_in_local_cache("test_key", "test_value", 60)

        result = backend.get_from_local_cache("test_key")

        assert result == "test_value"

    def test_get_from_local_cache_expired(self, backend):
        """Test getting expired value from local cache."""
        # Set with negative TTL to make it expired
        backend._local_cache["test_key"] = {
            "data": "test_value",
            "expires_at": datetime.utcnow() - timedelta(seconds=1)
        }

        result = backend.get_from_local_cache("test_key")

        assert result is None
        # Should be removed from cache
        assert "test_key" not in backend._local_cache

    def test_get_from_local_cache_not_found(self, backend):
        """Test getting non-existent value from local cache."""
        result = backend.get_from_local_cache("nonexistent")

        assert result is None

    def test_remove_from_local_cache(self, backend):
        """Test removing value from local cache."""
        backend.set_in_local_cache("test_key", "test_value", 60)
        backend.remove_from_local_cache("test_key")

        assert "test_key" not in backend._local_cache

    def test_clear_local_cache(self, backend):
        """Test clearing local cache."""
        backend.set_in_local_cache("key1", "value1", 60)
        backend.set_in_local_cache("key2", "value2", 60)

        backend.clear_local_cache()

        assert len(backend._local_cache) == 0

    def test_get_local_cache_size(self, backend):
        """Test getting local cache size."""
        backend.set_in_local_cache("key1", "value1", 60)
        backend.set_in_local_cache("key2", "value2", 60)

        size = backend.get_local_cache_size()

        assert size == 2

    def test_local_cache_disabled(self):
        """Test local cache operations when disabled."""
        from app.infrastructure.cache.redis_backend import RedisBackend

        backend = RedisBackend(enable_local_fallback=False)

        backend.set_in_local_cache("test_key", "test_value", 60)
        result = backend.get_from_local_cache("test_key")

        assert result is None
        assert len(backend._local_cache) == 0


class TestSyncRedisOperations:
    """Test synchronous Redis operations."""

    @pytest.fixture
    def backend_with_mock_client(self):
        """Create RedisBackend with mock sync client."""
        from app.infrastructure.cache.redis_backend import RedisBackend

        mock_client = Mock()
        backend = RedisBackend(redis_client=mock_client)
        return backend, mock_client

    def test_redis_get_success(self, backend_with_mock_client):
        """Test successful GET from Redis."""
        backend, mock_client = backend_with_mock_client
        mock_client.get.return_value = b"test_value"

        result = backend.redis_get("test_key")

        assert result == b"test_value"
        mock_client.get.assert_called_once_with("test_key")

    def test_redis_get_failure(self, backend_with_mock_client):
        """Test GET from Redis handles failure."""
        backend, mock_client = backend_with_mock_client
        mock_client.get.side_effect = Exception("Connection error")

        result = backend.redis_get("test_key")

        assert result is None

    def test_redis_set_success(self, backend_with_mock_client):
        """Test successful SET to Redis."""
        backend, mock_client = backend_with_mock_client
        mock_client.set.return_value = True

        result = backend.redis_set("test_key", "test_value", 60)

        assert result is True
        mock_client.set.assert_called_once_with("test_key", "test_value", ex=60)

    def test_redis_set_failure(self, backend_with_mock_client):
        """Test SET to Redis handles failure."""
        backend, mock_client = backend_with_mock_client
        mock_client.set.side_effect = Exception("Connection error")

        result = backend.redis_set("test_key", "test_value", 60)

        assert result is False

    def test_redis_delete_success(self, backend_with_mock_client):
        """Test successful DELETE from Redis."""
        backend, mock_client = backend_with_mock_client
        mock_client.delete.return_value = 1

        result = backend.redis_delete("test_key")

        assert result is True
        mock_client.delete.assert_called_once_with("test_key")

    def test_redis_exists_true(self, backend_with_mock_client):
        """Test EXISTS returns true."""
        backend, mock_client = backend_with_mock_client
        mock_client.exists.return_value = 1

        result = backend.redis_exists("test_key")

        assert result is True

    def test_redis_exists_false(self, backend_with_mock_client):
        """Test EXISTS returns false."""
        backend, mock_client = backend_with_mock_client
        mock_client.exists.return_value = 0

        result = backend.redis_exists("test_key")

        assert result is False

    def test_redis_ttl_valid(self, backend_with_mock_client):
        """Test TTL returns valid value."""
        backend, mock_client = backend_with_mock_client
        mock_client.ttl.return_value = 60

        result = backend.redis_ttl("test_key")

        assert result == 60

    def test_redis_ttl_expired(self, backend_with_mock_client):
        """Test TTL returns None for expired key."""
        backend, mock_client = backend_with_mock_client
        mock_client.ttl.return_value = -2

        result = backend.redis_ttl("test_key")

        assert result is None

    def test_redis_keys_success(self, backend_with_mock_client):
        """Test KEYS pattern matching."""
        backend, mock_client = backend_with_mock_client
        mock_client.keys.return_value = [b"key1", b"key2"]

        result = backend.redis_keys("test:*")

        assert result == [b"key1", b"key2"]
        mock_client.keys.assert_called_once_with("test:*")


class TestAsyncRedisOperations:
    """Test asynchronous Redis operations."""

    @pytest.fixture
    async def backend_with_mock_client(self):
        """Create RedisBackend with mock async client."""
        from app.infrastructure.cache.redis_backend import RedisBackend

        mock_client = AsyncMock()

        backend = RedisBackend()

        # Mock the get_async_redis_client method
        with patch.object(backend, 'get_async_redis_client', return_value=mock_client):
            yield backend, mock_client

    @pytest.mark.asyncio
    async def test_redis_get_async_success(self, backend_with_mock_client):
        """Test successful async GET from Redis."""
        backend, mock_client = await backend_with_mock_client
        mock_client.get.return_value = b"test_value"

        with patch.object(backend, 'get_async_redis_client', return_value=mock_client):
            result = await backend.redis_get_async("test_key")

        assert result == b"test_value"

    @pytest.mark.asyncio
    async def test_redis_set_async_success(self, backend_with_mock_client):
        """Test successful async SET to Redis."""
        backend, mock_client = await backend_with_mock_client
        mock_client.set.return_value = True

        with patch.object(backend, 'get_async_redis_client', return_value=mock_client):
            result = await backend.redis_set_async("test_key", "test_value", 60)

        assert result is True

    @pytest.mark.asyncio
    async def test_redis_delete_async_success(self, backend_with_mock_client):
        """Test successful async DELETE from Redis."""
        backend, mock_client = await backend_with_mock_client
        mock_client.delete.return_value = 1

        with patch.object(backend, 'get_async_redis_client', return_value=mock_client):
            result = await backend.redis_delete_async("test_key")

        assert result is True

    @pytest.mark.asyncio
    async def test_redis_exists_async_true(self, backend_with_mock_client):
        """Test async EXISTS returns true."""
        backend, mock_client = await backend_with_mock_client
        mock_client.exists.return_value = 1

        with patch.object(backend, 'get_async_redis_client', return_value=mock_client):
            result = await backend.redis_exists_async("test_key")

        assert result is True

    @pytest.mark.asyncio
    async def test_redis_keys_async_success(self, backend_with_mock_client):
        """Test async KEYS pattern matching."""
        backend, mock_client = await backend_with_mock_client
        mock_client.keys.return_value = [b"key1", b"key2"]

        with patch.object(backend, 'get_async_redis_client', return_value=mock_client):
            result = await backend.redis_keys_async("test:*")

        assert result == [b"key1", b"key2"]


class TestClientGetters:
    """Test Redis client getter methods."""

    @pytest.mark.asyncio
    async def test_get_async_redis_client_success(self):
        """Test getting async Redis client."""
        from app.infrastructure.cache.redis_backend import RedisBackend

        mock_client = AsyncMock()

        with patch('app.infrastructure.cache.redis_backend.get_async_redis', return_value=mock_client):
            backend = RedisBackend()
            client = await backend.get_async_redis_client()

            assert client is mock_client

    @pytest.mark.asyncio
    async def test_get_async_redis_client_failure(self):
        """Test async client getter handles failure."""
        from app.infrastructure.cache.redis_backend import RedisBackend

        with patch('app.infrastructure.cache.redis_backend.get_async_redis', side_effect=Exception("Connection failed")):
            backend = RedisBackend()
            client = await backend.get_async_redis_client()

            assert client is None

    def test_get_sync_redis_client_with_existing(self):
        """Test getting sync client when already set."""
        from app.infrastructure.cache.redis_backend import RedisBackend

        mock_client = Mock()
        backend = RedisBackend(redis_client=mock_client)

        client = backend.get_sync_redis_client()

        assert client is mock_client

    def test_get_sync_redis_client_from_unified(self):
        """Test getting sync client from unified module."""
        from app.infrastructure.cache.redis_backend import RedisBackend

        mock_client = Mock()

        with patch('app.infrastructure.cache.redis_backend.get_sync_redis', return_value=mock_client):
            backend = RedisBackend()
            client = backend.get_sync_redis_client()

            assert client is mock_client

    def test_get_sync_redis_client_failure(self):
        """Test sync client getter handles failure."""
        from app.infrastructure.cache.redis_backend import RedisBackend

        with patch('app.infrastructure.cache.redis_backend.get_sync_redis', side_effect=Exception("Connection failed")):
            backend = RedisBackend()
            client = backend.get_sync_redis_client()

            assert client is None
