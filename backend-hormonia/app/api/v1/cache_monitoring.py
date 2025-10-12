"""
Cache Monitoring API endpoints.
Provides cache performance metrics and management capabilities.
"""
import logging
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.services.analytics_cache import get_analytics_cache
from app.services.cache_invalidation import get_cache_invalidation_service
from app.core.monitoring_logging import monitoring_logger


logger = logging.getLogger(__name__)
router = APIRouter(tags=["cache-monitoring"])


@router.get(
    "/metrics",
    response_model=None,
    summary="Get cache performance metrics",
    description="Get comprehensive cache performance metrics and statistics"
)
async def get_cache_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get cache performance metrics."""
    # Only admins can access cache metrics
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Admin privileges required"
        )
    
    try:
        cache_service = get_analytics_cache()
        
        # Get comprehensive cache information
        cache_info = cache_service.get_cache_info()
        
        # Get performance metrics
        metrics = cache_service.get_metrics()
        
        # Combine all information
        response = {
            "cache_metrics": {
                "hits": metrics.hits,
                "misses": metrics.misses,
                "hit_rate_percentage": metrics.hit_rate,
                "invalidations": metrics.invalidations,
                "warming_operations": metrics.warming_operations
            },
            "cache_info": cache_info,
            "recommendations": _generate_cache_recommendations(metrics, cache_info)
        }
        
        monitoring_logger.log_system_event(
            event_type="cache_metrics_accessed",
            message="Cache metrics accessed by admin",
            level="INFO",
            context={
                "admin_user_id": str(current_user.id),
                "hit_rate": metrics.hit_rate
            }
        )
        
        logger.info(f"Cache metrics retrieved by admin {current_user.id}")
        return response
        
    except Exception as e:
        logger.error(f"Error getting cache metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve cache metrics"
        )


@router.post(
    "/invalidate",
    response_model=None,
    summary="Invalidate cache entries",
    description="Manually invalidate cache entries for specific types or doctors"
)
async def invalidate_cache(
    cache_type: Optional[str] = Query(None, description="Cache type to invalidate (dashboard, analytics, etc.)"),
    doctor_id: Optional[UUID] = Query(None, description="Doctor ID to invalidate cache for"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Manually invalidate cache entries."""
    # Only admins can invalidate cache
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Admin privileges required"
        )
    
    try:
        invalidation_service = get_cache_invalidation_service()
        cache_service = get_analytics_cache()
        
        invalidated_count = 0
        
        if cache_type:
            # Invalidate specific cache type
            if cache_type == "dashboard":
                invalidation_service.invalidate_dashboard_cache(doctor_id)
            elif cache_type == "analytics":
                invalidation_service.invalidate_analytics_cache(doctor_id)
            elif cache_type == "treatment_distribution":
                invalidation_service.invalidate_treatment_distribution_cache(doctor_id)
            elif cache_type == "patterns":
                invalidation_service.invalidate_patterns_cache()
            else:
                # Generic cache type invalidation
                invalidated_count = cache_service.invalidate(cache_type)
        else:
            # Invalidate all analytics caches
            if doctor_id:
                invalidation_service.invalidate_dashboard_cache(doctor_id)
                invalidation_service.invalidate_analytics_cache(doctor_id)
                invalidation_service.invalidate_treatment_distribution_cache(doctor_id)
            else:
                # Clear all caches
                invalidated_count = cache_service.clear_all()
        
        monitoring_logger.log_system_event(
            event_type="cache_manual_invalidation",
            message="Cache manually invalidated by admin",
            level="WARNING",
            context={
                "admin_user_id": str(current_user.id),
                "cache_type": cache_type,
                "doctor_id": str(doctor_id) if doctor_id else None,
                "invalidated_count": invalidated_count
            }
        )
        
        logger.warning(
            f"Cache invalidated by admin {current_user.id}: "
            f"type={cache_type}, doctor_id={doctor_id}, count={invalidated_count}"
        )
        
        return {
            "success": True,
            "message": "Cache invalidated successfully",
            "cache_type": cache_type,
            "doctor_id": str(doctor_id) if doctor_id else None,
            "invalidated_count": invalidated_count
        }
        
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to invalidate cache"
        )


