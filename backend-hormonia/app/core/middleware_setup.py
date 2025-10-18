"""
Middleware configuration for the FastAPI application.

Configures and applies middleware in the correct order:
1. Monitoring middleware (first for comprehensive instrumentation)
2. Request logging middleware (debug only)
3. Security headers middleware (production security headers)
4. Security middleware
5. Rate limiting middleware
6. Compression middleware
7. Custom CORS middleware (last - first to execute, supports wildcard patterns)
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

    Middleware is added in reverse order of execution:
    - Last added middleware executes first
    - First added middleware executes last

    Args:
        app: FastAPI application instance
    """
    logger = get_logger(__name__)

    # Add monitoring middleware first for comprehensive instrumentation
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
            logger.info("Monitoring middleware added successfully")
    except Exception as e:
        logger.warning(f"Failed to add monitoring middleware: {e}")

    # Add performance metrics middleware for request tracking
    app.add_middleware(PerformanceMetricsMiddleware)
    logger.info(
        "Performance metrics middleware added (correlation IDs, timing, query counts)"
    )

    # Add query performance middleware for database monitoring
    app.add_middleware(
        QueryPerformanceMiddleware,
        slow_request_threshold=1.0,  # Log requests slower than 1 second
        slow_query_threshold=1.0,  # Log queries slower than 1 second
    )
    logger.info("Query performance middleware added")

    # Add optimized middleware in order (last added = first executed)
    # Only add essential middleware in production for better performance
    if settings.DEBUG:
        app.add_middleware(
            RequestLoggingMiddleware,
            log_request_body=False,  # Disabled for performance
            log_response_body=False,
            sensitive_headers=["authorization", "cookie", "x-api-key", "x-auth-token"],
        )
        logger.info("Request logging middleware added (debug mode)")

    # Production security headers middleware
    # Adds OWASP recommended security headers to all responses
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
    logger.info("Security headers middleware added (production hardening)")

    # Webhook signature validation middleware
    # Protects webhook endpoints from unauthorized access and replay attacks
    if settings.EVOLUTION_WEBHOOK_SECRET:
        from app.middleware.webhook_validator import WebhookValidatorMiddleware

        app.add_middleware(
            WebhookValidatorMiddleware,
            secret_key=settings.EVOLUTION_WEBHOOK_SECRET,
            max_timestamp_age=300,  # 5 minutes
            signature_header="X-Webhook-Signature",
            timestamp_header="X-Webhook-Timestamp",
            webhook_paths=["/webhooks/"],
        )
        logger.info("✅ Webhook signature validation middleware added (HMAC-SHA256)")
    else:
        logger.warning(
            "⚠️  Webhook signature validation DISABLED - "
            "Set EVOLUTION_WEBHOOK_SECRET to enable security"
        )

    # Enhanced security middleware
    app.add_middleware(EnhancedSecurityMiddleware)
    logger.info("Enhanced security middleware added")

    # Distributed rate limiting middleware with Redis backend
    try:
        from app.core.redis_client import get_redis_client

        redis_client = get_redis_client()

        app.add_middleware(
            RateLimitMiddleware,
            redis=redis_client,
            default_limit=200,  # Increased for better throughput
            default_window=60,
        )
        logger.info(
            "✅ Distributed rate limiting middleware added (Redis-backed, sliding window)"
        )
    except Exception as e:
        logger.warning(
            f"⚠️  Failed to initialize distributed rate limiter with Redis: {e}. "
            "Falling back to in-memory rate limiting."
        )
        # Fallback to enhanced rate limiter without Redis
        from app.middleware.enhanced_middleware import EnhancedRateLimitMiddleware

        app.add_middleware(
            EnhancedRateLimitMiddleware,
            default_limit=200,
            default_window=60,
            whitelist_ips=getattr(settings, "RATE_LIMIT_WHITELIST_IPS", []),
            blacklist_ips=getattr(settings, "RATE_LIMIT_BLACKLIST_IPS", []),
        )
        logger.info("Enhanced rate limiting middleware added (in-memory fallback)")

    # Request validation middleware - validates and sanitizes request parameters
    app.add_middleware(RequestValidationMiddleware, max_page_size=100)
    logger.info("Request validation middleware added")

    # Enhanced compression middleware
    # Remove InputSanitizationMiddleware as it's redundant with EnhancedSecurityMiddleware
    app.add_middleware(
        EnhancedCompressionMiddleware,
        minimum_size=1000,
        compression_level=4,  # Optimized compression
    )
    logger.info("Enhanced compression middleware added")

    # CORS middleware - Use secure validation from cors.py
    from app.middleware.cors import configure_cors

    cors_origins = settings.get_cors_origins()
    is_production = settings.ENVIRONMENT.lower() == "production"

    # Configure CORS with security validation
    # Production: No regex, explicit HTTPS origins only
    # Development: Localhost regex pattern allowed
    configure_cors(
        app,
        allowed_origins=cors_origins,
        allowed_origin_regex=None
        if is_production
        else r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,  # ✅ CRITICAL: Required for httpOnly cookies and credentials
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "authorization",
            "content-type",
            "x-csrf-token",
            "x-requested-with",
            "accept",
            "origin",
        ],
    )

    logger.info(
        f"CORS configured securely for {'PRODUCTION' if is_production else 'DEVELOPMENT'}"
    )

    logger.info("All middleware configured successfully")
