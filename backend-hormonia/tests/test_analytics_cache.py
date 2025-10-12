"""
Tests for Analytics Cache Service.
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from app.services.analytics_cache import (
    AnalyticsCacheService,
    CacheConfig,
    CacheMetrics,
    cache_analytics_data,
    get_analytics_cache
)


class TestAnalyticsCacheService:
    """Test cases for AnalyticsCacheService."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        with patch('app.services.analytics_cache.get_sync_redis') as mock_redis:
            redis_client = Mock()
            mock_redis.return_value = redis_client
            yield redis_client
    
    @pytest.fixture
    def cache_service(self, mock_redis):
        """Create AnalyticsCacheService instance."""
        return AnalyticsCacheService()
    
    def test_initialization(self, cache_service):
        """Test cache service initialization."""
        assert cache_service is not None
        assert isinstance(cache_service._metrics, CacheMetrics)
        assert cache_service.CACHE_KEY_PREFIX == "analytics_cache"
    
    def test_cache_configurations(self, cache_service):
        """Test cache configurations for different data types."""
        configs = cache_service.CACHE_CONFIGS
        
        # Check that all expected cache types have configurations
        expected_types = [
            "dashboard", "treatment_distribution", "engagement_chart",
            "patient_analytics", "system_analytics", "query_performance", "patterns"
        ]
        
        for cache_type in expected_types:
            assert cache_type in configs
            config = configs[cache_type]
            assert isinstance(config, CacheConfig)
            assert config.ttl_seconds > 0
    
    def test_get_cache_hit(self, cache_service, mock_redis):
        """Test cache hit scenario."""
        # Setup mock Redis response
        test_data = {"key": "value", "number": 123}
        mock_redis.get.return_value = json.dumps(test_data)
        
        # Test cache get
        key_params = {"doctor_id": "123", "period": "7d"}
        result = cache_service.get("dashboard", key_params)
        
        assert result == test_data
        assert cache_service._metrics.hits == 1
        assert cache_service._metrics.misses == 0
        
        # Verify Redis was called with correct key
        mock_redis.get.assert_called_once()
        call_args = mock_redis.get.call_args[0]
        assert "analytics_cache:dashboard:" in call_args[0]
    
    def test_get_cache_miss(self, cache_service, mock_redis):
        """Test cache miss scenario."""
        # Setup mock Redis response (no data)
        mock_redis.get.return_value = None
        
        # Test cache get
        key_params = {"doctor_id": "123", "period": "7d"}
        result = cache_service.get("dashboard", key_params)
        
        assert result is None
        assert cache_service._metrics.hits == 0
        assert cache_service._metrics.misses == 1
    
    def test_set_cache(self, cache_service, mock_redis):
        """Test setting data in cache."""
        # Setup mock Redis response
        mock_redis.setex.return_value = True
        
        # Test cache set
        key_params = {"doctor_id": "123", "period": "7d"}
        test_data = {"total_patients": 50, "active_patients": 30}
        
        result = cache_service.set("dashboard", key_params, test_data)
        
        assert result is True
        
        # Verify Redis was called correctly
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[0]
        
        # Check key format
        assert "analytics_cache:dashboard:" in call_args[0]
        
        # Check TTL (should be dashboard config TTL)
        expected_ttl = cache_service.CACHE_CONFIGS["dashboard"].ttl_seconds
        assert call_args[1] == expected_ttl
        
        # Check data serialization
        stored_data = json.loads(call_args[2])
        assert stored_data == test_data
    
    def test_invalidate_specific_key(self, cache_service, mock_redis):
        """Test invalidating specific cache key."""
        mock_redis.delete.return_value = 1
        
        key_params = {"doctor_id": "123", "period": "7d"}
        deleted_count = cache_service.invalidate("dashboard", key_params)
        
        assert deleted_count == 1
        assert cache_service._metrics.invalidations == 1
        
        # Verify Redis delete was called
        mock_redis.delete.assert_called_once()
    
    def test_invalidate_all_keys_of_type(self, cache_service, mock_redis):
        """Test invalidating all keys of a specific type."""
        # Setup mock Redis responses
        mock_keys = [
            "analytics_cache:dashboard:doctor_id=123",
            "analytics_cache:dashboard:doctor_id=456"
        ]
        mock_redis.keys.return_value = mock_keys
        mock_redis.delete.return_value = 2
        
        deleted_count = cache_service.invalidate("dashboard")
        
        assert deleted_count == 2
        assert cache_service._metrics.invalidations == 2
        
        # Verify Redis operations
        mock_redis.keys.assert_called_once_with("analytics_cache:dashboard:*")
        mock_redis.delete.assert_called_once_with(*mock_keys)
    
    def test_warm_cache(self, cache_service, mock_redis):
        """Test cache warming functionality."""
        mock_redis.setex.return_value = True
        
        # Mock data generator function
        def data_generator():
            return {"generated": "data", "timestamp": datetime.utcnow().isoformat()}
        
        key_params = {"doctor_id": "123"}
        result = cache_service.warm_cache("dashboard", key_params, data_generator)
        
        assert result is True
        assert cache_service._metrics.warming_operations == 1
        
        # Verify Redis setex was called
        mock_redis.setex.assert_called_once()
    
    def test_get_or_set_cache_hit(self, cache_service, mock_redis):
        """Test get_or_set with cache hit."""
        # Setup cache hit
        test_data = {"cached": "data"}
        mock_redis.get.return_value = json.dumps(test_data)
        
        # Mock data generator (should not be called)
        data_generator = Mock()
        
        key_params = {"doctor_id": "123"}
        result = cache_service.get_or_set("dashboard", key_params, data_generator)
        
        assert result == test_data
        assert cache_service._metrics.hits == 1
        
        # Data generator should not have been called
        data_generator.assert_not_called()
    
    def test_get_or_set_cache_miss(self, cache_service, mock_redis):
        """Test get_or_set with cache miss."""
        # Setup cache miss
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        
        # Mock data generator
        fresh_data = {"fresh": "data"}
        data_generator = Mock(return_value=fresh_data)
        
        key_params = {"doctor_id": "123"}
        result = cache_service.get_or_set("dashboard", key_params, data_generator)
        
        assert result == fresh_data
        assert cache_service._metrics.misses == 1
        
        # Data generator should have been called
        data_generator.assert_called_once()
        
        # Fresh data should have been cached
        mock_redis.setex.assert_called_once()
    
    def test_get_metrics(self, cache_service):
        """Test getting cache metrics."""
        # Simulate some cache activity
        cache_service._metrics.hits = 80
        cache_service._metrics.misses = 20
        cache_service._metrics.invalidations = 5
        cache_service._metrics.warming_operations = 3
        
        metrics = cache_service.get_metrics()
        
        assert metrics.hits == 80
        assert metrics.misses == 20
        assert metrics.hit_rate == 80.0  # 80 / (80 + 20) * 100
        assert metrics.invalidations == 5
        assert metrics.warming_operations == 3
    
    def test_clear_all_cache(self, cache_service, mock_redis):
        """Test clearing all cache entries."""
        mock_keys = [
            "analytics_cache:dashboard:key1",
            "analytics_cache:treatment_distribution:key2",
            "analytics_cache:engagement_chart:key3"
        ]
        mock_redis.keys.return_value = mock_keys
        mock_redis.delete.return_value = 3
        
        deleted_count = cache_service.clear_all()
        
        assert deleted_count == 3
        
        # Verify Redis operations
        mock_redis.keys.assert_called_once_with("analytics_cache:*")
        mock_redis.delete.assert_called_once_with(*mock_keys)
    
    def test_get_cache_info(self, cache_service, mock_redis):
        """Test getting comprehensive cache information."""
        # Setup mock Redis responses
        mock_keys = [
            b"analytics_cache:dashboard:key1",
            b"analytics_cache:treatment_distribution:key2",
            b"analytics_cache:engagement_chart:key3"
        ]
        mock_redis.keys.return_value = mock_keys
        mock_redis.get.side_effect = [b'{"data": "value1"}', b'{"data": "value2"}', b'{"data": "value3"}']
        
        # Set some metrics
        cache_service._metrics.hits = 50
        cache_service._metrics.misses = 10
        
        cache_info = cache_service.get_cache_info()
        
        assert "metrics" in cache_info
        assert "total_keys" in cache_info
        assert "total_size_bytes" in cache_info
        assert "cache_types" in cache_info
        assert "configurations" in cache_info
        assert "timestamp" in cache_info
        
        assert cache_info["total_keys"] == 3
        assert cache_info["metrics"]["hits"] == 50
        assert cache_info["metrics"]["misses"] == 10
        
        # Check cache type counts
        cache_types = cache_info["cache_types"]
        assert cache_types["dashboard"] == 1
        assert cache_types["treatment_distribution"] == 1
        assert cache_types["engagement_chart"] == 1
    
    def test_build_cache_key_short_params(self, cache_service):
        """Test cache key building with short parameters."""
        key_params = {"doctor_id": "123", "period": "7d"}
        cache_key = cache_service._build_cache_key("dashboard", key_params)
        
        expected_key = "analytics_cache:dashboard:doctor_id=123&period=7d"
        assert cache_key == expected_key
    
    def test_build_cache_key_long_params(self, cache_service):
        """Test cache key building with long parameters (should use hash)."""
        # Create long parameter string
        key_params = {f"param_{i}": f"very_long_value_{i}" * 10 for i in range(10)}
        cache_key = cache_service._build_cache_key("dashboard", key_params)
        
        # Should use hash for long parameter strings
        assert cache_key.startswith("analytics_cache:dashboard:")
        assert len(cache_key.split(":")[-1]) == 32  # MD5 hash length
    
    def test_error_handling_redis_failure(self, cache_service, mock_redis):
        """Test error handling when Redis operations fail."""
        # Setup Redis to raise exception
        mock_redis.get.side_effect = Exception("Redis connection failed")
        
        # Cache operations should not raise exceptions
        key_params = {"doctor_id": "123"}
        result = cache_service.get("dashboard", key_params)
        
        assert result is None  # Should return None on error
        
        # Set operation should also handle errors gracefully
        mock_redis.setex.side_effect = Exception("Redis connection failed")
        result = cache_service.set("dashboard", key_params, {"data": "test"})
        
        assert result is False  # Should return False on error


