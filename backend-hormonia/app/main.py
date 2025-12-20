"""
FastAPI application entry point for Hormonia Backend System.

Clean, minimal main.py that delegates all concerns to specialized modules:
- Application factory handles app creation
- Middleware setup manages all middleware configuration
- Router registry handles route registration
- Lifespan manager handles startup/shutdown lifecycle
- Monitoring setup handles observability
"""

from app.core.application_factory import create_application
from app.config import settings

# Create application instance using factory pattern with appropriate mode
deployment_mode = "development" if settings.APP_ENABLE_DEBUG else "production"
app = create_application(deployment_mode=deployment_mode)


# Simple health check endpoint for Railway/Docker health checks
@app.get("/health", tags=["Health"])
async def root_health_check():
    """
    Simple health check endpoint at root level for Railway/Docker.
    Returns basic status without dependency checks.
    """
    from datetime import datetime

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "2.0.0",
        "environment": settings.APP_ENVIRONMENT,
    }


# Add a simple test endpoint to verify the server is working (debug mode only)
if settings.APP_ENABLE_DEBUG:

    @app.get("/test", tags=["Debug"])
    async def test_endpoint():
        return {
            "message": "Server is working",
            "debug": settings.APP_ENABLE_DEBUG,
            "mode": deployment_mode,
        }


# CSRF Token endpoint - redirects to /api/v2/auth/csrf-token
# NOTE: Use /api/v2/auth/csrf-token as the primary endpoint
@app.get("/csrf-token", tags=["Security"], include_in_schema=False)
async def get_csrf_token_root():
    """
    Legacy CSRF token endpoint - redirects to /api/v2/auth/csrf-token.

    This endpoint exists for backwards compatibility only.
    Use /api/v2/auth/csrf-token for new implementations.
    """
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/api/v2/auth/csrf-token", status_code=307)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=8000, reload=settings.APP_ENABLE_DEBUG
    )
