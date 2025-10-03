"""
Unified Cache Utility Service for Clinica Oncologica V01

This module provides a comprehensive caching solution that merges functionality
from app/utils/cache.py and app/utils/caching.py into a single, unified interface.

Features:
- Sync and async cache operations
- Consistent cache key prefix strategy
- TTL management with configurable defaults
- Cache invalidation patterns (by prefix, pattern matching)
- Cache statistics and monitoring
- Decorators for easy function caching
- Backward compatibility with existing usage
- Comprehensive error handling with fallbacks
- Local cache fallback when Redis is unavailable
- Multiple serialization methods (JSON, pickle)
- Cache compression support
- Cache warming and preloading
"""

import json
import pickle
import hashlib
import logging
import functools
import asyncio
import inspect
import time
from typing import Any, Callable, Optional, Union, List, Dict, Pattern
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from datetime import timedelta, datetime
from uuid import UUID
from decimal import Decimal
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager
import re
from concurrent.futures import ThreadPoolExecutor

from app.core.redis_unified import get_sync_redis, get_async_redis
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SerializationMethod(str, Enum):
    """Serialization methods for cache data."""
    JSON = "json"
    PICKLE = "pickle"


class CacheOperation(str, Enum):
    """Cache operation types for monitoring."""
    GET = "get"
    SET = "set"
    DELETE = "delete"
    INVALIDATE = "invalidate"
    CLEAR = "clear"


@dataclass
class CacheConfig:
    """Configuration for different cache types."""
    ttl: int  # Time to live in seconds
    key_prefix: str
    serialize_method: SerializationMethod = SerializationMethod.JSON
    compress: bool = False
    namespace: str = "cache"
    enable_local_fallback: bool = True
    max_key_length: int = 200


@dataclass
class CacheStats:
    """Cache statistics tracking."""
    hits: int = 0
    misses: int = 0
    errors: int = 0
    sets: int = 0
    deletes: int = 0
    invalidations: int = 0
    last_reset: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def total_requests(self) -> int:
        return self.hits + self.misses
    
    @property
    def hit_rate(self) -> float:
        return (self.hits / self.total_requests * 100) if self.total_requests > 0 else 0.0
    
    def reset(self):
        """Reset all statistics."""
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.sets = 0
        self.deletes = 0
        self.invalidations = 0
        self.last_reset = datetime.utcnow()


# Default cache configurations for different data types
DEFAULT_CACHE_CONFIGS = {
    "patient_list": CacheConfig(ttl=300, key_prefix="patients:list"),  # 5 minutes
    "patient_detail": CacheConfig(ttl=600, key_prefix="patients:detail"),  # 10 minutes
    "user_profile": CacheConfig(ttl=1800, key_prefix="users:profile"),  # 30 minutes
    "quiz_templates": CacheConfig(ttl=3600, key_prefix="quiz:templates"),  # 1 hour
    "flow_templates": CacheConfig(ttl=3600, key_prefix="flow:templates"),  # 1 hour
    "analytics_dashboard": CacheConfig(ttl=300, key_prefix="analytics:dashboard"),  # 5 minutes
    "system_metrics": CacheConfig(ttl=60, key_prefix="system:metrics"),  # 1 minute
    "message_stats": CacheConfig(ttl=300, key_prefix="messages:stats"),  # 5 minutes
    "report_data": CacheConfig(ttl=1800, key_prefix="reports:data"),  # 30 minutes
    "ai_responses": CacheConfig(ttl=7200, key_prefix="ai:responses"),  # 2 hours
    "template_cache": CacheConfig(ttl=3600, key_prefix="templates:cache"),  # 1 hour
    "session_data": CacheConfig(ttl=1800, key_prefix="sessions:data"),  # 30 minutes
}


