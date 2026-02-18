"""
CORS Configuration - Simplified Implementation

Simple, clean CORS configuration for FastAPI.
All origins come from settings.get_cors_origins().
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import logging

from app.config.settings import settings

logger = logging.getLogger(__name__)


def is_production() -> bool:
    """Check if running in production environment."""
    return settings.APP_ENVIRONMENT.lower() in ("production", "prod")


def get_allowed_origins() -> List[str]:
    """
    Get allowed CORS origins from settings.

    Returns origins from environment variables with development fallbacks.

    SECURITY: Validates that wildcard origins are not used in production
    to prevent credential theft attacks.
    """
    origins = settings.get_cors_origins()

    # SECURITY: Block wildcard origins in production
    # Wildcard with credentials=True is a critical security vulnerability
    if is_production():
        if "*" in origins:
            logger.error(
                "SECURITY CRITICAL: Wildcard '*' CORS origin is NOT allowed in production! "
                "This would allow any website to make authenticated requests. "
                "Please configure specific origins in CORS_ALLOWED_ORIGINS."
            )
            # Remove wildcard from origins in production
            origins = [o for o in origins if o != "*"]

        if not origins:
            logger.error(
                "SECURITY WARNING: No CORS origins configured for production! "
                "All cross-origin requests will be blocked. "
                "Set CORS_FRONTEND_URL or CORS_ALLOWED_ORIGINS environment variable."
            )

    # Development defaults (merged with explicit origins)
    if not is_production():
        dev_origins = [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://localhost:5176",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://127.0.0.1:5175",
            "http://127.0.0.1:5176",
        ]
        if origins:
            extra = [origin for origin in dev_origins if origin not in origins]
            if extra:
                origins = origins + extra
                logger.info("Added default localhost origins for development")
        else:
            origins = dev_origins
            logger.warning("Using default localhost origins for development")

    return origins


def configure_cors(app: FastAPI) -> None:
    """
    Configure CORS middleware with origins from settings.

    Middleware order note: CORS must execute FIRST to handle preflight OPTIONS.
    In FastAPI, middlewares execute in reverse order of addition, so CORS
    should be added LAST in the middleware setup.

    Args:
        app: FastAPI application instance
    """
    origins = get_allowed_origins()

    # Log each origin for debugging CORS issues
    if origins:
        logger.info(f"[CORS] Configuring {len(origins)} allowed origins:")
        for origin in origins:
            logger.info(f"[CORS]   - {origin}")
    else:
        logger.warning("[CORS] No origins configured! All CORS requests will be blocked.")

    # Allowed headers for CORS requests (validated in settings).
    default_allowed_headers = [
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-CSRF-Token",
        "X-CSRFToken",
        "X-XSRF-Token",
        "X-Session-ID",
        "X-Idempotency-Key",
    ]
    configured_headers = getattr(settings, "CORS_ALLOWED_HEADERS", None)
    if isinstance(configured_headers, (list, tuple, set)) and configured_headers:
        allowed_headers = list(configured_headers)
    else:
        allowed_headers = default_allowed_headers

    # Headers exposed to JavaScript
    expose_headers = [
        "Content-Type",
        "X-CSRF-Token",
        "X-Total-Count",
        "X-Page",
        "X-Per-Page",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=allowed_headers,
        expose_headers=expose_headers,
        max_age=3600,  # Cache preflight for 1 hour
    )

    # Log configuration summary
    env = "PRODUCTION" if is_production() else "DEVELOPMENT"
    logger.info(f"[CORS] {env} mode - {len(origins)} origins, credentials=True, max_age=3600s")
