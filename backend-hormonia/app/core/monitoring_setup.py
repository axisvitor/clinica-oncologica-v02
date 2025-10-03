"""
Monitoring setup for the FastAPI application.

Centralizes monitoring initialization including:
- Application performance monitoring (APM)
- Database monitoring
- Business metrics collection
- Error tracking
- Performance profiling
"""
from fastapi import FastAPI
from app.utils.logging import get_logger

logger = get_logger(__name__)


def setup_monitoring(app: FastAPI) -> None:
    """
    Configure monitoring for the FastAPI application.

    Sets up comprehensive monitoring including:
    - APM collector for application performance
    - Database monitoring for query performance
    - Business metrics for healthcare KPIs
    - Error tracking and alerting

    Args:
        app: FastAPI application instance
    """
    logger.info("Setting up monitoring systems...")

    try:
        # Import monitoring components
        from app.monitoring.manager import get_monitoring_manager

        # Get monitoring manager instance
        monitoring_manager = get_monitoring_manager()

        if monitoring_manager:
            # Store monitoring manager in app state for access during runtime
            app.state.monitoring_manager = monitoring_manager

            logger.info("✓ Monitoring manager initialized")

            # Setup monitoring middleware will be handled in middleware_setup.py
            # This keeps separation of concerns clean

        else:
            logger.warning("Monitoring manager not available - continuing without monitoring")
            app.state.monitoring_manager = None

    except ImportError as e:
        logger.warning(f"Monitoring components not available: {e}")
        logger.info("Continuing without comprehensive monitoring")
        app.state.monitoring_manager = None

    except Exception as e:
        logger.error(f"Failed to setup monitoring: {e}")
        logger.info("Continuing without comprehensive monitoring")
        app.state.monitoring_manager = None

    # Setup basic health check endpoint (always available)
    _setup_basic_health_check(app)

    logger.info("Monitoring setup completed")


def _setup_basic_health_check(app: FastAPI) -> None:
    """
    Setup basic health check endpoint.

    This is a minimal health check that's always available,
    even if comprehensive monitoring fails to initialize.
    """
    @app.get("/health", tags=["Health"])
    async def basic_health():
        """
        Basic health check endpoint.

        Returns basic application status and uptime.
        """
        import time
        from datetime import datetime

        # Get start time from app state if available
        start_time = getattr(app.state, 'start_time', time.time())
        uptime = time.time() - start_time

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "uptime_seconds": round(uptime, 2),
            "service": "hormonia-backend",
            "version": "1.0.0"
        }

    logger.info("✓ Basic health check endpoint configured")