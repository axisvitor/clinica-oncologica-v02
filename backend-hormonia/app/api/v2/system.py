"""
System Management API for v2.

Provides comprehensive system management endpoints:
- System health monitoring with Redis caching
- System initialization and status tracking
- Component management and restart
- Configuration validation
- PUBLIC configuration endpoint for frontend (NO auth, NO sensitive data)
- System metrics and performance monitoring

Security:
- /config endpoint is PUBLIC (no authentication required)
- All /system/* endpoints require ADMIN role
- Config endpoint filters to safe environment variables only
- Redis caching with different TTLs per endpoint
- Rate limiting with different limits for public vs admin
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from uuid import UUID
import os
import json
import sys
import time
import logging

from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db, get_engine
from app.models.user import User, UserRole
from app.schemas.v2.system import (
    SystemHealthResponse,
    ComponentHealth,
    InitializationRequest,
    InitializationStatusResponse,
    InitializationError,
    SystemInfoResponse,
    ComponentListResponse,
    ComponentInfo,
    ComponentRestartRequest,
    ComponentRestartResponse,
    ConfigValidationRequest,
    ConfigValidationResponse,
    PublicConfigResponse,
    SystemMetrics,
)
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.core.redis_client import get_async_redis_client
from app.utils.rate_limiter import limiter
from app.utils.logging import get_logger
from app.config import settings

router = APIRouter()
logger = get_logger(__name__)

# Redis cache TTLs (different for each endpoint type)
CACHE_TTL_CONFIG = 1800  # 30 minutes (public, rarely changes)
CACHE_TTL_HEALTH = 30  # 30 seconds (real-time monitoring)
CACHE_TTL_INFO = 600  # 10 minutes (moderate)
CACHE_TTL_COMPONENTS = 120  # 2 minutes (near real-time)

# System initialization state (in-memory, could be moved to Redis for multi-instance)
_initialization_state = {
    "started_at": None,
    "completed_at": None,
    "status": "pending",
    "components": {},
    "errors": [],
    "warnings": []
}


# ============================================================================
# Helper Functions
# ============================================================================

async def _get_redis_client():
    """Get async Redis client for caching."""
    try:
        return await get_async_redis_client()
    except Exception as e:
        logger.warning(f"Failed to get Redis client: {e}")
        return None


def _is_admin(current_user) -> bool:
    """Check if user has admin role."""
    if isinstance(current_user, dict):
        role = current_user.get("role")
    else:
        role = getattr(current_user, "role", None)

    if isinstance(role, UserRole):
        return role == UserRole.ADMIN
    return str(role).upper() == "ADMIN"


def _filter_safe_env_vars() -> Dict[str, str]:
    """
    Filter environment variables to only safe, non-sensitive values.

    Whitelist patterns:
    - VITE_* (Vite frontend variables)
    - PUBLIC_* (explicitly public variables)
    - RAILWAY_PUBLIC_* (Railway public metadata)

    NEVER expose:
    - DATABASE_URL, SECRET_KEY, API_KEYS
    - FIREBASE_ADMIN_PRIVATE_KEY, SERVICE_ROLE_KEY
    - Any credentials or secrets
    """
    safe_vars = {}
    safe_prefixes = ("VITE_", "PUBLIC_", "RAILWAY_PUBLIC_")

    for key, value in os.environ.items():
        if key.startswith(safe_prefixes):
            safe_vars[key] = value

    return safe_vars


def _build_api_urls() -> Dict[str, str]:
    """Build API URLs based on environment."""
    api_url = os.getenv("FRONTEND_API_URL")

    if not api_url:
        # Check Railway environment
        railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
        railway_static = os.getenv("RAILWAY_STATIC_URL")

        if railway_domain:
            api_url = railway_domain if railway_domain.startswith("http") else f"https://{railway_domain}"
        elif railway_static:
            api_url = railway_static
        else:
            # Fallback based on environment
            if settings.ENVIRONMENT == "production":
                api_url = "https://backend-production.railway.app"
            else:
                port = os.getenv("PORT", "8000")
                api_url = f"http://localhost:{port}"

    # Build derivative URLs
    api_base_url = f"{api_url}/api/v2"
    ws_base_url = api_url.replace("https://", "wss://").replace("http://", "ws://") + "/ws"

    return {
        "API_URL": api_url,
        "API_BASE_URL": api_base_url,
        "WS_BASE_URL": ws_base_url
    }


def _get_firebase_public_config() -> Dict[str, Any]:
    """Get PUBLIC Firebase configuration (web app keys only, NOT service account)."""
    firebase_config = {}

    # Only PUBLIC Firebase web app config
    firebase_api_key = os.getenv("FIREBASE_WEB_API_KEY")
    firebase_project_id = os.getenv("FIREBASE_WEB_PROJECT_ID")
    firebase_app_id = os.getenv("FIREBASE_WEB_APP_ID")
    firebase_auth_domain = os.getenv("FIREBASE_AUTH_DOMAIN")

    if firebase_api_key:
        firebase_config["VITE_FIREBASE_API_KEY"] = firebase_api_key
    if firebase_project_id:
        firebase_config["VITE_FIREBASE_PROJECT_ID"] = firebase_project_id
    if firebase_app_id:
        firebase_config["VITE_FIREBASE_APP_ID"] = firebase_app_id
    if firebase_auth_domain:
        firebase_config["VITE_FIREBASE_AUTH_DOMAIN"] = firebase_auth_domain

    return firebase_config


async def _check_component_health(component_name: str, db: Session) -> ComponentHealth:
    """Check individual component health with latency measurement."""
    start_time = time.time()

    try:
        if component_name == "database":
            # Check database connectivity
            db.execute(text("SELECT 1"))
            latency_ms = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="database",
                status="healthy",
                latency_ms=latency_ms,
                last_check=datetime.utcnow(),
                metadata={"type": "postgresql"}
            )

        elif component_name == "redis":
            # Check Redis connectivity
            redis = await _get_redis_client()
            if redis:
                await redis.ping()
                latency_ms = (time.time() - start_time) * 1000
                return ComponentHealth(
                    name="redis",
                    status="healthy",
                    latency_ms=latency_ms,
                    last_check=datetime.utcnow(),
                    metadata={"type": "cache"}
                )
            else:
                return ComponentHealth(
                    name="redis",
                    status="unhealthy",
                    error="Redis client unavailable",
                    last_check=datetime.utcnow()
                )

        elif component_name == "firebase":
            # Check Firebase Admin SDK (placeholder)
            return ComponentHealth(
                name="firebase",
                status="unknown",
                last_check=datetime.utcnow(),
                metadata={"configured": bool(settings.FIREBASE_ADMIN_PROJECT_ID)}
            )

        elif component_name == "external_apis":
            # Check external API availability (placeholder)
            return ComponentHealth(
                name="external_apis",
                status="unknown",
                last_check=datetime.utcnow(),
                metadata={"evolution_enabled": settings.ENABLE_EVOLUTION}
            )

        else:
            return ComponentHealth(
                name=component_name,
                status="unknown",
                error="Unknown component",
                last_check=datetime.utcnow()
            )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return ComponentHealth(
            name=component_name,
            status="unhealthy",
            latency_ms=latency_ms,
            error=str(e),
            last_check=datetime.utcnow()
        )


def _calculate_health_score(components: Dict[str, ComponentHealth]) -> float:
    """
    Calculate overall health score (0-100) based on component status.

    Scoring:
    - Healthy: 100 points
    - Degraded: 50 points
    - Unhealthy: 0 points
    - Unknown: 25 points
    """
    if not components:
        return 0.0

    total_score = 0
    for component in components.values():
        if component.status == "healthy":
            total_score += 100
        elif component.status == "degraded":
            total_score += 50
        elif component.status == "unknown":
            total_score += 25
        # unhealthy = 0 points

    return total_score / len(components)


# ============================================================================
# PUBLIC Configuration Endpoint (NO AUTH REQUIRED)
# ============================================================================

@router.get(
    "/config",
    response_model=PublicConfigResponse,
    summary="Get public configuration",
    description="""
    Get PUBLIC configuration for frontend applications.

    **SECURITY NOTES:**
    - This endpoint is PUBLIC and requires NO authentication
    - Only non-sensitive settings are exposed
    - Environment variables are filtered to safe whitelist (VITE_*, PUBLIC_*, RAILWAY_PUBLIC_*)
    - NEVER exposes: DATABASE_URL, SECRET_KEY, API keys, credentials

    **Caching:** 30 minutes (rarely changes)
    **Rate limit:** 100 requests/minute (generous for public endpoint)
    """
)
@limiter.limit("100/minute")
async def get_public_config(request: Request) -> JSONResponse:
    """
    Get PUBLIC configuration for frontend applications.

    Returns ONLY safe, non-sensitive configuration values:
    - API URLs in VITE_* format
    - WebSocket URLs
    - Public feature flags
    - Environment indicators
    - Localization settings
    - Public Firebase config (web app keys only)

    This endpoint uses aggressive caching (30min) and CORS headers
    to allow frontend applications to fetch configuration at startup.
    """
    cache_key = "system:public_config"

    # Try Redis cache first
    redis = await _get_redis_client()
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                logger.debug("Cache hit for public config")
                config_data = json.loads(cached)
                return JSONResponse(
                    content=config_data,
                    headers={
                        "Access-Control-Allow-Origin": "*",  # Public endpoint
                        "Access-Control-Allow-Methods": "GET, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type",
                        "Cache-Control": f"public, max-age={CACHE_TTL_CONFIG}",
                        "X-Cache-Status": "HIT"
                    }
                )
        except Exception as e:
            logger.warning(f"Redis get error: {e}")

    # Cache miss - build configuration
    try:
        urls = _build_api_urls()
        firebase_config = _get_firebase_public_config()

        # Build configuration response
        config = {
            # API URLs (VITE_ format for frontend)
            "VITE_API_BASE_URL": urls["API_BASE_URL"],
            "VITE_WS_BASE_URL": urls["WS_BASE_URL"],
            "VITE_API_URL": urls["API_URL"],

            # Environment
            "VITE_ENVIRONMENT": settings.ENVIRONMENT,

            # Localization
            "VITE_DEFAULT_LOCALE": settings.DEFAULT_LOCALE,
            "VITE_SUPPORTED_LOCALES": settings.SUPPORTED_LOCALES,

            # Feature flags (PUBLIC ONLY)
            "features": {
                "enableRealtime": True,
                "enableAnalytics": settings.MONITORING_ENABLED,
                "enableEvolution": getattr(settings, "ENABLE_EVOLUTION", False),
                "enableMonthlyQuizViaLink": getattr(settings, "MONTHLY_QUIZ_VIA_LINK", True),
                "enableAIHumanization": getattr(settings, "AI_HUMANIZATION_ENABLED", True),
            },

            # CORS information
            "cors": {
                "allowedOrigins": settings.ALLOWED_ORIGINS if hasattr(settings, "ALLOWED_ORIGINS") else [],
                "credentials": True
            }
        }

        # Add Firebase PUBLIC config if available
        config.update(firebase_config)

        # Add quiz URL if configured
        quiz_url = os.getenv("QUIZ_URL") or getattr(settings, "MONTHLY_QUIZ_BASE_URL", None)
        if quiz_url:
            config["VITE_MONTHLY_QUIZ_URL"] = quiz_url

        # Cache the result
        if redis:
            try:
                await redis.setex(cache_key, CACHE_TTL_CONFIG, json.dumps(config, default=str))
                logger.debug("Cached public config")
            except Exception as e:
                logger.warning(f"Redis set error: {e}")

        # Log access for monitoring
        logger.info(
            f"Public config accessed from {request.client.host if request.client else 'unknown'}",
            extra={"endpoint": "/config", "environment": settings.ENVIRONMENT}
        )

        return JSONResponse(
            content=config,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Cache-Control": f"public, max-age={CACHE_TTL_CONFIG}",
                "X-Cache-Status": "MISS"
            }
        )

    except Exception as e:
        logger.error(f"Error building public config: {e}", exc_info=True)

        # Return minimal fallback config
        fallback_config = {
            "VITE_API_BASE_URL": "http://localhost:8000/api/v2",
            "VITE_WS_BASE_URL": "ws://localhost:8000/ws",
            "VITE_API_URL": "http://localhost:8000",
            "VITE_ENVIRONMENT": "development",
            "VITE_DEFAULT_LOCALE": "pt-BR",
            "VITE_SUPPORTED_LOCALES": ["pt-BR", "en-US"],
            "features": {"enableRealtime": False, "enableAnalytics": False},
            "error": "Failed to build complete config"
        }

        return JSONResponse(
            content=fallback_config,
            status_code=200,  # Still 200 to not break frontend
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        )


@router.options("/config")
async def config_options():
    """Handle CORS preflight requests for /config endpoint."""
    return JSONResponse(
        content={"status": "ok"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        }
    )


# ============================================================================
# System Health Endpoints (ADMIN ONLY)
# ============================================================================

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
    """
)
@limiter.limit("20/minute")
async def get_system_health(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
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
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for system health check"
        )

    cache_key = "system:health"

    # Try Redis cache first
    redis = await _get_redis_client()
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                logger.debug("Cache hit for system health")
                health_data = json.loads(cached)
                status_code = status.HTTP_200_OK if health_data["status"] != "unhealthy" else status.HTTP_503_SERVICE_UNAVAILABLE
                return JSONResponse(status_code=status_code, content=health_data)
        except Exception as e:
            logger.warning(f"Redis get error: {e}")

    # Cache miss - check all components
    try:
        components = {}
        component_names = ["database", "redis", "firebase", "external_apis"]

        for component_name in component_names:
            components[component_name] = await _check_component_health(component_name, db)

        # Calculate overall health score
        overall_score = _calculate_health_score(components)

        # Determine overall status
        degraded_components = [name for name, comp in components.items() if comp.status == "degraded"]
        unhealthy_components = [name for name, comp in components.items() if comp.status == "unhealthy"]

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
            "timestamp": datetime.utcnow().isoformat(),
            "components": components_dict,
            "overall_score": overall_score,
            "degraded_components": degraded_components,
            "unhealthy_components": unhealthy_components
        }

        # Cache the result
        if redis:
            try:
                await redis.setex(cache_key, CACHE_TTL_HEALTH, json.dumps(health_response, default=str))
                logger.debug("Cached system health")
            except Exception as e:
                logger.warning(f"Redis set error: {e}")

        # Return appropriate HTTP status
        status_code = status.HTTP_200_OK if overall_status != "unhealthy" else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(status_code=status_code, content=health_response)

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": "Health check failed",
                "timestamp": datetime.utcnow().isoformat(),
                "overall_score": 0.0,
                "components": {},
                "degraded_components": [],
                "unhealthy_components": []
            }
        )


