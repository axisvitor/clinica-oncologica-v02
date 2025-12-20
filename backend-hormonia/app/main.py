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


# CSRF Token endpoint - stateless Double Submit Cookie pattern
@app.get("/csrf-token", tags=["Security"])
async def get_csrf_token_root():
    """
    Get CSRF token for stateless Double Submit Cookie pattern.

    Returns a signed CSRF token (HMAC-SHA256) that must be:
    1. Stored in cookie (done automatically by this endpoint)
    2. Sent in X-CSRF-Token header on state-changing requests (POST, PUT, DELETE, PATCH)

    Token format: {timestamp}.{random_hex}.{signature}
    Encoding: Hexadecimal (auditable, no padding issues)
    """
    from fastapi import Request, Response
    from fastapi.responses import JSONResponse
    from app.middleware.csrf import generate_csrf_token, get_csrf_settings

    # Generate token
    csrf_settings = get_csrf_settings()
    token = generate_csrf_token(csrf_settings.secret_key)

    # Create response with cookie
    response = JSONResponse(content={"csrf_token": token})
    response.set_cookie(
        key=csrf_settings.cookie_name,
        value=token,
        max_age=csrf_settings.token_expires_in,
        path=csrf_settings.cookie_path,
        domain=csrf_settings.cookie_domain,
        secure=csrf_settings.cookie_secure,
        httponly=csrf_settings.cookie_httponly,
        samesite=csrf_settings.cookie_samesite,
    )
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=8000, reload=settings.APP_ENABLE_DEBUG
    )
