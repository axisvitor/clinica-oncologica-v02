"""
Middleware Configuration - Simplified Implementation

Configures essential middlewares for the FastAPI application.

MIDDLEWARE EXECUTION ORDER (what request sees):
1. CORS (handles preflight OPTIONS) - MUST BE FIRST
2. Security Headers (HSTS, CSP, X-Frame-Options)
3. Rate Limiting (Redis-backed, prevents abuse)
4. CSRF Protection (Double Submit Cookie pattern)
5. Request Logging (debug only)
6. Compression (response optimization)

NOTE: FastAPI executes middlewares in REVERSE order of addition.
      Middleware added LAST executes FIRST.
"""

from fastapi import FastAPI
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


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
    # 2. REQUEST LOGGING (debug only)
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
            logger.info("[2/6] Request logging middleware added (debug mode)")
        except ImportError as e:
            logger.warning(f"Request logging middleware not available: {e}")

    # ========================================================================
    # 3. CSRF PROTECTION
    # ========================================================================
    csrf_secret = None
    if hasattr(settings, "SECURITY_CSRF_SECRET_KEY"):
        csrf_secret = settings.SECURITY_CSRF_SECRET_KEY
        if hasattr(csrf_secret, "get_secret_value"):
            csrf_secret = csrf_secret.get_secret_value()

    if csrf_secret:
        try:
            from app.middleware.csrf import CSRFMiddleware

            app.add_middleware(CSRFMiddleware)
            logger.info("[3/6] CSRF protection middleware added")
        except ImportError as e:
            logger.warning(f"CSRF middleware not available: {e}")
    else:
        logger.warning("[3/6] CSRF protection DISABLED - Set SECURITY_CSRF_SECRET_KEY")

    # ========================================================================
    # 4. RATE LIMITING (Redis-backed)
    # ========================================================================
    try:
        from app.core.redis_client import get_redis_client
        from app.middleware.distributed_rate_limiter import RateLimitMiddleware

        redis_client = get_redis_client()

        if redis_client:
            app.add_middleware(
                RateLimitMiddleware,
                redis=redis_client,
                default_limit=100,
                default_window=60,
            )
            logger.info("[4/6] Rate limiting middleware added (Redis-backed)")
        else:
            logger.warning("[4/6] Rate limiting DISABLED - Redis not available")
    except ImportError as e:
        logger.warning(f"[4/6] Rate limiting not available: {e}")
    except Exception as e:
        logger.error(f"[4/6] Rate limiting error: {e}")

    # ========================================================================
    # 5. SECURITY HEADERS
    # ========================================================================
    try:
        from app.middleware.security_headers import SecurityHeadersMiddleware

        is_production = settings.APP_ENVIRONMENT.lower() == "production"

        app.add_middleware(
            SecurityHeadersMiddleware,
            enable_hsts=is_production,
            hsts_max_age=31536000,
            hsts_include_subdomains=True,
            frame_options="DENY",
            content_type_options="nosniff",
            xss_protection="1; mode=block",
            referrer_policy="strict-origin-when-cross-origin",
        )
        logger.info("[5/6] Security headers middleware added")
    except ImportError as e:
        logger.warning(f"Security headers middleware not available: {e}")

    # ========================================================================
    # 6. CORS (added last, executes FIRST)
    # ========================================================================
    from app.core.cors import configure_cors

    configure_cors(app)
    logger.info("[6/6] CORS middleware added (executes FIRST)")

    # Summary
    env = "PRODUCTION" if settings.APP_ENVIRONMENT.lower() == "production" else "DEVELOPMENT"
    logger.info(f"Middleware setup complete - {env} mode")