@router.post(
    "/warm",
    response_model=None,
    summary="Warm cache entries",
    description="Manually warm frequently accessed cache entries"
)
async def warm_cache(
    doctor_id: Optional[UUID] = Query(None, description="Doctor ID to warm cache for"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Manually warm cache entries."""
    # Only admins can warm cache
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Admin privileges required"
        )
    
    try:
        invalidation_service = get_cache_invalidation_service()
        
        # Initiate cache warming
        invalidation_service.warm_frequently_accessed_cache(doctor_id)
        
        monitoring_logger.log_system_event(
            event_type="cache_manual_warming",
            message="Cache warming initiated by admin",
            level="INFO",
            context={
                "admin_user_id": str(current_user.id),
                "doctor_id": str(doctor_id) if doctor_id else None
            }
        )
        
        logger.info(f"Cache warming initiated by admin {current_user.id} for doctor: {doctor_id or 'all'}")
        
        return {
            "success": True,
            "message": "Cache warming initiated",
            "doctor_id": str(doctor_id) if doctor_id else None
        }
        
    except Exception as e:
        logger.error(f"Error warming cache: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to warm cache"
        )


@router.get(
    "/health",
    response_model=None,
    summary="Get cache health status",
    description="Get cache health status and performance indicators"
)
async def get_cache_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get cache health status."""
    # Only admins can access cache health
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Admin privileges required"
        )
    
    try:
        cache_service = get_analytics_cache()
        metrics = cache_service.get_metrics()
        
        # Determine health status based on metrics
        health_status = "healthy"
        issues = []
        
        # Check hit rate
        if metrics.hit_rate < 50:
            health_status = "warning"
            issues.append("Low cache hit rate (<50%)")
        elif metrics.hit_rate < 30:
            health_status = "critical"
            issues.append("Very low cache hit rate (<30%)")
        
        # Check if cache is being used
        if metrics.hits + metrics.misses == 0:
            health_status = "warning"
            issues.append("No cache activity detected")
        
        return {
            "status": health_status,
            "hit_rate_percentage": metrics.hit_rate,
            "total_operations": metrics.hits + metrics.misses,
            "issues": issues,
            "recommendations": _generate_health_recommendations(metrics)
        }
        
    except Exception as e:
        logger.error(f"Error getting cache health: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve cache health"
        )


def _generate_cache_recommendations(metrics, cache_info: Dict[str, Any]) -> list[str]:
    """Generate cache optimization recommendations."""
    recommendations = []
    
    # Hit rate recommendations
    if metrics.hit_rate < 50:
        recommendations.append("Consider increasing cache TTL for frequently accessed data")
        recommendations.append("Review cache invalidation strategy - may be too aggressive")
    
    if metrics.hit_rate > 90:
        recommendations.append("Excellent cache performance - consider expanding cache coverage")
    
    # Cache size recommendations
    total_keys = cache_info.get("total_keys", 0)
    if total_keys > 10000:
        recommendations.append("High number of cache keys - consider implementing cache cleanup")
    
    if total_keys < 10:
        recommendations.append("Low cache usage - verify cache is being utilized properly")
    
    # Invalidation recommendations
    if metrics.invalidations > metrics.hits:
        recommendations.append("High invalidation rate - review invalidation triggers")
    
    return recommendations


def _generate_health_recommendations(metrics) -> list[str]:
    """Generate cache health recommendations."""
    recommendations = []
    
    if metrics.hit_rate < 50:
        recommendations.append("Increase cache TTL or review cache strategy")
    
    if metrics.hits + metrics.misses == 0:
        recommendations.append("Verify cache integration is working properly")
    
    if metrics.invalidations > 100:
        recommendations.append("Consider reducing cache invalidation frequency")
    
    return recommendations