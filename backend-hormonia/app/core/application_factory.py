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
from app.utils.timezone import now_sao_paulo

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
        # CRITICAL: Disable redirect_slashes to prevent CORS issues
        # Without this, /patients?limit=100 redirects to /patients/?limit=100
        # which loses CORS headers and breaks frontend requests
        redirect_slashes=False,
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
                "timestamp": now_sao_paulo().isoformat(),
            },
        )

    logger.info("✓ API v2 exception handlers configured")

    # CSRF protection is handled by CSRFMiddleware (added in middleware_setup.py)
    # The middleware uses Double Submit Cookie pattern with native Python implementation.
    # Token endpoint: /api/v2/auth/csrf-token (defined in app/api/v2/routers/auth.py)
    logger.info("✓ CSRF protection uses CSRFMiddleware (Double Submit Cookie pattern)")

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

    # 5. Setup enhanced OpenAPI (if enabled)
    if enable_enhanced_openapi:
        setup_enhanced_openapi(app)
        logger.info("✓ Enhanced OpenAPI configured")

    # 6. Setup static file serving for uploads
    _setup_static_files(app)
    logger.info("✓ Static file serving configured")

    # Force a final middleware stack rebuild after routers/static mounts are complete.
    # In the assembled runtime this avoids a first-request deadlock on the login path
    # that disappears once the middleware stack is rebuilt explicitly.
    app.middleware_stack = app.build_middleware_stack()

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
            "timestamp": now_sao_paulo().isoformat(),
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
            logger.info(f"✓ {router_name} router registered successfully")
        except Exception as e:
            logger.error(f"✗ Failed to register {router_name} router: {e}")

