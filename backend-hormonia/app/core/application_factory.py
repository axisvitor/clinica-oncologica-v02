"""
Application Factory for clean separation of concerns.

Creates and configures the FastAPI application using modular components:
- Middleware setup for request/response processing
- Router registry for API endpoint management
- Lifespan management for startup/shutdown
- Monitoring setup for observability
- Enhanced error handling and debugging capabilities
- Production-ready security and performance features
"""

from typing import Literal
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime
import time

from app.config import settings
from app.utils.logging import get_logger
from app.utils.error_tracking import track_error

from .middleware_setup import setup_middleware
from .router_registry import register_routers
from .lifespan import lifespan
from .monitoring_setup import setup_monitoring
from app.core.exception_handlers import register_exception_handlers
from app.core.setup.sentry import setup_sentry
from app.core.setup.openapi import (
    setup_enhanced_openapi,
    get_api_description,
    get_openapi_tags,
)

# Import rate limiter components
from slowapi.errors import RateLimitExceeded
from app.utils.rate_limiter import limiter, rate_limit_handler

logger = get_logger(__name__)


def create_application(
    enable_monitoring: bool = True,
    enable_debug_endpoints: bool = None,
    deployment_mode: Literal["production", "development", "debug"] = "production",
    enable_error_tracking: bool = True,
    enable_enhanced_openapi: bool = True,
) -> FastAPI:
    """
    Create and configure FastAPI application with clean separation of concerns.

    This factory function creates a minimal, focused FastAPI application by delegating
    specific concerns to dedicated modules while providing enhanced production features:

    - Application metadata and OpenAPI configuration
    - Lifespan management (startup/shutdown)
    - Middleware configuration and ordering
    - Router registration and API structure
    - Monitoring and observability setup
    - Enhanced error handling with tracking
    - Optional debug endpoints for troubleshooting
    - Production-ready security and performance

    Args:
        enable_monitoring: Enable monitoring and observability (default: True)
        enable_debug_endpoints: Enable debug endpoints (default: None - auto-detect from settings.APP_ENABLE_DEBUG)
        deployment_mode: Deployment mode for configuration (default: "production")
        enable_error_tracking: Enable error tracking with correlation IDs (default: True)
        enable_enhanced_openapi: Enable enhanced OpenAPI with security schemes (default: True)

    Returns:
        FastAPI: Fully configured application instance with enhanced features
    """
    # Auto-detect debug endpoints if not explicitly set
    if enable_debug_endpoints is None:
        enable_debug_endpoints = settings.APP_ENABLE_DEBUG or deployment_mode == "debug"

    logger.info(
        f"Creating FastAPI application (mode: {deployment_mode}, debug: {enable_debug_endpoints})"
    )

    # Initialize Sentry for error tracking (before app creation)
    setup_sentry()

    # Determine documentation visibility based on deployment mode
    docs_available = deployment_mode != "production" or settings.APP_ENABLE_DEBUG

    # Create base FastAPI application with metadata
    app = FastAPI(
        title="Hormonia Backend API"
        + (f" ({deployment_mode.title()})" if deployment_mode != "production" else ""),
        description=get_api_description(deployment_mode),
        version="2.0.0",  # Updated version to reflect consolidation
        contact={
            "name": "Hormonia Support",
            "email": "support@hormonia.com",
            "url": "https://hormonia.com/support",
        },
        docs_url="/docs" if docs_available else None,
        redoc_url="/redoc" if docs_available else None,
        openapi_url="/openapi.json" if docs_available else None,
        lifespan=lifespan,
        openapi_tags=get_openapi_tags(),
    )

    # Store configuration in app state for reference
    app.state.deployment_mode = deployment_mode
    app.state.debug_endpoints_enabled = enable_debug_endpoints
    app.state.error_tracking_enabled = enable_error_tracking

    # Configure rate limiter
    if settings.RATE_LIMIT_ENABLE_SERVICE:
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
        logger.info("✓ Rate limiter configured")

    # Configure API v2 exception handlers
    from app.core.exceptions import APIException
    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exc: APIException):
        """Handle custom API exceptions with consistent format."""
        # Add request ID if available
        request_id = getattr(request.state, "request_id", None)

        logger.warning(
            f"API exception: {exc.error_code}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "path": str(request.url.path),
                "method": request.method,
                "request_id": request_id,
            },
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        """Handle Pydantic validation errors with detailed field information."""
        request_id = getattr(request.state, "request_id", None)

        # Format validation errors
        errors = []
        for error in exc.errors():
            errors.append(
                {
                    "field": ".".join(str(loc) for loc in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                }
            )

        logger.warning(
            f"Validation error: {len(errors)} field(s)",
            extra={
                "path": str(request.url.path),
                "method": request.method,
                "request_id": request_id,
                "errors": errors,
            },
        )

        return JSONResponse(
            status_code=422,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": errors},
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
        )

    logger.info("✓ API v2 exception handlers configured")

    # Configure CSRF protection
    try:
        from fastapi_csrf_protect.exceptions import CsrfProtectError
        from app.middleware.csrf import csrf_protect

        @app.exception_handler(CsrfProtectError)
        async def csrf_protect_exception_handler(
            request: Request, exc: CsrfProtectError
        ):
            """Handle CSRF validation failures with proper logging."""
            logger.warning(
                f"CSRF validation failed: {str(exc)}",
                extra={
                    "path": str(request.url.path),
                    "method": request.method,
                    "client_ip": request.client.host if request.client else "unknown",
                },
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_validation_failed",
                    "message": "CSRF token validation failed. Please refresh and try again.",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        # NOTE: Deprecated /api/v2/csrf-token endpoint removed.
        # Use /api/v2/auth/csrf-token instead (defined in app/api/v2/routers/auth.py)

        app.state.csrf_protect = csrf_protect
        logger.info("✓ CSRF protection configured")
    except Exception as e:
        logger.warning(f"CSRF protection not configured: {e}")

    # Configure application components in order
    logger.info("Setting up application components...")

    # 1. Setup global exception handler (if enabled)
    if enable_error_tracking:
        _setup_global_exception_handler(app)
        logger.info("✓ Global exception handler configured")

    # Register domain-specific exception handlers
    register_exception_handlers(app)
    logger.info("✓ Domain exception handlers registered")

    # 2. Setup monitoring first for comprehensive instrumentation (if enabled)
    if enable_monitoring:
        setup_monitoring(app)
        logger.info("✓ Monitoring configured")
    else:
        logger.info("⚠ Monitoring disabled")

    # 3. Setup middleware (order matters for middleware stack)
    setup_middleware(app)
    logger.info("✓ Middleware configured")

    # 4. Register all API routers with graceful failure handling
    _register_routers_with_resilience(app, deployment_mode)
    logger.info("✓ Routers registered")

    # 5. Add debug endpoints (if enabled)
    if enable_debug_endpoints:
        _add_debug_endpoints(app)
        logger.info("✓ Debug endpoints added")

    # 6. Setup enhanced OpenAPI (if enabled)
    if enable_enhanced_openapi:
        setup_enhanced_openapi(app)
        logger.info("✓ Enhanced OpenAPI configured")

    # 7. Setup static file serving for uploads
    _setup_static_files(app)
    logger.info("✓ Static file serving configured")

    logger.info(f"FastAPI application created successfully (mode: {deployment_mode})")
    return app


def _setup_static_files(app: FastAPI) -> None:
    """
    Setup static file serving for uploaded media files.

    Args:
        app: FastAPI application instance
    """
    try:
        # Create upload directory if it doesn't exist
        upload_dir = Path(settings.UPLOAD_DIRECTORY)
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Mount static files directory
        app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")
        logger.info(f"✓ Static files mounted at /uploads -> {upload_dir}")
    except Exception as e:
        logger.warning(f"Failed to setup static file serving: {e}")
        # Don't fail application startup if static files can't be mounted
        # Files can still be uploaded, just won't be served


def _setup_global_exception_handler(app: FastAPI) -> None:
    """Setup global exception handler with enhanced error tracking."""

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler with thread-safe error tracking."""
        logger = get_logger(__name__)

        # Generate request correlation ID if not present
        request_id = getattr(request.state, "request_id", "unknown")

        # Track error (thread-safe) if error tracking is enabled
        if getattr(app.state, "error_tracking_enabled", True):
            try:
                # FIX: track_error is synchronous, not async - remove await
                track_error(exc, request)
            except Exception as tracking_error:
                logger.error(f"Error tracking failed: {tracking_error}")

        # Log error with context
        logger.error(
            f"Unhandled exception: {exc}",
            extra={
                "request_id": request_id,
                "path": str(request.url),
                "method": request.method,
                "user_agent": request.headers.get("user-agent", "unknown"),
                "deployment_mode": getattr(app.state, "deployment_mode", "unknown"),
            },
        )

        # Determine error detail level based on deployment mode
        deployment_mode = getattr(app.state, "deployment_mode", "production")
        include_details = (
            deployment_mode in ["development", "debug"] or settings.APP_ENABLE_DEBUG
        )

        error_response = {
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "details": {},
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id,
        }

        # Add debug information if appropriate
        if include_details:
            error_response["details"] = {
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "path": str(request.url),
                "method": request.method,
            }

        return JSONResponse(status_code=500, content=error_response)


def _register_routers_with_resilience(app: FastAPI, deployment_mode: str) -> None:
    """Register routers with graceful failure handling for deployment resilience."""
    try:
        # Use the existing router registry with enhanced error handling
        register_routers(app)

    except Exception as e:
        logger.error(f"Critical error in router registration: {e}")

        # In production, this should fail fast
        if deployment_mode == "production":
            raise

        # In development/debug mode, try to register core routers individually
        logger.warning("Attempting individual router registration for debugging...")
        _register_core_routers_individually(app)


def _register_core_routers_individually(app: FastAPI) -> None:
    """Register core routers individually with error handling."""
    core_routers = [
        ("app.routers.health", "router", {"tags": ["Health"]}),
        ("app.monitoring.prometheus_exporters", "router", {"tags": ["Monitoring"]}),
        ("app.routers.auth_session", "router", {"tags": ["Session Authentication"]}),
        ("app.api.v2", "api_v2_router", {"tags": ["API v2"]}),
    ]

    for module_path, router_name, include_kwargs in core_routers:
        try:
            module = __import__(module_path, fromlist=[router_name])
            router = getattr(module, router_name)
            include_kwargs = include_kwargs or {}
            app.include_router(router, **include_kwargs)
            logger.info(f"? {router_name} router registered successfully")
        except Exception as e:
            logger.error(f"?? Failed to register {router_name} router: {e}")


def _add_debug_endpoints(app: FastAPI) -> None:
    """Add debug endpoints for troubleshooting (from minimal_main.py)."""
    import os
    import sys

    @app.get("/debug/env", tags=["Debug"])
    async def debug_env():
        """Debug environment variables (sensitive values masked)."""
        env_vars = {
            "PORT": os.getenv("PORT", "not_set"),
            "ENVIRONMENT": os.getenv("ENVIRONMENT", "not_set"),
            "DATABASE_URL": "***masked***" if os.getenv("DATABASE_URL") else "not_set",
            "REDIS_URL": "***masked***" if os.getenv("REDIS_URL") else "not_set",
            "PYTHONPATH": os.getenv("PYTHONPATH", "not_set"),
            "PWD": os.getenv("PWD", "not_set"),
            "DEBUG": str(settings.APP_ENABLE_DEBUG),
            "DEPLOYMENT_MODE": getattr(app.state, "deployment_mode", "unknown"),
        }
        return {
            "environment_variables": env_vars,
            "python_path": sys.path[:10],  # Limit for readability
            "app_state": {
                "deployment_mode": getattr(app.state, "deployment_mode", "unknown"),
                "debug_endpoints_enabled": getattr(
                    app.state, "debug_endpoints_enabled", False
                ),
                "error_tracking_enabled": getattr(
                    app.state, "error_tracking_enabled", True
                ),
            },
        }

    @app.get("/debug/imports", tags=["Debug"])
    async def debug_imports():
        """Test critical imports for troubleshooting."""
        import_results = {}

        critical_imports = [
            ("app.config", "Application configuration"),
            ("app.database", "Database connectivity"),
            ("app.services", "Core services"),
            ("app.core.application_factory", "Application factory"),
        ]

        for module_path, description in critical_imports:
            try:
                __import__(module_path)
                import_results[module_path] = {
                    "status": "success",
                    "description": description,
                }
            except Exception as e:
                import_results[module_path] = {
                    "status": "failed",
                    "error": str(e),
                    "description": description,
                }

        return {
            "import_test_results": import_results,
            "timestamp": datetime.utcnow().isoformat(),
        }

    @app.get("/debug/health", tags=["Debug"])
    async def debug_health():
        """Enhanced health check with debug information."""
        uptime = time.time() - getattr(app.state, "start_time", time.time())

        health_info = {
            "status": "healthy",
            "deployment_mode": getattr(app.state, "deployment_mode", "unknown"),
            "debug_mode": getattr(app.state, "debug_endpoints_enabled", False),
            "uptime_seconds": uptime,
            "version": "2.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "features": {
                "monitoring": hasattr(app.state, "monitoring_manager"),
                "redis": hasattr(app.state, "redis_client"),
                "session_manager": hasattr(app.state, "session_manager"),
                "error_tracking": getattr(app.state, "error_tracking_enabled", True),
            },
        }

        return health_info
