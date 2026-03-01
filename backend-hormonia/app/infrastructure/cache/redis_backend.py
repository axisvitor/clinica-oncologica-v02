"""
Redis Backend Module for Unified Cache System

This module handles all Redis operations, serialization, and local cache fallback.
"""

import json
import pickle
import fnmatch
import asyncio
import os
from typing import Any, Optional, Union, Dict
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID
from enum import Enum

try:
    from pydantic import BaseModel
except ImportError:
    BaseModel = None

from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from app.core.redis_manager import get_sync_redis_client, get_async_redis_client
from app.utils.logging import get_logger
from app.utils.timezone import now_sao_paulo

logger = get_logger(__name__)


class SerializationMethod(str, Enum):
    """Serialization methods for cache data."""

    JSON = "json"
    PICKLE = "pickle"


class RedisBackend:
    """
    Redis backend handler with serialization and local cache fallback.
    """

    def __init__(
        self,
        redis_client: Optional[Union[Redis, AsyncRedis]] = None,
        enable_local_fallback: bool = True,
    ):
        """
        Initialize Redis backend.

        Args:
            redis_client: Optional Redis client instance
            enable_local_fallback: Whether to use local cache as fallback
        """
        self.redis_client = redis_client
        self.enable_local_fallback = enable_local_fallback
        self._local_cache: Dict[str, Dict[str, Any]] = {}
        self._async_timeout_seconds = float(
            os.getenv("CACHE_ASYNC_REDIS_TIMEOUT_SECONDS", "2.0")
        )

    def _json_serializer(self, obj: Any) -> Any:
        """JSON serializer for complex objects."""
        if isinstance(obj, (datetime, UUID)):
            return str(obj)
        elif isinstance(obj, Decimal):
            return float(obj)
        elif BaseModel is not None and isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        elif hasattr(obj, "__dict__"):
            # For SQLAlchemy models or complex objects
            return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        else:
            return str(obj)

    def serialize_for_cache(
        self, obj: Any, method: SerializationMethod
    ) -> Union[str, bytes]:
        """Serialize complex objects for caching."""
        try:
            if method == SerializationMethod.JSON:
                if isinstance(obj, str):
                    return obj
                if BaseModel is not None and isinstance(obj, BaseModel):
                    return json.dumps(
                        obj.model_dump(mode="json"), default=self._json_serializer
                    )
                elif hasattr(obj, "__dict__"):
                    # For SQLAlchemy models or complex objects
                    data = {}
                    for key, value in obj.__dict__.items():
                        if not key.startswith("_") and not callable(value):
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

    def deserialize_from_cache(
        self, data: Union[str, bytes], method: SerializationMethod
    ) -> Any:
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

    def get_sync_redis_client(self):
        """Get synchronous Redis client."""
        if self.redis_client:
            return self.redis_client
        try:
            return get_sync_redis_client()
        except Exception as e:
            logger.warning(f"Failed to get sync Redis client: {e}")
            return None

    async def get_async_redis_client(self):
        """Get asynchronous Redis client."""
        try:
            return await asyncio.wait_for(
                get_async_redis_client(), timeout=self._async_timeout_seconds
            )
        except Exception as e:
            logger.warning(f"Failed to get async Redis client: {e}")
            return None

    def get_from_local_cache(self, cache_key: str) -> Optional[Any]:
        """Get value from local cache with expiration check."""
        if not self.enable_local_fallback or cache_key not in self._local_cache:
            return None

        cache_entry = self._local_cache[cache_key]
        if not self._is_cache_entry_expired(cache_entry["expires_at"]):
            return cache_entry["data"]
        else:
            # Expired, remove from local cache
            del self._local_cache[cache_key]
            return None

    def set_in_local_cache(self, cache_key: str, value: Any, ttl: int):
        """Set value in local cache with expiration."""
        if not self.enable_local_fallback:
            return

        self._local_cache[cache_key] = {
            "data": value,
            "expires_at": now_sao_paulo() + timedelta(seconds=ttl),
        }

    def remove_from_local_cache(self, cache_key: str):
        """Remove value from local cache."""
        self._local_cache.pop(cache_key, None)

    def clear_local_cache(self):
        """Clear local cache."""
        self._local_cache.clear()
        logger.info("Local cache cleared")

    def get_local_cache_size(self) -> int:
        """Get local cache size."""
        return len(self._local_cache)

    def _get_local_cache_ttl(self, cache_key: str) -> Optional[int]:
        """Get remaining TTL for a local cache entry."""
        if not self.enable_local_fallback:
            return None

        cache_entry = self._local_cache.get(cache_key)
        if not cache_entry:
            return None

        expires_at = cache_entry["expires_at"]
        remaining = int((expires_at - self._now_for_expiry(expires_at)).total_seconds())
        if remaining <= 0:
            self._local_cache.pop(cache_key, None)
            return None
        return remaining

    def _get_local_cache_keys(self, pattern: str) -> list:
        """Get local cache keys matching a pattern."""
        if not self.enable_local_fallback:
            return []

        matches = []
        for key, entry in list(self._local_cache.items()):
            if self._is_cache_entry_expired(entry["expires_at"]):
                self._local_cache.pop(key, None)
                continue
            if fnmatch.fnmatch(key, pattern):
                matches.append(key)
        return matches

    def _now_for_expiry(self, expires_at: Any) -> datetime:
        """
        Return current time with timezone-awareness compatible with `expires_at`.
        """
        now = now_sao_paulo()
        if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
            return now.replace(tzinfo=None)
        return now

    def _is_cache_entry_expired(self, expires_at: Any) -> bool:
        """
        Check expiration while handling both naive and aware datetimes.
        """
        if not isinstance(expires_at, datetime):
            return True
        return self._now_for_expiry(expires_at) >= expires_at

    # Sync Redis operations
    def redis_get(self, cache_key: str) -> Optional[bytes]:
        """Get value from Redis (synchronous)."""
        redis_client = self.get_sync_redis_client()
        if redis_client:
            try:
                cached = redis_client.get(cache_key)
                if cached is not None:
                    return cached
            except Exception as e:
                logger.warning(f"Redis GET failed for {cache_key}: {e}")
        local_value = self.get_from_local_cache(cache_key)
        if local_value is not None:
            logger.debug(f"Local cache fallback hit for key: {cache_key}")
        return local_value

    def redis_set(self, cache_key: str, value: Union[str, bytes], ttl: int) -> bool:
        """Set value in Redis (synchronous)."""
        redis_client = self.get_sync_redis_client()
        if redis_client:
            try:
                success = redis_client.set(cache_key, value, ex=ttl)
                if success:
                    logger.debug(f"Cached in Redis for key: {cache_key} (TTL: {ttl}s)")
                    return True
            except Exception as e:
                logger.warning(f"Redis SET failed for {cache_key}: {e}")
        self.set_in_local_cache(cache_key, value, ttl)
        logger.debug(f"Cached in local fallback for key: {cache_key} (TTL: {ttl}s)")
        return False

    def redis_delete(self, cache_key: str) -> bool:
        """Delete value from Redis (synchronous)."""
        redis_client = self.get_sync_redis_client()
        if redis_client:
            try:
                redis_client.delete(cache_key)
                logger.debug(f"Deleted from Redis: {cache_key}")
                return True
            except Exception as e:
                logger.warning(f"Redis DELETE failed for {cache_key}: {e}")
        return False

    def redis_exists(self, cache_key: str) -> bool:
        """Check if key exists in Redis (synchronous)."""
        redis_client = self.get_sync_redis_client()
        if redis_client:
            try:
                if redis_client.exists(cache_key):
                    return True
            except Exception as e:
                logger.warning(f"Redis EXISTS failed for {cache_key}: {e}")
        return self.get_from_local_cache(cache_key) is not None

    def redis_ttl(self, cache_key: str) -> Optional[int]:
        """Get TTL for key in Redis (synchronous)."""
        redis_client = self.get_sync_redis_client()
        if redis_client:
            try:
                ttl = redis_client.ttl(cache_key)
                if ttl > 0:
                    return ttl
            except Exception as e:
                logger.warning(f"Redis TTL failed for {cache_key}: {e}")
        local_ttl = self._get_local_cache_ttl(cache_key)
        if local_ttl is not None:
            logger.debug(f"Local cache TTL fallback for key: {cache_key}")
        return local_ttl

    def redis_keys(self, pattern: str) -> list:
        """Get keys matching pattern from Redis (synchronous)."""
        redis_client = self.get_sync_redis_client()
        if redis_client:
            try:
                return list(redis_client.scan_iter(match=pattern))
            except Exception as e:
                logger.warning(f"Redis SCAN failed for {pattern}: {e}")
        return self._get_local_cache_keys(pattern)

    # Async Redis operations
    async def redis_get_async(self, cache_key: str) -> Optional[bytes]:
        """Get value from Redis (asynchronous)."""
        redis_client = await self.get_async_redis_client()
        if redis_client:
            try:
                return await asyncio.wait_for(
                    redis_client.get(cache_key), timeout=self._async_timeout_seconds
                )
            except Exception as e:
                logger.warning(f"Async Redis GET failed for {cache_key}: {e}")
        return None

    async def redis_set_async(
        self, cache_key: str, value: Union[str, bytes], ttl: int
    ) -> bool:
        """Set value in Redis (asynchronous)."""
        redis_client = await self.get_async_redis_client()
        if redis_client:
            try:
                success = await asyncio.wait_for(
                    redis_client.set(cache_key, value, ex=ttl),
                    timeout=self._async_timeout_seconds,
                )
                if success:
                    logger.debug(
                        f"Cached in Redis (Async) for key: {cache_key} (TTL: {ttl}s)"
                    )
                return bool(success)
            except Exception as e:
                logger.warning(f"Async Redis SET failed for {cache_key}: {e}")
        return False

    async def redis_delete_async(self, cache_key: str) -> bool:
        """Delete value from Redis (asynchronous)."""
        redis_client = await self.get_async_redis_client()
        if redis_client:
            try:
                await asyncio.wait_for(
                    redis_client.delete(cache_key), timeout=self._async_timeout_seconds
                )
                logger.debug(f"Deleted from Redis (Async): {cache_key}")
                return True
            except Exception as e:
                logger.warning(f"Async Redis DELETE failed for {cache_key}: {e}")
        return False

    async def redis_exists_async(self, cache_key: str) -> bool:
        """Check if key exists in Redis (asynchronous)."""
        redis_client = await self.get_async_redis_client()
        if redis_client:
            try:
                exists = await asyncio.wait_for(
                    redis_client.exists(cache_key), timeout=self._async_timeout_seconds
                )
                return bool(exists)
            except Exception as e:
                logger.warning(f"Async Redis EXISTS failed for {cache_key}: {e}")
        return False

    async def redis_keys_async(self, pattern: str) -> list:
        """Get keys matching pattern from Redis (asynchronous)."""
        redis_client = await self.get_async_redis_client()
        if redis_client:
            try:
                async def _collect_scan_keys() -> list:
                    scan_result = redis_client.scan_iter(match=pattern)
                    if asyncio.iscoroutine(scan_result):
                        scan_result = await scan_result
                    if hasattr(scan_result, "__aiter__"):
                        return [key async for key in scan_result]
                    return list(scan_result)

                return await asyncio.wait_for(
                    _collect_scan_keys(), timeout=self._async_timeout_seconds
                )
            except Exception as e:
                logger.warning(f"Async Redis SCAN failed for {pattern}: {e}")
        return []


__all__ = ["RedisBackend", "SerializationMethod"]
