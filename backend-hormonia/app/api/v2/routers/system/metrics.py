"""
System Metrics Module.

Provides system performance metrics endpoints:
- GET /metrics: System-level performance metrics (CPU, memory, disk, network)
- GET /info: System information and feature flags

Security: Admin role required for all endpoints.
"""

from datetime import datetime, timezone
import sys
import json

from fastapi import APIRouter, HTTPException, status, Depends, Request

from app.schemas.v2.system import (
    SystemInfoResponse,
    SystemMetrics,
)
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter
from app.utils.logging import get_logger
from app.config import settings
from app.database import get_db
from app.utils.auth_helpers import is_admin as _is_admin
from app.utils.timezone import now_sao_paulo
from .helpers.auth import get_redis_client as _get_redis_client

router = APIRouter(tags=["system-metrics"])
logger = get_logger(__name__)

# Redis cache TTLs
CACHE_TTL_INFO = 600  # 10 minutes (moderate)


# ============================================================================
# System Metrics Endpoint (ADMIN ONLY)
# ============================================================================


@router.get(
    "/metrics",
    response_model=SystemMetrics,
    summary="Get system metrics",
    description="""
    Get system-level performance metrics.

    **Authentication:** Admin role required
    **Rate limit:** 20 requests/minute

    Returns:
    - CPU, memory, disk usage
    - Network connections
    - Database metrics
    - Cache metrics
    - Application metrics
    """,
)
@limiter.limit("20/minute")
async def get_system_metrics(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    """
    Get system-level performance metrics.

    Collects real-time metrics from:
    - System resources (CPU, memory, disk)
    - Database (connections, pool size)
    - Cache (hit rate, memory usage)
    - Application (sessions, request rate)
    """
    # Check admin privileges
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for system metrics",
        )

    try:
        import psutil

        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()

        # Memory metrics
        memory = psutil.virtual_memory()
        memory_total_mb = memory.total / (1024 * 1024)
        memory_used_mb = memory.used / (1024 * 1024)
        memory_percent = memory.percent

        # Disk metrics
        disk = psutil.disk_usage("/")
        disk_total_gb = disk.total / (1024 * 1024 * 1024)
        disk_used_gb = disk.used / (1024 * 1024 * 1024)
        disk_percent = disk.percent

        # Network connections
        network_connections = len(psutil.net_connections())

        # Database metrics from SQLAlchemy engine pool
        db_connections = 0
        db_pool_size = 0
        try:
            from app.database import engine

            pool = engine.pool
            db_pool_size = pool.size()
            db_connections = pool.checkedout()
        except Exception as e:
            logger.warning(f"Could not get DB pool stats: {e}")

        # Application metrics - active sessions count
        active_sessions = 0
        try:
            from sqlalchemy import text

            result = db.execute(
                text("SELECT COUNT(*) FROM sessions WHERE expires_at > NOW()")
            )
            active_sessions = result.scalar() or 0
        except Exception as e:
            logger.debug(f"Could not count sessions: {e}")

        request_rate_per_min = 0.0  # Would need request tracking middleware

        # Cache metrics (placeholder)
        cache_hit_rate = None
        cache_memory_mb = None
        redis = await _get_redis_client()
        if redis:
            try:
                info = await redis.info("stats")
                if "keyspace_hits" in info and "keyspace_misses" in info:
                    hits = info["keyspace_hits"]
                    misses = info["keyspace_misses"]
                    total = hits + misses
                    cache_hit_rate = (hits / total * 100) if total > 0 else 0.0

                memory_info = await redis.info("memory")
                if "used_memory" in memory_info:
                    cache_memory_mb = memory_info["used_memory"] / (1024 * 1024)
            except Exception as e:
                logger.debug(f"Redis info retrieval failed: {e}")

        return SystemMetrics(
            timestamp=now_sao_paulo(),
            cpu_percent=cpu_percent,
            cpu_count=cpu_count,
            memory_total_mb=memory_total_mb,
            memory_used_mb=memory_used_mb,
            memory_percent=memory_percent,
            disk_total_gb=disk_total_gb,
            disk_used_gb=disk_used_gb,
            disk_percent=disk_percent,
            network_connections=network_connections,
            active_sessions=active_sessions,
            request_rate_per_min=request_rate_per_min,
            db_connections=db_connections,
            db_pool_size=db_pool_size,
            cache_hit_rate=cache_hit_rate,
            cache_memory_mb=cache_memory_mb,
        )

    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="psutil not available - metrics unavailable",
        )
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system metrics",
        )


# ============================================================================
# System Information Endpoint (ADMIN ONLY)
# ============================================================================


@router.get(
    "/info",
    response_model=SystemInfoResponse,
    summary="Get system information",
    description="""
    Get system information and feature flags.

    **Authentication:** Admin role required
    **Caching:** 10 minutes (moderate)
    **Rate limit:** 30 requests/minute
    """,
)
@limiter.limit("30/minute")
async def get_system_info(
    request: Request,
    current_user=Depends(get_current_user_from_session),
):
    """
    Get system information and feature flags.

    Returns version, uptime, environment, and feature status.
    """
    # Check admin privileges
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for system info",
        )

    cache_key = "system:info"

    # Try Redis cache first
    redis = await _get_redis_client()
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                logger.debug("Cache hit for system info")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis get error: {e}")

    # Cache miss - build system info
    try:
        # Calculate uptime (simplified)
        uptime = "N/A"
        try:
            import psutil

            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime_delta = datetime.now() - boot_time
            days = uptime_delta.days
            hours, remainder = divmod(uptime_delta.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            uptime = f"{days}d {hours}h {minutes}m"
        except Exception:
            pass

        system_info = {
            "environment": settings.APP_ENVIRONMENT,
            "debug_mode": settings.APP_ENABLE_DEBUG,
            "version": "2.0.0",  # API v2 version
            "uptime": uptime,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "features": {
                "firebase_auth": bool(settings.FIREBASE_ADMIN_PROJECT_ID),
                "whatsapp_integration": settings.WHATSAPP_ENABLE_SERVICE,
                "ai_humanization": settings.AI_ENABLE_HUMANIZATION,
                "monitoring": settings.MONITORING_ENABLE_SERVICE,
                "rate_limiting": settings.RATE_LIMIT_ENABLE_SERVICE,
                "monthly_quiz_links": settings.QUIZ_ENABLE_VIA_LINK,
            },
            "build_info": {"api_version": "v2", "migration_phase": "9"},
        }

        # Cache the result
        if redis:
            try:
                await redis.setex(
                    cache_key, CACHE_TTL_INFO, json.dumps(system_info, default=str)
                )
                logger.debug("Cached system info")
            except Exception as e:
                logger.warning(f"Redis set error: {e}")

        return system_info

    except Exception as e:
        logger.error(f"Failed to get system info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system information",
        )
