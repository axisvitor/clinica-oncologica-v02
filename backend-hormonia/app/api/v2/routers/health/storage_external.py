"""
Storage and External Health Check Module

Provides storage health checks.
"""

import logging
import psutil

from fastapi import APIRouter, Depends

from app.models.user import User
from app.schemas.v2.health import StorageHealth, HealthStatus
from .compat import call_health_attr, get_current_user_compat


logger = logging.getLogger(__name__)
router = APIRouter()


async def check_storage_health() -> StorageHealth:
    """Check storage health."""
    try:
        disk = psutil.disk_usage("/")

        total_gb = disk.total / (1024**3)
        used_gb = disk.used / (1024**3)
        free_gb = disk.free / (1024**3)
        utilization = disk.percent

        storage_status = HealthStatus.HEALTHY
        if utilization > 85:
            storage_status = HealthStatus.DEGRADED
        if utilization > 95:
            storage_status = HealthStatus.UNHEALTHY

        return StorageHealth(
            status=storage_status,
            available_space_gb=round(free_gb, 2),
            used_space_gb=round(used_gb, 2),
            total_space_gb=round(total_gb, 2),
            utilization_percent=round(utilization, 2),
        )
    except Exception as e:
        logger.error(f"Storage health check failed: {e}")
        return StorageHealth(
            status=HealthStatus.UNKNOWN,
            available_space_gb=0.0,
            used_space_gb=0.0,
            total_space_gb=0.0,
            utilization_percent=0.0,
        )


@router.get("/storage", response_model=StorageHealth)
async def storage_health_check(
    current_user: User = Depends(get_current_user_compat),
) -> StorageHealth:
    """
    Storage health check (Authenticated).

    Returns disk space and utilization metrics.
    Cached for 2 minutes.
    """
    return await call_health_attr("check_storage_health", check_storage_health)
