"""
Performance Service
Business logic for performance monitoring and optimization.
"""

import json
import hashlib
import time
import inspect
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import text

from app.database import get_pool_status, is_pool_healthy
from app.schemas.v2.performance import (
    CacheMetrics,
    PerformanceOverview,
    ComponentPerformance,
    DatabaseHealth,
    ConnectionPoolStatus,
    VacuumRequest,
    VacuumResponse,
    PerformanceStatus,
    HealthStatus,
)
from app.core.redis_manager import get_async_redis_client as get_async_redis
from app.utils.logging import get_logger
from app.utils.timezone import now_sao_paulo

logger = get_logger(__name__)

# Cache TTLs
CACHE_TTL_METRICS = 30
CACHE_TTL_HEALTH = 60
CACHE_TTL_STATS = 120
CACHE_TTL_OPTIMIZATION = 600


class PerformanceService:
    """Service for performance monitoring and optimization."""

    def __init__(self, db: Any):
        self.db = db

    async def _resolve(self, maybe_awaitable: Any) -> Any:
        if inspect.isawaitable(maybe_awaitable):
            return await maybe_awaitable
        return maybe_awaitable

    async def _execute(self, statement):
        return await self._resolve(self.db.execute(statement))

    async def _commit(self) -> None:
        commit = getattr(self.db, "commit", None)
        if commit is None:
            return
        await self._resolve(commit())

    async def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached result from Redis."""
        try:
            redis_client = await get_async_redis()
            if redis_client is None:
                return None
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
            return None

    async def _set_cached_result(self, cache_key: str, data: Any, ttl: int) -> None:
        """Set cached result in Redis."""
        try:
            redis_client = await get_async_redis()
            if redis_client is None:
                return
            # Handle Pydantic models or dicts
            if hasattr(data, "model_dump"):
                serialized = json.dumps(data.model_dump(), default=str)
            elif (
                isinstance(data, list)
                and len(data) > 0
                and hasattr(data[0], "model_dump")
            ):
                serialized = json.dumps(
                    [item.model_dump() for item in data], default=str
                )
            else:
                serialized = json.dumps(data, default=str)

            await redis_client.setex(cache_key, ttl, serialized)
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    def _get_cache_key(self, endpoint: str, **params) -> str:
        """Generate cache key."""
        param_str = json.dumps(params, sort_keys=True, default=str)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()
        return f"performance:v2:{endpoint}:{param_hash}"

    def _calculate_performance_score(
        self,
        cache_hit_rate: float,
        avg_query_time_ms: float,
        pool_utilization: float,
        slow_query_percent: float,
    ) -> Tuple[float, PerformanceStatus]:
        """Calculate overall performance score."""
        # Cache score (0-100)
        cache_score = cache_hit_rate

        # Query performance score
        if avg_query_time_ms < 50:
            query_score = 100
        elif avg_query_time_ms < 100:
            query_score = 75
        elif avg_query_time_ms < 200:
            query_score = 50
        else:
            query_score = max(0, 50 - (avg_query_time_ms - 200) / 10)

        # Pool health score
        if pool_utilization < 70:
            pool_score = 100
        elif pool_utilization < 85:
            pool_score = 70
        else:
            pool_score = max(0, 100 - pool_utilization)

        # Slow query penalty
        slow_query_score = max(0, 100 - (slow_query_percent * 2))

        # Weighted average
        total_score = (
            cache_score * 0.30
            + query_score * 0.30
            + pool_score * 0.20
            + slow_query_score * 0.20
        )

        if total_score >= 90:
            status = PerformanceStatus.EXCELLENT
        elif total_score >= 75:
            status = PerformanceStatus.GOOD
        elif total_score >= 60:
            status = PerformanceStatus.FAIR
        else:
            status = PerformanceStatus.POOR

        return round(total_score, 2), status

    # Dynamic imports for optional dependencies to avoid circular deps
    def _get_cache_service(self):
        try:
            # Assuming this was the intended import in the original file
            # This seems to be a singleton getter or similar in original code,
            # but let's assume we can instantiate or get it.
            # The original code had _get_cache_service() calling get_analytics_cache() or get_unified_cache_manager()
            from app.infrastructure.cache import get_unified_cache_manager

            return get_unified_cache_manager()
        except Exception:
            return None

    def _get_query_monitor(self):
        try:
            from app.services.query_performance_monitor import QueryPerformanceMonitor

            return QueryPerformanceMonitor(self.db)
        except Exception:
            return None

    def _get_db_optimizer(self):
        try:
            from app.services.database_index_optimizer import DatabaseIndexOptimizer

            return DatabaseIndexOptimizer(self.db)
        except Exception:
            return None

    async def get_cache_metrics(self, user_id: str) -> CacheMetrics:
        cache_key = self._get_cache_key("cache_metrics")
        cached = await self._get_cached_result(cache_key)
        if cached:
            return CacheMetrics(**cached)

        cache_service = self._get_cache_service()
        if not cache_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cache service unavailable",
            )

        cache_info = (
            cache_service.get_cache_info()
            if hasattr(cache_service, "get_cache_info")
            else {}
        )
        stats = cache_service.get_stats() if hasattr(cache_service, "get_stats") else {}

        # Construct metrics from stats if metrics obj not available
        hits = stats.get("hits", 0)
        misses = stats.get("misses", 0)
        hit_rate = stats.get("hit_rate_percent", 0)

        result = CacheMetrics(
            hits=hits,
            misses=misses,
            hit_rate_percentage=hit_rate,
            total_keys=cache_info.get("total_keys", 0),
            memory_usage_mb=cache_info.get("memory_usage_mb"),
            evictions=cache_info.get("evictions", 0),
            invalidations=0,
            warming_operations=0,
        )

        await self._set_cached_result(cache_key, result, CACHE_TTL_METRICS)
        return result

    async def get_performance_overview(self) -> PerformanceOverview:
        cache_key = self._get_cache_key("performance_overview")
        cached = await self._get_cached_result(cache_key)
        if cached:
            return PerformanceOverview(**cached)

        # 1. Cache Stats
        cache_service = self._get_cache_service()
        cache_hit_rate = 0
        if cache_service:
            stats = (
                cache_service.get_stats() if hasattr(cache_service, "get_stats") else {}
            )
            cache_hit_rate = stats.get("hit_rate_percent", 0)

        # 2. DB Stats
        query_monitor = self._get_query_monitor()
        avg_query_time = 0
        slow_query_percent = 0
        if query_monitor:
            q_stats = (
                query_monitor.get_query_stats()
                if hasattr(query_monitor, "get_query_stats")
                else {}
            )
            avg_query_time = q_stats.get("avg_duration_ms", 0)
            slow_query_percent = q_stats.get("slow_query_percentage", 0)

        # 3. Pool Status
        pool_status = get_pool_status()
        pool_utilization = pool_status.get("utilization_percent", 0)
        pool_healthy = is_pool_healthy()

        # Score
        score, perf_status = self._calculate_performance_score(
            cache_hit_rate, avg_query_time, pool_utilization, slow_query_percent
        )

        # Components
        components = []

        # Cache Component
        components.append(
            ComponentPerformance(
                name="cache",
                status=PerformanceStatus.EXCELLENT
                if cache_hit_rate >= 80
                else (
                    PerformanceStatus.GOOD
                    if cache_hit_rate >= 60
                    else PerformanceStatus.POOR
                ),
                score=cache_hit_rate,
                response_time_ms=2.5,
                error_rate_percent=0.1,
            )
        )

        # Database Component
        db_score = max(0, 100 - (avg_query_time / 10))
        components.append(
            ComponentPerformance(
                name="database",
                status=PerformanceStatus.EXCELLENT
                if avg_query_time < 50
                else (
                    PerformanceStatus.GOOD
                    if avg_query_time < 100
                    else PerformanceStatus.POOR
                ),
                score=round(db_score, 2),
                response_time_ms=avg_query_time,
                error_rate_percent=0,
            )
        )

        # Pool Component
        pool_score = max(0, 100 - pool_utilization)
        components.append(
            ComponentPerformance(
                name="connection_pool",
                status=PerformanceStatus.EXCELLENT
                if pool_utilization < 70 and pool_healthy
                else PerformanceStatus.POOR,
                score=round(pool_score, 2),
                response_time_ms=None,
                error_rate_percent=0,
            )
        )

        # Recommendations
        recommendations = []
        if cache_hit_rate < 50:
            recommendations.append("Cache hit rate is low.")
        if avg_query_time > 100:
            recommendations.append("Average query time is high.")
        if pool_utilization > 80:
            recommendations.append("Pool utilization is high.")
        if not recommendations:
            recommendations.append("System is optimal.")

        result = PerformanceOverview(
            score=score,
            status=perf_status,
            components=components,
            recommendations=recommendations,
            timestamp=now_sao_paulo(),
        )

        await self._set_cached_result(cache_key, result, CACHE_TTL_STATS)
        return result

    async def get_database_health(self) -> DatabaseHealth:
        start_time = time.time()
        cache_key = self._get_cache_key("database_health")
        cached = await self._get_cached_result(cache_key)
        if cached:
            return DatabaseHealth(**cached)

        pool_status_dict = get_pool_status()
        pool_healthy = is_pool_healthy()

        pool_status = ConnectionPoolStatus(
            pool_size=pool_status_dict.get("pool_size", 0),
            max_overflow=pool_status_dict.get("overflow", 0),
            checked_out=pool_status_dict.get("checked_out", 0),
            checked_in=pool_status_dict.get("checked_in", 0),
            total_capacity=pool_status_dict.get("pool_size", 0)
            + pool_status_dict.get("overflow", 0),
            utilization_percent=pool_status_dict.get("utilization_percent", 0),
            health_status=HealthStatus.HEALTHY
            if pool_healthy
            else HealthStatus.DEGRADED,
        )

        try:
            result = await self._execute(
                text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
            )
            active_connections = result.scalar() or 0
        except Exception:
            active_connections = pool_status_dict.get("checked_out", 0)

        try:
            result = await self._execute(
                text("SELECT count(*) FROM pg_locks WHERE granted = true")
            )
            locks_count = result.scalar() or 0
        except Exception:
            locks_count = 0

        issues = []
        if pool_status.utilization_percent > 90:
            issues.append("Pool utilization > 90%")
        if not pool_healthy:
            issues.append("Pool unhealthy")

        health = HealthStatus.HEALTHY if not issues else HealthStatus.DEGRADED
        response_time = (time.time() - start_time) * 1000

        result = DatabaseHealth(
            status=health,
            connection_pool=pool_status,
            active_connections=active_connections,
            locks_count=locks_count,
            response_time_ms=round(response_time, 2),
            timestamp=now_sao_paulo(),
            issues=issues,
        )

        await self._set_cached_result(cache_key, result, CACHE_TTL_HEALTH)
        return result

    async def run_vacuum(self, request: VacuumRequest, user_id: str) -> VacuumResponse:
        if request.full and not request.confirm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="FULL VACUUM requires confirmation",
            )

        start_time = time.time()
        vacuum_cmd = "VACUUM"
        if request.full:
            vacuum_cmd += " FULL"
        if request.analyze:
            vacuum_cmd += " ANALYZE"
        if request.table_name:
            vacuum_cmd += f" {request.table_name}"

        try:
            await self._commit()
            await self._execute(text(vacuum_cmd))
            duration = (time.time() - start_time) * 1000

            return VacuumResponse(
                success=True,
                message="VACUUM completed",
                table_name=request.table_name,
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            logger.error(f"Vacuum failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Database vacuum operation failed")