class UnifiedCacheManager:
    """
    Unified cache manager that provides both sync and async operations
    with Redis backend and local fallback support.
    """
    
    def __init__(
        self,
        redis_client: Optional[Union[Redis, AsyncRedis]] = None,
        enable_stats: bool = True,
        enable_local_fallback: bool = True
    ):
        """
        Initialize unified cache manager.
        
        Args:
            redis_client: Optional Redis client instance
            enable_stats: Whether to track cache statistics
            enable_local_fallback: Whether to use local cache as fallback
        """
        self.redis_client = redis_client
        self.enable_stats = enable_stats
        self.enable_local_fallback = enable_local_fallback
        self._local_cache: Dict[str, Dict[str, Any]] = {}
        self._stats = CacheStats() if enable_stats else None
        self._cache_configs = DEFAULT_CACHE_CONFIGS.copy()
        self._executor = ThreadPoolExecutor(max_workers=4)
        
    def register_cache_config(self, cache_type: str, config: CacheConfig):
        """Register a new cache configuration."""
        self._cache_configs[cache_type] = config
        
    def get_cache_config(self, cache_type: str) -> Optional[CacheConfig]:
        """Get cache configuration for a given type."""
        return self._cache_configs.get(cache_type)
    
    def _json_serializer(self, obj: Any) -> Any:
        """JSON serializer for complex objects."""
        if isinstance(obj, (datetime, UUID)):
            return str(obj)
        elif isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, '__dict__'):
            # For SQLAlchemy models or complex objects
            return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
        else:
            return str(obj)
    
    def _serialize_for_cache(self, obj: Any, method: SerializationMethod) -> Union[str, bytes]:
        """Serialize complex objects for caching."""
        try:
            if method == SerializationMethod.JSON:
                if isinstance(obj, str):
                    return obj
                elif hasattr(obj, '__dict__'):
                    # For SQLAlchemy models or complex objects
                    data = {}
                    for key, value in obj.__dict__.items():
                        if not key.startswith('_') and not callable(value):
                            data[key] = value
                    return json.dumps(data, default=self._json_serializer)
                else:
                    return json.dumps(obj, default=self._json_serializer)
            elif method == SerializationMethod.PICKLE:
                return pickle.dumps(obj)
            else:
                return str(obj)
        except (TypeError, ValueError) as e:
            logger.warning(f"Serialization failed: {e}")
            return str(obj)
    
    def _deserialize_from_cache(self, data: Union[str, bytes], method: SerializationMethod) -> Any:
        """Deserialize data from cache with fallback."""
        try:
            if method == SerializationMethod.JSON:
                if isinstance(data, bytes):
                    data = data.decode()
                return json.loads(data)
            elif method == SerializationMethod.PICKLE:
                if isinstance(data, str):
                    data = data.encode()
                return pickle.loads(data)
            else:
                return data
        except (json.JSONDecodeError, TypeError, pickle.UnpicklingError):
            return data
    
    def _generate_cache_key(
        self,
        config: CacheConfig,
        key_parts: Optional[List[str]] = None,
        *args,
        **kwargs
    ) -> str:
        """
        Generate a unique cache key from configuration and arguments.
        
        Args:
            config: Cache configuration
            key_parts: Optional list of key parts
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Unique cache key string
        """
        # Start with namespace and prefix
        key_components = [config.namespace, config.key_prefix]
        
        # Add provided key parts
        if key_parts:
            key_components.extend([str(part) for part in key_parts])
        
        # Add function arguments
        if args:
            key_components.extend([str(arg) for arg in args])
        
        if kwargs:
            # Sort kwargs for consistent key generation
            sorted_kwargs = sorted(kwargs.items())
            key_components.extend([f"{k}={v}" for k, v in sorted_kwargs])
        
        # Join parts and hash if too long
        cache_key = ":".join(key_components)
        
        # Hash long keys to avoid Redis key length limits
        if len(cache_key) > config.max_key_length:
            hash_suffix = hashlib.md5(cache_key.encode()).hexdigest()
            cache_key = f"{config.namespace}:{config.key_prefix}:hash:{hash_suffix}"
        
        return cache_key
    
    def _update_stats(self, operation: CacheOperation, success: bool = True):
        """Update cache statistics."""
        if not self._stats:
            return
            
        if operation == CacheOperation.GET:
            if success:
                self._stats.hits += 1
            else:
                self._stats.misses += 1
        elif operation == CacheOperation.SET:
            if success:
                self._stats.sets += 1
            else:
                self._stats.errors += 1
        elif operation == CacheOperation.DELETE:
            if success:
                self._stats.deletes += 1
            else:
                self._stats.errors += 1
        elif operation == CacheOperation.INVALIDATE:
            if success:
                self._stats.invalidations += 1
            else:
                self._stats.errors += 1
    
    def _get_sync_redis_client(self):
        """Get synchronous Redis client."""
        if self.redis_client:
            return self.redis_client
        try:
            return get_sync_redis()
        except Exception as e:
            logger.warning(f"Failed to get sync Redis client: {e}")
            return None

    async def _get_async_redis_client(self):
        """Get asynchronous Redis client."""
        try:
            return await get_async_redis()
        except Exception as e:
            logger.warning(f"Failed to get async Redis client: {e}")
            return None
    
    def _get_from_local_cache(self, cache_key: str) -> Optional[Any]:
        """Get value from local cache with expiration check."""
        if not self.enable_local_fallback or cache_key not in self._local_cache:
            return None
            
        cache_entry = self._local_cache[cache_key]
        if datetime.utcnow() < cache_entry["expires_at"]:
            return cache_entry["data"]
        else:
            # Expired, remove from local cache
            del self._local_cache[cache_key]
            return None
    
    def _set_in_local_cache(self, cache_key: str, value: Any, ttl: int):
        """Set value in local cache with expiration."""
        if not self.enable_local_fallback:
            return
            
        self._local_cache[cache_key] = {
            "data": value,
            "expires_at": datetime.utcnow() + timedelta(seconds=ttl)
        }
    
    def _remove_from_local_cache(self, cache_key: str):
        """Remove value from local cache."""
        self._local_cache.pop(cache_key, None)
    
    def get(
        self,
        cache_type: str,
        key_parts: Optional[List[str]] = None,
        default: Any = None,
        *args,
        **kwargs
    ) -> Any:
        """
        Get value from cache (synchronous).
        
        Args:
            cache_type: Type of cache (must be in registered configs)
            key_parts: List of key components
            default: Default value if not found
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation
        
        Returns:
            Cached value or default
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            logger.warning(f"Unknown cache type: {cache_type}")
            self._update_stats(CacheOperation.GET, False)
            return default
        
        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)
        
        try:
            # Try Redis first
            redis_client = self._get_sync_redis_client()
            if redis_client:
                try:
                    cached_data = redis_client.get(cache_key)
                    if cached_data is not None:
                        result = self._deserialize_from_cache(cached_data, config.serialize_method)
                        self._update_stats(CacheOperation.GET, True)
                        logger.debug(f"Cache HIT (Redis) for key: {cache_key}")
                        return result
                except Exception as e:
                    logger.warning(f"Redis GET failed for {cache_key}: {e}")
            
            # Fallback to local cache
            local_result = self._get_from_local_cache(cache_key)
            if local_result is not None:
                self._update_stats(CacheOperation.GET, True)
                logger.debug(f"Cache HIT (Local) for key: {cache_key}")
                return local_result
            
            # Cache miss
            self._update_stats(CacheOperation.GET, False)
            logger.debug(f"Cache MISS for key: {cache_key}")
            return default
            
        except Exception as e:
            logger.error(f"Cache GET error for key {cache_key}: {e}")
            self._update_stats(CacheOperation.GET, False)
            return default
    
    async def get_async(
        self,
        cache_type: str,
        key_parts: Optional[List[str]] = None,
        default: Any = None,
        *args,
        **kwargs
    ) -> Any:
        """
        Get value from cache (asynchronous).
        
        Args:
            cache_type: Type of cache (must be in registered configs)
            key_parts: List of key components
            default: Default value if not found
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation
        
        Returns:
            Cached value or default
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            logger.warning(f"Unknown cache type: {cache_type}")
            self._update_stats(CacheOperation.GET, False)
            return default
        
        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)
        
        try:
            # Try Redis first
            redis_client = await self._get_async_redis_client()
            if redis_client:
                try:
                    cached_data = await redis_client.get(cache_key)
                    if cached_data is not None:
                        result = self._deserialize_from_cache(cached_data, config.serialize_method)
                        self._update_stats(CacheOperation.GET, True)
                        logger.debug(f"Cache HIT (Redis Async) for key: {cache_key}")
                        return result
                except Exception as e:
                    logger.warning(f"Async Redis GET failed for {cache_key}: {e}")
            
            # Fallback to local cache
            local_result = self._get_from_local_cache(cache_key)
            if local_result is not None:
                self._update_stats(CacheOperation.GET, True)
                logger.debug(f"Cache HIT (Local Async) for key: {cache_key}")
                return local_result
            
            # Cache miss
            self._update_stats(CacheOperation.GET, False)
            logger.debug(f"Cache MISS (Async) for key: {cache_key}")
            return default
            
        except Exception as e:
            logger.error(f"Async cache GET error for key {cache_key}: {e}")
            self._update_stats(CacheOperation.GET, False)
            return default
    
    def set(
        self,
        cache_type: str,
        value: Any,
        key_parts: Optional[List[str]] = None,
        ttl_override: Optional[Union[int, timedelta]] = None,
        *args,
        **kwargs
    ) -> bool:
        """
        Set value in cache (synchronous).
        
        Args:
            cache_type: Type of cache (must be in registered configs)
            value: Value to cache
            key_parts: List of key components
            ttl_override: Override default TTL
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation
        
        Returns:
            True if successful, False otherwise
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            logger.warning(f"Unknown cache type: {cache_type}")
            self._update_stats(CacheOperation.SET, False)
            return False
        
        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)
        
        # Calculate TTL
        if ttl_override is not None:
            ttl = ttl_override.total_seconds() if isinstance(ttl_override, timedelta) else ttl_override
        else:
            ttl = config.ttl
        
        try:
            # Serialize the data
            serialized_data = self._serialize_for_cache(value, config.serialize_method)
            
            # Try Redis first
            redis_client = self._get_sync_redis_client()
            if redis_client:
                try:
                    success = redis_client.set(cache_key, serialized_data, ex=int(ttl))
                    if success:
                        logger.debug(f"Cached in Redis for key: {cache_key} (TTL: {ttl}s)")
                except Exception as e:
                    logger.warning(f"Redis SET failed for {cache_key}: {e}")
            
            # Also set in local cache as fallback
            self._set_in_local_cache(cache_key, value, int(ttl))
            
            self._update_stats(CacheOperation.SET, True)
            return True
            
        except Exception as e:
            logger.error(f"Cache SET error for key {cache_key}: {e}")
            self._update_stats(CacheOperation.SET, False)
            return False
    
    async def set_async(
        self,
        cache_type: str,
        value: Any,
        key_parts: Optional[List[str]] = None,
        ttl_override: Optional[Union[int, timedelta]] = None,
        *args,
        **kwargs
    ) -> bool:
        """
        Set value in cache (asynchronous).
        
        Args:
            cache_type: Type of cache (must be in registered configs)
            value: Value to cache
            key_parts: List of key components
            ttl_override: Override default TTL
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation
        
        Returns:
            True if successful, False otherwise
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            logger.warning(f"Unknown cache type: {cache_type}")
            self._update_stats(CacheOperation.SET, False)
            return False
        
        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)
        
        # Calculate TTL
        if ttl_override is not None:
            ttl = ttl_override.total_seconds() if isinstance(ttl_override, timedelta) else ttl_override
        else:
            ttl = config.ttl
        
        try:
            # Serialize the data
            serialized_data = self._serialize_for_cache(value, config.serialize_method)
            
            # Try Redis first
            redis_client = await self._get_async_redis_client()
            if redis_client:
                try:
                    success = await redis_client.set(cache_key, serialized_data, ex=int(ttl))
                    if success:
                        logger.debug(f"Cached in Redis (Async) for key: {cache_key} (TTL: {ttl}s)")
                except Exception as e:
                    logger.warning(f"Async Redis SET failed for {cache_key}: {e}")
            
            # Also set in local cache as fallback
            self._set_in_local_cache(cache_key, value, int(ttl))
            
            self._update_stats(CacheOperation.SET, True)
            return True
            
        except Exception as e:
            logger.error(f"Async cache SET error for key {cache_key}: {e}")
            self._update_stats(CacheOperation.SET, False)
            return False
    
    def delete(
        self,
        cache_type: str,
        key_parts: Optional[List[str]] = None,
        *args,
        **kwargs
    ) -> bool:
        """
        Delete value from cache (synchronous).
        
        Args:
            cache_type: Type of cache
            key_parts: List of key components
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation
        
        Returns:
            True if deleted, False otherwise
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            self._update_stats(CacheOperation.DELETE, False)
            return False
        
        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)
        
        try:
            # Delete from Redis
            redis_client = self._get_sync_redis_client()
            if redis_client:
                try:
                    redis_client.delete(cache_key)
                    logger.debug(f"Deleted from Redis: {cache_key}")
                except Exception as e:
                    logger.warning(f"Redis DELETE failed for {cache_key}: {e}")
            
            # Remove from local cache
            self._remove_from_local_cache(cache_key)
            
            self._update_stats(CacheOperation.DELETE, True)
            return True
            
        except Exception as e:
            logger.error(f"Cache DELETE error for key {cache_key}: {e}")
            self._update_stats(CacheOperation.DELETE, False)
            return False
    
    async def delete_async(
        self,
        cache_type: str,
        key_parts: Optional[List[str]] = None,
        *args,
        **kwargs
    ) -> bool:
        """
        Delete value from cache (asynchronous).
        
        Args:
            cache_type: Type of cache
            key_parts: List of key components
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation
        
        Returns:
            True if deleted, False otherwise
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            self._update_stats(CacheOperation.DELETE, False)
            return False
        
        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)
        
        try:
            # Delete from Redis
            redis_client = await self._get_async_redis_client()
            if redis_client:
                try:
                    await redis_client.delete(cache_key)
                    logger.debug(f"Deleted from Redis (Async): {cache_key}")
                except Exception as e:
                    logger.warning(f"Async Redis DELETE failed for {cache_key}: {e}")
            
            # Remove from local cache
            self._remove_from_local_cache(cache_key)
            
            self._update_stats(CacheOperation.DELETE, True)
            return True
            
        except Exception as e:
            logger.error(f"Async cache DELETE error for key {cache_key}: {e}")
            self._update_stats(CacheOperation.DELETE, False)
            return False
    
    def invalidate_pattern(self, pattern: str, namespace: Optional[str] = None) -> int:
        """
        Invalidate all cache keys matching a pattern (synchronous).
        
        Args:
            pattern: Key pattern (supports wildcards like "user:*")
            namespace: Optional namespace filter
        
        Returns:
            Number of keys deleted
        """
        if namespace:
            full_pattern = f"{namespace}:{pattern}"
        else:
            full_pattern = pattern
        
        deleted_count = 0
        
        try:
            # Delete from Redis
            redis_client = self._get_sync_redis_client()
            if redis_client:
                try:
                    keys = redis_client.keys(full_pattern)
                    if keys:
                        deleted_count += redis_client.delete(*keys)
                    logger.debug(f"Deleted {deleted_count} keys from Redis matching: {full_pattern}")
                except Exception as e:
                    logger.warning(f"Redis pattern invalidation failed for {full_pattern}: {e}")
            
            # Delete from local cache
            pattern_regex = re.compile(full_pattern.replace('*', '.*'))
            keys_to_remove = [key for key in self._local_cache.keys() if pattern_regex.match(key)]
            for key in keys_to_remove:
                del self._local_cache[key]
                deleted_count += 1
            
            self._update_stats(CacheOperation.INVALIDATE, True)
            logger.info(f"Invalidated {deleted_count} cache keys matching: {full_pattern}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Cache invalidation error for pattern {full_pattern}: {e}")
            self._update_stats(CacheOperation.INVALIDATE, False)
            return 0
    
    async def invalidate_pattern_async(self, pattern: str, namespace: Optional[str] = None) -> int:
        """
        Invalidate all cache keys matching a pattern (asynchronous).
        
        Args:
            pattern: Key pattern (supports wildcards like "user:*")
            namespace: Optional namespace filter
        
        Returns:
            Number of keys deleted
        """
        if namespace:
            full_pattern = f"{namespace}:{pattern}"
        else:
            full_pattern = pattern
        
        deleted_count = 0
        
        try:
            # Delete from Redis
            redis_client = await self._get_async_redis_client()
            if redis_client:
                try:
                    keys = await redis_client.keys(full_pattern)
                    if keys:
                        deleted_count += await redis_client.delete(*keys)
                    logger.debug(f"Deleted {deleted_count} keys from Redis (Async) matching: {full_pattern}")
                except Exception as e:
                    logger.warning(f"Async Redis pattern invalidation failed for {full_pattern}: {e}")
            
            # Delete from local cache
            pattern_regex = re.compile(full_pattern.replace('*', '.*'))
            keys_to_remove = [key for key in self._local_cache.keys() if pattern_regex.match(key)]
            for key in keys_to_remove:
                del self._local_cache[key]
                deleted_count += 1
            
            self._update_stats(CacheOperation.INVALIDATE, True)
            logger.info(f"Invalidated {deleted_count} cache keys (Async) matching: {full_pattern}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Async cache invalidation error for pattern {full_pattern}: {e}")
            self._update_stats(CacheOperation.INVALIDATE, False)
            return 0
    
    def invalidate_namespace(self, namespace: str) -> int:
        """
        Invalidate all cache keys in a namespace (synchronous).
        
        Args:
            namespace: Namespace to invalidate
        
        Returns:
            Number of keys deleted
        """
        return self.invalidate_pattern("*", namespace=namespace)
    
    async def invalidate_namespace_async(self, namespace: str) -> int:
        """
        Invalidate all cache keys in a namespace (asynchronous).
        
        Args:
            namespace: Namespace to invalidate
        
        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern_async("*", namespace=namespace)
    
    def exists(
        self,
        cache_type: str,
        key_parts: Optional[List[str]] = None,
        *args,
        **kwargs
    ) -> bool:
        """
        Check if key exists in cache (synchronous).
        
        Args:
            cache_type: Type of cache
            key_parts: List of key components
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation
        
        Returns:
            True if key exists, False otherwise
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            return False
        
        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)
        
        try:
            # Check Redis first
            redis_client = self._get_sync_redis_client()
            if redis_client:
                try:
                    return bool(redis_client.exists(cache_key))
                except Exception as e:
                    logger.warning(f"Redis EXISTS failed for {cache_key}: {e}")
            
            # Check local cache
            return self._get_from_local_cache(cache_key) is not None
            
        except Exception as e:
            logger.error(f"Cache EXISTS error for {cache_key}: {e}")
            return False
    
    async def exists_async(
        self,
        cache_type: str,
        key_parts: Optional[List[str]] = None,
        *args,
        **kwargs
    ) -> bool:
        """
        Check if key exists in cache (asynchronous).
        
        Args:
            cache_type: Type of cache
            key_parts: List of key components
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation
        
        Returns:
            True if key exists, False otherwise
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            return False
        
        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)
        
        try:
            # Check Redis first
            redis_client = await self._get_async_redis_client()
            if redis_client:
                try:
                    return bool(await redis_client.exists(cache_key))
                except Exception as e:
                    logger.warning(f"Async Redis EXISTS failed for {cache_key}: {e}")
            
            # Check local cache
            return self._get_from_local_cache(cache_key) is not None
            
        except Exception as e:
            logger.error(f"Async cache EXISTS error for {cache_key}: {e}")
            return False
    
    def get_ttl(
        self,
        cache_type: str,
        key_parts: Optional[List[str]] = None,
        *args,
        **kwargs
    ) -> Optional[int]:
        """
        Get remaining TTL for a cache key (synchronous).
        
        Args:
            cache_type: Type of cache
            key_parts: List of key components
            *args: Additional arguments for key generation
            **kwargs: Additional keyword arguments for key generation
        
        Returns:
            Remaining TTL in seconds, None if key doesn't exist or no TTL
        """
        config = self._cache_configs.get(cache_type)
        if not config:
            return None
        
        cache_key = self._generate_cache_key(config, key_parts, *args, **kwargs)
        
        try:
            # Check Redis first
            redis_client = self._get_sync_redis_client()
            if redis_client:
                try:
                    ttl = redis_client.ttl(cache_key)
                    return ttl if ttl > 0 else None
                except Exception as e:
                    logger.warning(f"Redis TTL failed for {cache_key}: {e}")
            
            # Check local cache
            if cache_key in self._local_cache:
                cache_entry = self._local_cache[cache_key]
                remaining = (cache_entry["expires_at"] - datetime.utcnow()).total_seconds()
                return int(remaining) if remaining > 0 else None
            
            return None
            
        except Exception as e:
            logger.error(f"Cache TTL error for {cache_key}: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary containing cache statistics
        """
        if not self._stats:
            return {"stats_disabled": True}
        
        return {
            "hits": self._stats.hits,
            "misses": self._stats.misses,
            "errors": self._stats.errors,
            "sets": self._stats.sets,
            "deletes": self._stats.deletes,
            "invalidations": self._stats.invalidations,
            "total_requests": self._stats.total_requests,
            "hit_rate_percent": round(self._stats.hit_rate, 2),
            "local_cache_size": len(self._local_cache),
            "last_reset": self._stats.last_reset.isoformat(),
            "registered_cache_types": list(self._cache_configs.keys())
        }
    
    def reset_stats(self):
        """Reset cache statistics."""
        if self._stats:
            self._stats.reset()
    
    def clear_local_cache(self):
        """Clear local cache."""
        self._local_cache.clear()
        logger.info("Local cache cleared")
    
    async def clear_all_cache(self) -> bool:
        """
        Clear all cache data (Redis and local).
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Clear Redis cache
            redis_client = await self._get_async_redis_client()
            if redis_client:
                try:
                    # Clear all keys with our namespaces
                    for config in self._cache_configs.values():
                        pattern = f"{config.namespace}:{config.key_prefix}:*"
                        keys = await redis_client.keys(pattern)
                        if keys:
                            await redis_client.delete(*keys)
                    logger.info("Redis cache cleared")
                except Exception as e:
                    logger.warning(f"Redis cache clear failed: {e}")
            
            # Clear local cache
            self.clear_local_cache()
            
            return True
            
        except Exception as e:
            logger.error(f"Cache clear all error: {e}")
            return False
    
    def warmup_cache(self, cache_type: str, data_loader: Callable, key_parts_list: List[List[str]]):
        """
        Warm up cache with preloaded data (synchronous).
        
        Args:
            cache_type: Type of cache
            data_loader: Function to load data
            key_parts_list: List of key parts for cache entries
        """
        logger.info(f"Starting cache warmup for {cache_type} with {len(key_parts_list)} entries")
        
        for key_parts in key_parts_list:
            try:
                data = data_loader(*key_parts)
                if data is not None:
                    self.set(cache_type, data, key_parts)
                    logger.debug(f"Warmed up cache for {cache_type}:{':'.join(key_parts)}")
            except Exception as e:
                logger.warning(f"Cache warmup failed for {cache_type}:{':'.join(key_parts)}: {e}")
        
        logger.info(f"Cache warmup completed for {cache_type}")
    
    async def warmup_cache_async(self, cache_type: str, data_loader: Callable, key_parts_list: List[List[str]]):
        """
        Warm up cache with preloaded data (asynchronous).
        
        Args:
            cache_type: Type of cache
            data_loader: Async function to load data
            key_parts_list: List of key parts for cache entries
        """
        logger.info(f"Starting async cache warmup for {cache_type} with {len(key_parts_list)} entries")
        
        tasks = []
        for key_parts in key_parts_list:
            async def _warmup_entry(kp=key_parts):
                try:
                    data = await data_loader(*kp)
                    if data is not None:
                        await self.set_async(cache_type, data, kp)
                        logger.debug(f"Warmed up cache (async) for {cache_type}:{':'.join(kp)}")
                except Exception as e:
                    logger.warning(f"Async cache warmup failed for {cache_type}:{':'.join(kp)}: {e}")
            
            tasks.append(_warmup_entry())
        
        # Execute warmup tasks concurrently
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"Async cache warmup completed for {cache_type}")


# Decorator functions for easy caching
def cache(
    cache_type: str = "analytics_dashboard",
    ttl: Optional[Union[int, timedelta]] = None,
    key_prefix: Optional[str] = None,
    namespace: str = "cache"
) -> Callable:
    """
    Decorator to cache function results (synchronous functions).
    
    Args:
        cache_type: Type of cache to use (must be registered)
        ttl: Time-to-live override
        key_prefix: Custom key prefix (defaults to function name)
        namespace: Cache namespace
    
    Usage:
        @cache(cache_type="user_profile", ttl=300)
        def get_user_data(user_id: int):
            return fetch_user_from_db(user_id)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get cache manager
            manager = get_unified_cache_manager()
            
            # Generate cache key from function name and arguments
            func_name = key_prefix or func.__name__
            
            # If cache_type is not registered, register it with defaults
            if cache_type not in manager._cache_configs:
                default_ttl = ttl.total_seconds() if isinstance(ttl, timedelta) else (ttl or 3600)
                config = CacheConfig(
                    ttl=int(default_ttl),
                    key_prefix=func_name,
                    namespace=namespace
                )
                manager.register_cache_config(cache_type, config)
            
            # Try to get from cache
            cached_result = manager.get(cache_type, None, None, *args, **kwargs)
            if cached_result is not None:
                logger.debug(f"Cache HIT for function: {func_name}")
                return cached_result
            
            # Cache miss - execute function
            logger.debug(f"Cache MISS for function: {func_name}")
            result = func(*args, **kwargs)
            
            # Store in cache
            if result is not None:
                manager.set(cache_type, result, None, ttl, *args, **kwargs)
                logger.debug(f"Cached result for function: {func_name}")
            
            return result
        
        return wrapper
    return decorator


