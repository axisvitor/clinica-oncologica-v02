"""
Performance monitoring and metrics endpoints.
"""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from app.models.user import User
from app.utils.unified_cache import get_unified_cache_manager as get_cache_manager
from app.utils.database_optimization import get_db_optimizer
from app.database import get_pool_status, is_pool_healthy

router = APIRouter()


@router.get("/performance/cache", response_model=None)
async def get_cache_performance(
    current_user: User = Depends(get_current_user)
):
    """
    Get cache performance statistics.
    
    Requires authentication.
    """
    cache_manager = get_cache_manager()
    stats = cache_manager.get_stats()
    
    return {
        "cache_stats": stats,
        "status": "healthy" if stats["hit_rate_percent"] > 50 else "degraded"
    }


@router.get("/performance/database", response_model=None)
async def get_database_performance(
    current_user: User = Depends(get_current_user)
):
    """
    Get database performance statistics.
    
    Requires authentication.
    """
    db_optimizer = get_db_optimizer()
    query_stats = db_optimizer.get_query_stats()
    pool_status = get_pool_status()
    pool_healthy = is_pool_healthy()
    
    return {
        "query_stats": query_stats,
        "connection_pool": pool_status,
        "pool_healthy": pool_healthy,
        "status": "healthy" if pool_healthy and query_stats.get("slow_query_percentage", 0) < 10 else "degraded"
    }


@router.get("/performance/slow-queries", response_model=None)
async def get_slow_queries(
    limit: int = 10,
    current_user: User = Depends(get_current_user)
):
    """
    Get slowest database queries.
    
    Requires authentication.
    """
    db_optimizer = get_db_optimizer()
    slow_queries = db_optimizer.get_slowest_queries(limit=limit)
    
    return {
        "slow_queries": slow_queries,
        "count": len(slow_queries)
    }


@router.post("/performance/cache/clear", response_model=None)
async def clear_cache(
    current_user: User = Depends(get_current_user)
):
    """
    Clear all cache data.
    
    Requires authentication.
    """
    cache_manager = get_cache_manager()
    success = await cache_manager.clear_all()
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )
    
    return {"message": "Cache cleared successfully"}


@router.get("/performance/overview", response_model=None)
async def get_performance_overview(
    current_user: User = Depends(get_current_user)
):
    """
    Get overall system performance overview.
    
    Requires authentication.
    """
    # Get cache stats
    cache_manager = get_cache_manager()
    cache_stats = cache_manager.get_stats()
    
    # Get database stats
    db_optimizer = get_db_optimizer()
    query_stats = db_optimizer.get_query_stats()
    pool_status = get_pool_status()
    pool_healthy = is_pool_healthy()
    
    # Calculate overall health score
    health_score = 100
    
    # Deduct points for poor cache performance
    if cache_stats["hit_rate_percent"] < 50:
        health_score -= 20
    elif cache_stats["hit_rate_percent"] < 70:
        health_score -= 10
    
    # Deduct points for slow queries
    slow_query_percentage = query_stats.get("slow_query_percentage", 0)
    if slow_query_percentage > 20:
        health_score -= 30
    elif slow_query_percentage > 10:
        health_score -= 15
    
    # Deduct points for unhealthy connection pool
    if not pool_healthy:
        health_score -= 25
    elif pool_status.get("utilization_percent", 0) > 80:
        health_score -= 10
    
    # Determine status
    if health_score >= 90:
        status = "excellent"
    elif health_score >= 75:
        status = "good"
    elif health_score >= 60:
        status = "fair"
    else:
        status = "poor"
    
    return {
        "health_score": max(0, health_score),
        "status": status,
        "cache": {
            "hit_rate_percent": cache_stats["hit_rate_percent"],
            "total_requests": cache_stats["hits"] + cache_stats["misses"],
            "errors": cache_stats["errors"]
        },
        "database": {
            "avg_query_time_ms": query_stats.get("avg_duration_ms", 0),
            "slow_query_percentage": slow_query_percentage,
            "pool_utilization_percent": pool_status.get("utilization_percent", 0),
            "pool_healthy": pool_healthy
        },
        "recommendations": _generate_performance_recommendations(
            cache_stats, query_stats, pool_status, pool_healthy
        )
    }


def _generate_performance_recommendations(
    cache_stats: dict[str, Any],
    query_stats: dict[str, Any],
    pool_status: dict[str, Any],
    pool_healthy: bool
) -> list[str]:
    """Generate performance recommendations based on metrics."""
    recommendations = []
    
    # Cache recommendations
    if cache_stats["hit_rate_percent"] < 50:
        recommendations.append("Cache hit rate is low. Consider increasing cache TTL or reviewing cache strategy.")
    
    if cache_stats["errors"] > 0:
        recommendations.append("Cache errors detected. Check Redis connectivity and configuration.")
    
    # Database recommendations
    slow_query_percentage = query_stats.get("slow_query_percentage", 0)
    if slow_query_percentage > 10:
        recommendations.append("High percentage of slow queries detected. Review database indexes and query optimization.")
    
    avg_query_time = query_stats.get("avg_duration_ms", 0)
    if avg_query_time > 100:
        recommendations.append("Average query time is high. Consider database performance tuning.")
    
    # Connection pool recommendations
    utilization = pool_status.get("utilization_percent", 0)
    if utilization > 90:
        recommendations.append("Database connection pool utilization is very high. Consider increasing pool size.")
    elif utilization > 80:
        recommendations.append("Database connection pool utilization is high. Monitor for potential bottlenecks.")
    
    if not pool_healthy:
        recommendations.append("Database connection pool is unhealthy. Check database connectivity and pool configuration.")
    
    if not recommendations:
        recommendations.append("System performance is optimal. No immediate recommendations.")
    
    return recommendations