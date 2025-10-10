"""
Comprehensive Tests for Query Cache Layer

Sprint 1 (P1-1): Verify 40% database load reduction and cache performance targets.

Test Coverage:
- Cache hit/miss scenarios
- TTL management
- Tag-based invalidation
- Performance metrics (<10ms operations)
- Serialization of complex types
"""

import pytest
import time
from uuid import uuid4
from datetime import datetime
from decimal import Decimal

from app.utils.query_cache import QueryCache, cached_query, get_query_cache
from app.core.redis_manager import get_sync_redis_client


@pytest.fixture
def redis_client():
    """Get Redis client for testing."""
    return get_sync_redis_client()


@pytest.fixture
def query_cache(redis_client):
    """Create QueryCache instance for testing."""
    cache = QueryCache(redis_client=redis_client, default_ttl=60)
    # Clear any existing test keys
    for key in redis_client.scan_iter(match="query_cache:test:*"):
        redis_client.delete(key)
    cache.reset_stats()
    return cache


class TestQueryCache:
    """Test QueryCache basic operations."""

    def test_cache_set_and_get(self, query_cache):
        """Test basic cache set/get operations."""
        # Set value
        key = query_cache.generate_cache_key('test', user_id='123')
        query_cache.set(key, {'name': 'Test User', 'age': 30})

        # Get value
        cached_value = query_cache.get(key)

        assert cached_value is not None
        assert cached_value['name'] == 'Test User'
        assert cached_value['age'] == 30

        # Verify stats
        stats = query_cache.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 0

    def test_cache_miss(self, query_cache):
        """Test cache miss scenario."""
        key = query_cache.generate_cache_key('test', user_id='nonexistent')
        cached_value = query_cache.get(key)

        assert cached_value is None

        # Verify stats
        stats = query_cache.get_stats()
        assert stats['hits'] == 0
        assert stats['misses'] == 1

    def test_cache_ttl_expiration(self, query_cache):
        """Test TTL expiration."""
        # Set value with 1 second TTL
        key = query_cache.generate_cache_key('test', user_id='ttl_test')
        query_cache.set(key, {'data': 'test'}, ttl=1)

        # Should exist immediately
        assert query_cache.get(key) is not None

        # Wait for expiration
        time.sleep(1.5)

        # Should be expired
        assert query_cache.get(key) is None

    def test_cache_key_generation(self, query_cache):
        """Test deterministic cache key generation."""
        # Same parameters should generate same key
        key1 = query_cache.generate_cache_key('test', user_id='123', name='test')
        key2 = query_cache.generate_cache_key('test', name='test', user_id='123')

        assert key1 == key2

        # Different parameters should generate different keys
        key3 = query_cache.generate_cache_key('test', user_id='456')

        assert key1 != key3

    def test_complex_type_serialization(self, query_cache):
        """Test serialization of complex Python types."""
        # UUID serialization
        test_uuid = uuid4()
        key = query_cache.generate_cache_key('test', id=str(test_uuid))
        query_cache.set(key, {'id': test_uuid})

        cached = query_cache.get(key)
        assert cached['id'] == str(test_uuid)

        # Datetime serialization
        test_dt = datetime.utcnow()
        key2 = query_cache.generate_cache_key('test', dt=str(test_dt))
        query_cache.set(key2, {'timestamp': test_dt})

        cached2 = query_cache.get(key2)
        assert cached2['timestamp'] == test_dt.isoformat()

        # Decimal serialization
        key3 = query_cache.generate_cache_key('test', price='99.99')
        query_cache.set(key3, {'price': Decimal('99.99')})

        cached3 = query_cache.get(key3)
        assert cached3['price'] == 99.99

    def test_tag_based_invalidation(self, query_cache, redis_client):
        """Test tag-based cache invalidation."""
        # Create multiple cache entries with same tag
        for i in range(5):
            key = query_cache.generate_cache_key('test', user_id=f'user_{i}')
            query_cache.set(key, {'user': f'user_{i}'}, tags=[f'patient:123'])

        # Verify all entries exist
        for i in range(5):
            key = query_cache.generate_cache_key('test', user_id=f'user_{i}')
            assert query_cache.get(key) is not None

        # Invalidate by tag
        deleted = query_cache.invalidate_by_tag('patient:123')

        assert deleted == 5

        # Verify all entries are gone
        for i in range(5):
            key = query_cache.generate_cache_key('test', user_id=f'user_{i}')
            assert query_cache.get(key) is None

    def test_pattern_invalidation(self, query_cache):
        """Test pattern-based cache invalidation."""
        # Create multiple cache entries
        for i in range(3):
            key = query_cache.generate_cache_key('test_pattern', user_id=f'{i}')
            query_cache.set(key, {'data': i})

        # Invalidate by pattern
        deleted = query_cache.invalidate_by_pattern('query_cache:test_pattern:*')

        assert deleted == 3

    def test_performance_tracking(self, query_cache):
        """Test cache performance metrics."""
        # Perform multiple operations
        for i in range(10):
            key = query_cache.generate_cache_key('test', id=str(i))
            query_cache.set(key, {'value': i})

        for i in range(10):
            key = query_cache.generate_cache_key('test', id=str(i))
            query_cache.get(key)

        # Check stats
        stats = query_cache.get_stats()

        assert stats['hits'] == 10
        assert stats['total_requests'] == 10
        assert stats['hit_rate_percent'] == 100.0
        assert stats['avg_get_time_ms'] < 10  # Target: <10ms


