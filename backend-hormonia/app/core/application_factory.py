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
from typing import Optional, Literal
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
from datetime import datetime
import time

from app.config import settings
from app.utils.logging import get_logger
from app.utils.error_tracking import track_error

from .middleware_setup import setup_middleware
from .router_registry import register_routers
from .lifespan import lifespan
from .monitoring_setup import setup_monitoring

# Import rate limiter components
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.utils.rate_limiter import limiter, rate_limit_handler

logger = get_logger(__name__)


def _setup_sentry() -> None:
    """
    Initialize Sentry SDK for error tracking and performance monitoring.

    Sentry provides:
    - Automatic error capture and reporting
    - Performance monitoring and tracing
    - Release tracking
    - Environment-based configuration
    - Integration with FastAPI

    Configuration via environment variables:
    - SENTRY_DSN: Sentry project DSN (required)
    - ENVIRONMENT: Environment name (production, staging, development)
    - SENTRY_TRACES_SAMPLE_RATE: Performance monitoring sample rate (0.0-1.0)
    """
    sentry_dsn = settings.SENTRY_DSN if hasattr(settings, 'SENTRY_DSN') else None

    if not sentry_dsn:
        logger.info("⚠️  Sentry not configured (SENTRY_DSN not set)")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.redis import RedisIntegration

        # Determine environment
        environment = getattr(settings, 'ENVIRONMENT', 'development')

        # Configure sample rates based on environment
        traces_sample_rate = 0.1  # 10% in production
        if environment == 'development':
            traces_sample_rate = 1.0  # 100% in development
        elif environment == 'staging':
            traces_sample_rate = 0.5  # 50% in staging

        # Initialize Sentry
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=environment,
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=0.1,  # Profile 10% of transactions
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                RedisIntegration(),
            ],
            # Send default PII (Personally Identifiable Information)
            send_default_pii=False,  # Don't send PII for HIPAA compliance
            # Release tracking
            release=f"hormonia-backend@2.0.0",
            # Before send callback to filter sensitive data
            before_send=_sentry_before_send,
        )

        logger.info(f"✅ Sentry initialized (env: {environment}, traces: {traces_sample_rate*100}%)")

    except ImportError:
        logger.warning("⚠️  Sentry SDK not installed. Install with: pip install sentry-sdk[fastapi]")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Sentry: {e}")


def _sentry_before_send(event, hint):
    """
    Filter and sanitize events before sending to Sentry.

    This callback:
    - Removes sensitive data (passwords, tokens, PHI)
    - Filters out known non-critical errors
    - Adds custom context

    Args:
        event: Sentry event dictionary
        hint: Additional context about the event

    Returns:
        Modified event or None to drop the event
    """
    # Filter out health check errors
    if 'request' in event:
        url = event['request'].get('url', '')
        if '/health' in url or '/metrics' in url:
            return None  # Don't send health check errors

    # Remove sensitive headers
    if 'request' in event and 'headers' in event['request']:
        sensitive_headers = ['Authorization', 'Cookie', 'X-API-Key', 'X-CSRF-Token']
        for header in sensitive_headers:
            if header in event['request']['headers']:
                event['request']['headers'][header] = '[Filtered]'

    # Remove sensitive query parameters
    if 'request' in event and 'query_string' in event['request']:
        sensitive_params = ['token', 'api_key', 'password', 'secret']
        query_string = event['request'].get('query_string', '')
        for param in sensitive_params:
            if param in query_string.lower():
                event['request']['query_string'] = '[Filtered]'
                break

    return event


