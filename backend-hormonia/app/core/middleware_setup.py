"""
Middleware configuration for the FastAPI application.

⚠️ CRITICAL: FastAPI executes middlewares in REVERSE ORDER of addition!
- Middleware added LAST executes FIRST
- Middleware added FIRST executes LAST

CORRECT EXECUTION ORDER (what the request sees):
1. CORS middleware (handles preflight, must execute FIRST)
2. Security headers middleware
3. Webhook validation middleware
4. CSRF middleware
5. Enhanced security middleware
6. Rate limiting middleware
7. Request validation middleware
8. Compression middleware
9. Request logging middleware (debug)
10. Query performance middleware
11. Performance metrics middleware
12. Monitoring middleware (executes LAST for comprehensive instrumentation)

ADDITION ORDER (reversed from execution):
The middlewares are added below in REVERSE of the execution order above.
"""

from fastapi import FastAPI
from app.config import settings
from app.middleware.enhanced_middleware import (
    EnhancedSecurityMiddleware,
    RequestLoggingMiddleware,
)
from app.middleware.distributed_rate_limiter import RateLimitMiddleware
from app.middleware.security_headers import create_production_security_middleware

# Custom CORS middleware imported inline to avoid circular imports
from app.utils.compression import EnhancedCompressionMiddleware
from app.utils.logging import get_logger
from app.middleware.query_logger import QueryPerformanceMiddleware
from app.middleware.metrics import PerformanceMetricsMiddleware
from app.middleware.request_validation_middleware import RequestValidationMiddleware


