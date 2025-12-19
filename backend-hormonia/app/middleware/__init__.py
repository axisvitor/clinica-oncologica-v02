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
from .rate_limit import RateLimitMiddleware
from .logging import RequestLoggingMiddleware as LoggingMiddleware

# Import from legacy middleware.py
import sys
from pathlib import Path
# Add parent to import from app.middleware (the .py file)
_middleware_py = Path(__file__).parent.parent / "middleware.py"
if _middleware_py.exists():
    import importlib.util
    spec = importlib.util.spec_from_file_location("app_middleware_legacy", str(_middleware_py))
    _legacy_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_legacy_module)
    InputSanitizationMiddleware = _legacy_module.InputSanitizationMiddleware
    LoggingMiddleware = _legacy_module.LoggingMiddleware  # Use the one from .py file
else:
    InputSanitizationMiddleware = None

from .config import (
    get_cors_config,
    CSRF_EXEMPT_PATHS,
    RATE_LIMIT_WHITELIST_IPS,
    RATE_LIMIT_EXEMPT_PATHS,
    SECURITY_HEADERS_CONFIG,
)

__all__ = [
    "EnhancedRateLimitMiddleware",
    "EnhancedSecurityMiddleware",
    "RequestLoggingMiddleware",
    "RateLimitRule",
    "SecurityConfig",
    "SecurityHeadersMiddleware",
    "create_production_security_middleware",
    "SecurityMiddleware",
    "RateLimitMiddleware",
    "LoggingMiddleware",
    "InputSanitizationMiddleware",
    "get_cors_config",
    "CSRF_EXEMPT_PATHS",
    "RATE_LIMIT_WHITELIST_IPS",
    "RATE_LIMIT_EXEMPT_PATHS",
    "SECURITY_HEADERS_CONFIG",
]
