"""
Router registration for the FastAPI application.

V2-ONLY SYSTEM: All V1 endpoints foram removidos.
Somente a API v2 e os endpoints essenciais de health/monitoring seguem ativos.
"""
from datetime import datetime
from fastapi import FastAPI
import os
from app.config import settings
from app.utils.logging import get_logger
import redis.asyncio as redis
from app.utils.security import mask_sensitive_url


def register_routers(app: FastAPI) -> None:
    """
    Register all API routers with the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    logger = get_logger(__name__)
    logger.info("Loading router registration. V2 API only - V1 has been removed.")

    # === V2 & ESSENTIAL IMPORTS ===
    from app.routers.health import router as health_monitoring
    from app.routers.auth_session import router as auth_session
    from app.monitoring import prometheus_exporters
    try:
        from app.api.v2 import api_v2_router
        logger.info("✓ API v2 router imported successfully.")
    except ImportError as e:
        logger.critical(f"FATAL: API v2 could not be imported. Application cannot start. Error: {e}")
        raise RuntimeError("Application startup failed: API v2 router could not be imported") from e

    # === ESSENTIAL ROUTERS (ACTIVE) ===
    # Monitoring health endpoints
    app.include_router(health_monitoring, tags=["Health"])
    logger.info("✓ Health monitoring endpoints registered (/health/live, /health/ready, /health/metrics)")

    # Include Prometheus metrics router
    app.include_router(prometheus_exporters.router)
    logger.info("✓ Prometheus metrics exporter registered (/metrics)")

    # Session authentication endpoints
    app.include_router(auth_session, tags=["Session Authentication"])
    logger.info("✓ Session authentication endpoints registered (/session)")

    # Redis health endpoint (migrated from v1)
    @app.get("/api/v2/redis/health", tags=["Health"])
    async def redis_health():
        redis_url = settings.REDIS_URL
        health_data = {"timestamp": datetime.utcnow().isoformat() + 'Z', "redis_url": mask_sensitive_url(redis_url), "status": "unknown"}
        redis_client = None
        try:
            redis_client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=3)
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
                await redis_client.close()
        return health_data
    logger.info("✓ Redis health check endpoint registered (/api/v2/redis/health)")

    # === API V2 ROUTER (PRIMARY API) ===
    # Include API v2 router - Modern REST API with cursor pagination
    app.include_router(api_v2_router, tags=["API v2"])
    logger.info("✓ API v2 endpoints registered (/api/v2)")

    # WhatsApp integration (if enabled) - Migrated to use v2 patterns
    try:
        if getattr(settings, 'ENABLE_EVOLUTION', False):
            from app.integrations.whatsapp import whatsapp_router, webhook_router
            app.include_router(whatsapp_router, tags=["WhatsApp"])
            app.include_router(webhook_router)
            logger.info("✓ WhatsApp integration endpoints registered")
    except ImportError as e:
        logger.warning(f"WhatsApp integration not available: {e}")

    logger.info("✅ All routers registered successfully. V2 API is now the primary and only API version.")
