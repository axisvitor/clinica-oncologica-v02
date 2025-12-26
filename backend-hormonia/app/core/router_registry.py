"""
Router registration for the FastAPI application.

V2 VERSIONING SYSTEM:
- API v2 (current version)
- Essential health/monitoring endpoints
"""

from datetime import datetime, timezone
from fastapi import FastAPI
from app.config import settings
from app.utils.logging import get_logger
import redis.asyncio as redis
from app.utils.security import mask_sensitive_url
from app.core.redis_manager import get_redis_connection_kwargs, get_redis_url_with_ssl

# Import API versioning infrastructure
from app.api.versioning import get_versioned_router


def register_routers(app: FastAPI) -> None:
    """
    Register all API routers with the FastAPI application.

    Includes:
    - Health/monitoring endpoints
    - API v2 (current)
    - Version middleware

    Args:
        app: FastAPI application instance
    """
    logger = get_logger(__name__)
    logger.info("Loading router registration with API versioning support (v2)")

    # === V2 IMPORTS ===
    from app.routers.health import router as health_monitoring
    from app.routers.auth_session import router as auth_session
    from app.monitoring import prometheus_exporters

    # Import v2 API (current)
    try:
        from app.api.v2 import api_v2_router

        logger.info("✓ API v2 router imported successfully (current)")
    except ImportError as e:
        logger.critical(f"FATAL: API v2 could not be imported. Error: {e}")
        raise RuntimeError(
            "Application startup failed: API v2 router could not be imported"
        ) from e

    # === ESSENTIAL ROUTERS (ACTIVE) ===
    # Monitoring health endpoints
    app.include_router(health_monitoring, tags=["Health"])
    logger.info(
        "✓ Health monitoring endpoints registered (/health/live, /health/ready, /health/metrics)"
    )

    # Include Prometheus metrics router
    app.include_router(prometheus_exporters.router)
    logger.info("✓ Prometheus metrics exporter registered (/metrics)")

    # Session authentication endpoints
    app.include_router(auth_session, tags=["Session Authentication"])
    logger.info("✓ Session authentication endpoints registered (/session)")

    # Redis health endpoint (migrated from v1)
    @app.get("/api/v2/redis/health", tags=["Health"])
    async def redis_health():
        redis_url = get_redis_url_with_ssl()
        health_data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "redis_url": mask_sensitive_url(redis_url),
            "status": "unknown",
        }
        redis_client = None
        try:
            kwargs = get_redis_connection_kwargs(socket_connect_timeout=3)
            redis_client = redis.from_url(redis_url, **kwargs)
            await redis_client.ping()
            info = await redis_client.info()
            health_data["status"] = "healthy"
            health_data["version"] = info.get("redis_version")
            health_data["memory_usage"] = info.get("used_memory_human")
        except Exception as e:
            health_data["status"] = "unavailable"
            health_data["error"] = str(e)
            logger.error(f"Redis health check failed: {e}")
        finally:
            if redis_client:
                await redis_client.aclose()  # Redis 5.x uses aclose() for async
        return health_data

    logger.info("✓ Redis health check endpoint registered (/api/v2/redis/health)")

    # === VERSIONING SETUP ===
    # Get versioned router instance
    versioned_router = get_versioned_router()

    # Register v2 API (current version)
    versioned_router.add_version(version="v2", router=api_v2_router, is_default=True)
    app.include_router(api_v2_router, tags=["API v2"])
    logger.info("✓ API v2 endpoints registered (/api/v2) - CURRENT VERSION")

    # Add version middleware (must be added after routes)
    app.middleware("http")(versioned_router.get_version_middleware())
    logger.info("✓ API versioning middleware enabled")

    # WhatsApp integration (if enabled)
    try:
        if getattr(settings, "WHATSAPP_ENABLE_SERVICE", False):
            from app.integrations.whatsapp import whatsapp_router, webhook_router

            app.include_router(whatsapp_router, tags=["WhatsApp"])
            app.include_router(webhook_router)
            logger.info("✓ WhatsApp integration endpoints registered")
    except ImportError as e:
        logger.warning(f"WhatsApp integration not available: {e}")

    logger.info("✅ All routers registered successfully. API v2 is active.")
