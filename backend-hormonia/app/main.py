"""
FastAPI application entry point for Hormonia Backend System.

Clean, minimal main.py that delegates all concerns to specialized modules:
- Application factory handles app creation
- Middleware setup manages all middleware configuration
- Router registry handles route registration
- Lifespan manager handles startup/shutdown lifecycle
- Monitoring setup handles observability

Last deployment: 2025-12-20T16:50:00Z
"""

import logging
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file immediately (skip for pytest)
if "pytest" not in sys.modules and "PYTEST_CURRENT_TEST" not in os.environ:
    load_dotenv(override=True)

# Early diagnostic logging - helps identify startup issues
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
_startup_logger = logging.getLogger("app.main.startup")
_startup_logger.info("=== MAIN.PY LOADING - FastAPI Entry Point ===")

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
    from datetime import datetime, timezone

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
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


# CSRF Token endpoint - returns token directly (no redirect for CORS compatibility)
@app.get("/csrf-token", tags=["Security"], include_in_schema=False)
async def get_csrf_token_root():
    """
    CSRF token endpoint for backwards compatibility.

    Returns token directly instead of redirecting to avoid CORS issues.
    Cross-origin redirects don't carry CORS headers properly, causing
    preflight requests to fail.

    Primary endpoint: /api/v2/auth/csrf-token
    """
    from fastapi.responses import JSONResponse
    from app.middleware.csrf import get_csrf_token, set_csrf_cookie

    token = get_csrf_token()
    response = JSONResponse(content={"csrf_token": token})
    set_csrf_cookie(response, token)
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=8000, reload=settings.APP_ENABLE_DEBUG
    )
