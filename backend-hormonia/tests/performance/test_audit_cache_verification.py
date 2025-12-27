import pytest
from unittest.mock import patch, MagicMock
from app.infrastructure.cache.cache_decorators import cache, async_cache
from app.infrastructure.cache.invalidation import invalidate_user_cache, invalidate_patient_cache, CacheInvalidator
import time

@pytest.mark.performance
class TestCacheAuditVerification:
    """
    Audit verification tests for Cache Service utilization and invalidation.
    """

    def test_sync_cache_decorator(self):
        """Verify that the sync @cache decorator stores and retrieves values."""
        call_count = 0
        
        @cache(cache_type="test_sync", ttl=60)
        def get_data(x):
            nonlocal call_count
            call_count += 1
            return f"data-{x}"
            
        # First call - should execute function
        result1 = get_data(1)
        assert result1 == "data-1"
        assert call_count == 1
        
        # Second call - should return cached value
        result2 = get_data(1)
        assert result2 == "data-1"
        assert call_count == 1 # Still 1
        
        # Call with different arg - should execute again
        result3 = get_data(2)
        assert result3 == "data-2"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_cache_decorator(self):
        """Verify that the async @async_cache decorator stores and retrieves values."""
        call_count = 0
        
        @async_cache(cache_type="test_async", ttl=60)
        async def get_data_async(x):
            nonlocal call_count
            call_count += 1
            return f"async-data-{x}"
            
        # First call
        result1 = await get_data_async(1)
        assert result1 == "async-data-1"
        assert call_count == 1
        
        # Second call
        result2 = await get_data_async(1)
        assert result2 == "async-data-1"
        assert call_count == 1
        
    def test_user_cache_invalidation(self):
        """Verify that user cache invalidation works."""
        from app.infrastructure.cache.invalidation import cache_user_data, get_cached_user_data
        
        user_id = "test-user-123"
        data = {"name": "Test User"}
        
        # 1. Cache some data
        cache_user_data(user_id, data)
        
        # 2. Verify it's cached
        cached = get_cached_user_data(user_id)
        assert cached == data
        
        # 3. Invalidate
        invalidate_user_cache(user_id)
        
        # 4. Verify it's gone
        assert get_cached_user_data(user_id) is None

    def test_patient_cache_invalidation(self):
        """Verify that patient cache invalidation works."""
        from app.infrastructure.cache.invalidation import cache_patient_data, get_cached_patient_data
        
        patient_id = "test-patient-456"
        data = {"name": "Test Patient"}
        
        cache_patient_data(patient_id, data)
        assert get_cached_patient_data(patient_id) == data
        
        invalidate_patient_cache(patient_id)
        assert get_cached_patient_data(patient_id) is None

    def test_pattern_invalidation(self):
        """Verify that pattern-based invalidation works."""
        from app.infrastructure.cache.cache_manager import get_unified_cache_manager
        manager = get_unified_cache_manager()
        invalidator = CacheInvalidator(manager)
        
        # Manually set some keys via backend
        manager._backend.redis_set("cache:test:1", "val1", 60)
        manager._backend.redis_set("cache:test:2", "val2", 60)
        manager._backend.redis_set("cache:other:1", "val3", 60)
        
        # Invalidate pattern
        count = invalidator.invalidate_pattern("cache:test:*")
        
        # We can't easily check Redis keys in unit test without mocking
        # but we can verify the return count if we use fakeredis (which conftest should provide)
        assert count >= 2
        
        assert manager._backend.redis_get("cache:test:1") is None
        assert manager._backend.redis_get("cache:test:2") is None
        assert manager._backend.redis_get("cache:other:1") is not None