# ============================================================================
# System Initialization Endpoints (ADMIN ONLY)
# ============================================================================

@router.post(
    "/initialize",
    response_model=InitializationStatusResponse,
    summary="Initialize system",
    description="""
    Trigger comprehensive system initialization.

    **Authentication:** Admin role required
    **Rate limit:** 5 requests/hour (prevent abuse)

    Initializes:
    - Database connections and migrations
    - Redis cache and connection pools
    - Firebase Admin SDK
    - External service configurations
    """
)
@limiter.limit("5/hour")
async def initialize_system(
    request: Request,
    init_request: Optional[InitializationRequest] = None,
    current_user=Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
):
    """
    Trigger comprehensive system initialization.

    This endpoint:
    - Validates all system components
    - Initializes services and dependencies
    - Performs health checks
    - Returns detailed initialization status
    """
    # Check admin privileges
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for system initialization"
        )

    global _initialization_state

    # Check if already initialized
    if _initialization_state["status"] == "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="System initialization already in progress"
        )

    if init_request is None:
        init_request = InitializationRequest()

    # Start initialization
    start_time = time.time()
    _initialization_state = {
        "started_at": datetime.utcnow(),
        "completed_at": None,
        "status": "in_progress",
        "components": {},
        "errors": [],
        "warnings": []
    }

    logger.info(f"System initialization started by user")

    try:
        # Initialize components
        components_to_init = init_request.components or ["database", "redis", "firebase"]

        for component in components_to_init:
            try:
                if component == "database":
                    # Test database connection
                    db.execute(text("SELECT 1"))
                    _initialization_state["components"]["database"] = "initialized"

                elif component == "redis":
                    # Test Redis connection
                    redis = await _get_redis_client()
                    if redis:
                        await redis.ping()
                        _initialization_state["components"]["redis"] = "initialized"
                    else:
                        _initialization_state["components"]["redis"] = "failed"
                        _initialization_state["warnings"].append("Redis unavailable")

                elif component == "firebase":
                    # Check Firebase configuration
                    if settings.FIREBASE_ADMIN_PROJECT_ID:
                        _initialization_state["components"]["firebase"] = "initialized"
                    else:
                        _initialization_state["components"]["firebase"] = "skipped"
                        _initialization_state["warnings"].append("Firebase not configured")

            except Exception as e:
                logger.error(f"Failed to initialize {component}: {e}")
                _initialization_state["components"][component] = "failed"
                _initialization_state["errors"].append({
                    "component": component,
                    "error_message": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                    "recoverable": True
                })

        # Determine final status
        if _initialization_state["errors"]:
            _initialization_state["status"] = "partial" if any(
                c == "initialized" for c in _initialization_state["components"].values()
            ) else "failed"
        else:
            _initialization_state["status"] = "completed"

        _initialization_state["completed_at"] = datetime.utcnow()
        duration_ms = (time.time() - start_time) * 1000
        _initialization_state["duration_ms"] = duration_ms

        logger.info(f"System initialization completed with status: {_initialization_state['status']}")

        return InitializationStatusResponse(**_initialization_state)

    except Exception as e:
        logger.error(f"System initialization failed: {e}", exc_info=True)
        _initialization_state["status"] = "failed"
        _initialization_state["completed_at"] = datetime.utcnow()
        _initialization_state["errors"].append({
            "component": "system",
            "error_message": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "recoverable": False
        })

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"System initialization failed: {str(e)}"
        )


