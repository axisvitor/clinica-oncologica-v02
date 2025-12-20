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
    """
    origins = settings.get_cors_origins()

    # Development fallback if no origins configured
    if not origins and not is_production():
        origins = [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:5173",
        ]
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

    # Allowed headers for CORS requests
    allowed_headers = [
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-CSRF-Token",
        "X-CSRFToken",
        "X-XSRF-Token",
    ]

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
