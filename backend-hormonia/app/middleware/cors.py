"""
CORS Middleware Configuration - Production Security Guard

This module provides CORS configuration with production security validation.
All CORS origins MUST come from environment variables via settings.get_cors_origins().

Security Rules:
1. NO regex patterns in production
2. NO wildcard (*) origins in production
3. All origins must be HTTPS in production
4. Origins are ONLY sourced from SecuritySettings (no env var parsing here)

Architecture:
- settings.py: Single source of truth for CORS origins (parses env vars)
- cors.py: Security validation and middleware configuration
"""

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from typing import List, Optional
from app.config.settings import settings


def is_production() -> bool:
    """
    Check if running in production environment.

    Returns:
        bool: True if production mode
    """
    return settings.APP_ENVIRONMENT.lower() in ["production", "prod"]


def validate_cors_origins(
    allow_origins: List[str], allow_origin_regex: Optional[str] = None
) -> None:
    """
    Validate CORS configuration for production safety

    Security Rules:
    1. NO regex patterns in production
    2. NO wildcard (*) origins in production
    3. All origins must be HTTPS in production

    Args:
        allow_origins: List of allowed origin URLs
        allow_origin_regex: Regex pattern for origins

    Raises:
        ValueError: If configuration violates production security rules
    """
    if not is_production():
        return  # Development mode - no restrictions

    # Rule 1: No regex in production
    if allow_origin_regex:
        raise ValueError(
            "CORS origin regex not allowed in production. "
            "Use explicit origin list instead for security."
        )

    # Rule 2: No wildcard origins in production
    if "*" in allow_origins:
        raise ValueError(
            "CORS wildcard origin (*) not allowed in production. "
            "Specify explicit origins for security."
        )

    # Rule 3: All origins must be HTTPS in production
    for origin in allow_origins:
        if not origin.startswith("https://"):
            raise ValueError(
                f"CORS origin '{origin}' must use HTTPS in production. "
                f"HTTP is not allowed for security."
            )


def configure_cors(
    app: FastAPI,
    allowed_origin_regex: Optional[str] = None,
    allow_credentials: bool = True,
    allow_methods: Optional[List[str]] = None,
    allow_headers: Optional[List[str]] = None,
) -> None:
    """
    Configure CORS middleware with production security validation.

    IMPORTANT: ALL origins are sourced from settings.get_cors_origins().
    Do NOT pass origins manually - configure via environment variables instead.

    Production Security:
    - Origins must be explicit HTTPS URLs (no wildcards, no regex)
    - Credentials enabled for httpOnly cookies
    - Explicit header whitelist (NEVER "*" with credentials)

    Development Defaults:
    - Origins from environment or localhost fallbacks
    - More permissive configuration

    Security Note:
    Using allow_headers=["*"] with allow_credentials=True is a critical
    vulnerability that exposes all request headers (Authorization, cookies)
    to cross-origin requests. Always use explicit header whitelists.

    Args:
        app: FastAPI application instance
        allowed_origin_regex: Regex pattern for origins (forbidden in production)
        allow_credentials: Allow credentials (cookies)
        allow_methods: Allowed HTTP methods
        allow_headers: Allowed request headers (explicit list required)

    Raises:
        ValueError: If production security rules violated or origins not configured
    """
    # Get origins from settings (single source of truth)
    allowed_origins = settings.get_cors_origins()

    # Fallback to localhost in development if no origins configured
    if not allowed_origins and not is_production():
        allowed_origins = [
            "http://localhost:3000",  # Legacy frontend port
            "http://localhost:3001",  # Quiz Interface
            "http://localhost:5173",  # Frontend Hormonia Vite (current)
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:5173",
        ]

    # Production requires explicit origins from environment
    if is_production() and not allowed_origins:
        raise ValueError(
            "CORS origins must be configured in production via environment variables:\n"
            "  - CORS_ALLOWED_ORIGINS: Explicit list of allowed origins\n"
            "  - CORS_FRONTEND_URL: Frontend application URL\n"
            "  - CORS_QUIZ_URL: Quiz interface URL\n"
            "See app/config/settings/security.py for configuration details."
        )

    # Validate configuration for production security
    validate_cors_origins(allowed_origins, allowed_origin_regex)

    # Default methods
    if allow_methods is None:
        allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]

    # Default headers - Use explicit list for security
    # SECURITY: Never use ["*"] with allow_credentials=True
    # This would expose all request headers to cross-origin requests,
    # potentially leaking sensitive authentication tokens and credentials.
    # Explicit whitelist follows principle of least privilege.
    if allow_headers is None:
        allow_headers = [
            "Content-Type",  # Standard content negotiation
            "Authorization",  # Bearer tokens and basic auth
            "X-Requested-With",  # AJAX request detection
            "X-CSRF-Token",  # CSRF protection tokens
            "Accept",  # Content type acceptance
            "Origin",  # Request origin (required for CORS)
        ]

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=allowed_origin_regex,
        allow_credentials=allow_credentials,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
        expose_headers=[
            "content-type",
            "x-csrf-token",
            "x-total-count",
            "x-page",
            "x-per-page",
        ],
        max_age=3600,  # Cache preflight for 1 hour
    )

    # Log configuration (sanitized) for debugging
    import logging

    logger = logging.getLogger(__name__)

    log_context = {
        "origins_count": len(allowed_origins),
        "environment": settings.APP_ENVIRONMENT,
        "allow_credentials": allow_credentials,
        "allowed_origins": allowed_origins,  # Full list for debugging
    }

    if is_production():
        logger.info("CORS configured for PRODUCTION", extra=log_context)
        # Also print to stdout for easier debugging in production logs
        print(f"[CORS] Production origins ({len(allowed_origins)}): {allowed_origins}")
    else:
        logger.warning("CORS configured for DEVELOPMENT", extra=log_context)
