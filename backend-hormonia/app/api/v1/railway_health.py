"""
Railway-specific health check endpoints with proper service initialization validation.
Designed to handle Railway's containerized environment and service dependencies.
"""

from fastapi import APIRouter, HTTPException, status
from typing import Any, Dict
import time
import os
import asyncio
import logging
from datetime import datetime

from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health", response_model=None)
async def railway_health_check() -> Dict[str, Any]:
    """
    Railway-optimized health check endpoint.

    This endpoint is specifically designed for Railway's health check requirements:
    - Fast response time (< 5 seconds)
    - Validates critical service initialization
    - Handles Railway's containerized environment
    - Provides detailed error information for debugging
    """
    start_time = time.time()

    try:
        # Basic service availability
        health_data = {
            "status": "healthy",
            "service": "hormonia-backend",
            "environment": os.getenv("ENVIRONMENT", "unknown"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "checks": {}
        }

        # 1. Database connectivity check
        db_check = await _check_database_connection()
        health_data["checks"]["database"] = db_check

        if not db_check["healthy"]:
            health_data["status"] = "unhealthy"

        # 2. Service provider initialization check (most critical)
        service_provider_check = await _check_service_provider_initialization()
        health_data["checks"]["service_provider"] = service_provider_check

        if not service_provider_check["healthy"]:
            health_data["status"] = "unhealthy"

        # 3. Redis connectivity check (non-blocking)
        redis_check = await _check_redis_connection()
        health_data["checks"]["redis"] = redis_check
        # Don't mark as unhealthy for Redis issues - it's optional

        # 4. Application startup check
        startup_check = await _check_application_startup()
        health_data["checks"]["application"] = startup_check

        if not startup_check["healthy"]:
            health_data["status"] = "unhealthy"

        # Add performance metrics
        response_time = (time.time() - start_time) * 1000
        health_data["response_time_ms"] = round(response_time, 2)
        health_data["version"] = "1.0.0"

        # Log health status
        logger.info(
            f"Railway health check completed - Status: {health_data['status']}",
            extra={
                "event_type": "railway_health_check",
                "status": health_data["status"],
                "response_time_ms": response_time,
                "checks": {k: v["healthy"] for k, v in health_data["checks"].items()}
            }
        )

        # Return appropriate HTTP status
        if health_data["status"] == "unhealthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=health_data
            )

        return health_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Railway health check failed: {str(e)}",
            extra={"event_type": "railway_health_check_error"},
            exc_info=True
        )

        error_response = {
            "status": "error",
            "service": "hormonia-backend",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "response_time_ms": round((time.time() - start_time) * 1000, 2)
        }

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_response
        )


async def _check_database_connection() -> Dict[str, Any]:
    """Check database connectivity for Railway."""
    try:
        from app.database import SessionLocal, test_connection

        # Test database connection with timeout
        db_status = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, test_connection),
            timeout=5.0
        )

        if db_status.get("status") == "connected":
            return {
                "healthy": True,
                "message": "Database connected successfully",
                "details": {
                    "connection_time_ms": db_status.get("connection_time_ms", 0),
                    "database_url_configured": bool(os.getenv("DATABASE_URL"))
                }
            }
        else:
            return {
                "healthy": False,
                "message": "Database connection failed",
                "error": db_status.get("error", "Unknown error"),
                "details": {
                    "database_url_configured": bool(os.getenv("DATABASE_URL"))
                }
            }

    except asyncio.TimeoutError:
        return {
            "healthy": False,
            "message": "Database connection timeout",
            "error": "Connection attempt exceeded 5 seconds",
            "details": {
                "timeout_seconds": 5,
                "database_url_configured": bool(os.getenv("DATABASE_URL"))
            }
        }
    except Exception as e:
        return {
            "healthy": False,
            "message": "Database connectivity check failed",
            "error": str(e),
            "details": {
                "database_url_configured": bool(os.getenv("DATABASE_URL"))
            }
        }


async def _check_service_provider_initialization() -> Dict[str, Any]:
    """Check ServiceProvider initialization - the most critical component."""
    try:
        from app.services import ServiceProvider
        from app.dependencies.session_manager import get_db

        # Create a test database session
        db = next(get_db())

        # Try to initialize ServiceProvider
        service_provider = ServiceProvider(db)

        # Test that ServiceProvider can access basic services
        try:
            # Test auth service initialization (doesn't require Redis)
            auth_service = service_provider.auth_service
            if auth_service:
                success_msg = "ServiceProvider initialized with auth service"
            else:
                success_msg = "ServiceProvider initialized but auth service unavailable"

            # Test Redis client availability
            redis_available = service_provider.redis_client is not None
            redis_type = service_provider._redis_client_type

            db.close()  # Cleanup

            return {
                "healthy": True,
                "message": success_msg,
                "details": {
                    "redis_client_available": redis_available,
                    "redis_client_type": redis_type,
                    "session_active": True,
                    "auth_service_available": bool(auth_service)
                }
            }

        except Exception as service_error:
            db.close()  # Cleanup
            return {
                "healthy": False,
                "message": "ServiceProvider service initialization failed",
                "error": f"Service error: {str(service_error)}",
                "details": {
                    "error_type": type(service_error).__name__,
                    "service_provider_created": True
                }
            }

    except Exception as e:
        return {
            "healthy": False,
            "message": "ServiceProvider initialization failed",
            "error": f"Initialization error: {str(e)}",
            "details": {
                "error_type": type(e).__name__,
                "service_provider_created": False
            }
        }


