"""
Middleware package for the Hormonia Backend System.
Contains enhanced middleware components for security, rate limiting, and logging.

NOTE: Rate limiting is handled by distributed_rate_limiter.py (RateLimitMiddleware)
which provides Redis-based distributed rate limiting with tier support.
"""

from .enhanced_middleware import (
    EnhancedSecurityMiddleware,
    RequestLoggingMiddleware,
    SecurityConfig,
)
from .security_headers import (
    SecurityHeadersMiddleware,
    create_production_security_middleware,
)
from .distributed_rate_limiter import RateLimitMiddleware
from .config import (
    get_cors_config,
    CSRF_EXEMPT_PATHS,
    RATE_LIMIT_WHITELIST_IPS,
    RATE_LIMIT_EXEMPT_PATHS,
    SECURITY_HEADERS_CONFIG,
)

__all__ = [
    # Enhanced middleware (security and logging)
    "EnhancedSecurityMiddleware",
    "RequestLoggingMiddleware",
    "SecurityConfig",
    # Security headers
    "SecurityHeadersMiddleware",
    "create_production_security_middleware",
    # Rate limiting (distributed Redis-based)
    "RateLimitMiddleware",
    # Configuration
    "get_cors_config",
    "CSRF_EXEMPT_PATHS",
    "RATE_LIMIT_WHITELIST_IPS",
    "RATE_LIMIT_EXEMPT_PATHS",
    "SECURITY_HEADERS_CONFIG",
]