def setup_middleware(app: FastAPI) -> None:
    """
    Configure and add middleware to the FastAPI application.

    ⚠️ CRITICAL: Middleware is added in REVERSE ORDER of execution!
    - Last added middleware executes FIRST
    - First added middleware executes LAST

    This function adds middlewares in the order below, which means they execute
    in the REVERSE order (CORS executes first, monitoring executes last).

    Args:
        app: FastAPI application instance
    """
    logger = get_logger(__name__)

    # ========================================================================
    # STEP 1: Monitoring middleware (added FIRST, executes LAST)
    # ========================================================================
    # Provides comprehensive instrumentation after all other middlewares
    try:
        from app.monitoring.manager import get_monitoring_manager

        monitoring_manager = get_monitoring_manager()
        monitoring_middleware = monitoring_manager.get_middleware(app)
        if monitoring_middleware:
            app.add_middleware(
                type(monitoring_middleware),
                apm_collector=monitoring_manager.apm_collector,
                db_monitor=monitoring_manager.db_monitor,
                business_metrics=monitoring_manager.business_metrics,
            )
            logger.info("✅ [1/12] Monitoring middleware added (executes LAST)")
    except Exception as e:
        logger.warning(f"Failed to add monitoring middleware: {e}")

    # ========================================================================
    # STEP 2: Performance metrics middleware
    # ========================================================================
    # Tracks correlation IDs, timing, and query counts
    app.add_middleware(PerformanceMetricsMiddleware)
    logger.info("✅ [2/12] Performance metrics middleware added")

    # ========================================================================
    # STEP 3: Query performance middleware
    # ========================================================================
    # Monitors database query performance
    app.add_middleware(
        QueryPerformanceMiddleware,
        slow_request_threshold=1.0,  # Log requests slower than 1 second
        slow_query_threshold=1.0,  # Log queries slower than 1 second
    )
    logger.info("✅ [3/12] Query performance middleware added")

    # ========================================================================
    # STEP 4: Request logging middleware (debug only)
    # ========================================================================
    # Logs detailed request/response information in debug mode
    if settings.APP_ENABLE_DEBUG:
        app.add_middleware(
            RequestLoggingMiddleware,
            log_request_body=False,  # Disabled for performance
            log_response_body=False,
            sensitive_headers=["authorization", "cookie", "x-api-key", "x-auth-token"],
        )
        logger.info("✅ [4/12] Request logging middleware added (debug mode)")

    # ========================================================================
    # STEP 5: Compression middleware
    # ========================================================================
    # Compresses responses to reduce bandwidth
    app.add_middleware(
        EnhancedCompressionMiddleware,
        minimum_size=1000,
        compression_level=4,  # Optimized compression
    )
    logger.info("✅ [5/12] Enhanced compression middleware added")

    # ========================================================================
    # STEP 6: Request validation middleware
    # ========================================================================
    # Validates and sanitizes request parameters
    app.add_middleware(RequestValidationMiddleware, max_page_size=100)
    logger.info("✅ [6/12] Request validation middleware added")

    # ========================================================================
    # STEP 7: Rate limiting middleware
    # ========================================================================
    # SECURITY FIX: P0-01 (CVSS 9.1) - Prevents DoS, brute force, and API abuse
    # Uses Redis-backed distributed rate limiting with configurable limits
    try:
        from app.core.redis_client import get_redis_client
        from app.core.rate_limit_config import (
            RATE_LIMIT_WHITELIST_IPS,
            RATE_LIMIT_EXEMPT_PATHS,
        )
        from app.middleware.distributed_rate_limiter import (
            RateLimitTier,
            RateLimitConfig,
        )

        redis_client = get_redis_client()

        if redis_client:
            app.add_middleware(
                RateLimitMiddleware,
                redis=redis_client,
                default_limit=100,  # Global default: 100 requests/minute
                default_window=60,
                tier_configs={
                    RateLimitTier.PUBLIC: RateLimitConfig(
                        requests=100, window=60, tier=RateLimitTier.PUBLIC
                    ),
                    RateLimitTier.DOCTOR: RateLimitConfig(
                        requests=1000, window=60, tier=RateLimitTier.DOCTOR
                    ),
                    RateLimitTier.ADMIN: RateLimitConfig(
                        requests=10000, window=60, tier=RateLimitTier.ADMIN
                    ),
                },
                exempt_paths=RATE_LIMIT_EXEMPT_PATHS,
                whitelist_ips=RATE_LIMIT_WHITELIST_IPS,
            )
            logger.info("✅ [7/12] Rate limiting middleware ENABLED (Redis-backed)")
        else:
            logger.warning("⚠️  Redis unavailable - using in-memory rate limiting")
            from app.middleware.rate_limiter import RateLimitMiddleware as SimpleLimiter

            app.add_middleware(SimpleLimiter)
            logger.info("✅ [7/12] Rate limiting middleware ENABLED (in-memory)")
    except Exception as e:
        logger.error(f"❌ Failed to configure rate limiting middleware: {e}")
        raise

    # ========================================================================
    # STEP 8: Enhanced security middleware
    # ========================================================================
    # Provides XSS protection, input sanitization, and path traversal prevention
    app.add_middleware(EnhancedSecurityMiddleware)
    logger.info("✅ [8/12] Enhanced security middleware added")

    # ========================================================================
    # STEP 9: CSRF Protection middleware
    # ========================================================================
    # Protects against Cross-Site Request Forgery attacks
    if settings.SECURITY_CSRF_SECRET_KEY:
        from app.core.csrf_middleware import CSRFMiddleware

        app.add_middleware(
            CSRFMiddleware,
            secret_key=settings.SECURITY_CSRF_SECRET_KEY,
            token_expiry=3600,  # 1 hour
            exempt_paths=[
                "/api/v2/auth/csrf-token",
                "/api/v2/auth/firebase/verify",
                "/webhooks/",
                "/api/public/",
                "/api/v2/quiz-extensions/monthly/public",
                "/api/v2/monthly-quiz-public/monthly/public",
                "/api/v2/monthly-quiz/monthly/public",
            ],
        )
        logger.info("✅ [9/12] CSRF protection middleware added (HMAC-SHA256)")
    else:
        logger.warning("⚠️  CSRF protection DISABLED - Set CSRF_SECRET_KEY to enable")

    # ========================================================================
    # STEP 10: Webhook validation middleware
    # ========================================================================
    # Validates webhook signatures to prevent unauthorized access
    if settings.WHATSAPP_EVOLUTION_WEBHOOK_SECRET:
        from app.middleware.webhook_validator import WebhookValidatorMiddleware

        app.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=settings.WHATSAPP_EVOLUTION_WEBHOOK_SECRET,
            max_timestamp_age=300,  # 5 minutes
            signature_header="X-Webhook-Signature",
            timestamp_header="X-Webhook-Timestamp",
            webhook_paths=["/webhooks/"],
        )
        logger.info("✅ [10/12] Webhook validation middleware added (HMAC-SHA256)")
    else:
        logger.warning(
            "⚠️  Webhook validation DISABLED - Set EVOLUTION_WEBHOOK_SECRET to enable"
        )

    # ========================================================================
    # STEP 11: Security headers middleware
    # ========================================================================
    # Adds OWASP recommended security headers (HSTS, CSP, X-Frame-Options, etc.)
    middleware = create_production_security_middleware(app)
    app.add_middleware(
        type(middleware),
        enable_hsts=middleware.enable_hsts,
        hsts_max_age=middleware.hsts_max_age,
        hsts_include_subdomains=middleware.hsts_include_subdomains,
        hsts_preload=middleware.hsts_preload,
        frame_options=middleware.frame_options,
        content_type_options=middleware.content_type_options,
        xss_protection=middleware.xss_protection,
        referrer_policy=middleware.referrer_policy,
        csp_policy=middleware.csp_policy,
        permissions_policy=middleware.permissions_policy,
    )
    logger.info("✅ [11/12] Security headers middleware added")

    # ========================================================================
    # STEP 12: CORS middleware (added LAST, executes FIRST)
    # ========================================================================
    # ⚠️ CRITICAL: CORS must execute FIRST to handle preflight OPTIONS requests
    # This is why it's added LAST in the middleware stack
    from app.middleware.cors import configure_cors

    cors_origins = settings.get_cors_origins()
    is_production = settings.APP_ENVIRONMENT.lower() == "production"

    # Configure CORS with security validation
    # Production: No regex, explicit HTTPS origins only (from settings)
    # Development: Localhost regex pattern allowed + default origins
    # Note: allow_methods and allow_headers have secure defaults in cors.py
    configure_cors(
        app,
        allowed_origins=cors_origins,
        allowed_origin_regex=None
        if is_production
        else r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,  # Required for httpOnly cookies and credentials
    )

    logger.info(
        f"✅ [12/12] CORS middleware added (executes FIRST) - "
        f"{'PRODUCTION' if is_production else 'DEVELOPMENT'} mode"
    )

    logger.info("🎉 All 12 middlewares configured successfully in correct order")