async def _check_redis_connection() -> Dict[str, Any]:
    """Check Redis connectivity (non-blocking) using unified RedisManager."""
    try:
        from app.core.redis_manager import get_redis_manager
        from app.utils.security import mask_sensitive_url

        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return {
                "healthy": False,
                "message": "Redis URL not configured",
                "warning": "Application will continue without Redis features",
                "details": {"redis_url_configured": False}
            }

        # Use unified RedisManager for consistent SSL/TLS handling
        redis_manager = get_redis_manager()

        # Test connection with timeout using async client
        response = await asyncio.wait_for(
            redis_manager.get_async_client(),
            timeout=5.0
        )

        # Test ping
        ping_result = await asyncio.wait_for(
            response.ping(),
            timeout=5.0
        )

        if ping_result:
            return {
                "healthy": True,
                "message": "Redis connected successfully",
                "details": {
                    "redis_url_configured": True,
                    "ssl_enabled": redis_url.startswith('rediss://'),
                    "url": mask_sensitive_url(redis_url)
                }
            }
        else:
            return {
                "healthy": False,
                "message": "Redis ping failed",
                "warning": "Application will continue without Redis features",
                "details": {"redis_url_configured": True}
            }

    except asyncio.TimeoutError:
        return {
            "healthy": False,
            "message": "Redis connection timeout",
            "warning": "Application will continue without Redis features",
            "details": {"timeout_seconds": 5}
        }
    except Exception as e:
        return {
            "healthy": False,
            "message": "Redis connectivity check failed",
            "error": str(e),
            "warning": "Application will continue without Redis features",
            "details": {
                "redis_url_configured": bool(os.getenv("REDIS_URL")),
                "error_type": type(e).__name__
            }
        }


async def _check_application_startup() -> Dict[str, Any]:
    """Check if application startup completed successfully."""
    try:
        # Check if FastAPI app is properly initialized
        from fastapi import FastAPI

        # Try to import core modules
        from app.config import settings
        from app.core.application_factory import create_application

        # Basic configuration validation
        required_env_vars = ["DATABASE_URL", "SECRET_KEY"]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]

        if missing_vars:
            return {
                "healthy": False,
                "message": "Critical environment variables missing",
                "error": f"Missing: {', '.join(missing_vars)}",
                "details": {"missing_env_vars": missing_vars}
            }

        # Check if settings can be loaded
        debug_mode = settings.DEBUG
        environment = settings.ENVIRONMENT

        return {
            "healthy": True,
            "message": "Application startup completed successfully",
            "details": {
                "environment": environment,
                "debug_mode": debug_mode,
                "all_required_env_vars_set": True
            }
        }

    except Exception as e:
        return {
            "healthy": False,
            "message": "Application startup check failed",
            "error": str(e),
            "details": {"error_type": type(e).__name__}
        }


@router.get("/health/readiness", response_model=None)
async def railway_readiness_probe() -> Dict[str, Any]:
    """
    Railway readiness probe - check if service is ready to receive traffic.
    """
    try:
        # Quick database check
        db_result = await _check_database_connection()
        service_result = await _check_service_provider_initialization()

        ready = db_result["healthy"] and service_result["healthy"]

        if ready:
            return {
                "status": "ready",
                "service": "hormonia-backend",
                "message": "Service is ready to receive traffic"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "not_ready",
                    "service": "hormonia-backend",
                    "message": "Service is not ready",
                    "database_ready": db_result["healthy"],
                    "service_provider_ready": service_result["healthy"]
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness probe failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "error", "message": str(e)}
        )


@router.get("/health/liveness", response_model=None)
async def railway_liveness_probe() -> Dict[str, Any]:
    """
    Railway liveness probe - check if service is alive.
    """
    return {
        "status": "alive",
        "service": "hormonia-backend",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "uptime_seconds": time.time() - (os.getenv("APP_START_TIME", time.time()))
    }


@router.get("/health/startup", response_model=None)
async def railway_startup_probe() -> Dict[str, Any]:
    """
    Railway startup probe - check if service has started successfully.
    """
    try:
        startup_result = await _check_application_startup()

        if startup_result["healthy"]:
            return {
                "status": "started",
                "service": "hormonia-backend",
                "message": "Service startup completed successfully",
                "details": startup_result["details"]
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "starting",
                    "service": "hormonia-backend",
                    "message": startup_result["message"],
                    "error": startup_result.get("error")
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Startup probe failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "error", "message": str(e)}
        )