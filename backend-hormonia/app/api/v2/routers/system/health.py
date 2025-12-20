"""
System Health Monitoring API Endpoints.

ADMIN-ONLY endpoints for system health monitoring and diagnostics.
Requires authentication and admin role.
"""

from datetime import datetime, timezone
import json

from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import JSONResponse

from app.schemas.v2.system import SystemHealthResponse
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.database import get_db
from app.utils.rate_limiter import limiter
from app.utils.logging import get_logger

from .helpers.health_checker import (
    check_component_health,
    calculate_health_score,
)
from .helpers.auth import is_admin
from .helpers.redis_helper import get_redis_client

router = APIRouter()
logger = get_logger(__name__)

# Redis cache TTL for health endpoint
CACHE_TTL_HEALTH = 30  # 30 seconds (real-time monitoring)


@router.get(
    "/health",
    response_model=SystemHealthResponse,
    summary="Get comprehensive system health",
    description="""
    Get comprehensive system health status with component-level details.

    **Authentication:** Admin role required
    **Caching:** 30 seconds (real-time monitoring)
    **Rate limit:** 20 requests/minute

    Returns:
    - Overall health status (healthy/degraded/unhealthy)
    - Component health details with latency
    - Overall health score (0-100)
    - Lists of degraded/unhealthy components
    """,
)
@limiter.limit("20/minute")
async def get_system_health(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    """
    Get comprehensive system health status with Redis caching.

    Checks all components:
    - Database connectivity
    - Redis cache availability
    - Firebase Admin SDK status
    - External API configurations

    Returns HTTP 200 for healthy/degraded, HTTP 503 for unhealthy.
    """
    # Check admin privileges
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for system health check",
        )

    cache_key = "system:health"

    # Try Redis cache first
    redis = await get_redis_client()
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                logger.debug("Cache hit for system health")
                health_data = json.loads(cached)
                status_code = (
                    status.HTTP_200_OK
                    if health_data["status"] != "unhealthy"
                    else status.HTTP_503_SERVICE_UNAVAILABLE
                )
                return JSONResponse(status_code=status_code, content=health_data)
        except Exception as e:
            logger.warning(f"Redis get error: {e}")

    # Cache miss - check all components
    try:
        components = {}
        component_names = ["database", "redis", "firebase", "external_apis"]

        for component_name in component_names:
            components[component_name] = await check_component_health(
                component_name, db
            )

        # Calculate overall health score
        overall_score = calculate_health_score(components)

        # Determine overall status
        degraded_components = [
            name for name, comp in components.items() if comp.status == "degraded"
        ]
        unhealthy_components = [
            name for name, comp in components.items() if comp.status == "unhealthy"
        ]

        if unhealthy_components:
            overall_status = "unhealthy"
        elif degraded_components:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        # Serialize component health
        components_dict = {name: comp.dict() for name, comp in components.items()}

        health_response = {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": components_dict,
            "overall_score": overall_score,
            "degraded_components": degraded_components,
            "unhealthy_components": unhealthy_components,
        }

        # Cache the result
        if redis:
            try:
                await redis.setex(
                    cache_key,
                    CACHE_TTL_HEALTH,
                    json.dumps(health_response, default=str),
                )
                logger.debug("Cached system health")
            except Exception as e:
                logger.warning(f"Redis set error: {e}")

        # Return appropriate HTTP status
        status_code = (
            status.HTTP_200_OK
            if overall_status != "unhealthy"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return JSONResponse(status_code=status_code, content=health_response)

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": "Health check failed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "overall_score": 0.0,
                "components": {},
                "degraded_components": [],
                "unhealthy_components": [],
            },
        )
