"""
Performance Monitoring API v2
Unified performance monitoring system consolidating cache, database health, and optimization.
"""

import asyncio
import json
import hashlib
import logging
import time
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.database import get_db, get_pool_status, is_pool_healthy
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.models.user import User, UserRole
from app.schemas.v2.performance import (
    # Cache
    CacheMetrics,
    CacheStats,
    CacheInvalidationRequest,
    CacheInvalidationResponse,
    CacheClearResponse,
    # Performance
    PerformanceOverview,
    ComponentPerformance,
    DatabasePerformance,
    APIPerformance,
    SlowQuery,
    SlowQueriesResponse,
    OptimizationRecommendation,
    # Database Health
    DatabaseHealth,
    ConnectionPoolStatus,
    ActiveConnection,
    ActiveConnectionsResponse,
    DatabaseLock,
    DatabaseLocksResponse,
    # Database Optimization
    IndexRecommendation,
    IndexAnalysis,
    VacuumRequest,
    VacuumResponse,
    TableStatistics,
    OptimizationSuggestion,
    # Enums
    PerformanceStatus,
    HealthStatus,
    OptimizationBenefit,
    IndexType,
)
from app.utils.logging import get_logger
from app.services.unified_cache import UnifiedCacheService

logger = get_logger(__name__)
router = APIRouter()

# Cache TTLs (short for real-time monitoring)
CACHE_TTL_METRICS = 30  # 30 seconds for real-time metrics
CACHE_TTL_HEALTH = 60  # 1 minute for health checks
CACHE_TTL_STATS = 120  # 2 minutes for statistics
CACHE_TTL_OPTIMIZATION = 600  # 10 minutes for optimization suggestions

# Rate limit configuration
RATE_LIMIT_STANDARD = 50  # requests per minute for monitoring
RATE_LIMIT_EXPENSIVE = 10  # requests per minute for expensive operations


# ============================================================================
# Helper Functions
# ============================================================================

def _get_cache_key(endpoint: str, **params) -> str:
    """Generate cache key from endpoint and parameters."""
    param_str = json.dumps(params, sort_keys=True, default=str)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()
    return f"performance:v2:{endpoint}:{param_hash}"