def async_cache(
    cache_type: str = "analytics_dashboard",
    ttl: Optional[Union[int, timedelta]] = None,
    key_prefix: Optional[str] = None,
    namespace: str = "cache"
) -> Callable:
    """
    Decorator to cache async function results.
    
    Args:
        cache_type: Type of cache to use (must be registered)
        ttl: Time-to-live override
        key_prefix: Custom key prefix (defaults to function name)
        namespace: Cache namespace
    
    Usage:
        @async_cache(cache_type="user_profile", ttl=300)
        async def get_user_data_async(user_id: int):
            return await fetch_user_from_db_async(user_id)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get cache manager
            manager = get_unified_cache_manager()
            
            # Generate cache key from function name and arguments
            func_name = key_prefix or func.__name__
            
            # If cache_type is not registered, register it with defaults
            if cache_type not in manager._cache_configs:
                default_ttl = ttl.total_seconds() if isinstance(ttl, timedelta) else (ttl or 3600)
                config = CacheConfig(
                    ttl=int(default_ttl),
                    key_prefix=func_name,
                    namespace=namespace
                )
                manager.register_cache_config(cache_type, config)
            
            # Try to get from cache
            cached_result = await manager.get_async(cache_type, None, None, *args, **kwargs)
            if cached_result is not None:
                logger.debug(f"Cache HIT for async function: {func_name}")
                return cached_result
            
            # Cache miss - execute function
            logger.debug(f"Cache MISS for async function: {func_name}")
            result = await func(*args, **kwargs)
            
            # Store in cache
            if result is not None:
                await manager.set_async(cache_type, result, None, ttl, *args, **kwargs)
                logger.debug(f"Cached result for async function: {func_name}")
            
            return result
        
        return wrapper
    return decorator


# Context managers for cache operations
@asynccontextmanager
async def cache_context():
    """
    Async context manager for cache operations.
    
    Usage:
        async with cache_context() as cache:
            await cache.set_async("user_profile", user_data, ["user_123"])
            data = await cache.get_async("user_profile", ["user_123"])
    """
    manager = get_unified_cache_manager()
    try:
        yield manager
    finally:
        pass


# Global cache manager instance
_unified_cache_manager: Optional[UnifiedCacheManager] = None


def get_unified_cache_manager(
    redis_client: Optional[Union[Redis, AsyncRedis]] = None,
    enable_stats: bool = True,
    enable_local_fallback: bool = True
) -> UnifiedCacheManager:
    """
    Get global unified cache manager singleton.
    
    Args:
        redis_client: Optional Redis client instance
        enable_stats: Whether to track cache statistics
        enable_local_fallback: Whether to use local cache as fallback
    
    Returns:
        UnifiedCacheManager instance
    """
    global _unified_cache_manager
    if _unified_cache_manager is None:
        _unified_cache_manager = UnifiedCacheManager(
            redis_client=redis_client,
            enable_stats=enable_stats,
            enable_local_fallback=enable_local_fallback
        )
    return _unified_cache_manager


# Backward compatibility functions
# These functions maintain compatibility with existing cache.py usage

def cache_user_data(user_id: str, data: Any, ttl: int = 1800) -> bool:
    """Cache user data with 30-minute default TTL (backward compatibility)."""
    manager = get_unified_cache_manager()
    return manager.set("user_profile", data, [user_id], ttl)


def get_cached_user_data(user_id: str) -> Optional[Any]:
    """Get cached user data (backward compatibility)."""
    manager = get_unified_cache_manager()
    return manager.get("user_profile", [user_id])


def invalidate_user_cache(user_id: str) -> bool:
    """Invalidate specific user cache (backward compatibility)."""
    manager = get_unified_cache_manager()
    return manager.delete("user_profile", [user_id])


async def cache_user_data_async(user_id: str, data: Any, ttl: int = 1800) -> bool:
    """Cache user data with 30-minute default TTL (async backward compatibility)."""
    manager = get_unified_cache_manager()
    return await manager.set_async("user_profile", data, [user_id], ttl)


async def get_cached_user_data_async(user_id: str) -> Optional[Any]:
    """Get cached user data (async backward compatibility)."""
    manager = get_unified_cache_manager()
    return await manager.get_async("user_profile", [user_id])


async def invalidate_user_cache_async(user_id: str) -> bool:
    """Invalidate specific user cache (async backward compatibility)."""
    manager = get_unified_cache_manager()
    return await manager.delete_async("user_profile", [user_id])


def cache_patient_data(patient_id: str, data: Any, ttl: int = 3600) -> bool:
    """Cache patient data with 1-hour default TTL (backward compatibility)."""
    manager = get_unified_cache_manager()
    return manager.set("patient_detail", data, [patient_id], ttl)


def get_cached_patient_data(patient_id: str) -> Optional[Any]:
    """Get cached patient data (backward compatibility)."""
    manager = get_unified_cache_manager()
    return manager.get("patient_detail", [patient_id])


def invalidate_patient_cache(patient_id: str) -> bool:
    """Invalidate specific patient cache (backward compatibility)."""
    manager = get_unified_cache_manager()
    return manager.delete("patient_detail", [patient_id])


async def cache_patient_data_async(patient_id: str, data: Any, ttl: int = 3600) -> bool:
    """Cache patient data with 1-hour default TTL (async backward compatibility)."""
    manager = get_unified_cache_manager()
    return await manager.set_async("patient_detail", data, [patient_id], ttl)


async def get_cached_patient_data_async(patient_id: str) -> Optional[Any]:
    """Get cached patient data (async backward compatibility)."""
    manager = get_unified_cache_manager()
    return await manager.get_async("patient_detail", [patient_id])


async def invalidate_patient_cache_async(patient_id: str) -> bool:
    """Invalidate specific patient cache (async backward compatibility)."""
    manager = get_unified_cache_manager()
    return await manager.delete_async("patient_detail", [patient_id])


# Compatibility with caching.py
def get_cache_manager() -> UnifiedCacheManager:
    """Get cache manager (backward compatibility with caching.py)."""
    return get_unified_cache_manager()


def cache_result(
    cache_type: str,
    key_generator: Callable[..., List[str]],
    ttl_override: Optional[int] = None
):
    """
    Decorator for caching function results (backward compatibility with caching.py).
    
    Args:
        cache_type: Type of cache to use
        key_generator: Function to generate cache key parts from function args
        ttl_override: Override default TTL
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache_manager = get_unified_cache_manager()
            
            # Generate cache key
            try:
                key_parts = key_generator(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Cache key generation failed: {e}")
                return await func(*args, **kwargs)
            
            # Try to get from cache
            cached_result = await cache_manager.get_async(cache_type, key_parts)
            if cached_result is not None:
                logger.debug(f"Cache hit for {cache_type}:{':'.join(key_parts)}")
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            
            # Cache the result
            await cache_manager.set_async(cache_type, result, key_parts, ttl_override)
            logger.debug(f"Cached result for {cache_type}:{':'.join(key_parts)}")
            
            return result
        
        return wrapper
    return decorator


def cache_response(seconds: int = 300):
    """
    Decorator for caching HTTP response data (backward compatibility with caching.py).
    
    Args:
        seconds: Cache TTL in seconds (default 5 minutes)
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache_manager = get_unified_cache_manager()
            
            # Generate cache key from function name and arguments
            func_name = func.__name__
            key_parts = [
                func_name,
                str(hash(str(args) + str(sorted(kwargs.items()))))
            ]
            
            # Try to get from cache
            cached_result = await cache_manager.get_async("analytics_dashboard", key_parts)
            if cached_result is not None:
                logger.debug(f"Cache hit for response {func_name}")
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            
            # Cache the result
            await cache_manager.set_async("analytics_dashboard", result, key_parts, seconds)
            logger.debug(f"Cached response for {func_name}")
            
            return result
        
        return wrapper
    return decorator


# Additional utility functions
def generate_request_cache_key(request, additional_parts: List[str] = None) -> List[str]:
    """Generate cache key parts from request (backward compatibility)."""
    parts = [
        request.method,
        request.url.path,
        str(sorted(request.query_params.items()))
    ]
    
    if additional_parts:
        parts.extend(additional_parts)
    
    return parts


def generate_user_cache_key(user_id: str, additional_parts: List[str] = None) -> List[str]:
    """Generate cache key parts for user-specific data (backward compatibility)."""
    parts = [user_id]
    
    if additional_parts:
        parts.extend(additional_parts)
    
    return parts


def invalidate_cache(cache_type: str, key_parts: List[str]):
    """Invalidate specific cache entry (backward compatibility)."""
    async def _invalidate():
        cache_manager = get_unified_cache_manager()
        await cache_manager.delete_async(cache_type, key_parts)
    
    return _invalidate


# Export main classes and functions
__all__ = [
    "UnifiedCacheManager",
    "CacheConfig",
    "CacheStats",
    "SerializationMethod",
    "CacheOperation",
    "get_unified_cache_manager",
    "cache",
    "async_cache",
    "cache_context",
    "cache_user_data",
    "get_cached_user_data",
    "invalidate_user_cache",
    "cache_user_data_async",
    "get_cached_user_data_async",
    "invalidate_user_cache_async",
    "cache_patient_data",
    "get_cached_patient_data",
    "invalidate_patient_cache",
    "cache_patient_data_async",
    "get_cached_patient_data_async",
    "invalidate_patient_cache_async",
    "get_cache_manager",
    "cache_result",
    "cache_response",
    "generate_request_cache_key",
    "generate_user_cache_key",
    "invalidate_cache",
    "DEFAULT_CACHE_CONFIGS"
]
