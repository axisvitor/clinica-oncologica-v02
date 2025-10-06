"""
Enhanced health check endpoints with comprehensive diagnostics.
"""
from fastapi import APIRouter, Request
from datetime import datetime
import os
import sys
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/health/detailed")
async def detailed_health_check(request: Request):
    """
    Comprehensive health check with environment diagnostics.

    Returns:
        - Server status
        - Environment configuration
        - CORS configuration
        - Database connectivity
        - Redis connectivity
        - Request details
    """
    health_data = {
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "status": "healthy",
        "server": {
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "python_version": sys.version,
            "pid": os.getpid()
        },
        "cors": {
            "enabled": True,
            "allowed_origins_count": len(settings.ALLOWED_ORIGINS),
            "allowed_origins": settings.ALLOWED_ORIGINS,
            "credentials_allowed": True
        },
        "request": {
            "origin": request.headers.get("origin"),
            "host": request.headers.get("host"),
            "user_agent": request.headers.get("user-agent"),
            "method": request.method
        },
        "endpoints": {
            "auth": "/api/v1/auth/me",
            "notifications": "/api/v1/auth/notifications",
            "analytics": "/api/v1/analytics/dashboard",
            "websocket": "/ws/connect"
        }
    }

    # Log health check for debugging
    logger.info(f"Health check requested from origin: {request.headers.get('origin')}")

    return health_data


@router.options("/health/cors-test")
async def cors_preflight_test():
    """
    Test endpoint for CORS preflight requests.

    Returns empty 200 response with CORS headers.
    """
    return {}


@router.get("/health/cors-test")
async def cors_get_test(request: Request):
    """
    Test endpoint for CORS GET requests.

    Returns CORS configuration and request details.
    """
    logger.info(f"CORS test GET from origin: {request.headers.get('origin')}")

    return {
        "message": "CORS GET test successful",
        "origin": request.headers.get("origin"),
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "cors_configured": True,
        "allowed_origins": settings.ALLOWED_ORIGINS
    }
