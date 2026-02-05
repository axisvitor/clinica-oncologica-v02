"""
Middleware Configuration - Simplified Implementation

Configures essential middlewares for the FastAPI application.

MIDDLEWARE EXECUTION ORDER (what request sees):
1. CORS (handles preflight OPTIONS) - MUST BE FIRST
2. Security Headers (HSTS, CSP, X-Frame-Options)
3. Rate Limiting (Redis-backed, prevents abuse)
4. CSRF Protection (Double Submit Cookie pattern)
5. Request Logging (debug only)
6. HTTP Response Caching (ETag + user-specific caching)
7. Compression (response optimization)

NOTE: FastAPI executes middlewares in REVERSE order of addition.
      Middleware added LAST executes FIRST.
"""
import time
from typing import Dict

from fastapi import FastAPI
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

# ==========================================================================
# CRITICAL MIDDLEWARES TRACKING
# ==========================================================================
# Track loading status of critical security middlewares for health checks.
# In production, all must be loaded or the application will fail to start.
# ==========================================================================

CRITICAL_MIDDLEWARES: Dict[str, bool] = {
    "csrf": False,
    "security_headers": False,
    "rate_limiting": False,
}


def get_middleware_status() -> Dict[str, bool]:
    """Return copy of critical middleware status for health checks."""
    return CRITICAL_MIDDLEWARES.copy()


