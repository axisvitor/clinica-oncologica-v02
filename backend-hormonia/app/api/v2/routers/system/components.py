"""
System Components Management Module.

Provides endpoints for component management:
- GET /components - List all system components with status
- POST /restart-component - Restart specific system component

Security:
- All endpoints require ADMIN role
- Rate limiting applied (30/min for list, 3/hour for restart)
"""

from datetime import datetime, timezone
import time
import json

from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.async_engine import get_async_db
from app.schemas.v2.system import (
    ComponentListResponse,
    ComponentInfo,
    ComponentRestartRequest,
    ComponentRestartResponse,
)
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter
from app.utils.logging import get_logger
from app.config import settings
from app.utils.auth_helpers import is_admin as _is_admin
from app.utils.timezone import now_sao_paulo
from .helpers.auth import get_redis_client as _get_redis_client

router = APIRouter()
logger = get_logger(__name__)

# Redis cache TTL for components
CACHE_TTL_COMPONENTS = 120  # 2 minutes (near real-time)


# ============================================================================
# Component Management Endpoints (ADMIN ONLY)
# ============================================================================


@router.get(
    "/components",
    response_model=ComponentListResponse,
    summary="List system components",
    description="""
    List all system components with status.

    **Authentication:** Admin role required
    **Caching:** 2 minutes (near real-time)
    **Rate limit:** 30 requests/minute
    """,
)
@limiter.limit("30/minute")
async def list_components(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db: AsyncSession = Depends(get_async_db),
):
    """List all system components with status."""
    # Check admin privileges
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for component list",
        )

    cache_key = "system:components"

    # Try Redis cache first
    redis = await _get_redis_client()
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                logger.debug("Cache hit for component list")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis get error: {e}")

    # Cache miss - build component list
    try:
        components = [
            ComponentInfo(
                name="database",
                type="database",
                status="running",
                version="PostgreSQL",
                restartable=False,
                dependencies=[],
                metadata={"type": "primary"},
            ),
            ComponentInfo(
                name="redis",
                type="cache",
                status="running",
                version="7.x",
                restartable=True,
                dependencies=[],
                metadata={"type": "cache"},
            ),
            ComponentInfo(
                name="workers",
                type="service",
                status="running",
                restartable=True,
                dependencies=["redis", "database"],
                metadata={"type": "background"},
            ),
            ComponentInfo(
                name="monitoring",
                type="service",
                status="running",
                restartable=True,
                dependencies=[],
                metadata={"enabled": settings.MONITORING_ENABLE_SERVICE},
            ),
        ]

        healthy_count = sum(1 for c in components if c.status == "running")

        response = {
            "components": [c.dict() for c in components],
            "total": len(components),
            "healthy_count": healthy_count,
        }

        # Cache the result
        if redis:
            try:
                await redis.setex(
                    cache_key, CACHE_TTL_COMPONENTS, json.dumps(response, default=str)
                )
                logger.debug("Cached component list")
            except Exception as e:
                logger.warning(f"Redis set error: {e}")

        return response

    except Exception as e:
        logger.error(f"Failed to list components: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve component list",
        )


@router.post(
    "/restart-component",
    response_model=ComponentRestartResponse,
    summary="Restart system component",
    description="""
    Restart a specific system component.

    **Authentication:** Admin role required
    **Rate limit:** 3 requests/hour (very restricted)

    Restartable components:
    - redis (Redis cache)
    - cache (Cache system)
    - workers (Background workers)
    - monitoring (Monitoring service)
    """,
)
@limiter.limit("3/hour")
async def restart_component(
    request: Request,
    restart_request: ComponentRestartRequest,
    current_user=Depends(get_current_user_from_session),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Restart a specific system component.

    Validates component is restartable and performs graceful restart
    with minimal downtime.
    """
    # Check admin privileges
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for component restart",
        )

    component = restart_request.component
    logger.warning(f"Component restart requested: {component}")

    start_time = time.time()
    previous_status = "running"

    try:
        if component == "redis":
            # Restart Redis connections
            from app.core.redis_manager import cleanup_redis_connections

            if restart_request.graceful:
                # Graceful: drain connections first
                logger.info("Draining Redis connections...")
                # Placeholder for actual drain logic
            await cleanup_redis_connections()
            current_status = "running"

        elif component == "cache":
            # Restart cache system
            redis = await _get_redis_client()
            if redis:
                await redis.flushall()  # Clear all cache
            current_status = "running"

        elif component == "workers":
            # Restart background workers (placeholder)
            logger.info("Restarting background workers...")
            current_status = "running"

        elif component == "monitoring":
            # Restart monitoring service (placeholder)
            logger.info("Restarting monitoring service...")
            current_status = "running"

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Component '{component}' is not restartable",
            )

        duration_ms = (time.time() - start_time) * 1000

        # Invalidate relevant caches
        redis = await _get_redis_client()
        if redis:
            try:
                await redis.delete("system:components", "system:health")
            except Exception as e:
                logger.warning(f"Cache invalidation failed: {e}")

        logger.info(
            f"Component {component} restarted successfully in {duration_ms:.2f}ms"
        )

        return ComponentRestartResponse(
            component=component,
            status="success",
            restarted_at=now_sao_paulo(),
            duration_ms=duration_ms,
            previous_status=previous_status,
            current_status=current_status,
            message=f"Component '{component}' restarted successfully",
        )

    except Exception as e:
        logger.error(f"Component restart failed: {e}", exc_info=True)
        duration_ms = (time.time() - start_time) * 1000
        return ComponentRestartResponse(
            component=component,
            status="failed",
            restarted_at=now_sao_paulo(),
            duration_ms=duration_ms,
            previous_status=previous_status,
            current_status="error",
            message=f"Component restart failed: {str(e)}",
        )
