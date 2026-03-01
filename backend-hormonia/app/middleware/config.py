"""
Centralized Middleware Configuration

This module provides a single source of truth for all middleware settings.
All middleware configuration should be imported from here.
"""

from typing import Set
from app.config import settings


# =============================================================================
# CORS Configuration
# =============================================================================
def get_cors_config() -> dict:
    """Get CORS configuration from settings."""
    is_production = settings.APP_ENVIRONMENT.lower() == "production"

    return {
        "allowed_origins": settings.get_cors_origins(),
        "allowed_origin_regex": None if is_production else r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": [
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "X-CSRF-Token",
            "Accept",
            "Origin",
        ],
        "expose_headers": [
            "content-type",
            "x-csrf-token",
            "x-total-count",
            "x-page",
            "x-per-page",
        ],
        "max_age": 3600,
    }


# =============================================================================
# CSRF Exempt Paths (LEGACY - not used by CSRFMiddleware)
# The actual CSRF middleware uses its own EXEMPT_PATHS in csrf.py.
# Kept for backward compatibility with test_refactor_validation.py.
# =============================================================================
CSRF_EXEMPT_PATHS: Set[str] = {
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/api/v2/auth/csrf-token",
    "/api/v2/auth/logout",
    "/api/v2/auth/firebase/verify",
    "/api/v2/enhanced-messages",
    "/webhooks/",
    "/api/public/",
    "/api/v2/quiz-extensions/monthly/public",
}


# =============================================================================
# Rate Limit Configuration
# =============================================================================
# LEGACY: Always empty. The actual rate limiter (distributed_rate_limiter.py)
# uses its own whitelist. Kept for backward compatibility.
RATE_LIMIT_WHITELIST_IPS: Set[str] = set()

RATE_LIMIT_EXEMPT_PATHS: Set[str] = {
    "/health",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
}


# =============================================================================
# Security Headers Configuration
# =============================================================================
SECURITY_HEADERS_CONFIG = {
    "enable_hsts": True,
    "hsts_max_age": 31536000,  # 1 year
    "hsts_include_subdomains": True,
    "hsts_preload": False,
    "frame_options": "DENY",
    "content_type_options": "nosniff",
    "xss_protection": "1; mode=block",
    "referrer_policy": "strict-origin-when-cross-origin",
    "permissions_policy": (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=()"
    ),
}
