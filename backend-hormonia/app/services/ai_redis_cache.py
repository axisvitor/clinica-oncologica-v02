"""
AI-specific Redis caching service with cache warming and metrics.
Provides enhanced caching for AI endpoints with intelligent invalidation.
"""
import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta
import json
import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)


class AICacheMetrics:
    """Track cache performance metrics."""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.invalidations = 0
        self.warming_operations = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "invalidations": self.invalidations,
            "warming_operations": self.warming_operations,
            "hit_rate": round(self.hit_rate, 2),
            "total_requests": self.hits + self.misses
        }


class AIRedisCacheService:
    """Enhanced Redis caching service specifically for AI endpoints."""

    # Cache TTL configurations (in seconds)
    TTL_INSIGHTS = 300  # 5 minutes
    TTL_RECOMMENDATIONS = 600  # 10 minutes
    TTL_SUMMARY = 900  # 15 minutes
    TTL_ANALYSIS = 180  # 3 minutes

    def __init__(self):
        self.metrics = AICacheMetrics()
        self._client: Optional[redis.Redis] = None

    async def get_client(self) -> Optional[redis.Redis]:
        """Get or create Redis client with connection pooling."""
        if self._client is None:
            try:
                self._client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    socket_keepalive=True,
                    health_check_interval=30,
                    max_connections=20,
                    retry_on_timeout=True
                )
                await self._client.ping()
                logger.info("AI Redis cache client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize AI Redis cache: {e}")
                self._client = None
        return self._client

    async def get_cached(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached data with metrics tracking."""
        client = await self.get_client()
        if client is None:
            self.metrics.errors += 1
            return None

        try:
            data = await client.get(cache_key)
            if data:
                self.metrics.hits += 1
                logger.debug(f"[CACHE HIT] Key: {cache_key}")
                return json.loads(data)
            else:
                self.metrics.misses += 1
                logger.debug(f"[CACHE MISS] Key: {cache_key}")
                return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for {cache_key}: {e}")
            self.metrics.errors += 1
            # Clean corrupted cache entry
            try:
                await client.delete(cache_key)
            except:
                pass
            return None
        except Exception as e:
            logger.error(f"Cache read error for {cache_key}: {e}")
            self.metrics.errors += 1
            return None

    async def set_cached(
        self,
        cache_key: str,
        data: Dict[str, Any],
        ttl_seconds: int
    ) -> bool:
        """Set cached data with JSON serialization."""
        client = await self.get_client()
        if client is None:
            return False

        try:
            serialized = json.dumps(data, default=str, ensure_ascii=False)
            await client.setex(cache_key, ttl_seconds, serialized)
            logger.debug(f"[CACHE SET] Key: {cache_key} (TTL: {ttl_seconds}s)")
            return True
        except TypeError as e:
            logger.error(f"JSON serialization error for {cache_key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Cache write error for {cache_key}: {e}")
            return False

    async def invalidate_patient_cache(self, patient_id: UUID) -> int:
        """Invalidate all AI cache entries for a patient."""
        client = await self.get_client()
        if client is None:
            return 0

        invalidated_count = 0
        patterns = [
            f"ai:insights:{patient_id}*",
            f"ai:recommendations:{patient_id}*",
            f"ai:summary:{patient_id}*",
            f"ai:analysis:{patient_id}*"
        ]

        try:
            for pattern in patterns:
                cursor = 0
                while True:
                    cursor, keys = await client.scan(
                        cursor=cursor,
                        match=pattern,
                        count=100
                    )
                    if keys:
                        deleted = await client.delete(*keys)
                        invalidated_count += deleted

                    if cursor == 0:
                        break

            self.metrics.invalidations += invalidated_count
            logger.info(f"Invalidated {invalidated_count} AI cache entries for patient {patient_id}")
            return invalidated_count
        except Exception as e:
            logger.error(f"Cache invalidation error for patient {patient_id}: {e}")
            return invalidated_count

    async def warm_patient_cache(
        self,
        patient_id: UUID,
        insights_data: Optional[Dict[str, Any]] = None,
        recommendations_data: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Warm cache for a patient with pre-computed data.
        Used for frequently accessed patients.
        """
        client = await self.get_client()
        if client is None:
            return 0

        warmed_count = 0

        try:
            if insights_data:
                cache_key = f"ai:insights:{patient_id}:30"  # Default 30 days
                if await self.set_cached(cache_key, insights_data, self.TTL_INSIGHTS):
                    warmed_count += 1

            if recommendations_data:
                cache_key = f"ai:recommendations:{patient_id}"
                if await self.set_cached(cache_key, recommendations_data, self.TTL_RECOMMENDATIONS):
                    warmed_count += 1

            self.metrics.warming_operations += 1
            logger.info(f"Warmed {warmed_count} cache entries for patient {patient_id}")
            return warmed_count
        except Exception as e:
            logger.error(f"Cache warming error for patient {patient_id}: {e}")
            return warmed_count

    async def warm_frequent_patients(
        self,
        patient_ids: List[UUID],
        data_generator_func
    ) -> int:
        """
        Warm cache for multiple frequent patients.

        Args:
            patient_ids: List of patient IDs to warm
            data_generator_func: Async function that generates cache data for a patient
        """
        total_warmed = 0

        for patient_id in patient_ids:
            try:
                # Generate data for patient
                insights, recommendations = await data_generator_func(patient_id)

                # Warm cache
                warmed = await self.warm_patient_cache(
                    patient_id,
                    insights,
                    recommendations
                )
                total_warmed += warmed
            except Exception as e:
                logger.error(f"Failed to warm cache for patient {patient_id}: {e}")

        logger.info(f"Cache warming completed: {total_warmed} entries for {len(patient_ids)} patients")
        return total_warmed

    async def get_metrics(self) -> Dict[str, Any]:
        """Get cache performance metrics."""
        client = await self.get_client()

        metrics_data = {
            "cache_metrics": self.metrics.to_dict(),
            "redis_available": client is not None,
            "ttl_config": {
                "insights": self.TTL_INSIGHTS,
                "recommendations": self.TTL_RECOMMENDATIONS,
                "summary": self.TTL_SUMMARY,
                "analysis": self.TTL_ANALYSIS
            }
        }

        if client:
            try:
                info = await client.info("memory")
                metrics_data["redis_memory"] = {
                    "used_memory_human": info.get("used_memory_human", "unknown"),
                    "used_memory_peak_human": info.get("used_memory_peak_human", "unknown"),
                    "fragmentation_ratio": info.get("mem_fragmentation_ratio", 0)
                }
            except Exception as e:
                logger.error(f"Failed to get Redis memory info: {e}")

        return metrics_data

    async def health_check(self) -> Dict[str, Any]:
        """Check cache service health."""
        client = await self.get_client()

        health_data = {
            "status": "healthy" if client else "degraded",
            "redis_connected": False,
            "timestamp": datetime.utcnow().isoformat()
        }

        if client:
            try:
                await client.ping()
                health_data["redis_connected"] = True
                health_data["status"] = "healthy"
            except Exception as e:
                health_data["status"] = "unhealthy"
                health_data["error"] = str(e)

        return health_data

    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("AI Redis cache client closed")


# Global cache service instance
_ai_cache_service: Optional[AIRedisCacheService] = None


async def get_ai_cache_service() -> AIRedisCacheService:
    """Get or create the global AI cache service instance."""
    global _ai_cache_service
    if _ai_cache_service is None:
        _ai_cache_service = AIRedisCacheService()
    return _ai_cache_service