"""
CORS Middleware Configuration - Production Security Guard
SECURITY: Prevents CORS regex wildcards in production
"""
import os
import re
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from typing import List, Optional


def is_production() -> bool:
    """Check if running in production environment"""
    env = os.getenv("ENVIRONMENT", "development").lower()
    return env in ["production", "prod"]


def validate_cors_origins(
    allow_origins: List[str],
    allow_origin_regex: Optional[str] = None
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
    allow_headers: Optional[List[str]] = None
) -> None:
    """
    Configure CORS middleware with production security validation

    Production Defaults:
    - allow_origins: Must be explicit HTTPS URLs
    - allow_credentials: True (for httpOnly cookies)
    - allow_methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    - allow_headers: ["*"]

    Development Defaults:
    - allow_origins: ["http://localhost:3000", "http://localhost:3001"]
    - More permissive configuration

    Args:
        app: FastAPI application instance
        allowed_origins: List of allowed origin URLs
        allowed_origin_regex: Regex pattern for origins (PROD: forbidden)
        allow_credentials: Allow credentials (cookies)
        allow_methods: Allowed HTTP methods
        allow_headers: Allowed request headers

    Raises:
        ValueError: If production security rules violated
    """
    # Default origins
    if allowed_origins is None:
        if is_production():
            # Production: Must be explicitly configured via env vars
            allowed_origins = os.getenv("CORS_ORIGINS", "").split(",")
            allowed_origins = [origin.strip() for origin in allowed_origins if origin.strip()]

            if not allowed_origins:
                raise ValueError(
                    "CORS_ORIGINS environment variable must be set in production"
                )
        else:
            # Development: Local origins
            allowed_origins = [
                "http://localhost:3000",  # Frontend Hormonia
                "http://localhost:3001",  # Quiz Interface
                "http://127.0.0.1:3000",
                "http://127.0.0.1:3001",
            ]

    # Validate configuration for production
    validate_cors_origins(allowed_origins, allowed_origin_regex)

    # Default methods
    if allow_methods is None:
        allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]

    # Default headers
    if allow_headers is None:
        allow_headers = ["*"]

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=allowed_origin_regex,
        allow_credentials=allow_credentials,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
        expose_headers=["*"],
        max_age=3600,  # Cache preflight for 1 hour
    )

    # Log configuration (sanitized)
    if is_production():
        print(f"✅ CORS configured for PRODUCTION with {len(allowed_origins)} explicit origins")
    else:
        print(f"⚠️  CORS configured for DEVELOPMENT with {len(allowed_origins)} origins")
