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
    logger.info("Loading router registration. V1 endpoints are deprecated and disabled.")

    # === V1 IMPORTS (DISABLED) ===
    # logger.info("V1 router imports are disabled.")
    # try:
    #     from app.api.v1 import (
    #         auth, patients, messages, flows, quiz, quiz_responses, reports, alerts, webhooks,
    #         tasks, localization, analytics, dashboard, docs, health, performance,
    #         platform_sync, template_management, template_versioning, monthly_quiz, monthly_quiz_public, ai, metrics, debug, config, admin_users, admin_roles,
    #         health_rls, upload, medico, physician, system, templates_crud, worker_health
    #     )
    #     from app.api.v1.health import router as comprehensive_health_router
    #     from app.routers.quiz_auth import router as quiz_auth
    #     from app.routers.auth_session import router as auth_session
    #     from app.routers.health import router as health_monitoring
    # except Exception as e:
    #     logger.error(f"An error occurred during V1 router import (which is expected as they are disabled): {e}")

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


    # === V1 ROUTERS (ALL DISABLED) ===
    logger.warning("All /api/v1/ endpoints are disabled and will be removed in a future update.")
    # app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    # app.include_router(auth_session, prefix="/api/v1", tags=["Session Authentication"])
    # app.include_router(medico.router, prefix="/api/v1", tags=["Medico"])
    # app.include_router(physician.router, prefix="/api/v1", tags=["Physician"])
    # app.include_router(worker_health.router, prefix="/api/v1", tags=["Worker Health"])
    # from app.api.v1.admin import admin_router
    # app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])
    # app.include_router(admin_roles.router, prefix="/api/v1/admin/roles", tags=["Admin Roles"])
    # app.include_router(patients.router, prefix="/api/v1/patients", tags=["Patients"])
    # app.include_router(messages.router, prefix="/api/v1/messages", tags=["Messages"])
    # app.include_router(flows.router, prefix="/api/v1/flows", tags=["Flows"])
    # app.include_router(upload.router, prefix="/api/v1/upload", tags=["Upload"])
    # app.include_router(template_management.router, prefix="/api/v1/template-management", tags=["Template Management"])
    # app.include_router(template_versioning.router, prefix="/api/v1/flows/templates", tags=["Template Versioning"])
    # app.include_router(templates_crud.router, prefix="/api/v1", tags=["Templates CRUD"])
    # app.include_router(quiz.router, prefix="/api/v1/quiz", tags=["Quiz"])
    # app.include_router(quiz_responses.router, prefix="/api/v1", tags=["Quiz Responses"])
    # app.include_router(monthly_quiz.router, prefix="/api/v1/monthly-quiz", tags=["Monthly Quiz"])
    # app.include_router(monthly_quiz_public.router, prefix="/api/v1/monthly-quiz-public", tags=["Monthly Quiz Public"])
    # app.include_router(quiz_auth, tags=["Quiz Authentication"])
    # app.include_router(ai.router, prefix="/api/v1", tags=["AI Services"])
    # app.include_router(metrics.router, prefix="/api/v1", tags=["Healthcare Metrics"])
    # app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
    # app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
    # app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
    # app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alerts"])
    # app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
    # app.include_router(tasks.router, prefix="/api/v1", tags=["Tasks"])
    # app.include_router(localization.router, prefix="/api/v1/localization", tags=["Localization"])
    # app.include_router(docs.router, prefix="/api/v1/docs", tags=["Documentation"])
    # app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    # from app.api.v1 import enhanced_health
    # app.include_router(enhanced_health.router, prefix="/api/v1", tags=["Health"])
    # app.include_router(config.router, prefix="/api/v1", tags=["Configuration"])
    # app.include_router(config.router, prefix="", tags=["Configuration"])
    # if settings.DEBUG or getattr(settings, 'ENABLE_DEBUG_ENDPOINTS', False):
    #     app.include_router(debug.router, prefix="/api/v1/debug", tags=["Debug"])
    # app.include_router(comprehensive_health_router, prefix="/api/v1", tags=["Health"])
    # from app.api.v1.production_health import router as prod_health_router
    # app.include_router(prod_health_router, tags=["Health"])
    # from app.api.v1 import database_health
    # app.include_router(database_health.router, prefix="/api/v1", tags=["Database Health"])
    # app.include_router(system.router, prefix="/api/v1/system", tags=["System Management"])
    # app.include_router(performance.router, prefix="/api/v1", tags=["Performance"])
    # app.include_router(platform_sync.router, prefix="/api/v1", tags=["Platform Sync"])
    # from app.api import websockets, enhanced_websockets
    # app.include_router(websockets.router, prefix="/ws")
    # from app.api.v1 import (
    #     enhanced_analytics, enhanced_messages, enhanced_quiz,
    #     enhanced_reports, enhanced_monitoring, monitoring
    # )
    # app.include_router(enhanced_analytics.router, prefix="/api/v1/enhanced/analytics", tags=["Enhanced Analytics"])
    # app.include_router(enhanced_messages.router, prefix="/api/v1/enhanced/messages", tags=["Enhanced Messages"])
    # app.include_router(enhanced_quiz.router, prefix="/api/v1/enhanced/quiz", tags=["Enhanced Quiz"])
    # app.include_router(enhanced_reports.router, prefix="/api/v1/enhanced/reports", tags=["Enhanced Reports"])
    # app.include_router(enhanced_monitoring.router, prefix="/api/v1/enhanced", tags=["Enhanced Monitoring"])
    # app.include_router(enhanced_websockets.router, prefix="/ws/enhanced", tags=["Enhanced WebSocket"])
    # try:
    #     if getattr(settings, 'ENABLE_EVOLUTION', False):
    #         from app.integrations.whatsapp import whatsapp_router, webhook_router
    #         app.include_router(whatsapp_router, tags=["WhatsApp"])
    #         app.include_router(webhook_router)
    # except ImportError as e:
    #     logger.warning(f"WhatsApp integration not available: {e}")
    # app.include_router(monitoring.router, prefix="/api/v1", tags=["Monitoring"])


    # === API V2 ROUTER (ACTIVE) ===
    # Include API v2 router - Modern REST API with cursor pagination
    app.include_router(api_v2_router, tags=["API v2"])
    logger.info("✓ API v2 endpoints registered (/api/v2)")

    logger.info("All active routers registered successfully. API v2 is the primary API.")