def setup_middleware(app: FastAPI) -> None:
    """
    Configure essential middlewares for the application.

    Middlewares are added in reverse order of execution:
    - First added = Last to execute
    - Last added = First to execute (CORS)
    """

    # ========================================================================
    # 1. COMPRESSION (added first, executes last)
    # ========================================================================
    try:
        from app.utils.compression import EnhancedCompressionMiddleware

        app.add_middleware(
            EnhancedCompressionMiddleware,
            minimum_size=1000,
            compression_level=4,
        )
        logger.info("[1/6] Compression middleware added")
    except ImportError as e:
        logger.warning(f"Compression middleware not available: {e}")

    # ========================================================================
    # 2. HTTP RESPONSE CACHING (added second, executes second-to-last)
    # ========================================================================
    try:
        from app.middleware.cache_middleware import CacheMiddleware

        app.add_middleware(
            CacheMiddleware,
            default_ttl=300,  # 5 minutes for public endpoints
            authenticated_ttl=90,  # 90 seconds for authenticated endpoints
            cache_authenticated=True,  # ENABLED for performance after login
            exclude_patterns=[
                "/api/v2/auth",  # Never cache auth endpoints
                "/api/v2/admin",  # Never cache admin endpoints
                "/ws",  # Never cache WebSocket
                "/health",  # Never cache health checks
            ],
        )
        logger.info("[2/7] HTTP cache middleware added (with user-specific caching)")
    except ImportError as e:
        logger.warning(f"Cache middleware not available: {e}")

    # ========================================================================
    # 3. REQUEST LOGGING (debug only)
    # ========================================================================
    if settings.APP_ENABLE_DEBUG:
        try:
            from app.middleware.enhanced_middleware import RequestLoggingMiddleware

            app.add_middleware(
                RequestLoggingMiddleware,
                log_request_body=False,
                log_response_body=False,
                sensitive_headers=["authorization", "cookie", "x-api-key"],
            )
            logger.info("[3/7] Request logging middleware added (debug mode)")
        except ImportError as e:
            logger.warning(f"Request logging middleware not available: {e}")

    # ========================================================================
    # 4. CSRF PROTECTION (fail-fast in production)
    # ========================================================================
    is_production = settings.APP_ENVIRONMENT.lower() == "production"

    csrf_secret = None
    if hasattr(settings, "SECURITY_CSRF_SECRET_KEY"):
        csrf_secret = settings.SECURITY_CSRF_SECRET_KEY
        if hasattr(csrf_secret, "get_secret_value"):
            csrf_secret = csrf_secret.get_secret_value()

    if csrf_secret:
        try:
            from app.middleware.csrf import CSRFMiddleware

            app.add_middleware(CSRFMiddleware)
            CRITICAL_MIDDLEWARES["csrf"] = True
            logger.info("[4/7] CSRF protection middleware added")
        except ImportError as e:
            logger.error(f"CSRF middleware failed to load: {e}")
            if is_production:
                raise RuntimeError(
                    "CRITICAL: CSRF middleware failed to load in production. "
                    "Ensure app.middleware.csrf module is available."
                )
            logger.warning("CSRF middleware not available in development mode")
    else:
        logger.warning("[4/7] CSRF protection DISABLED - Set SECURITY_CSRF_SECRET_KEY")
        if is_production:
            raise RuntimeError(
                "CRITICAL: CSRF secret not configured in production. "
                "Set SECURITY_CSRF_SECRET_KEY environment variable."
            )

    # ========================================================================
    # 5. RATE LIMITING (Redis-backed, retry with exponential backoff)
    # ========================================================================
    max_retries = 3
    rate_limiting_loaded = False

    for attempt in range(max_retries):
        try:
            from app.core.redis_client import get_redis_client
            from app.middleware.distributed_rate_limiter import RateLimitMiddleware

            redis_client = get_redis_client()

            if redis_client:
                # Test Redis connection
                redis_client.ping()

                app.add_middleware(
                    RateLimitMiddleware,
                    redis=redis_client,
                    default_limit=100,
                    default_window=60,
                )
                CRITICAL_MIDDLEWARES["rate_limiting"] = True
                rate_limiting_loaded = True
                logger.info("[5/7] Rate limiting middleware added (Redis-backed)")
                break
            else:
                raise ConnectionError("Redis client returned None")

        except (ImportError, ConnectionError, Exception) as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                logger.warning(
                    f"Rate limiting attempt {attempt + 1}/{max_retries} failed: {e}. "
                    f"Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"Rate limiting failed after {max_retries} attempts: {e}")
                if is_production:
                    raise RuntimeError(
                        f"CRITICAL: Rate limiting failed after {max_retries} retries. "
                        "Ensure Redis is available and properly configured."
                    )
                logger.warning("Rate limiting DISABLED in development mode")

    if not rate_limiting_loaded:
        logger.warning("[5/7] Rate limiting DISABLED - Redis not available")

    # ========================================================================
    # 6. SECURITY HEADERS (fail-fast in production)
    # ========================================================================
    try:
        from app.middleware.security_headers import SecurityHeadersMiddleware

        app.add_middleware(
            SecurityHeadersMiddleware,
            enable_hsts=is_production,
            hsts_max_age=31536000,
            hsts_include_subdomains=True,
            frame_options="DENY",
            content_type_options="nosniff",
            xss_protection="1; mode=block",
            referrer_policy="strict-origin-when-cross-origin",
            permissions_policy=(
                "geolocation=(), "
                "microphone=(), "
                "camera=(), "
                "payment=(), "
                "usb=(), "
                "magnetometer=(), "
                "gyroscope=(), "
                "accelerometer=()"
            ),
        )
        CRITICAL_MIDDLEWARES["security_headers"] = True
        logger.info("[6/7] Security headers middleware added")
    except ImportError as e:
        logger.error(f"Security headers middleware failed to load: {e}")
        if is_production:
            raise RuntimeError(
                "CRITICAL: Security headers middleware failed to load in production. "
                "Ensure app.middleware.security_headers module is available."
            )
        logger.warning("Security headers middleware not available in development mode")

    # ========================================================================
    # 7. LGPD COMPLIANCE (added seventh, executes second)
    # ========================================================================
    try:
        from app.middleware.lgpd_middleware import LGPDMiddleware

        app.add_middleware(LGPDMiddleware, enable_ip_logging=True)
        logger.info("[7/8] LGPD compliance middleware added")
    except ImportError as e:
        logger.warning(f"LGPD middleware not available: {e}")

    # ========================================================================
    # 8. CORS (added last, executes FIRST)
    # ========================================================================
    from app.core.cors import configure_cors

    configure_cors(app)
    logger.info("[8/8] CORS middleware added (executes FIRST)")

    # ========================================================================
    # FINAL VALIDATION (production only)
    # ========================================================================
    if is_production:
        failed_middlewares = [
            name for name, loaded in CRITICAL_MIDDLEWARES.items()
            if not loaded
        ]
        if failed_middlewares:
            error_msg = (
                f"CRITICAL: Failed to load essential middlewares: {', '.join(failed_middlewares)}. "
                "Application cannot start without these security protections."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        logger.info("All critical middlewares loaded successfully")

    # Summary
    env = "PRODUCTION" if is_production else "DEVELOPMENT"
    logger.info(f"Middleware setup complete - {env} mode with HTTP caching enabled")

