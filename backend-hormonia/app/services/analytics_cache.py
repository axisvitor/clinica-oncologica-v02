"""
Analytics Caching Service.
Provides Redis-based caching for analytics dashboard data with intelligent invalidation.
"""
import logging
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from functools import wraps
from dataclasses import dataclass, asdict

from app.core.redis_unified import get_sync_redis
from app.core.monitoring_logging import monitoring_logger


logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """Cache configuration for different data types."""
    ttl_seconds: int
    warm_on_miss: bool = True
    invalidate_on_update: bool = True
    compress: bool = False


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    hits: int = 0
    misses: int = 0
    invalidations: int = 0
    warming_operations: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate percentage."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0


class AnalyticsCacheService:
    """
    Redis-based caching service for analytics data.
    
    Features:
    - Configurable TTL per data type
    - Intelligent cache invalidation
    - Cache warming for frequently accessed data
    - Performance metrics tracking
    - Compression for large datasets
    """
    
    CACHE_KEY_PREFIX = "analytics_cache"
    METRICS_KEY = "analytics_cache:metrics"
    
    # Cache configurations for different data types
    CACHE_CONFIGS = {
        "dashboard": CacheConfig(ttl_seconds=300, warm_on_miss=True),  # 5 minutes
        "treatment_distribution": CacheConfig(ttl_seconds=300, warm_on_miss=True),  # 5 minutes
        "engagement_chart": CacheConfig(ttl_seconds=180, warm_on_miss=True),  # 3 minutes
        "patient_analytics": CacheConfig(ttl_seconds=600, warm_on_miss=False),  # 10 minutes
        "system_analytics": CacheConfig(ttl_seconds=120, warm_on_miss=True),  # 2 minutes
        "query_performance": CacheConfig(ttl_seconds=60, warm_on_miss=False),  # 1 minute
        "patterns": CacheConfig(ttl_seconds=900, warm_on_miss=False),  # 15 minutes
    }
    
    def __init__(self):
        """Initialize analytics cache service."""
        self.redis_client = get_sync_redis()
        self._metrics = CacheMetrics()
        self._load_metrics()
        
        logger.info("Analytics Cache Service initialized")
    
    def get(self, cache_type: str, key_params: Dict[str, Any]) -> Optional[Any]:
        """
        Get data from cache.
        
        Args:
            cache_type: Type of cached data (dashboard, treatment_distribution, etc.)
            key_params: Parameters to build cache key
            
        Returns:
            Cached data or None if not found
        """
        try:
            cache_key = self._build_cache_key(cache_type, key_params)
            
            # Get from Redis
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                self._metrics.hits += 1
                self._save_metrics()
                
                # Deserialize data
                data = json.loads(cached_data)
                
                monitoring_logger.log_system_event(
                    event_type="cache_hit",
                    message=f"Cache hit for {cache_type}",
                    level="DEBUG",
                    context={
                        "cache_type": cache_type,
                        "cache_key": cache_key,
                        "hit_rate": self._metrics.hit_rate
                    }
                )
                
                logger.debug(f"Cache hit for {cache_type}: {cache_key}")
                return data
            else:
                self._metrics.misses += 1
                self._save_metrics()
                
                logger.debug(f"Cache miss for {cache_type}: {cache_key}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            return None
    
    def set(self, cache_type: str, key_params: Dict[str, Any], data: Any, ttl: Optional[int] = None) -> bool:
        """
        Set data in cache.
        
        Args:
            cache_type: Type of cached data
            key_params: Parameters to build cache key
            data: Data to cache
            ttl: Optional TTL override (seconds). If not provided, uses default for cache_type
            
        Returns:
            True if successful, False otherwise
        """
        try:
            config = self.CACHE_CONFIGS.get(cache_type, CacheConfig(ttl_seconds=300))
            cache_key = self._build_cache_key(cache_type, key_params)
            
            # Use provided TTL or default from config
            ttl_seconds = ttl if ttl is not None else config.ttl_seconds
            
            # Serialize data
            serialized_data = json.dumps(data, default=str)
            
            # Set in Redis with TTL
            success = self.redis_client.setex(
                cache_key,
                ttl_seconds,
                serialized_data
            )
            
            if success:
                monitoring_logger.log_system_event(
                    event_type="cache_set",
                    message=f"Data cached for {cache_type}",
                    level="DEBUG",
                    context={
                        "cache_type": cache_type,
                        "cache_key": cache_key,
                        "ttl_seconds": ttl_seconds,
                        "data_size_bytes": len(serialized_data)
                    }
                )
                
                logger.debug(f"Data cached for {cache_type}: {cache_key}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            return False
    
    def invalidate(self, cache_type: str, key_params: Optional[Dict[str, Any]] = None) -> int:
        """
        Invalidate cache entries.
        
        Args:
            cache_type: Type of cached data to invalidate
            key_params: Specific key parameters (if None, invalidates all of this type)
            
        Returns:
            Number of keys invalidated
        """
        try:
            if key_params:
                # Invalidate specific key
                cache_key = self._build_cache_key(cache_type, key_params)
                deleted = self.redis_client.delete(cache_key)
            else:
                # Invalidate all keys of this type
                pattern = f"{self.CACHE_KEY_PREFIX}:{cache_type}:*"
                keys = self.redis_client.keys(pattern)
                deleted = self.redis_client.delete(*keys) if keys else 0
            
            if deleted > 0:
                self._metrics.invalidations += deleted
                self._save_metrics()
                
                monitoring_logger.log_system_event(
                    event_type="cache_invalidation",
                    message=f"Cache invalidated for {cache_type}",
                    level="INFO",
                    context={
                        "cache_type": cache_type,
                        "keys_deleted": deleted,
                        "specific_key": key_params is not None
                    }
                )
                
                logger.info(f"Invalidated {deleted} cache entries for {cache_type}")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return 0
    
    def warm_cache(self, cache_type: str, key_params: Dict[str, Any], 
                   data_generator: Callable[[], Any]) -> bool:
        """
        Warm cache with fresh data.
        
        Args:
            cache_type: Type of cached data
            key_params: Parameters to build cache key
            data_generator: Function to generate fresh data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate fresh data
            fresh_data = data_generator()
            
            # Cache the fresh data
            success = self.set(cache_type, key_params, fresh_data)
            
            if success:
                self._metrics.warming_operations += 1
                self._save_metrics()
                
                monitoring_logger.log_system_event(
                    event_type="cache_warming",
                    message=f"Cache warmed for {cache_type}",
                    level="INFO",
                    context={
                        "cache_type": cache_type,
                        "warming_operations": self._metrics.warming_operations
                    }
                )
                
                logger.info(f"Cache warmed for {cache_type}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error warming cache: {e}")
            return False
    
    def get_or_set(self, cache_type: str, key_params: Dict[str, Any], 
                   data_generator: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        """
        Get data from cache or generate and cache if not found.
        
        Args:
            cache_type: Type of cached data
            key_params: Parameters to build cache key
            data_generator: Function to generate fresh data if cache miss
            ttl: Optional TTL override (seconds). If not provided, uses default for cache_type
            
        Returns:
            Cached or freshly generated data
        """
        # Try to get from cache first
        cached_data = self.get(cache_type, key_params)
        
        if cached_data is not None:
            return cached_data
        
        # Cache miss - generate fresh data
        try:
            fresh_data = data_generator()
            
            # Cache the fresh data with optional TTL override
            if ttl is not None:
                self.set(cache_type, key_params, fresh_data, ttl=ttl)
            else:
                self.set(cache_type, key_params, fresh_data)
            
            return fresh_data
            
        except Exception as e:
            logger.error(f"Error generating fresh data for cache: {e}")
            raise
    
    def get_metrics(self) -> CacheMetrics:
        """Get cache performance metrics."""
        return self._metrics
    
    def clear_all(self) -> int:
        """
        Clear all analytics cache entries.
        
        Returns:
            Number of keys deleted
        """
        try:
            pattern = f"{self.CACHE_KEY_PREFIX}:*"
            keys = self.redis_client.keys(pattern)
            deleted = self.redis_client.delete(*keys) if keys else 0
            
            if deleted > 0:
                monitoring_logger.log_system_event(
                    event_type="cache_clear_all",
                    message=f"All analytics cache cleared",
                    level="WARNING",
                    context={"keys_deleted": deleted}
                )
                
                logger.warning(f"Cleared all analytics cache: {deleted} keys")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Error clearing all cache: {e}")
            return 0
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get comprehensive cache information.
        
        Returns:
            Dictionary with cache statistics and configuration
        """
        try:
            # Get all cache keys
            pattern = f"{self.CACHE_KEY_PREFIX}:*"
            all_keys = self.redis_client.keys(pattern)
            
            # Analyze cache types
            type_counts = {}
            total_size = 0
            
            for key in all_keys:
                try:
                    # Extract cache type from key
                    key_parts = key.decode() if isinstance(key, bytes) else key
                    cache_type = key_parts.split(':')[1] if ':' in key_parts else 'unknown'
                    
                    type_counts[cache_type] = type_counts.get(cache_type, 0) + 1
                    
                    # Get key size (approximate)
                    key_size = len(self.redis_client.get(key) or b'')
                    total_size += key_size
                    
                except Exception:
                    continue
            
            return {
                "metrics": asdict(self._metrics),
                "total_keys": len(all_keys),
                "total_size_bytes": total_size,
                "cache_types": type_counts,
                "configurations": {k: asdict(v) for k, v in self.CACHE_CONFIGS.items()},
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting cache info: {e}")
            return {}
    
    def _build_cache_key(self, cache_type: str, key_params: Dict[str, Any]) -> str:
        """Build cache key from type and parameters."""
        # Sort parameters for consistent key generation
        sorted_params = sorted(key_params.items())
        params_str = "&".join(f"{k}={v}" for k, v in sorted_params)
        
        # Create hash for long parameter strings
        if len(params_str) > 100:
            params_hash = hashlib.md5(params_str.encode()).hexdigest()
            return f"{self.CACHE_KEY_PREFIX}:{cache_type}:{params_hash}"
        else:
            return f"{self.CACHE_KEY_PREFIX}:{cache_type}:{params_str}"
    
    def _load_metrics(self):
        """Load metrics from Redis."""
        try:
            metrics_data = self.redis_client.get(self.METRICS_KEY)
            if metrics_data:
                data = json.loads(metrics_data)
                self._metrics = CacheMetrics(**data)
        except Exception as e:
            logger.warning(f"Could not load cache metrics: {e}")
    
    def _save_metrics(self):
        """Save metrics to Redis."""
        try:
            metrics_data = json.dumps(asdict(self._metrics))
            self.redis_client.setex(self.METRICS_KEY, 86400, metrics_data)  # 24 hours
        except Exception as e:
            logger.warning(f"Could not save cache metrics: {e}")


def cache_analytics_data(cache_type: str, key_params: Optional[Dict[str, Any]] = None):
    """
    Decorator to cache analytics data.
    
    Args:
        cache_type: Type of cached data
        key_params: Optional key parameters (if None, uses function args)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_service = AnalyticsCacheService()
            
            # Build key parameters
            if key_params:
                cache_key_params = key_params
            else:
                # Use function arguments as key parameters
                cache_key_params = {
                    "func": func.__name__,
                    "args": str(args)[:100],  # Limit length
                    "kwargs": str(sorted(kwargs.items()))[:100]
                }
            
            # Try cache first
            def data_generator():
                return func(*args, **kwargs)
            
            return cache_service.get_or_set(cache_type, cache_key_params, data_generator)
        
        return wrapper
    return decorator


# Global cache service instance
_cache_service = None


def get_analytics_cache() -> AnalyticsCacheService:
    """Get global analytics cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = AnalyticsCacheService()
    return _cache_service