class TestCacheConfig:
    """Test cases for CacheConfig dataclass."""
    
    def test_cache_config_defaults(self):
        """Test CacheConfig default values."""
        config = CacheConfig(ttl_seconds=300)
        
        assert config.ttl_seconds == 300
        assert config.warm_on_miss is True
        assert config.invalidate_on_update is True
        assert config.compress is False
    
    def test_cache_config_custom_values(self):
        """Test CacheConfig with custom values."""
        config = CacheConfig(
            ttl_seconds=600,
            warm_on_miss=False,
            invalidate_on_update=False,
            compress=True
        )
        
        assert config.ttl_seconds == 600
        assert config.warm_on_miss is False
        assert config.invalidate_on_update is False
        assert config.compress is True


class TestCacheMetrics:
    """Test cases for CacheMetrics dataclass."""
    
    def test_cache_metrics_defaults(self):
        """Test CacheMetrics default values."""
        metrics = CacheMetrics()
        
        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.invalidations == 0
        assert metrics.warming_operations == 0
        assert metrics.hit_rate == 0.0
    
    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        metrics = CacheMetrics(hits=80, misses=20)
        assert metrics.hit_rate == 80.0
        
        metrics = CacheMetrics(hits=0, misses=0)
        assert metrics.hit_rate == 0.0
        
        metrics = CacheMetrics(hits=100, misses=0)
        assert metrics.hit_rate == 100.0