class TestCachedQueryDecorator:
    """Test @cached_query decorator."""

    def test_decorator_caches_result(self, redis_client):
        """Test that decorator caches function results."""
        call_count = 0

        @cached_query('test_func', ttl=60)
        def expensive_function(db, user_id):
            nonlocal call_count
            call_count += 1
            return {'user_id': user_id, 'data': 'expensive_result'}

        # First call - should execute function
        result1 = expensive_function(None, '123')
        assert result1['user_id'] == '123'
        assert call_count == 1

        # Second call - should use cache
        result2 = expensive_function(None, '123')
        assert result2['user_id'] == '123'
        assert call_count == 1  # Function not called again

        # Different parameter - should execute function
        result3 = expensive_function(None, '456')
        assert result3['user_id'] == '456'
        assert call_count == 2

    def test_decorator_respects_ttl(self, redis_client):
        """Test that decorator respects TTL."""
        call_count = 0

        @cached_query('test_ttl', ttl=1)
        def quick_expiry_func(db, value):
            nonlocal call_count
            call_count += 1
            return {'value': value}

        # First call
        quick_expiry_func(None, 'test')
        assert call_count == 1

        # Immediate second call - cached
        quick_expiry_func(None, 'test')
        assert call_count == 1

        # Wait for expiration
        time.sleep(1.5)

        # Call after expiration - not cached
        quick_expiry_func(None, 'test')
        assert call_count == 2


class TestCacheIntegration:
    """Integration tests for cache system."""

    def test_cache_with_list_results(self, query_cache):
        """Test caching with list results (common for repository queries)."""
        # Simulate list of model objects
        patient_list = [
            {'id': str(uuid4()), 'name': 'Patient 1'},
            {'id': str(uuid4()), 'name': 'Patient 2'},
            {'id': str(uuid4()), 'name': 'Patient 3'}
        ]

        key = query_cache.generate_cache_key('patients', doctor_id='doctor_123')
        query_cache.set(key, patient_list)

        # Retrieve and verify
        cached_list = query_cache.get(key)

        assert isinstance(cached_list, list)
        assert len(cached_list) == 3
        assert cached_list[0]['name'] == 'Patient 1'

    def test_cache_hit_rate_calculation(self, query_cache):
        """Test cache hit rate calculation."""
        # Create some cache entries
        for i in range(5):
            key = query_cache.generate_cache_key('test', id=str(i))
            query_cache.set(key, {'value': i})

        # Mix of hits and misses
        for i in range(5):
            key = query_cache.generate_cache_key('test', id=str(i))
            query_cache.get(key)  # Hit

        for i in range(5, 10):
            key = query_cache.generate_cache_key('test', id=str(i))
            query_cache.get(key)  # Miss

        stats = query_cache.get_stats()

        assert stats['hits'] == 5
        assert stats['misses'] == 5
        assert stats['hit_rate_percent'] == 50.0

    def test_cache_invalidation_on_mutation(self, query_cache):
        """Test cache invalidation after data mutation."""
        # Cache patient data
        patient_id = str(uuid4())
        key = query_cache.generate_cache_key('patient', patient_id=patient_id)
        query_cache.set(key, {'name': 'Original Name'}, tags=[f'patient:{patient_id}'])

        # Verify cached
        assert query_cache.get(key)['name'] == 'Original Name'

        # Simulate mutation - invalidate cache
        query_cache.invalidate_by_tag(f'patient:{patient_id}')

        # Verify cache cleared
        assert query_cache.get(key) is None

    def test_global_cache_singleton(self):
        """Test global cache instance."""
        cache1 = get_query_cache()
        cache2 = get_query_cache()

        assert cache1 is cache2  # Should be same instance


@pytest.mark.performance
class TestCachePerformance:
    """Performance tests for cache operations."""

    def test_cache_operation_latency(self, query_cache):
        """Test that cache operations are <10ms."""
        test_data = {'key': 'value', 'number': 123}

        # Test SET performance
        key = query_cache.generate_cache_key('perf_test', id='123')
        start = time.time()
        query_cache.set(key, test_data)
        set_time_ms = (time.time() - start) * 1000

        assert set_time_ms < 10, f"SET took {set_time_ms:.2f}ms (target: <10ms)"

        # Test GET performance
        start = time.time()
        query_cache.get(key)
        get_time_ms = (time.time() - start) * 1000

        assert get_time_ms < 10, f"GET took {get_time_ms:.2f}ms (target: <10ms)"

    def test_bulk_cache_performance(self, query_cache):
        """Test cache performance with bulk operations."""
        # Create 100 cache entries
        start = time.time()

        for i in range(100):
            key = query_cache.generate_cache_key('bulk_test', id=str(i))
            query_cache.set(key, {'value': i})

        bulk_set_time = time.time() - start

        # Average should be <10ms per operation
        avg_time_ms = (bulk_set_time / 100) * 1000
        assert avg_time_ms < 10, f"Average SET: {avg_time_ms:.2f}ms (target: <10ms)"

        # Retrieve all entries
        start = time.time()

        for i in range(100):
            key = query_cache.generate_cache_key('bulk_test', id=str(i))
            query_cache.get(key)

        bulk_get_time = time.time() - start

        avg_get_time_ms = (bulk_get_time / 100) * 1000
        assert avg_get_time_ms < 10, f"Average GET: {avg_get_time_ms:.2f}ms (target: <10ms)"