def create_application(
    enable_monitoring: bool = True,
    enable_debug_endpoints: bool = None,
    deployment_mode: Literal["production", "development", "debug"] = "production",
    enable_error_tracking: bool = True,
    enable_enhanced_openapi: bool = True
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
        enable_debug_endpoints: Enable debug endpoints (default: None - auto-detect from settings.DEBUG)
        deployment_mode: Deployment mode for configuration (default: "production")
        enable_error_tracking: Enable error tracking with correlation IDs (default: True)
        enable_enhanced_openapi: Enable enhanced OpenAPI with security schemes (default: True)

    Returns:
        FastAPI: Fully configured application instance with enhanced features
    """
    # Auto-detect debug endpoints if not explicitly set
    if enable_debug_endpoints is None:
        enable_debug_endpoints = settings.DEBUG or deployment_mode == "debug"

    logger.info(f"Creating FastAPI application (mode: {deployment_mode}, debug: {enable_debug_endpoints})")

    # Initialize Sentry for error tracking (before app creation)
    _setup_sentry()

    # Determine documentation visibility based on deployment mode
    docs_available = deployment_mode != "production" or settings.DEBUG

    # Create base FastAPI application with metadata
    app = FastAPI(
        title="Hormonia Backend API" + (f" ({deployment_mode.title()})" if deployment_mode != "production" else ""),
        description=_get_api_description(deployment_mode),
        version="2.0.0",  # Updated version to reflect consolidation
        contact={
            "name": "Hormonia Support",
            "email": "support@hormonia.com",
            "url": "https://hormonia.com/support"
        },
        docs_url="/docs" if docs_available else None,
        redoc_url="/redoc" if docs_available else None,
        openapi_url="/openapi.json" if docs_available else None,
        lifespan=lifespan,
        openapi_tags=_get_openapi_tags()
    )

    # Store configuration in app state for reference
    app.state.deployment_mode = deployment_mode
    app.state.debug_endpoints_enabled = enable_debug_endpoints
    app.state.error_tracking_enabled = enable_error_tracking

    # Configure rate limiter
    if settings.RATE_LIMIT_ENABLED:
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
        logger.info("✓ Rate limiter configured")

    # Configure API v2 exception handlers
    from app.core.exceptions import APIException
    from fastapi.exceptions import RequestValidationError
    from pydantic import ValidationError as PydanticValidationError
    
    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exc: APIException):
        """Handle custom API exceptions with consistent format."""
        # Add request ID if available
        request_id = getattr(request.state, 'request_id', None)
        
        logger.warning(
            f"API exception: {exc.error_code}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "path": str(request.url.path),
                "method": request.method,
                "request_id": request_id
            }
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors with detailed field information."""
        request_id = getattr(request.state, 'request_id', None)
        
        # Format validation errors
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })
        
        logger.warning(
            f"Validation error: {len(errors)} field(s)",
            extra={
                "path": str(request.url.path),
                "method": request.method,
                "request_id": request_id,
                "errors": errors
            }
        )
        
        return JSONResponse(
            status_code=422,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": errors},
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }
        )
    
    logger.info("✓ API v2 exception handlers configured")

    # Configure CSRF protection
    try:
        from fastapi_csrf_protect.exceptions import CsrfProtectError
        from app.middleware.csrf import csrf_protect, get_csrf_token

        @app.exception_handler(CsrfProtectError)
        async def csrf_protect_exception_handler(request: Request, exc: CsrfProtectError):
            """Handle CSRF validation failures with proper logging."""
            logger.warning(
                f"CSRF validation failed: {str(exc)}",
                extra={
                    "path": str(request.url.path),
                    "method": request.method,
                    "client_ip": request.client.host if request.client else "unknown"
                }
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_validation_failed",
                    "message": "CSRF token validation failed. Please refresh and try again.",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

        # Add CSRF token endpoint with custom implementation (V2)
        @app.get("/api/v2/csrf-token", tags=["Authentication"])
        async def get_csrf_token_endpoint(request: Request):
            """
            Get CSRF token for session-based authentication.

            Returns CSRF token in response body for cross-domain compatibility.
            Frontend must include this token in X-CSRF-Token header for
            state-changing requests (POST, PUT, DELETE) to session endpoints.

            Returns:
                dict: CSRF token and expiration information
            """
            # PRODUCTION FIX: Use custom CSRF implementation for cross-domain compatibility
            try:
                from app.middleware.custom_csrf import create_csrf_token_response
                return create_csrf_token_response()
            except ImportError:
                # Fallback to original implementation
                from fastapi.responses import JSONResponse
                token = get_csrf_token(request)
                
                response = JSONResponse(content={
                    "csrf_token": token,
                    "expires_in": 3600,  # 1 hour
                    "usage": "Include this token in X-CSRF-Token header for POST/PUT/DELETE requests"
                })
                
                # Set cookie with the same token used in JSON response
                from app.middleware.csrf import set_csrf_cookie as set_csrf_cookie_helper
                set_csrf_cookie_helper(request, response, token)
                return response

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
        _setup_enhanced_openapi(app)
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
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Mount static files directory
        app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")
        logger.info(f"✓ Static files mounted at /uploads -> {upload_dir}")
    except Exception as e:
        logger.warning(f"Failed to setup static file serving: {e}")
        # Don't fail application startup if static files can't be mounted
        # Files can still be uploaded, just won't be served


def _get_api_description(deployment_mode: str = "production") -> str:
    """Get comprehensive API description with deployment-specific information."""
    base_description = """
## Healthcare Communication Platform for Hormone Therapy Patients

The Hormonia Backend System is a comprehensive healthcare communication platform that enables
automated patient engagement through WhatsApp integration, AI-powered conversation flows,
medical questionnaires, and report generation.

### Key Features
- **Patient Management**: Complete patient lifecycle management
- **WhatsApp Integration**: Automated messaging with interactive elements
- **Conversation Flows**: State-machine-driven communication flows
- **AI Personalization**: Google Gemini integration for message humanization
- **Medical Assessments**: Structured quiz system for health data collection
- **Reporting & Analytics**: PDF report generation with insights
- **Real-time Alerts**: Automated detection of concerning patterns
- **WebSocket Communication**: Real-time updates for healthcare providers

### Architecture
This API follows a clean architecture pattern with:
- **Modular Design**: Separated concerns across focused modules
- **Event-Driven**: WebSocket and Redis-based real-time communication
- **Monitoring**: Comprehensive observability with metrics and logging
- **Security**: Enhanced security middleware and rate limiting
- **Scalability**: Redis-backed caching and session management
- **Thread-Safe**: Request-scoped services for multi-worker deployments
"""

    # Add deployment-specific information
    if deployment_mode == "debug":
        base_description += """
### Debug Mode Features
- **Debug Endpoints**: `/debug/env`, `/debug/imports`, `/debug/health` for troubleshooting
- **Enhanced Logging**: Detailed request/response logging
- **Development Tools**: Full OpenAPI documentation available
"""
    elif deployment_mode == "development":
        base_description += """
### Development Environment
- **Enhanced Debugging**: Detailed error messages and stack traces
- **Full Documentation**: Complete OpenAPI specification available
- **Development Tools**: All debugging features enabled
"""

    return base_description


def _get_openapi_tags() -> list:
    """Get OpenAPI tags for API documentation."""
    return [
        {"name": "Authentication", "description": "User authentication and authorization"},
        {"name": "Admin Users", "description": "Administrative user management operations"},
        {"name": "Patients", "description": "Patient management operations"},
        {"name": "Messages", "description": "WhatsApp message handling"},
        {"name": "Flows", "description": "Conversation flow management"},
        {"name": "Quiz", "description": "Medical questionnaire system"},
        {"name": "Monthly Quiz", "description": "Monthly wellness questionnaires"},
        {"name": "AI Services", "description": "AI-powered features and analytics"},
        {"name": "Healthcare Metrics", "description": "Clinical metrics and KPIs"},
        {"name": "Reports", "description": "Medical report generation"},
        {"name": "Analytics", "description": "System and patient analytics"},
        {"name": "Enhanced Analytics", "description": "Advanced analytics features"},
        {"name": "Enhanced Messages", "description": "Advanced messaging features"},
        {"name": "Enhanced Quiz", "description": "Advanced quiz features"},
        {"name": "Enhanced Reports", "description": "Advanced reporting features"},
        {"name": "Enhanced Monitoring", "description": "Advanced monitoring features"},
        {"name": "Monitoring", "description": "System monitoring and health checks"},
        {"name": "Health", "description": "System health monitoring"},
        {"name": "Performance", "description": "Performance monitoring and optimization"},
        {"name": "Alerts", "description": "Alert management system"},
        {"name": "Webhooks", "description": "Webhook endpoints for integrations"},
        {"name": "Tasks", "description": "Background task management"},
        {"name": "Localization", "description": "Multi-language support"},
        {"name": "Documentation", "description": "API documentation endpoints"},
        {"name": "Template Management", "description": "Message template management"},
        {"name": "Platform Sync", "description": "External platform synchronization"},
        {"name": "WhatsApp", "description": "WhatsApp integration endpoints"},
        {"name": "Hive-Mind", "description": "AI coordination system"},
        {"name": "Debug", "description": "Debug and diagnostics endpoints (debug mode only)"}
    ]


def _setup_global_exception_handler(app: FastAPI) -> None:
    """Setup global exception handler with enhanced error tracking."""

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler with thread-safe error tracking."""
        logger = get_logger(__name__)

        # Generate request correlation ID if not present
        request_id = getattr(request.state, 'request_id', 'unknown')

        # Track error (thread-safe) if error tracking is enabled
        if getattr(app.state, 'error_tracking_enabled', True):
            try:
                # FIX: track_error is synchronous, not async - remove await
                track_error(exc, request)
            except Exception as tracking_error:
                logger.error(f"Error tracking failed: {tracking_error}")

        # Log error with context
        logger.error(f"Unhandled exception: {exc}", extra={
            'request_id': request_id,
            'path': str(request.url),
            'method': request.method,
            'user_agent': request.headers.get('user-agent', 'unknown'),
            'deployment_mode': getattr(app.state, 'deployment_mode', 'unknown')
        })

        # Determine error detail level based on deployment mode
        deployment_mode = getattr(app.state, 'deployment_mode', 'production')
        include_details = deployment_mode in ['development', 'debug'] or settings.DEBUG

        error_response = {
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "details": {},
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id
        }

        # Add debug information if appropriate
        if include_details:
            error_response["details"] = {
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "path": str(request.url),
                "method": request.method
            }

        return JSONResponse(
            status_code=500,
            content=error_response
        )


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
            "DEBUG": str(settings.DEBUG),
            "DEPLOYMENT_MODE": getattr(app.state, 'deployment_mode', 'unknown')
        }
        return {
            "environment_variables": env_vars,
            "python_path": sys.path[:10],  # Limit for readability
            "app_state": {
                "deployment_mode": getattr(app.state, 'deployment_mode', 'unknown'),
                "debug_endpoints_enabled": getattr(app.state, 'debug_endpoints_enabled', False),
                "error_tracking_enabled": getattr(app.state, 'error_tracking_enabled', True)
            }
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
                import_results[module_path] = {"status": "success", "description": description}
            except Exception as e:
                import_results[module_path] = {
                    "status": "failed",
                    "error": str(e),
                    "description": description
                }

        return {
            "import_test_results": import_results,
            "timestamp": datetime.utcnow().isoformat()
        }

    @app.get("/debug/health", tags=["Debug"])
    async def debug_health():
        """Enhanced health check with debug information."""
        uptime = time.time() - getattr(app.state, 'start_time', time.time())

        health_info = {
            "status": "healthy",
            "deployment_mode": getattr(app.state, 'deployment_mode', 'unknown'),
            "debug_mode": getattr(app.state, 'debug_endpoints_enabled', False),
            "uptime_seconds": uptime,
            "version": "2.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "features": {
                "monitoring": hasattr(app.state, 'monitoring_manager'),
                "redis": hasattr(app.state, 'redis_client'),
                "session_manager": hasattr(app.state, 'session_manager'),
                "error_tracking": getattr(app.state, 'error_tracking_enabled', True)
            }
        }

        return health_info


def _setup_enhanced_openapi(app: FastAPI) -> None:
    """Setup enhanced OpenAPI with security schemes (from main_v2.py)."""

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        # Get base OpenAPI schema from FastAPI
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        # Ensure components structure exists (robust setdefault pattern)
        openapi_schema.setdefault("components", {})
        openapi_schema["components"].setdefault("securitySchemes", {})
        openapi_schema["components"].setdefault("examples", {})

        # Add security schemes
        openapi_schema["components"]["securitySchemes"].update({
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT token obtained from /api/v2/auth/login endpoint"
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for service-to-service authentication"
            }
        })

        # Add common error response examples (already initialized above)
        openapi_schema["components"]["examples"].update({
            "ValidationError": {
                "summary": "Validation Error",
                "value": {
                    "error": "validation_error",
                    "message": "Invalid input data provided",
                    "details": {"field": "email", "issue": "Invalid email format"},
                    "timestamp": "2024-01-01T00:00:00Z",
                    "request_id": "req_123456789"
                }
            },
            "UnauthorizedError": {
                "summary": "Unauthorized",
                "value": {
                    "error": "unauthorized",
                    "message": "Authentication credentials required",
                    "details": {},
                    "timestamp": "2024-01-01T00:00:00Z",
                    "request_id": "req_123456789"
                }
            },
            "InternalServerError": {
                "summary": "Internal Server Error",
                "value": {
                    "error": "internal_server_error",
                    "message": "An unexpected error occurred",
                    "details": {},
                    "timestamp": "2024-01-01T00:00:00Z",
                    "request_id": "req_123456789"
                }
            }
        })

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