class TestCacheDecorator:
    """Test cases for cache_analytics_data decorator."""
    
    def test_cache_decorator_with_default_params(self):
        """Test cache decorator with default parameters."""
        with patch('app.services.analytics_cache.AnalyticsCacheService') as MockCacheService:
            mock_cache = Mock()
            MockCacheService.return_value = mock_cache
            mock_cache.get_or_set.return_value = {"result": "cached_data"}
            
            @cache_analytics_data("test_cache")
            def test_function(arg1, arg2, kwarg1=None):
                return {"result": "fresh_data"}
            
            result = test_function("value1", "value2", kwarg1="kwarg_value")
            
            assert result == {"result": "cached_data"}
            
            # Verify cache service was used
            mock_cache.get_or_set.assert_called_once()
            call_args = mock_cache.get_or_set.call_args
            assert call_args[0][0] == "test_cache"  # cache_type
    
    def test_cache_decorator_with_custom_params(self):
        """Test cache decorator with custom key parameters."""
        with patch('app.services.analytics_cache.AnalyticsCacheService') as MockCacheService:
            mock_cache = Mock()
            MockCacheService.return_value = mock_cache
            mock_cache.get_or_set.return_value = {"result": "cached_data"}
            
            custom_params = {"custom_key": "custom_value"}
            
            @cache_analytics_data("test_cache", custom_params)
            def test_function():
                return {"result": "fresh_data"}
            
            result = test_function()
            
            assert result == {"result": "cached_data"}
            
            # Verify custom parameters were used
            call_args = mock_cache.get_or_set.call_args
            assert call_args[0][1] == custom_params  # key_params