async def _get_cached_result(cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached result from Redis."""
    try:
        from app.core.redis_unified import get_async_redis
        redis_client = await get_async_redis()
        if redis_client is None:
            return None
        cached = await redis_client.get(cache_key)
        if cached:
            logger.debug(f"Cache HIT: {cache_key}")
            return json.loads(cached)
        logger.debug(f"Cache MISS: {cache_key}")
        return None
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")
        return None


async def _set_cached_result(cache_key: str, data: dict, ttl: int) -> None:
    """Set cached result in Redis."""
    try:
        from app.core.redis_unified import get_async_redis
        redis_client = await get_async_redis()
        if redis_client is None:
            return
        await redis_client.setex(cache_key, ttl, json.dumps(data, default=str))
        logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")


def _check_admin_role(current_user: User) -> None:
    """Check if user has admin role."""
    if isinstance(current_user, dict):
        role = current_user.get("role", "").upper()
    else:
        role = getattr(current_user, "role", "").upper() if hasattr(current_user, "role") else ""

    if role != "ADMIN" and role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )


def _calculate_performance_score(
    cache_hit_rate: float,
    avg_query_time_ms: float,
    pool_utilization: float,
    slow_query_percent: float
) -> Tuple[float, PerformanceStatus]:
    """
    Calculate overall performance score (0-100).

    Weighted average:
    - Cache hit rate: 30%
    - DB query performance: 30%
    - Connection pool health: 20%
    - API latency: 20% (using query time as proxy)
    """
    # Cache score (0-100)
    cache_score = cache_hit_rate  # Already a percentage

    # Query performance score (0-100)
    # Good: < 50ms, Fair: < 100ms, Poor: >= 100ms
    if avg_query_time_ms < 50:
        query_score = 100
    elif avg_query_time_ms < 100:
        query_score = 75
    elif avg_query_time_ms < 200:
        query_score = 50
    else:
        query_score = max(0, 50 - (avg_query_time_ms - 200) / 10)

    # Pool health score (0-100)
    # Good: < 70%, Fair: < 85%, Poor: >= 85%
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
        cache_score * 0.30 +
        query_score * 0.30 +
        pool_score * 0.20 +
        slow_query_score * 0.20
    )

    # Determine status
    if total_score >= 90:
        perf_status = PerformanceStatus.EXCELLENT
    elif total_score >= 75:
        perf_status = PerformanceStatus.GOOD
    elif total_score >= 60:
        perf_status = PerformanceStatus.FAIR
    else:
        perf_status = PerformanceStatus.POOR

    return round(total_score, 2), perf_status


def _get_cache_service():
    """Get cache service (analytics cache or unified cache)."""
    try:
        
        return get_analytics_cache()
    except Exception:
        try:
            from app.utils.unified_cache import get_unified_cache_manager
            return get_unified_cache_manager()
        except Exception as e:
            logger.error(f"Failed to get cache service: {e}")
            return None


def _get_cache_invalidation_service():
    """Get cache invalidation service."""
    try:
        
        return get_cache_invalidation_service()
    except Exception as e:
        logger.error(f"Failed to get cache invalidation service: {e}")
        return None


def _get_db_optimizer(db: Session):
    """Get database optimizer service."""
    try:
        from app.services.database_index_optimizer import DatabaseIndexOptimizer
        return DatabaseIndexOptimizer(db)
    except Exception as e:
        logger.error(f"Failed to get database optimizer: {e}")
        return None


def _get_query_monitor(db: Session):
    """Get query performance monitor."""
    try:
        from app.services.query_performance_monitor import QueryPerformanceMonitor
        return QueryPerformanceMonitor(db)
    except Exception as e:
        logger.error(f"Failed to get query monitor: {e}")
        return None


# ============================================================================
# Cache Monitoring Endpoints (4 endpoints)
# ============================================================================

@router.get(
    "/cache/metrics",
    response_model=CacheMetrics,
    summary="Get cache performance metrics",
    description="Get comprehensive cache performance metrics and statistics"
)
async def get_cache_metrics(
    current_user: User = Depends(get_current_user_from_session),
) -> CacheMetrics:
    """Get cache performance metrics."""
    try:
        # Check cache first
        cache_key = _get_cache_key("cache_metrics")
        cached = await _get_cached_result(cache_key)
        if cached:
            return CacheMetrics(**cached)

        cache_service = _get_cache_service()
        if not cache_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cache service unavailable"
            )

        # Get cache information
        cache_info = cache_service.get_cache_info() if hasattr(cache_service, 'get_cache_info') else {}
        metrics = cache_service.get_metrics() if hasattr(cache_service, 'get_metrics') else None
        stats = cache_service.get_stats() if hasattr(cache_service, 'get_stats') else None

        # Build response from available data
        if metrics:
            hits = getattr(metrics, 'hits', 0)
            misses = getattr(metrics, 'misses', 0)
            hit_rate = getattr(metrics, 'hit_rate', 0)
            invalidations = getattr(metrics, 'invalidations', 0)
            warming_operations = getattr(metrics, 'warming_operations', 0)
        elif stats:
            hits = stats.get('hits', 0)
            misses = stats.get('misses', 0)
            hit_rate = stats.get('hit_rate_percent', 0)
            invalidations = 0
            warming_operations = 0
        else:
            hits = 0
            misses = 0
            hit_rate = 0
            invalidations = 0
            warming_operations = 0

        result = CacheMetrics(
            hits=hits,
            misses=misses,
            hit_rate_percentage=hit_rate,
            total_keys=cache_info.get("total_keys", 0),
            memory_usage_mb=cache_info.get("memory_usage_mb"),
            evictions=cache_info.get("evictions", 0),
            invalidations=invalidations,
            warming_operations=warming_operations
        )

        # Cache result
        await _set_cached_result(cache_key, result.model_dump(), CACHE_TTL_METRICS)

        logger.info(f"Cache metrics retrieved by user {getattr(current_user, 'id', 'unknown')}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cache metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cache metrics"
        )


@router.get(
    "/cache/stats",
    response_model=CacheStats,
    summary="Get cache statistics",
    description="Get cache statistics including hit rate and performance"
)
async def get_cache_stats(
    current_user: User = Depends(get_current_user_from_session),
) -> CacheStats:
    """Get cache statistics."""
    try:
        # Check cache first
        cache_key = _get_cache_key("cache_stats")
        cached = await _get_cached_result(cache_key)
        if cached:
            return CacheStats(**cached)

        cache_service = _get_cache_service()
        if not cache_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cache service unavailable"
            )

        stats = cache_service.get_stats() if hasattr(cache_service, 'get_stats') else {}

        hits = stats.get('hits', 0)
        misses = stats.get('misses', 0)
        errors = stats.get('errors', 0)
        hit_rate = stats.get('hit_rate_percent', 0)
        total_ops = hits + misses

        # Determine health status
        if hit_rate >= 70:
            health = HealthStatus.HEALTHY
        elif hit_rate >= 50:
            health = HealthStatus.DEGRADED
        else:
            health = HealthStatus.CRITICAL

        result = CacheStats(
            hits=hits,
            misses=misses,
            errors=errors,
            hit_rate_percent=hit_rate,
            total_operations=total_ops,
            avg_response_time_ms=stats.get('avg_response_time_ms', 2.0),
            status=health
        )

        # Cache result
        await _set_cached_result(cache_key, result.model_dump(), CACHE_TTL_STATS)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cache statistics"
        )


@router.post(
    "/cache/invalidate",
    response_model=CacheInvalidationResponse,
    summary="Invalidate cache entries",
    description="Manually invalidate cache entries for specific types or doctors (Admin only)"
)
async def invalidate_cache(
    request: CacheInvalidationRequest,
    current_user: User = Depends(get_current_user_from_session),
) -> CacheInvalidationResponse:
    """Manually invalidate cache entries."""
    _check_admin_role(current_user)

    try:
        invalidation_service = _get_cache_invalidation_service()
        cache_service = _get_cache_service()

        invalidated_count = 0

        if request.cache_type:
            # Invalidate specific cache type
            if invalidation_service:
                if request.cache_type == "dashboard":
                    invalidation_service.invalidate_dashboard_cache(request.doctor_id)
                elif request.cache_type == "analytics":
                    invalidation_service.invalidate_analytics_cache(request.doctor_id)
                elif request.cache_type == "treatment_distribution":
                    invalidation_service.invalidate_treatment_distribution_cache(request.doctor_id)
                elif request.cache_type == "patterns":
                    invalidation_service.invalidate_patterns_cache()
                else:
                    # Generic invalidation
                    if cache_service and hasattr(cache_service, 'invalidate'):
                        invalidated_count = cache_service.invalidate(request.cache_type)
            elif cache_service and hasattr(cache_service, 'invalidate'):
                invalidated_count = cache_service.invalidate(request.cache_type)
        elif request.pattern:
            # Pattern-based invalidation
            from app.core.redis_unified import get_async_redis
            redis = await get_async_redis()
            if redis:
                keys = await redis.keys(request.pattern)
                if keys:
                    await redis.delete(*keys)
                    invalidated_count = len(keys)
        elif request.keys:
            # Specific keys invalidation
            from app.core.redis_unified import get_async_redis
            redis = await get_async_redis()
            if redis and request.keys:
                await redis.delete(*request.keys)
                invalidated_count = len(request.keys)
        else:
            # Clear all caches
            if invalidation_service and request.doctor_id:
                invalidation_service.invalidate_dashboard_cache(request.doctor_id)
                invalidation_service.invalidate_analytics_cache(request.doctor_id)
                invalidation_service.invalidate_treatment_distribution_cache(request.doctor_id)
            elif cache_service and hasattr(cache_service, 'clear_all'):
                invalidated_count = await cache_service.clear_all() if asyncio.iscoroutinefunction(cache_service.clear_all) else cache_service.clear_all()

        logger.warning(
            f"Cache invalidated by admin {getattr(current_user, 'id', 'unknown')}: "
            f"type={request.cache_type}, doctor_id={request.doctor_id}, count={invalidated_count}"
        )

        return CacheInvalidationResponse(
            success=True,
            message="Cache invalidated successfully",
            cache_type=request.cache_type,
            doctor_id=str(request.doctor_id) if request.doctor_id else None,
            invalidated_count=invalidated_count
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invalidate cache"
        )


@router.delete(
    "/cache/clear",
    response_model=CacheClearResponse,
    summary="Clear all cache data",
    description="Clear all cache data (Admin only - use with caution)"
)
async def clear_cache(
    current_user: User = Depends(get_current_user_from_session),
) -> CacheClearResponse:
    """Clear all cache data."""
    _check_admin_role(current_user)

    try:
        cache_service = _get_cache_service()

        if cache_service and hasattr(cache_service, 'clear_all'):
            if asyncio.iscoroutinefunction(cache_service.clear_all):
                success = await cache_service.clear_all()
            else:
                success = cache_service.clear_all()

            # Get count if available
            cleared_count = 0
            if hasattr(cache_service, 'get_cache_info'):
                info = cache_service.get_cache_info()
                cleared_count = info.get('total_keys', 0)
        else:
            # Fallback to Redis direct clear
            from app.core.redis_unified import get_async_redis
            redis = await get_async_redis()
            if redis:
                await redis.flushdb()
                success = True
                cleared_count = 0
            else:
                success = False
                cleared_count = 0

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to clear cache"
            )

        logger.warning(f"Cache cleared by admin {getattr(current_user, 'id', 'unknown')}")

        return CacheClearResponse(
            success=True,
            message="Cache cleared successfully",
            cleared_count=cleared_count
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )


# ============================================================================
# Performance Overview Endpoints (5 endpoints)
# ============================================================================

@router.get(
    "/overview",
    response_model=PerformanceOverview,
    summary="Get overall performance overview",
    description="Get comprehensive system performance overview with scoring"
)
async def get_performance_overview(
    current_user: User = Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
) -> PerformanceOverview:
    """Get overall system performance overview."""
    try:
        # Check cache first
        cache_key = _get_cache_key("performance_overview")
        cached = await _get_cached_result(cache_key)
        if cached:
            return PerformanceOverview(**cached)

        # Get cache stats
        cache_service = _get_cache_service()
        if cache_service:
            cache_stats = cache_service.get_stats() if hasattr(cache_service, 'get_stats') else {}
            cache_hit_rate = cache_stats.get('hit_rate_percent', 0)
        else:
            cache_hit_rate = 0

        # Get database stats
        query_monitor = _get_query_monitor(db)
        if query_monitor:
            query_stats = query_monitor.get_query_stats() if hasattr(query_monitor, 'get_query_stats') else {}
            avg_query_time = query_stats.get('avg_duration_ms', 0)
            slow_query_percent = query_stats.get('slow_query_percentage', 0)
        else:
            avg_query_time = 0
            slow_query_percent = 0

        # Get pool status
        pool_status = get_pool_status()
        pool_utilization = pool_status.get('utilization_percent', 0)
        pool_healthy = is_pool_healthy()

        # Calculate overall performance score
        score, perf_status = _calculate_performance_score(
            cache_hit_rate,
            avg_query_time,
            pool_utilization,
            slow_query_percent
        )

        # Build component metrics
        components = []

        # Cache component
        if cache_hit_rate >= 80:
            cache_status = PerformanceStatus.EXCELLENT
        elif cache_hit_rate >= 60:
            cache_status = PerformanceStatus.GOOD
        elif cache_hit_rate >= 40:
            cache_status = PerformanceStatus.FAIR
        else:
            cache_status = PerformanceStatus.POOR

        components.append(ComponentPerformance(
            name="cache",
            status=cache_status,
            score=cache_hit_rate,
            response_time_ms=2.5,
            error_rate_percent=0.1
        ))

        # Database component
        if avg_query_time < 50:
            db_status = PerformanceStatus.EXCELLENT
        elif avg_query_time < 100:
            db_status = PerformanceStatus.GOOD
        elif avg_query_time < 200:
            db_status = PerformanceStatus.FAIR
        else:
            db_status = PerformanceStatus.POOR

        db_score = max(0, 100 - (avg_query_time / 10))

        components.append(ComponentPerformance(
            name="database",
            status=db_status,
            score=round(db_score, 2),
            response_time_ms=avg_query_time,
            error_rate_percent=0
        ))

        # Connection pool component
        if pool_utilization < 70 and pool_healthy:
            pool_status_enum = PerformanceStatus.EXCELLENT
        elif pool_utilization < 85 and pool_healthy:
            pool_status_enum = PerformanceStatus.GOOD
        elif pool_utilization < 95:
            pool_status_enum = PerformanceStatus.FAIR
        else:
            pool_status_enum = PerformanceStatus.POOR

        pool_score = max(0, 100 - pool_utilization)

        components.append(ComponentPerformance(
            name="connection_pool",
            status=pool_status_enum,
            score=round(pool_score, 2),
            response_time_ms=None,
            error_rate_percent=0
        ))

        # Generate recommendations
        recommendations = []
        if cache_hit_rate < 50:
            recommendations.append("Cache hit rate is low. Consider increasing cache TTL or reviewing cache strategy.")
        if avg_query_time > 100:
            recommendations.append("Average query time is high. Review database indexes and query optimization.")
        if pool_utilization > 80:
            recommendations.append("Database connection pool utilization is high. Consider increasing pool size.")
        if slow_query_percent > 10:
            recommendations.append("High percentage of slow queries detected. Review slow query log.")
        if not recommendations:
            recommendations.append("System performance is optimal. No immediate recommendations.")

        result = PerformanceOverview(
            score=score,
            status=perf_status,
            components=components,
            recommendations=recommendations,
            timestamp=datetime.now(timezone.utc)
        )

        # Cache result
        await _set_cached_result(cache_key, result.model_dump(), CACHE_TTL_STATS)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting performance overview: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve performance overview"
        )


@router.get(
    "/database",
    response_model=DatabasePerformance,
    summary="Get database performance metrics",
    description="Get database performance metrics including query times and pool status"
)
async def get_database_performance(
    current_user: User = Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
) -> DatabasePerformance:
    """Get database performance metrics."""
    try:
        # Check cache first
        cache_key = _get_cache_key("database_performance")
        cached = await _get_cached_result(cache_key)
        if cached:
            return DatabasePerformance(**cached)

        # Get query stats
        query_monitor = _get_query_monitor(db)
        if query_monitor:
            query_stats = query_monitor.get_query_stats() if hasattr(query_monitor, 'get_query_stats') else {}
            query_metrics = query_monitor.get_performance_metrics() if hasattr(query_monitor, 'get_performance_metrics') else None

            if query_metrics:
                avg_query_time = query_metrics.avg_duration_ms
                slow_query_count = query_metrics.slow_queries
                total_queries = query_metrics.total_queries
            else:
                avg_query_time = query_stats.get('avg_duration_ms', 0)
                slow_query_count = query_stats.get('slow_queries', 0)
                total_queries = query_stats.get('total_queries', 0)

            slow_query_percentage = query_stats.get('slow_query_percentage', 0)
        else:
            avg_query_time = 0
            slow_query_count = 0
            slow_query_percentage = 0
            total_queries = 0

        # Get pool status
        pool_status = get_pool_status()
        pool_utilization = pool_status.get('utilization_percent', 0)
        pool_healthy = is_pool_healthy()
        active_connections = pool_status.get('checked_out', 0)

        result = DatabasePerformance(
            avg_query_time_ms=avg_query_time,
            slow_query_count=slow_query_count,
            slow_query_percentage=slow_query_percentage,
            pool_utilization_percent=pool_utilization,
            active_connections=active_connections,
            pool_healthy=pool_healthy,
            total_queries=total_queries
        )

        # Cache result
        await _set_cached_result(cache_key, result.model_dump(), CACHE_TTL_STATS)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting database performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve database performance"
        )


@router.get(
    "/api",
    response_model=List[APIPerformance],
    summary="Get API endpoint performance",
    description="Get API endpoint latency statistics and error rates"
)
async def get_api_performance(
    current_user: User = Depends(get_current_user_from_session),
    limit: int = Query(20, ge=1, le=100, description="Number of endpoints to return"),
) -> List[APIPerformance]:
    """Get API endpoint performance metrics."""
    try:
        # Check cache first
        cache_key = _get_cache_key("api_performance", limit=limit)
        cached = await _get_cached_result(cache_key)
        if cached:
            return [APIPerformance(**item) for item in cached]

        # TODO: Implement API performance tracking
        # For now, return mock data
        result = [
            APIPerformance(
                endpoint="/api/v2/patients",
                avg_latency_ms=125.5,
                request_count=1542,
                error_count=3,
                error_rate_percent=0.19,
                p95_latency_ms=250.0,
                p99_latency_ms=450.0
            )
        ]

        # Cache result
        await _set_cached_result(cache_key, [r.model_dump() for r in result], CACHE_TTL_STATS)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting API performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API performance"
        )


@router.get(
    "/queries",
    response_model=SlowQueriesResponse,
    summary="Get slow query analysis",
    description="Get slow query analysis with optimization suggestions"
)
async def get_slow_queries(
    current_user: User = Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100, description="Number of queries to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> SlowQueriesResponse:
    """Get slow query analysis."""
    try:
        # Check cache first
        cache_key = _get_cache_key("slow_queries", limit=limit, offset=offset)
        cached = await _get_cached_result(cache_key)
        if cached:
            return SlowQueriesResponse(**cached)

        query_monitor = _get_query_monitor(db)
        if not query_monitor:
            return SlowQueriesResponse(
                queries=[],
                total=0,
                limit=limit,
                offset=offset,
                has_more=False
            )

        # Get slow queries
        slow_queries_list = query_monitor.identify_slow_queries(limit=limit + 1) if hasattr(query_monitor, 'identify_slow_queries') else []

        # Convert to schema
        queries = []
        for sq in slow_queries_list[:limit]:
            queries.append(SlowQuery(
                query_text=getattr(sq, 'query_text', ''),
                avg_duration_ms=getattr(sq, 'avg_duration_ms', 0),
                execution_count=getattr(sq, 'execution_count', 0),
                total_duration_ms=getattr(sq, 'total_duration_ms', 0),
                suggestion=getattr(sq, 'suggestion', None),
                tables_involved=getattr(sq, 'tables_involved', [])
            ))

        total = len(slow_queries_list)
        has_more = total > limit

        result = SlowQueriesResponse(
            queries=queries,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more
        )

        # Cache result
        await _set_cached_result(cache_key, result.model_dump(), CACHE_TTL_STATS)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting slow queries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve slow queries"
        )


@router.get(
    "/recommendations",
    response_model=List[OptimizationRecommendation],
    summary="Get performance optimization recommendations",
    description="Get performance optimization recommendations based on current metrics"
)
async def get_optimization_recommendations(
    current_user: User = Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
) -> List[OptimizationRecommendation]:
    """Get performance optimization recommendations."""
    try:
        # Check cache first
        cache_key = _get_cache_key("optimization_recommendations")
        cached = await _get_cached_result(cache_key)
        if cached:
            return [OptimizationRecommendation(**item) for item in cached]

        recommendations = []

        # Cache recommendations
        cache_service = _get_cache_service()
        if cache_service:
            cache_stats = cache_service.get_stats() if hasattr(cache_service, 'get_stats') else {}
            cache_hit_rate = cache_stats.get('hit_rate_percent', 0)

            if cache_hit_rate < 50:
                recommendations.append(OptimizationRecommendation(
                    type="cache",
                    severity="high",
                    title="Low cache hit rate",
                    description="Cache hit rate is below 50%. Consider increasing cache TTL or reviewing cache strategy.",
                    impact=OptimizationBenefit.HIGH,
                    effort="low",
                    action_items=[
                        "Review cache TTL settings",
                        "Analyze cache invalidation patterns",
                        "Consider warming frequently accessed data"
                    ]
                ))

        # Database recommendations
        query_monitor = _get_query_monitor(db)
        if query_monitor:
            query_stats = query_monitor.get_query_stats() if hasattr(query_monitor, 'get_query_stats') else {}
            slow_query_percent = query_stats.get('slow_query_percentage', 0)

            if slow_query_percent > 10:
                recommendations.append(OptimizationRecommendation(
                    type="database",
                    severity="high",
                    title="High percentage of slow queries",
                    description=f"{slow_query_percent}% of queries are slow. Review database indexes and query optimization.",
                    impact=OptimizationBenefit.HIGH,
                    effort="medium",
                    action_items=[
                        "Review slow query log",
                        "Analyze missing indexes",
                        "Optimize N+1 query patterns"
                    ]
                ))

        # Pool recommendations
        pool_status = get_pool_status()
        pool_utilization = pool_status.get('utilization_percent', 0)

        if pool_utilization > 80:
            recommendations.append(OptimizationRecommendation(
                type="connection_pool",
                severity="medium",
                title="High connection pool utilization",
                description=f"Connection pool utilization is at {pool_utilization}%. Consider increasing pool size.",
                impact=OptimizationBenefit.MEDIUM,
                effort="low",
                action_items=[
                    "Increase pool size configuration",
                    "Review connection leak patterns",
                    "Optimize long-running queries"
                ]
            ))

        # Cache result
        await _set_cached_result(cache_key, [r.model_dump() for r in recommendations], CACHE_TTL_OPTIMIZATION)

        return recommendations

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting optimization recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve optimization recommendations"
        )


# ============================================================================
# Database Health Endpoints (4 endpoints)
# ============================================================================

@router.get(
    "/database/health",
    response_model=DatabaseHealth,
    summary="Get database health status",
    description="Get comprehensive database health check including pool and connections"
)
async def get_database_health(
    current_user: User = Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
) -> DatabaseHealth:
    """Get database health status."""
    start_time = time.time()

    try:
        # Check cache first
        cache_key = _get_cache_key("database_health")
        cached = await _get_cached_result(cache_key)
        if cached:
            return DatabaseHealth(**cached)

        # Get pool status
        pool_status_dict = get_pool_status()
        pool_healthy = is_pool_healthy()

        pool_status = ConnectionPoolStatus(
            pool_size=pool_status_dict.get('pool_size', 0),
            max_overflow=pool_status_dict.get('overflow', 0),
            checked_out=pool_status_dict.get('checked_out', 0),
            checked_in=pool_status_dict.get('checked_in', 0),
            total_capacity=pool_status_dict.get('pool_size', 0) + pool_status_dict.get('overflow', 0),
            utilization_percent=pool_status_dict.get('utilization_percent', 0),
            health_status=HealthStatus.HEALTHY if pool_healthy else HealthStatus.DEGRADED
        )

        # Get active connections count
        try:
            result = db.execute(text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"))
            active_connections = result.scalar() or 0
        except Exception:
            active_connections = pool_status_dict.get('checked_out', 0)

        # Get locks count
        try:
            result = db.execute(text("SELECT count(*) FROM pg_locks WHERE granted = true"))
            locks_count = result.scalar() or 0
        except Exception:
            locks_count = 0

        # Determine overall health
        issues = []
        if pool_status.utilization_percent > 90:
            issues.append("Connection pool utilization is very high")
        if not pool_healthy:
            issues.append("Connection pool is unhealthy")
        if locks_count > 100:
            issues.append(f"High number of database locks: {locks_count}")

        if not issues and pool_healthy:
            health = HealthStatus.HEALTHY
        elif pool_status.utilization_percent > 90 or not pool_healthy:
            health = HealthStatus.DEGRADED
        else:
            health = HealthStatus.HEALTHY

        response_time = (time.time() - start_time) * 1000

        result = DatabaseHealth(
            status=health,
            connection_pool=pool_status,
            active_connections=active_connections,
            locks_count=locks_count,
            response_time_ms=round(response_time, 2),
            timestamp=datetime.now(timezone.utc),
            issues=issues
        )

        # Cache result
        await _set_cached_result(cache_key, result.model_dump(), CACHE_TTL_HEALTH)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting database health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve database health"
        )


@router.get(
    "/database/pool",
    response_model=ConnectionPoolStatus,
    summary="Get connection pool status",
    description="Get detailed connection pool metrics and utilization"
)
async def get_connection_pool_status(
    current_user: User = Depends(get_current_user_from_session),
) -> ConnectionPoolStatus:
    """Get connection pool status."""
    try:
        # Check cache first
        cache_key = _get_cache_key("connection_pool_status")
        cached = await _get_cached_result(cache_key)
        if cached:
            return ConnectionPoolStatus(**cached)

        pool_status = get_pool_status()
        pool_healthy = is_pool_healthy()

        total_capacity = pool_status.get('pool_size', 0) + pool_status.get('overflow', 0)
        utilization = pool_status.get('utilization_percent', 0)

        if utilization < 70 and pool_healthy:
            health = HealthStatus.HEALTHY
        elif utilization < 90 and pool_healthy:
            health = HealthStatus.DEGRADED
        else:
            health = HealthStatus.CRITICAL

        result = ConnectionPoolStatus(
            pool_size=pool_status.get('pool_size', 0),
            max_overflow=pool_status.get('overflow', 0),
            checked_out=pool_status.get('checked_out', 0),
            checked_in=pool_status.get('checked_in', 0),
            total_capacity=total_capacity,
            utilization_percent=utilization,
            health_status=health
        )

        # Cache result
        await _set_cached_result(cache_key, result.model_dump(), CACHE_TTL_HEALTH)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting connection pool status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve connection pool status"
        )


@router.get(
    "/database/connections",
    response_model=ActiveConnectionsResponse,
    summary="Get active database connections",
    description="Get list of active database connections with query details"
)
async def get_active_connections(
    current_user: User = Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100, description="Number of connections to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> ActiveConnectionsResponse:
    """Get active database connections."""
    try:
        # Check cache first
        cache_key = _get_cache_key("active_connections", limit=limit, offset=offset)
        cached = await _get_cached_result(cache_key)
        if cached:
            return ActiveConnectionsResponse(**cached)

        # Query active connections
        query = text("""
            SELECT
                pid,
                usename as user,
                datname as database,
                client_addr::text as client_addr,
                state,
                query,
                EXTRACT(EPOCH FROM (now() - query_start)) * 1000 as duration_ms
            FROM pg_stat_activity
            WHERE state = 'active'
                AND pid != pg_backend_pid()
            ORDER BY query_start
            LIMIT :limit OFFSET :offset
        """)

        result = db.execute(query, {"limit": limit + 1, "offset": offset})
        rows = result.fetchall()

        connections = []
        for row in rows[:limit]:
            connections.append(ActiveConnection(
                pid=row[0],
                user=row[1],
                database=row[2],
                client_addr=row[3],
                state=row[4],
                query=row[5][:500] if row[5] else None,  # Truncate long queries
                duration_ms=round(row[6], 2) if row[6] else None
            ))

        # Get total count
        count_query = text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active' AND pid != pg_backend_pid()")
        total_result = db.execute(count_query)
        total = total_result.scalar() or 0

        has_more = len(rows) > limit

        response = ActiveConnectionsResponse(
            connections=connections,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more
        )

        # Cache result
        await _set_cached_result(cache_key, response.model_dump(), CACHE_TTL_METRICS)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting active connections: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve active connections"
        )


@router.get(
    "/database/locks",
    response_model=DatabaseLocksResponse,
    summary="Get database locks",
    description="Get list of active database locks"
)
async def get_database_locks(
    current_user: User = Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100, description="Number of locks to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> DatabaseLocksResponse:
    """Get database locks."""
    try:
        # Check cache first
        cache_key = _get_cache_key("database_locks", limit=limit, offset=offset)
        cached = await _get_cached_result(cache_key)
        if cached:
            return DatabaseLocksResponse(**cached)

        # Query database locks
        query = text("""
            SELECT
                l.locktype as lock_type,
                c.relname as relation,
                l.mode,
                l.granted,
                l.pid,
                a.query
            FROM pg_locks l
            LEFT JOIN pg_class c ON l.relation = c.oid
            LEFT JOIN pg_stat_activity a ON l.pid = a.pid
            WHERE l.granted = true
            ORDER BY l.pid
            LIMIT :limit OFFSET :offset
        """)

        result = db.execute(query, {"limit": limit + 1, "offset": offset})
        rows = result.fetchall()

        locks = []
        for row in rows[:limit]:
            locks.append(DatabaseLock(
                lock_type=row[0],
                relation=row[1],
                mode=row[2],
                granted=row[3],
                pid=row[4],
                query=row[5][:500] if row[5] else None
            ))

        # Get total count
        count_query = text("SELECT count(*) FROM pg_locks WHERE granted = true")
        total_result = db.execute(count_query)
        total = total_result.scalar() or 0

        has_more = len(rows) > limit

        response = DatabaseLocksResponse(
            locks=locks,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more
        )

        # Cache result
        await _set_cached_result(cache_key, response.model_dump(), CACHE_TTL_METRICS)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting database locks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve database locks"
        )


# ============================================================================
# Database Optimization Endpoints (5 endpoints)
# ============================================================================

@router.get(
    "/database/optimization",
    response_model=List[OptimizationSuggestion],
    summary="Get database optimization suggestions",
    description="Get database optimization suggestions based on current performance"
)
async def get_optimization_suggestions(
    current_user: User = Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
) -> List[OptimizationSuggestion]:
    """Get database optimization suggestions."""
    _check_admin_role(current_user)

    try:
        # Check cache first
        cache_key = _get_cache_key("optimization_suggestions")
        cached = await _get_cached_result(cache_key)
        if cached:
            return [OptimizationSuggestion(**item) for item in cached]

        suggestions = []

        # Get index recommendations
        optimizer = _get_db_optimizer(db)
        if optimizer:
            analysis = optimizer.analyze_indexes() if hasattr(optimizer, 'analyze_indexes') else None

            if analysis:
                # Missing indexes
                for rec in analysis.missing_indexes[:5]:  # Top 5
                    suggestions.append(OptimizationSuggestion(
                        category="indexes",
                        table=rec.table_name,
                        suggestion=f"Add index on {rec.table_name}({', '.join(rec.columns)}): {rec.reason}",
                        impact=rec.estimated_benefit,
                        cost="low",
                        priority=1 if rec.estimated_benefit == OptimizationBenefit.HIGH else 2,
                        sql_commands=[f"CREATE INDEX idx_{rec.table_name}_{'_'.join(rec.columns)} ON {rec.table_name}({', '.join(rec.columns)})"]
                    ))

        # Check for table bloat
        query = text("""
            SELECT
                schemaname || '.' || tablename as table_name,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                n_dead_tup as dead_tuples
            FROM pg_stat_user_tables
            WHERE n_dead_tup > 1000
            ORDER BY n_dead_tup DESC
            LIMIT 5
        """)

        result = db.execute(query)
        for row in result:
            suggestions.append(OptimizationSuggestion(
                category="vacuum",
                table=row[0],
                suggestion=f"Table {row[0]} has {row[2]} dead tuples. Consider running VACUUM.",
                impact=OptimizationBenefit.MEDIUM,
                cost="medium",
                priority=2,
                sql_commands=[f"VACUUM ANALYZE {row[0]}"]
            ))

        # Cache result
        await _set_cached_result(cache_key, [s.model_dump() for s in suggestions], CACHE_TTL_OPTIMIZATION)

        return suggestions

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting optimization suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve optimization suggestions"
        )


@router.post(
    "/database/optimize",
    summary="Run database optimization",
    description="Run database optimization based on suggestions (Admin only)"
)
async def run_database_optimization(
    dry_run: bool = Query(True, description="Preview changes without executing"),
    current_user: User = Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Run database optimization."""
    _check_admin_role(current_user)

    try:
        optimizer = _get_db_optimizer(db)
        if not optimizer:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database optimizer service unavailable"
            )

        analysis = optimizer.analyze_indexes() if hasattr(optimizer, 'analyze_indexes') else None

        if not analysis:
            return {
                "success": True,
                "message": "No optimizations needed",
                "dry_run": dry_run,
                "optimizations": []
            }

        # Get high-benefit indexes
        high_benefit = [rec for rec in analysis.missing_indexes if rec.estimated_benefit == OptimizationBenefit.HIGH]

        sql_statements = []
        if not dry_run and high_benefit:
            sql_statements = optimizer.create_recommended_indexes(high_benefit, dry_run=False) if hasattr(optimizer, 'create_recommended_indexes') else []
        else:
            sql_statements = [f"CREATE INDEX idx_{rec.table_name}_{'_'.join(rec.columns)} ON {rec.table_name}({', '.join(rec.columns)})" for rec in high_benefit]

        logger.warning(
            f"Database optimization {'simulated' if dry_run else 'executed'} "
            f"by admin {getattr(current_user, 'id', 'unknown')}: {len(sql_statements)} statements"
        )

        return {
            "success": True,
            "message": f"Optimization {'preview' if dry_run else 'completed'}",
            "dry_run": dry_run,
            "optimizations_count": len(high_benefit),
            "sql_statements": sql_statements
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running database optimization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run database optimization"
        )


