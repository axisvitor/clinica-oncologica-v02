"""
Middleware package for the Hormonia Backend System.
Contains enhanced middleware components for security, rate limiting, and logging.
"""

from .enhanced_middleware import (
    EnhancedRateLimitMiddleware,
    EnhancedSecurityMiddleware,
    RequestLoggingMiddleware,
    RateLimitRule,
    SecurityConfig,
)
from .security_headers import (
    SecurityHeadersMiddleware,
    create_production_security_middleware,
)
from .security import SecurityHeadersMiddleware as SecurityMiddleware
from .distributed_rate_limiter import RateLimitMiddleware
from .logging import RequestLoggingMiddleware as RequestLoggingMiddlewareAlias
from .request_logging import LoggingMiddleware
from .input_sanitization import InputSanitizationMiddleware
from .config import (
    get_cors_config,
    CSRF_EXEMPT_PATHS,
    RATE_LIMIT_WHITELIST_IPS,
    RATE_LIMIT_EXEMPT_PATHS,
    SECURITY_HEADERS_CONFIG,
)

__all__ = [
    # Enhanced middleware
    "EnhancedRateLimitMiddleware",
    "EnhancedSecurityMiddleware",
    "RequestLoggingMiddleware",
    "RateLimitRule",
    "SecurityConfig",
    # Security headers
    "SecurityHeadersMiddleware",
    "create_production_security_middleware",
    "SecurityMiddleware",
    # Rate limiting
    "RateLimitMiddleware",
    # Logging
    "LoggingMiddleware",
    "RequestLoggingMiddlewareAlias",
    # Input sanitization
    "InputSanitizationMiddleware",
    # Configuration
    "get_cors_config",
    "CSRF_EXEMPT_PATHS",
    "RATE_LIMIT_WHITELIST_IPS",
    "RATE_LIMIT_EXEMPT_PATHS",
    "SECURITY_HEADERS_CONFIG",
]
