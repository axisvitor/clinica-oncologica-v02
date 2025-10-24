"""
Router registration for the FastAPI application.

Centralizes all router inclusion logic. This file has been refactored
to disable all V1 endpoints, preparing for their complete removal.
Only V2 and essential health/monitoring endpoints are now active.
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
    logger.info("Loading router registration. V1 and V2 endpoints are both active.")

    # === V1 IMPORTS (ACTIVE FOR PRODUCTION) ===
    logger.info("Importing V1 routers for production use...")
    try:
        from app.api.v1 import (
            auth, patients, messages, flows, quiz, quiz_responses, reports, alerts, webhooks,
            monthly_quiz, monthly_quiz_public, ai, metrics, admin_users,
            upload, medico, physician, analytics, dashboard
        )
        from app.routers.quiz_auth import router as quiz_auth
        logger.info("✓ V1 routers imported successfully.")
    except Exception as e:
        logger.error(f"Error importing V1 routers: {e}")
        raise

    # === ESSENTIAL & V2 IMPORTS ===
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

    # Redis health endpoint (kept from V1 as it's a critical health check)
    @app.get("/api/v1/redis/health", tags=["Health"])
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
    logger.info("✓ Redis health check endpoint registered.")


    # === V1 ROUTERS (ACTIVE FOR PRODUCTION) ===
    logger.info("Registering V1 endpoints for production use...")
    
    # Core authentication and session
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(auth_session, prefix="/api/v1", tags=["Session Authentication"])
    logger.info("✓ Auth endpoints registered")
    
    # Patient management
    app.include_router(patients.router, prefix="/api/v1/patients", tags=["Patients"])
    app.include_router(medico.router, prefix="/api/v1", tags=["Medico"])
    app.include_router(physician.router, prefix="/api/v1", tags=["Physician"])
    logger.info("✓ Patient management endpoints registered")
    
    # Quiz system
    app.include_router(quiz.router, prefix="/api/v1/quiz", tags=["Quiz"])
    app.include_router(quiz_responses.router, prefix="/api/v1", tags=["Quiz Responses"])
    app.include_router(monthly_quiz.router, prefix="/api/v1/monthly-quiz", tags=["Monthly Quiz"])
    app.include_router(monthly_quiz_public.router, prefix="/api/v1/monthly-quiz-public", tags=["Monthly Quiz Public"])
    app.include_router(quiz_auth, tags=["Quiz Authentication"])
    logger.info("✓ Quiz endpoints registered")
    
    # Communication
    app.include_router(messages.router, prefix="/api/v1/messages", tags=["Messages"])
    app.include_router(flows.router, prefix="/api/v1/flows", tags=["Flows"])
    app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
    logger.info("✓ Communication endpoints registered")
    
    # Reports and analytics
    app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
    app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
    app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
    app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alerts"])
    logger.info("✓ Reports and analytics endpoints registered")
    
    # AI and metrics
    app.include_router(ai.router, prefix="/api/v1", tags=["AI Services"])
    app.include_router(metrics.router, prefix="/api/v1", tags=["Healthcare Metrics"])
    logger.info("✓ AI and metrics endpoints registered")
    
    # Admin and utilities
    app.include_router(admin_users.router, prefix="/api/v1/admin/users", tags=["Admin Users"])
    app.include_router(upload.router, prefix="/api/v1/upload", tags=["Upload"])
    logger.info("✓ Admin and utility endpoints registered")
    
    # WhatsApp integration (if enabled)
    try:
        if getattr(settings, 'ENABLE_EVOLUTION', False):
            from app.integrations.whatsapp import whatsapp_router, webhook_router
            app.include_router(whatsapp_router, tags=["WhatsApp"])
            app.include_router(webhook_router)
            logger.info("✓ WhatsApp integration endpoints registered")
    except ImportError as e:
        logger.warning(f"WhatsApp integration not available: {e}")


    # === API V2 ROUTER (ACTIVE) ===
    # Include API v2 router - Modern REST API with cursor pagination
    app.include_router(api_v2_router, tags=["API v2"])
    logger.info("✓ API v2 endpoints registered (/api/v2)")

    logger.info("All routers registered successfully. V1 (production) and V2 (ready for migration) are both active.")