@router.get(
    "/database/indexes",
    response_model=List[IndexAnalysis],
    summary="Get index analysis",
    description="Get database index usage analysis and effectiveness"
)
async def get_index_analysis(
    current_user: User = Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
) -> List[IndexAnalysis]:
    """Get index analysis."""
    _check_admin_role(current_user)

    try:
        # Check cache first
        cache_key = _get_cache_key("index_analysis")
        cached = await _get_cached_result(cache_key)
        if cached:
            return [IndexAnalysis(**item) for item in cached]

        # Query index statistics
        query = text("""
            SELECT
                schemaname || '.' || tablename as table_name,
                indexname as index_name,
                pg_size_pretty(pg_relation_size(indexrelid))::text as size,
                idx_scan as scans,
                idx_tup_read as tuples_read,
                idx_tup_fetch as tuples_fetched
            FROM pg_stat_user_indexes
            ORDER BY idx_scan DESC
            LIMIT 50
        """)

        result = db.execute(query)
        rows = result.fetchall()

        indexes = []
        for row in rows:
            # Parse size (e.g., "2560 kB" -> 2.5 MB)
            size_str = row[2]
            if 'kB' in size_str:
                size_mb = float(size_str.replace(' kB', '')) / 1024
            elif 'MB' in size_str:
                size_mb = float(size_str.replace(' MB', ''))
            elif 'GB' in size_str:
                size_mb = float(size_str.replace(' GB', '')) * 1024
            else:
                size_mb = 0

            scans = row[3]
            tuples_read = row[4]
            tuples_fetched = row[5]

            # Calculate effectiveness
            if tuples_read > 0:
                effectiveness = (tuples_fetched / tuples_read) * 100
            else:
                effectiveness = 0

            # Determine if redundant
            is_redundant = scans == 0 and size_mb > 1

            recommendation = None
            if is_redundant:
                recommendation = "Consider dropping - never used"
            elif effectiveness > 80:
                recommendation = "Keep - highly effective"
            elif effectiveness < 30:
                recommendation = "Review - low effectiveness"

            indexes.append(IndexAnalysis(
                table_name=row[0],
                index_name=row[1],
                size_mb=round(size_mb, 2),
                scans=scans,
                tuples_read=tuples_read,
                tuples_fetched=tuples_fetched,
                effectiveness=round(effectiveness, 2),
                is_redundant=is_redundant,
                recommendation=recommendation
            ))

        # Cache result
        await _set_cached_result(cache_key, [idx.model_dump() for idx in indexes], CACHE_TTL_OPTIMIZATION)

        return indexes

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting index analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve index analysis"
        )


