"""
Centralized cache invalidation service.

This module provides a unified interface for cache invalidation across
different cache backends (Redis, local memory) with retry logic,
logging, and pattern-based invalidation.
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from redis import Redis
from redis.exceptions import RedisError

from app.services.cache.key_builder import CacheKeyBuilder


logger = logging.getLogger(__name__)


class InvalidationStrategy(str, Enum):
    """Cache invalidation strategies."""

    SINGLE = "single"  # Invalidate single key
    PATTERN = "pattern"  # Invalidate by pattern matching
    TAGS = "tags"  # Invalidate by tags
    CASCADE = "cascade"  # Invalidate key and related keys


class CacheBackend(str, Enum):
    """Supported cache backends."""

    REDIS = "redis"
    LOCAL = "local"


class CacheInvalidationService:
    """
    Centralized service for cache invalidation with retry logic.

    This service provides:
    - Multiple invalidation strategies (single, pattern, tags)
    - Retry logic with exponential backoff
    - Support for Redis and local cache fallback
    - Detailed logging and metrics
    - Tag-based cache management
    """

    def __init__(
        self,
        redis_client: Optional[Redis] = None,
        key_builder: Optional[CacheKeyBuilder] = None,
        max_retries: int = 3,
        retry_delay: float = 0.1,
        retry_backoff: float = 2.0,
    ):
        """
        Initialize the cache invalidation service.

        Args:
            redis_client: Redis client instance (optional)
            key_builder: Cache key builder instance
            max_retries: Maximum number of retry attempts
            retry_delay: Initial retry delay in seconds
            retry_backoff: Backoff multiplier for retries
        """
        self.redis_client = redis_client
        self.key_builder = key_builder or CacheKeyBuilder()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff

        # Local cache fallback
        self._local_cache: Dict[str, Any] = {}
        self._tag_registry: Dict[str, Set[str]] = {}

        # Metrics
        self._metrics = {
            "invalidations": 0,
            "retries": 0,
            "failures": 0,
            "fallbacks": 0,
        }

    async def invalidate(
        self,
        key: Optional[str] = None,
        pattern: Optional[str] = None,
        tags: Optional[List[str]] = None,
        strategy: InvalidationStrategy = InvalidationStrategy.SINGLE,
        cascade: bool = False,
    ) -> bool:
        """
        Invalidate cache entries based on the specified strategy.

        Args:
            key: Single cache key to invalidate
            pattern: Pattern for matching multiple keys
            tags: List of tags for tag-based invalidation
            strategy: Invalidation strategy to use
            cascade: Whether to cascade invalidation to related keys

        Returns:
            True if invalidation succeeded, False otherwise

        Examples:
            >>> service = CacheInvalidationService(redis_client)
            >>> await service.invalidate(key="patient:123")
            >>> await service.invalidate(pattern="patient:*", strategy=InvalidationStrategy.PATTERN)
            >>> await service.invalidate(tags=["patient", "active"], strategy=InvalidationStrategy.TAGS)
        """
        try:
            self._metrics["invalidations"] += 1

            if strategy == InvalidationStrategy.SINGLE and key:
                return await self._invalidate_single(key, cascade)

            elif strategy == InvalidationStrategy.PATTERN and pattern:
                return await self._invalidate_pattern(pattern)

            elif strategy == InvalidationStrategy.TAGS and tags:
                return await self._invalidate_tags(tags)

            elif strategy == InvalidationStrategy.CASCADE and key:
                return await self._invalidate_cascade(key)

            logger.warning(
                "Invalid invalidation parameters",
                extra={
                    "strategy": strategy,
                    "key": key,
                    "pattern": pattern,
                    "tags": tags,
                },
            )
            return False

        except Exception as e:
            logger.error(
                "Cache invalidation failed",
                extra={
                    "error": str(e),
                    "strategy": strategy,
                    "key": key,
                    "pattern": pattern,
                    "tags": tags,
                },
                exc_info=True,
            )
            self._metrics["failures"] += 1
            return False

    async def invalidate_entity(
        self,
        entity: str,
        identifier: Optional[str] = None,
        cascade: bool = True,
    ) -> bool:
        """
        Invalidate all cache entries for an entity.

        This is a high-level method that invalidates common patterns
        for an entity (list, count, search, etc.).

        Args:
            entity: Entity type (e.g., 'patient', 'quiz')
            identifier: Optional specific entity identifier
            cascade: Whether to invalidate related queries

        Returns:
            True if all invalidations succeeded

        Examples:
            >>> await service.invalidate_entity('patient', '123')
            >>> await service.invalidate_entity('quiz', cascade=True)
        """
        success = True

        # Invalidate specific entity if identifier provided
        if identifier:
            key = self.key_builder.build(entity, identifier)
            success &= await self.invalidate(key=key, cascade=cascade)

        # Invalidate common query patterns
        if cascade:
            patterns = self.key_builder.get_entity_patterns(entity)
            for pattern in patterns:
                result = await self.invalidate(
                    pattern=pattern,
                    strategy=InvalidationStrategy.PATTERN,
                )
                success &= result

        logger.info(
            "Entity cache invalidated",
            extra={
                "entity": entity,
                "identifier": identifier,
                "cascade": cascade,
                "success": success,
            },
        )

        return success

    async def tag_key(self, key: str, tags: List[str]) -> bool:
        """
        Associate tags with a cache key for tag-based invalidation.

        Args:
            key: Cache key to tag
            tags: List of tags to associate

        Returns:
            True if tagging succeeded
        """
        try:
            if self.redis_client:
                return await self._tag_key_redis(key, tags)
            else:
                return self._tag_key_local(key, tags)
        except Exception as e:
            logger.error(
                "Failed to tag cache key",
                extra={"key": key, "tags": tags, "error": str(e)},
                exc_info=True,
            )
            return False

    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get cache invalidation metrics.

        Returns:
            Dictionary with metrics data
        """
        return {
            **self._metrics,
            "timestamp": datetime.utcnow().isoformat(),
            "backend": CacheBackend.REDIS if self.redis_client else CacheBackend.LOCAL,
        }

    async def clear_all(self, confirm: bool = False) -> bool:
        """
        Clear all cache entries (dangerous operation).

        Args:
            confirm: Must be True to execute

        Returns:
            True if cleared successfully
        """
        if not confirm:
            logger.warning("clear_all called without confirmation")
            return False

        try:
            if self.redis_client:
                pattern = self.key_builder.build_pattern("*")
                await self._invalidate_pattern(pattern)
            else:
                self._local_cache.clear()
                self._tag_registry.clear()

            logger.warning("All cache entries cleared")
            return True

        except Exception as e:
            logger.error("Failed to clear cache", extra={"error": str(e)}, exc_info=True)
            return False

    # Private methods

    async def _invalidate_single(self, key: str, cascade: bool = False) -> bool:
        """Invalidate a single cache key with retry logic."""
        attempt = 0
        delay = self.retry_delay

        while attempt < self.max_retries:
            try:
                if self.redis_client:
                    result = self.redis_client.delete(key)
                    logger.debug(
                        "Cache key invalidated (Redis)",
                        extra={"key": key, "result": result},
                    )
                    return bool(result)
                else:
                    # Fallback to local cache
                    self._metrics["fallbacks"] += 1
                    self._local_cache.pop(key, None)
                    logger.debug(
                        "Cache key invalidated (local)",
                        extra={"key": key},
                    )
                    return True

            except RedisError as e:
                attempt += 1
                self._metrics["retries"] += 1

                if attempt >= self.max_retries:
                    logger.error(
                        "Failed to invalidate cache key after retries",
                        extra={
                            "key": key,
                            "attempt": attempt,
                            "error": str(e),
                        },
                        exc_info=True,
                    )
                    # Fallback to local cache
                    self._local_cache.pop(key, None)
                    self._metrics["fallbacks"] += 1
                    return False

                logger.warning(
                    "Retrying cache invalidation",
                    extra={
                        "key": key,
                        "attempt": attempt,
                        "delay": delay,
                    },
                )
                await asyncio.sleep(delay)
                delay *= self.retry_backoff

        return False

    async def _invalidate_pattern(self, pattern: str) -> bool:
        """Invalidate all keys matching a pattern."""
        try:
            if self.redis_client:
                cursor = 0
                count = 0

                while True:
                    cursor, keys = self.redis_client.scan(
                        cursor=cursor,
                        match=pattern,
                        count=100,
                    )

                    if keys:
                        self.redis_client.delete(*keys)
                        count += len(keys)

                    if cursor == 0:
                        break

                logger.info(
                    "Cache pattern invalidated",
                    extra={"pattern": pattern, "count": count},
                )
                return True
            else:
                # Fallback to local cache
                self._metrics["fallbacks"] += 1
                matching_keys = [
                    k for k in self._local_cache.keys()
                    if self._matches_pattern(k, pattern)
                ]
                for key in matching_keys:
                    self._local_cache.pop(key, None)

                logger.info(
                    "Cache pattern invalidated (local)",
                    extra={"pattern": pattern, "count": len(matching_keys)},
                )
                return True

        except Exception as e:
            logger.error(
                "Failed to invalidate pattern",
                extra={"pattern": pattern, "error": str(e)},
                exc_info=True,
            )
            return False

    async def _invalidate_tags(self, tags: List[str]) -> bool:
        """Invalidate all keys associated with tags."""
        try:
            all_keys: Set[str] = set()

            for tag in tags:
                if self.redis_client:
                    tag_key = self.key_builder.build_tag_key(tag)
                    keys = self.redis_client.smembers(tag_key)
                    all_keys.update(k.decode() if isinstance(k, bytes) else k for k in keys)
                else:
                    # Local cache
                    all_keys.update(self._tag_registry.get(tag, set()))

            if all_keys:
                if self.redis_client:
                    self.redis_client.delete(*all_keys)
                else:
                    for key in all_keys:
                        self._local_cache.pop(key, None)

            logger.info(
                "Cache tags invalidated",
                extra={"tags": tags, "count": len(all_keys)},
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to invalidate tags",
                extra={"tags": tags, "error": str(e)},
                exc_info=True,
            )
            return False

    async def _invalidate_cascade(self, key: str) -> bool:
        """Invalidate a key and all related keys."""
        # Parse key to extract entity
        components = self.key_builder.parse(key)
        entity = components.get("entity")

        if not entity:
            return await self._invalidate_single(key)

        # Invalidate the key itself
        success = await self._invalidate_single(key)

        # Invalidate related patterns
        patterns = self.key_builder.get_entity_patterns(entity)
        for pattern in patterns:
            result = await self._invalidate_pattern(pattern)
            success &= result

        return success

    async def _tag_key_redis(self, key: str, tags: List[str]) -> bool:
        """Tag a key in Redis."""
        try:
            for tag in tags:
                tag_key = self.key_builder.build_tag_key(tag)
                self.redis_client.sadd(tag_key, key)
            return True
        except Exception as e:
            logger.error(
                "Failed to tag key in Redis",
                extra={"key": key, "tags": tags, "error": str(e)},
                exc_info=True,
            )
            return False

    def _tag_key_local(self, key: str, tags: List[str]) -> bool:
        """Tag a key in local cache."""
        for tag in tags:
            if tag not in self._tag_registry:
                self._tag_registry[tag] = set()
            self._tag_registry[tag].add(key)
        return True

    def _matches_pattern(self, key: str, pattern: str) -> bool:
        """Check if a key matches a wildcard pattern."""
        import re
        regex_pattern = pattern.replace("*", ".*").replace("?", ".")
        return bool(re.match(f"^{regex_pattern}$", key))
