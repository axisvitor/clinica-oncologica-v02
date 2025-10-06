"""
Middleware configuration for the FastAPI application.

Configures and applies middleware in the correct order:
1. Monitoring middleware (first for comprehensive instrumentation)
2. Request logging middleware (debug only)
3. Security middleware
4. Rate limiting middleware
5. Compression middleware
6. Custom CORS middleware (last - first to execute, supports wildcard patterns)
"""
from fastapi import FastAPI
from app.config import settings
from app.middleware.enhanced_middleware import (
    EnhancedRateLimitMiddleware,
    EnhancedSecurityMiddleware,
    RequestLoggingMiddleware
)
# Custom CORS middleware imported inline to avoid circular imports
from app.utils.compression import EnhancedCompressionMiddleware
from app.utils.logging import get_logger
from app.middleware.query_logger import QueryPerformanceMiddleware


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
                business_metrics=monitoring_manager.business_metrics
            )
            logger.info("Monitoring middleware added successfully")
    except Exception as e:
        logger.warning(f"Failed to add monitoring middleware: {e}")

    # Add query performance middleware for database monitoring
    app.add_middleware(
        QueryPerformanceMiddleware,
        slow_request_threshold=1.0,  # Log requests slower than 1 second
        slow_query_threshold=1.0     # Log queries slower than 1 second
    )
    logger.info("Query performance middleware added")

    # Add optimized middleware in order (last added = first executed)
    # Only add essential middleware in production for better performance
    if settings.DEBUG:
        app.add_middleware(
            RequestLoggingMiddleware,
            log_request_body=False,  # Disabled for performance
            log_response_body=False,
            sensitive_headers=["authorization", "cookie", "x-api-key", "x-auth-token"]
        )
        logger.info("Request logging middleware added (debug mode)")

    # Enhanced security middleware
    app.add_middleware(EnhancedSecurityMiddleware)
    logger.info("Enhanced security middleware added")
    
    # Enhanced rate limiting middleware
    app.add_middleware(
        EnhancedRateLimitMiddleware,
        default_limit=200,  # Increased for better throughput
        default_window=60,
        whitelist_ips=getattr(settings, 'RATE_LIMIT_WHITELIST_IPS', []),
        blacklist_ips=getattr(settings, 'RATE_LIMIT_BLACKLIST_IPS', [])
    )
    logger.info("Enhanced rate limiting middleware added")
    
    # Enhanced compression middleware
    # Remove InputSanitizationMiddleware as it's redundant with EnhancedSecurityMiddleware
    app.add_middleware(
        EnhancedCompressionMiddleware,
        minimum_size=1000,
        compression_level=4  # Optimized compression
    )
    logger.info("Enhanced compression middleware added")
    
    # CORS middleware - Dynamic configuration (domain-only in prod, regex in dev)
    from fastapi.middleware.cors import CORSMiddleware

    cors_origins = settings.get_cors_origins()
    is_production = settings.ENVIRONMENT.lower() == "production"

    if is_production:
        # Production: use explicit domains only
        logger.info(f"CORS Production Mode: {len(cors_origins)} allowed origins")
        logger.info(f"Allowed origins: {cors_origins}")

        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
            max_age=86400
        )
    else:
        # Development: use regex for localhost/127.0.0.1 with any port
        logger.info("CORS Development Mode: Using regex for localhost (any port)")
        logger.info("Allowed pattern: http(s)://localhost:* and http(s)://127.0.0.1:*")

        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
            max_age=86400
        )

    logger.info("Dynamic CORS middleware configured successfully")
    
    logger.info("All middleware configured successfully")