@router.post(
    "/database/vacuum",
    response_model=VacuumResponse,
    summary="Run VACUUM operation",
    description="Run VACUUM operation on database tables (Admin only)"
)
async def run_vacuum(
    request: VacuumRequest,
    current_user: User = Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
) -> VacuumResponse:
    """Run VACUUM operation."""
    _check_admin_role(current_user)

    # Require confirmation for FULL VACUUM
    if request.full and not request.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FULL VACUUM requires confirmation flag"
        )

    try:
        start_time = time.time()

        # Build VACUUM command
        vacuum_cmd = "VACUUM"
        if request.full:
            vacuum_cmd += " FULL"
        if request.analyze:
            vacuum_cmd += " ANALYZE"

        if request.table_name:
            vacuum_cmd += f" {request.table_name}"

        # Execute VACUUM (Note: Cannot be in transaction)
        db.commit()  # Commit any pending transaction
        db.execute(text(vacuum_cmd))

        duration = (time.time() - start_time) * 1000

        logger.warning(
            f"VACUUM executed by admin {getattr(current_user, 'id', 'unknown')}: "
            f"table={request.table_name or 'all'}, full={request.full}"
        )

        return VacuumResponse(
            success=True,
            message="VACUUM completed successfully",
            table_name=request.table_name,
            reclaimed_space_mb=None,  # PostgreSQL doesn't report this directly
            duration_ms=round(duration, 2)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running VACUUM: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run VACUUM: {str(e)}"
        )


