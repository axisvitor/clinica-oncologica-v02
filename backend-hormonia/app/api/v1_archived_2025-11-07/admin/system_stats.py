"""
Admin system statistics API endpoints.
Provides real-time system monitoring metrics for admin dashboard.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_thread_safe_db, get_admin_user
from app.models.user import User
from app.models.admin import SystemStatsResponse
from app.services.admin_stats_service import AdminStatsService
from app.utils.cache import get_async_cache_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/system-stats",
    response_model=SystemStatsResponse,
    summary="Get system statistics",
    description="""
    Get real-time system statistics for admin dashboard.

    **Requires**: Admin role

    **Returns**:
    - System metrics (CPU, memory, disk usage, uptime)
    - User metrics (total, active, by role)
    - Database metrics (records, connections)
    - Timestamp of data collection

    **Caching**: Results cached for 30 seconds in Redis

    **Performance**: Typical response time < 100ms
    """,
    responses={
        200: {
            "description": "System statistics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "system": {
                            "cpu_percent": 15.2,
                            "memory_percent": 45.8,
                            "disk_percent": 62.3,
                            "uptime_seconds": 86400
                        },
                        "users": {
                            "total": 125,
                            "active_now": 23,
                            "by_role": {
                                "admin": 5,
                                "doctor": 120
                            }
                        },
                        "database": {
                            "total_records": 1250,
                            "total_patients": 1000,
                            "total_users": 125,
                            "connections": 12
                        },
                        "timestamp": "2025-10-06T14:30:00.000Z"
                    }
                }
            }
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin role required)"},
        500: {"description": "Internal server error"}
    }
)
async def get_system_stats(
    db: Session = Depends(get_thread_safe_db),
    current_user: User = Depends(get_admin_user)
) -> SystemStatsResponse:
    """
    Get real-time system statistics (Admin only).

    This endpoint provides comprehensive system monitoring metrics including:
    - System resource usage (CPU, memory, disk)
    - User statistics and activity
    - Database health and connections

    Results are cached in Redis for 30 seconds to reduce database load.
    """
    try:
        # Check cache first
        cache_manager = get_async_cache_manager()
        cache_key = "admin:system-stats"

        cached_data = await cache_manager.get(cache_key, namespace="admin")
        if cached_data:
            logger.debug("Returning cached system stats")
            return SystemStatsResponse(**cached_data)

        # Cache miss - collect fresh metrics
        logger.debug("Cache miss - collecting fresh system stats")
        service = AdminStatsService(db)
        stats_data = service.get_all_stats()

        # Cache the result for 30 seconds
        await cache_manager.set(
            cache_key,
            stats_data,
            ttl=30,
            namespace="admin"
        )

        return SystemStatsResponse(**stats_data)

    except Exception as e:
        logger.error(f"Failed to get system stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve system statistics: {str(e)}"
        )
