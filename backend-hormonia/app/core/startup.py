"""
Application Startup Configuration for Production Stability.

This module handles the initialization of all systems during application startup,
ensuring that both primary and fallback systems are ready to handle requests.
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

# Import all systems that need initialization
from app.core.database_direct import initialize_direct_database, cleanup_direct_database
from app.core.redis_unified import get_sync_redis, cleanup_redis
from app.core.session_manager import initialize_session_manager

from app.config import settings

logger = logging.getLogger(__name__)


async def initialize_primary_systems():
    """
    Initialize primary (complex) systems.

    Returns:
        dict: Status of primary system initialization
    """
    results = {
        "session_manager": {"status": "unknown", "error": None},
        "redis": {"status": "unknown", "error": None},
    }

    # Initialize session manager
    try:
        # Try to initialize with Redis if available
        redis_client = None
        try:
            from app.core.redis_unified import get_async_redis

            if hasattr(settings, "REDIS_URL") and settings.REDIS_URL:
                # Use unified Redis client - SSL/TLS handled automatically
                redis_client = await get_async_redis()
                await redis_client.ping()  # Test connection
                logger.info(
                    "Unified async Redis client initialized for session manager"
                )
        except Exception as redis_error:
            logger.warning(f"Unified Redis initialization failed: {redis_error}")
            redis_client = None

        # Initialize session manager
        initialize_session_manager(redis_client)
        results["session_manager"] = {
            "status": "initialized",
            "redis_available": redis_client is not None,
        }
        logger.info("Primary session manager initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize session manager: {e}")
        results["session_manager"] = {"status": "failed", "error": str(e)}

    return results


async def initialize_fallback_systems():
    """
    Initialize fallback (simplified) systems.

    Returns:
        dict: Status of fallback system initialization
    """
    results = {
        "direct_database": {"status": "unknown", "error": None},
        "simple_redis": {"status": "unknown", "error": None},
    }

    # Initialize direct database
    try:
        success = initialize_direct_database()
        results["direct_database"] = {
            "status": "initialized" if success else "failed",
            "success": success,
        }
        if success:
            logger.info("Direct database system initialized successfully")
        else:
            logger.warning("Direct database system failed to initialize")
    except Exception as e:
        logger.error(f"Failed to initialize direct database: {e}")
        results["direct_database"] = {"status": "failed", "error": str(e)}

    # Initialize unified Redis
    try:
        redis_client = get_sync_redis()
        redis_available = redis_client.ping() if redis_client else False
        results["simple_redis"] = {
            "status": "initialized",
            "available": redis_available,
            "redis_configured": hasattr(settings, "REDIS_URL")
            and settings.REDIS_URL is not None,
        }
        logger.info(f"Unified Redis initialized - available: {redis_available}")
    except Exception as e:
        logger.error(f"Failed to initialize unified Redis: {e}")
        results["simple_redis"] = {"status": "failed", "error": str(e)}

    return results


async def validate_authentication_system():
    """
    Validate that authentication system is working.

    Returns:
        dict: Authentication system validation results
    """
    results = {
        "service_provider": {"status": "unknown", "error": None},
        "auth_service": {"status": "unknown", "error": None},
    }

    try:
        # Test simplified service provider creation
        from app.services.simple_provider import SimplifiedServiceProvider
        from app.core.database_direct import get_direct_session
        from app.core.redis_unified import get_sync_redis

        with get_direct_session() as db:
            redis_client = get_sync_redis()
            provider = SimplifiedServiceProvider(db, redis_client)

            results["service_provider"] = {
                "status": "available" if provider.is_initialized else "failed",
                "initialized": provider.is_initialized,
                "redis_available": redis_client is not None,
            }

            # Test auth service
            if provider.is_initialized:
                try:
                    auth_service = provider.auth_service
                    results["auth_service"] = {
                        "status": "available",
                        "type": type(auth_service).__name__,
                    }
                except Exception as auth_error:
                    results["auth_service"] = {
                        "status": "failed",
                        "error": str(auth_error),
                    }

        logger.info("Authentication system validation completed")

    except Exception as e:
        logger.error(f"Authentication system validation failed: {e}")
        results["service_provider"] = {"status": "failed", "error": str(e)}

    return results


async def startup_sequence():
    """
    Execute complete startup sequence.

    Returns:
        dict: Complete startup results
    """
    logger.info("Starting application initialization sequence")
    start_time = asyncio.get_event_loop().time()

    results = {
        "primary_systems": {},
        "fallback_systems": {},
        "authentication_validation": {},
        "overall_status": "unknown",
        "startup_time_seconds": 0,
    }

    try:
        # Initialize primary systems first
        logger.info("Initializing primary systems...")
        results["primary_systems"] = await initialize_primary_systems()

        # Initialize fallback systems
        logger.info("Initializing fallback systems...")
        results["fallback_systems"] = await initialize_fallback_systems()

        # Validate authentication system
        logger.info("Validating authentication system...")
        results["authentication_validation"] = await validate_authentication_system()

        # Calculate startup time
        end_time = asyncio.get_event_loop().time()
        results["startup_time_seconds"] = round(end_time - start_time, 2)

        # Determine overall status
        auth_working = (
            results["authentication_validation"]["service_provider"]["status"]
            == "available"
        )
        db_working = (
            results["primary_systems"].get("session_manager", {}).get("status")
            == "initialized"
            or results["fallback_systems"].get("direct_database", {}).get("status")
            == "initialized"
        )

        if auth_working and db_working:
            results["overall_status"] = "healthy"
            logger.info(
                f"Application startup completed successfully in {results['startup_time_seconds']} seconds"
            )
        else:
            results["overall_status"] = "degraded"
            logger.warning(
                f"Application startup completed with issues in {results['startup_time_seconds']} seconds"
            )

    except Exception as e:
        logger.error(f"Startup sequence failed: {e}")
        results["overall_status"] = "failed"
        results["startup_error"] = str(e)

    return results


async def cleanup_sequence():
    """Execute cleanup sequence during shutdown."""
    logger.info("Starting application cleanup sequence")

    try:
        # Cleanup direct database
        cleanup_direct_database()
        logger.info("Direct database cleaned up")

        # Cleanup unified Redis
        await cleanup_redis()
        logger.info("Unified Redis cleaned up")

        logger.info("Application cleanup completed successfully")

    except Exception as e:
        logger.error(f"Cleanup sequence failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.

    Handles startup and shutdown events for the application.
    """
    # Startup
    try:
        startup_results = await startup_sequence()

        # Store startup results in app state for health checks
        app.state.startup_results = startup_results
        app.state.startup_timestamp = asyncio.get_event_loop().time()

        # Log startup summary
        if startup_results["overall_status"] == "healthy":
            logger.info("🚀 Application started successfully - all systems operational")
        elif startup_results["overall_status"] == "degraded":
            logger.warning(
                "⚠️ Application started with degraded performance - some systems unavailable"
            )
        else:
            logger.error(
                "❌ Application startup failed - system may not work correctly"
            )

        yield

    except Exception as startup_error:
        logger.error(f"Fatal startup error: {startup_error}")
        # Still yield to allow the app to start, but in degraded mode
        app.state.startup_results = {
            "overall_status": "failed",
            "startup_error": str(startup_error),
        }
        yield

    finally:
        # Shutdown
        try:
            await cleanup_sequence()
            logger.info("👋 Application shutdown completed")
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}")


def get_startup_results(app: FastAPI) -> dict:
    """
    Get startup results from app state.

    Args:
        app: FastAPI application instance

    Returns:
        dict: Startup results or empty dict if not available
    """
    return getattr(
        app.state,
        "startup_results",
        {"overall_status": "unknown", "error": "Startup results not available"},
    )