@router.get(
    "/database/table-stats",
    response_model=List[TableStatistics],
    summary="Get table statistics",
    description="Get table size, bloat, and maintenance statistics"
)
async def get_table_statistics(
    current_user: User = Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
) -> List[TableStatistics]:
    """Get table statistics."""
    _check_admin_role(current_user)

    try:
        # Check cache first
        cache_key = _get_cache_key("table_statistics")
        cached = await _get_cached_result(cache_key)
        if cached:
            return [TableStatistics(**item) for item in cached]

        # Query table statistics
        query = text("""
            SELECT
                schemaname || '.' || tablename as table_name,
                n_live_tup as row_count,
                pg_total_relation_size(schemaname||'.'||tablename) / (1024*1024.0) as size_mb,
                pg_indexes_size(schemaname||'.'||tablename) / (1024*1024.0) as indexes_size_mb,
                n_dead_tup as dead_tuples,
                CASE
                    WHEN n_live_tup > 0 THEN (n_dead_tup::float / n_live_tup) * 100
                    ELSE 0
                END as bloat_ratio,
                last_vacuum,
                last_analyze
            FROM pg_stat_user_tables
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            LIMIT 20
        """)

        result = db.execute(query)
        rows = result.fetchall()

        tables = []
        for row in rows:
            bloat_ratio = row[5]
            needs_vacuum = bloat_ratio > 10 or row[4] > 1000

            tables.append(TableStatistics(
                table_name=row[0],
                row_count=row[1],
                size_mb=round(row[2], 2),
                indexes_size_mb=round(row[3], 2),
                total_size_mb=round(row[2] + row[3], 2),
                dead_tuples=row[4],
                bloat_ratio=round(bloat_ratio, 2),
                last_vacuum=row[6],
                last_analyze=row[7],
                needs_vacuum=needs_vacuum
            ))

        # Cache result
        await _set_cached_result(cache_key, [t.model_dump() for t in tables], CACHE_TTL_STATS)

        return tables

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting table statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve table statistics"
        )