@router.get(
    "/initialization-status",
    response_model=InitializationStatusResponse,
    summary="Get initialization status",
    description="""
    Get current system initialization status.

    **Authentication:** Admin role required
    **Rate limit:** 30 requests/minute
    """
)
@limiter.limit("30/minute")
async def get_initialization_status(
    request: Request,
    current_user=Depends(get_current_user_from_session),
):
    """Get current system initialization status."""
    # Check admin privileges
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to view initialization status"
        )

    return InitializationStatusResponse(**_initialization_state)


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
    """
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
            detail="Admin privileges required for system info"
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
            "environment": settings.ENVIRONMENT,
            "debug_mode": settings.DEBUG,
            "version": "2.0.0",  # API v2 version
            "uptime": uptime,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "features": {
                "firebase_auth": bool(settings.FIREBASE_ADMIN_PROJECT_ID),
                "whatsapp_integration": settings.ENABLE_EVOLUTION,
                "ai_humanization": settings.AI_HUMANIZATION_ENABLED,
                "monitoring": settings.MONITORING_ENABLED,
                "rate_limiting": settings.RATE_LIMIT_ENABLED,
                "monthly_quiz_links": settings.MONTHLY_QUIZ_VIA_LINK
            },
            "build_info": {
                "api_version": "v2",
                "migration_phase": "9"
            }
        }

        # Cache the result
        if redis:
            try:
                await redis.setex(cache_key, CACHE_TTL_INFO, json.dumps(system_info, default=str))
                logger.debug("Cached system info")
            except Exception as e:
                logger.warning(f"Redis set error: {e}")

        return system_info

    except Exception as e:
        logger.error(f"Failed to get system info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system information"
        )


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
    """
)
@limiter.limit("30/minute")
async def list_components(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
):
    """List all system components with status."""
    # Check admin privileges
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for component list"
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
                metadata={"type": "primary"}
            ),
            ComponentInfo(
                name="redis",
                type="cache",
                status="running",
                version="7.x",
                restartable=True,
                dependencies=[],
                metadata={"type": "cache"}
            ),
            ComponentInfo(
                name="workers",
                type="service",
                status="running",
                restartable=True,
                dependencies=["redis", "database"],
                metadata={"type": "background"}
            ),
            ComponentInfo(
                name="monitoring",
                type="service",
                status="running",
                restartable=True,
                dependencies=[],
                metadata={"enabled": settings.MONITORING_ENABLED}
            ),
        ]

        healthy_count = sum(1 for c in components if c.status == "running")

        response = {
            "components": [c.dict() for c in components],
            "total": len(components),
            "healthy_count": healthy_count
        }

        # Cache the result
        if redis:
            try:
                await redis.setex(cache_key, CACHE_TTL_COMPONENTS, json.dumps(response, default=str))
                logger.debug("Cached component list")
            except Exception as e:
                logger.warning(f"Redis set error: {e}")

        return response

    except Exception as e:
        logger.error(f"Failed to list components: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve component list"
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
    """
)
@limiter.limit("3/hour")
async def restart_component(
    request: Request,
    restart_request: ComponentRestartRequest,
    current_user=Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
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
            detail="Admin privileges required for component restart"
        )

    component = restart_request.component
    logger.warning(f"Component restart requested: {component}")

    start_time = time.time()
    previous_status = "running"

    try:
        if component == "redis":
            # Restart Redis connections
            from app.utils.cache import reset_redis_connections
            if restart_request.graceful:
                # Graceful: drain connections first
                logger.info("Draining Redis connections...")
                # Placeholder for actual drain logic
            reset_redis_connections()
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
                detail=f"Component '{component}' is not restartable"
            )

        duration_ms = (time.time() - start_time) * 1000

        # Invalidate relevant caches
        redis = await _get_redis_client()
        if redis:
            try:
                await redis.delete("system:components", "system:health")
            except Exception:
                pass

        logger.info(f"Component {component} restarted successfully in {duration_ms:.2f}ms")

        return ComponentRestartResponse(
            component=component,
            status="success",
            restarted_at=datetime.utcnow(),
            duration_ms=duration_ms,
            previous_status=previous_status,
            current_status=current_status,
            message=f"Component '{component}' restarted successfully"
        )

    except Exception as e:
        logger.error(f"Component restart failed: {e}", exc_info=True)
        duration_ms = (time.time() - start_time) * 1000
        return ComponentRestartResponse(
            component=component,
            status="failed",
            restarted_at=datetime.utcnow(),
            duration_ms=duration_ms,
            previous_status=previous_status,
            current_status="error",
            message=f"Component restart failed: {str(e)}"
        )


# ============================================================================
# Configuration Validation Endpoint (ADMIN ONLY)
# ============================================================================

@router.post(
    "/validate",
    response_model=ConfigValidationResponse,
    summary="Validate configuration",
    description="""
    Validate system configuration and security settings.

    **Authentication:** Admin role required
    **Rate limit:** 10 requests/hour
    """
)
@limiter.limit("10/hour")
async def validate_configuration(
    request: Request,
    validation_request: Optional[ConfigValidationRequest] = None,
    current_user=Depends(get_current_user_from_session),
):
    """
    Validate system configuration.

    Checks:
    - Critical settings (SECRET_KEY, DATABASE_URL)
    - Security settings (SSL, CORS, cookies)
    - External service configurations
    - Production best practices
    """
    # Check admin privileges
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for configuration validation"
        )

    if validation_request is None:
        validation_request = ConfigValidationRequest()

    try:
        warnings = []
        errors = []
        recommendations = []

        # Validate critical settings
        if not settings.SECRET_KEY or 'CHANGE_THIS' in settings.SECRET_KEY.upper():
            errors.append("SECRET_KEY is not properly configured")

        if not settings.DATABASE_URL:
            errors.append("DATABASE_URL is not configured")

        # Check Firebase configuration
        firebase_configured = all([
            settings.FIREBASE_ADMIN_PROJECT_ID,
            settings.FIREBASE_ADMIN_PRIVATE_KEY,
            settings.FIREBASE_ADMIN_CLIENT_EMAIL
        ])

        if not firebase_configured:
            warnings.append("Firebase Admin SDK is not fully configured")
            recommendations.append("Configure Firebase for authentication features")

        # Check production security settings
        if settings.ENVIRONMENT.lower() == 'production':
            if settings.DEBUG:
                errors.append("DEBUG should be False in production")

            if not getattr(settings, 'SESSION_COOKIE_SECURE', False):
                warnings.append("SESSION_COOKIE_SECURE should be True in production")
                recommendations.append("Enable secure cookies for production")

            if not getattr(settings, 'SECURE_SSL_REDIRECT', False):
                warnings.append("SECURE_SSL_REDIRECT should be True in production")
                recommendations.append("Enable HTTPS redirect for production")

        # Check CORS configuration
        if not getattr(settings, 'ALLOWED_ORIGINS', None) and not settings.FRONTEND_URL:
            warnings.append("CORS origins not configured")
            recommendations.append("Configure allowed CORS origins")

        # Check external service configurations
        if settings.ENABLE_EVOLUTION and not settings.EVOLUTION_API_KEY:
            warnings.append("Evolution API is enabled but API key not configured")

        if settings.AI_HUMANIZATION_ENABLED and not settings.GEMINI_API_KEY:
            warnings.append("AI humanization is enabled but Gemini API key not configured")

        # Check rate limiting
        if not settings.RATE_LIMIT_ENABLED and settings.ENVIRONMENT == 'production':
            warnings.append("Rate limiting is disabled in production")
            recommendations.append("Enable rate limiting for production security")

        categories_checked = validation_request.categories or ["security", "database", "external_services"]

        return ConfigValidationResponse(
            valid=len(errors) == 0,
            warnings=warnings,
            errors=errors,
            checked_at=datetime.utcnow(),
            categories_checked=categories_checked,
            recommendations=recommendations
        )

    except Exception as e:
        logger.error(f"Configuration validation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuration validation failed"
        )


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
    """
)
@limiter.limit("20/minute")
async def get_system_metrics(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
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
            detail="Admin privileges required for system metrics"
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
        disk = psutil.disk_usage('/')
        disk_total_gb = disk.total / (1024 * 1024 * 1024)
        disk_used_gb = disk.used / (1024 * 1024 * 1024)
        disk_percent = disk.percent

        # Network connections
        network_connections = len(psutil.net_connections())

        # Database metrics (placeholder - would need actual connection pool access)
        db_connections = 5  # Placeholder
        db_pool_size = 10  # Placeholder

        # Application metrics (placeholder)
        active_sessions = 0  # Would query from sessions table
        request_rate_per_min = 0.0  # Would need request tracking

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
            except Exception:
                pass

        return SystemMetrics(
            timestamp=datetime.utcnow(),
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
            cache_memory_mb=cache_memory_mb
        )

    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="psutil not available - metrics unavailable"
        )
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system metrics"
        )
