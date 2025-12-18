"""
CORS Middleware Configuration - Production Security Guard
SECURITY: Prevents CORS regex wildcards in production
"""

import json
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from typing import List, Optional


def is_production() -> bool:
    """
    Check if running in production environment

    Environment Variables:
    - APP_ENVIRONMENT (current): Preferred variable
    - ENVIRONMENT (deprecated v2.1.0): Legacy support, will be removed in v3.0

    Returns:
        bool: True if production mode
    """
    import warnings

    # Check for deprecated ENVIRONMENT variable
    if os.getenv("ENVIRONMENT") and not os.getenv("APP_ENVIRONMENT"):
        warnings.warn(
            "ENVIRONMENT variable is deprecated since v2.1.0. Use APP_ENVIRONMENT instead. "
            "ENVIRONMENT will be removed in v3.0.",
            DeprecationWarning,
            stacklevel=2,
        )

    # Check APP_ENVIRONMENT first (new convention), then ENVIRONMENT (legacy)
    env = os.getenv("APP_ENVIRONMENT", os.getenv("ENVIRONMENT", "development")).lower()
    return env in ["production", "prod"]


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
    allowed_origins: Optional[List[str]] = None,
    allowed_origin_regex: Optional[str] = None,
    allow_credentials: bool = True,
    allow_methods: Optional[List[str]] = None,
    allow_headers: Optional[List[str]] = None,
) -> None:
    """
    Configure CORS middleware with production security validation

    Production Defaults:
    - allow_origins: Must be explicit HTTPS URLs
    - allow_credentials: True (for httpOnly cookies)
    - allow_methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    - allow_headers: Explicit whitelist (NEVER "*" with credentials)

    Development Defaults:
    - allow_origins: ["http://localhost:3000", "http://localhost:3001"]
    - More permissive configuration

    SECURITY NOTE:
    Using allow_headers=["*"] with allow_credentials=True is a critical
    security vulnerability that exposes all request headers (including
    Authorization, cookies, etc.) to cross-origin requests. This violates
    the CORS security model and can lead to credential leakage.

    Args:
        app: FastAPI application instance
        allowed_origins: List of allowed origin URLs
        allowed_origin_regex: Regex pattern for origins (PROD: forbidden)
        allow_credentials: Allow credentials (cookies)
        allow_methods: Allowed HTTP methods
        allow_headers: Allowed request headers (explicit list required)

    Raises:
        ValueError: If production security rules violated
    """
    # Default origins
    if allowed_origins is None:
        if is_production():
            # Production: Must be explicitly configured via env vars (fallback if not passed in args)
            # Support both CORS_ALLOWED_ORIGINS (preferred) and CORS_ORIGINS (deprecated v2.1.0)
            # CORS_ORIGINS will be removed in v3.0
            import warnings

            if os.getenv("CORS_ORIGINS") and not os.getenv("CORS_ALLOWED_ORIGINS"):
                warnings.warn(
                    "CORS_ORIGINS is deprecated since v2.1.0. Use CORS_ALLOWED_ORIGINS instead. "
                    "CORS_ORIGINS will be removed in v3.0.",
                    DeprecationWarning,
                    stacklevel=2,
                )

            cors_env = os.getenv("CORS_ALLOWED_ORIGINS", os.getenv("CORS_ORIGINS", ""))

            # Try to parse as JSON array first
            if cors_env.startswith("["):
                try:
                    allowed_origins = json.loads(cors_env)
                except json.JSONDecodeError:
                    allowed_origins = []
            else:
                # Fallback to comma-separated format
                allowed_origins = [
                    origin.strip() for origin in cors_env.split(",") if origin.strip()
                ]

            if not allowed_origins:
                raise ValueError(
                    "CORS_ALLOWED_ORIGINS or CORS_ORIGINS environment variable must be set in production"
                )
        else:
            # Development: Local origins
            allowed_origins = [
                "http://localhost:3000",  # Legacy frontend port (deprecated)
                "http://localhost:3001",  # Quiz Interface
                "http://localhost:5173",  # Frontend Hormonia Vite (current)
                "http://127.0.0.1:3000",
                "http://127.0.0.1:3001",
                "http://127.0.0.1:5173",
            ]
    # Validate configuration for production
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

    # Log configuration (sanitized)
    import logging

    logger = logging.getLogger(__name__)

    if is_production():
        logger.info(
            "CORS configured for PRODUCTION",
            extra={
                "origins_count": len(allowed_origins),
                "environment": "production",
                "allow_credentials": allow_credentials,
            },
        )
    else:
        logger.warning(
            "CORS configured for DEVELOPMENT",
            extra={
                "origins_count": len(allowed_origins),
                "environment": "development",
                "origins": allowed_origins,
            },
        )