class TestGlobalCacheService:
    """Test cases for global cache service functions."""
    
    def test_get_analytics_cache_singleton(self):
        """Test that get_analytics_cache returns singleton instance."""
        with patch('app.services.analytics_cache.AnalyticsCacheService') as MockCacheService:
            mock_instance = Mock()
            MockCacheService.return_value = mock_instance
            
            # Reset global instance
            import app.services.analytics_cache
            app.services.analytics_cache._cache_service = None
            
            # First call should create instance
            cache1 = get_analytics_cache()
            
            # Second call should return same instance
            cache2 = get_analytics_cache()
            
            assert cache1 is cache2
            
            # Constructor should only be called once
            MockCacheService.assert_called_once()


@pytest.mark.integration
class TestAnalyticsCacheIntegration:
    """Integration tests for AnalyticsCacheService."""
    
    def test_cache_workflow_integration(self):
        """Test complete cache workflow integration."""
        with patch('app.services.analytics_cache.get_sync_redis') as mock_redis_func:
            redis_client = Mock()
            mock_redis_func.return_value = redis_client
            
            # Setup Redis responses for complete workflow
            redis_client.get.side_effect = [None, json.dumps({"cached": "data"})]  # Miss then hit
            redis_client.setex.return_value = True
            redis_client.keys.return_value = ["analytics_cache:test:key1"]
            redis_client.delete.return_value = 1
            
            cache_service = AnalyticsCacheService()
            
            # Test cache miss -> set -> hit workflow
            key_params = {"test": "params"}
            
            # 1. Cache miss
            result1 = cache_service.get("test_type", key_params)
            assert result1 is None
            assert cache_service._metrics.misses == 1
            
            # 2. Set data
            test_data = {"test": "data"}
            success = cache_service.set("test_type", key_params, test_data)
            assert success is True
            
            # 3. Cache hit
            result2 = cache_service.get("test_type", key_params)
            assert result2 == {"cached": "data"}
            assert cache_service._metrics.hits == 1
            
            # 4. Invalidate
            deleted = cache_service.invalidate("test_type")
            assert deleted == 1
            assert cache_service._metrics.invalidations == 1
    
    def test_metrics_persistence(self):
        """Test metrics persistence to Redis."""
        with patch('app.services.analytics_cache.get_sync_redis') as mock_redis_func:
            redis_client = Mock()
            mock_redis_func.return_value = redis_client
            
            # Setup Redis responses for metrics persistence
            redis_client.get.return_value = json.dumps({
                "hits": 10,
                "misses": 5,
                "invalidations": 2,
                "warming_operations": 1
            })
            redis_client.setex.return_value = True
            
            cache_service = AnalyticsCacheService()
            
            # Verify metrics were loaded
            assert cache_service._metrics.hits == 10
            assert cache_service._metrics.misses == 5
            
            # Simulate some activity
            cache_service._metrics.hits += 1
            cache_service._save_metrics()
            
            # Verify metrics were saved
            redis_client.setex.assert_called()
            save_call = [call for call in redis_client.setex.call_args_list 
                        if "analytics_cache:metrics" in str(call)]
            assert len(save_call) > 0