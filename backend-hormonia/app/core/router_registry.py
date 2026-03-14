"""
Router registration for the FastAPI application.

V2 VERSIONING SYSTEM:
- API v2 (current version)
- Essential health/monitoring endpoints
"""

from fastapi import FastAPI
from app.config import settings
from app.utils.logging import get_logger
import redis.asyncio as redis
import os
import sys
from app.utils.security import mask_sensitive_url
from app.core.redis_manager import get_redis_connection_kwargs, get_redis_url_with_ssl

# Import API versioning infrastructure
from app.api.versioning import get_versioned_router
from app.utils.timezone import now_sao_paulo, to_sao_paulo


def _is_test_environment() -> bool:
    return bool(
        "pytest" in sys.modules
        or os.getenv("PYTEST_CURRENT_TEST")
        or os.getenv("TESTING") == "1"
        or os.getenv("APP_ENVIRONMENT", "").lower() in ("test", "testing")
    )


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

    # Legacy root /session tombstones
    app.include_router(auth_session, tags=["Retired Session Endpoints"])
    logger.info("✓ Legacy /session retirement endpoints registered")

    # Redis health endpoint (migrated from v1)
    @app.get("/api/v2/redis/health", tags=["Health"])
    async def redis_health():
        from app.core.redis_manager import get_redis_manager
        redis_url = get_redis_url_with_ssl()
        health_data = {
            "timestamp": now_sao_paulo().isoformat(),
            "redis_url": mask_sensitive_url(redis_url),
            "status": "unknown",
        }
        try:
            manager = get_redis_manager()
            client = await manager.get_async_client()
            await client.ping()
            info = await client.info()
            health_data["status"] = "healthy"
            health_data["version"] = info.get("redis_version")
            health_data["memory_usage"] = info.get("used_memory_human")
        except Exception as e:
            health_data["status"] = "unavailable"
            health_data["error"] = str(e)
            logger.error(f"Redis health check failed: {e}")
        return health_data

    logger.info("✓ Redis health check endpoint registered (/api/v2/redis/health)")

    # Short quiz link resolver (simple redirect to tokenized link)
    from fastapi import Depends, HTTPException
    from fastapi.responses import RedirectResponse
    from sqlalchemy.orm import Session
    from app.database import get_db
    from app.models.quiz import QuizSession
    from app.domain.quizzes.session import TokenManager
    from app.core.monthly_quiz_config import get_monthly_quiz_config
    from datetime import datetime, timedelta

    @app.get("/q/{code}", tags=["Quiz"])
    async def resolve_quiz_short_link(code: str, db: Session = Depends(get_db)):
        code = code.strip()
        if not code:
            raise HTTPException(status_code=404, detail="Link inválido")

        session = (
            db.query(QuizSession)
            .filter(QuizSession.session_metadata["short_code"].astext == code)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Link inválido")

        if session.status in ["completed", "cancelled", "expired"]:
            raise HTTPException(status_code=410, detail="Link expirado")

        metadata = dict(session.session_metadata or {})
        link_status = str(metadata.get("link_status", "")).strip().lower()
        if link_status in {"cancelled", "revoked", "expired"}:
            raise HTTPException(status_code=410, detail="Link expirado")

        config = get_monthly_quiz_config()
        now = now_sao_paulo()

        metadata_expires_at = None
        raw_expires_at = metadata.get("expires_at")
        if raw_expires_at:
            try:
                metadata_expires_at = to_sao_paulo(datetime.fromisoformat(raw_expires_at))
            except (TypeError, ValueError):
                metadata_expires_at = None

        session_expires_at = to_sao_paulo(session.expiration_date) if session.expiration_date else None
        if session_expires_at and metadata_expires_at:
            expires_at = min(session_expires_at, metadata_expires_at)
        else:
            expires_at = session_expires_at or metadata_expires_at

        if expires_at is None:
            expires_at = now + timedelta(hours=config.MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS)

        if now >= expires_at:
            session.status = "expired"
            metadata["link_status"] = "expired"
            metadata["expired_at"] = now.isoformat()
            metadata["expires_at"] = expires_at.isoformat()
            session.expiration_date = expires_at
            session.session_metadata = metadata
            db.commit()
            raise HTTPException(status_code=410, detail="Link expirado")

        token_manager = TokenManager()
        token = token_manager.generate_token(
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            expires_at=expires_at,
            session_id=session.id,
            token_type="quiz_access",
        )

        # Persist access and token metadata for consistency with other flows.
        metadata["token_hash"] = token_manager.hash_token(token)
        metadata["expires_at"] = expires_at.isoformat()
        metadata["access_count"] = int(metadata.get("access_count", 0) or 0) + 1
        metadata["accessed_at"] = now.isoformat()
        metadata["link_status"] = "active"
        session.expiration_date = expires_at
        session.session_metadata = metadata
        db.commit()

        redirect_url = f"{config.MONTHLY_QUIZ_BASE_URL}?token={token}"
        return RedirectResponse(url=redirect_url, status_code=302)

    # === VERSIONING SETUP ===
    # Get versioned router instance
    versioned_router = get_versioned_router()

    # Register v2 API (current version)
    versioned_router.add_version(version="v2", router=api_v2_router, is_default=True)
    app.include_router(api_v2_router, tags=["API v2"])
    logger.info("✓ API v2 endpoints registered (/api/v2) - CURRENT VERSION")

    # Add version middleware (must be added after routes)
    if _is_test_environment():
        logger.info("ℹ️ Skipping API versioning middleware in test environment")
    else:
        app.middleware("http")(versioned_router.get_version_middleware())
        logger.info("✓ API versioning middleware enabled")

    # WhatsApp integration (if enabled)
    try:
        if getattr(settings, "WHATSAPP_ENABLE_SERVICE", False):
            from app.integrations.whatsapp import whatsapp_router

            app.include_router(whatsapp_router, tags=["WhatsApp"])
            logger.info("✓ WhatsApp integration endpoints registered")
    except ImportError as e:
        logger.warning(f"WhatsApp integration not available: {e}")

    # === WEBSOCKETS ===
    try:
        from app.api.websockets import router as websocket_router
        app.include_router(websocket_router, prefix="/ws", tags=["WebSockets"])
        logger.info("✓ WebSocket endpoints registered (/ws)")
    except ImportError as e:
        logger.error(f"Failed to register WebSocket router: {e}")


    logger.info("✅ All routers registered successfully. API v2 is active.")
