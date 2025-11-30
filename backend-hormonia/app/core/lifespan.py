"""
Application lifespan management.

Provides a clean lifespan context manager that handles:
- Application startup procedures
- Service initialization
- Resource allocation
- Graceful shutdown procedures
- Resource cleanup
"""
import time
import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.database import get_db
from app.utils.logging import setup_logging, get_logger
from app.utils.security import mask_sensitive_url
from app.core.redis_manager import get_redis_manager, cleanup_redis_connections
from app.core.session_manager import initialize_session_manager
from app.utils.structured_logger import configure_logging as configure_structured_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager with clean startup and shutdown procedures.

    Handles:
    - Logging setup
    - Monitoring system initialization
    - Redis connection for WebSocket events
    - ServiceProvider initialization
    - AI service integration
    - Graceful cleanup on shutdown

    Args:
        app: FastAPI application instance

    Yields:
        None: Application runs between startup and shutdown
    """
    logger = await _startup(app)
    try:
        yield
    finally:
        await _shutdown(app, logger)


async def _startup(app: FastAPI) -> object:
    """
    Handle application startup procedures.

    Args:
        app: FastAPI application instance

    Returns:
        logger: Logger instance for use during shutdown
    """
    # Setup logging first
    setup_logging()
    logger = get_logger(__name__)

    # Configure structured logging with JSON output
    log_level = 'DEBUG' if settings.APP_ENABLE_DEBUG else 'INFO'
    configure_structured_logging(log_level=log_level)
    logger.info("Structured logging configured", extra={'log_level': log_level})

    # Record startup time
    app.state.start_time = time.time()
    logger.info("Starting Hormonia Backend System", extra={'event_type': 'application_startup'})

    # Initialize monitoring system
    await _initialize_monitoring(app, logger)

    # Initialize Redis and WebSocket events
    await _initialize_redis_websocket_events(app, logger)

    # Initialize unified WebSocket manager with lifecycle
    await _initialize_websocket_manager(app, logger)

    # Initialize Redis Pub/Sub for horizontal WebSocket scaling
    await _initialize_redis_pubsub(app, logger)

    # Initialize thread-safe session management
    await _initialize_session_manager(app, logger)

    # Initialize AI services
    await _initialize_ai_services(app, logger)

    # Initialize enum validation middleware
    await _initialize_enum_validation(app, logger)

    logger.info("Hormonia Backend System startup completed successfully")
    return logger


async def _shutdown(app: FastAPI, logger) -> None:
    """
    Handle application shutdown procedures.

    Args:
        app: FastAPI application instance
        logger: Logger instance from startup
    """
    logger.info("Initiating Hormonia Backend System shutdown...")

    try:
        # Stop monitoring system
        await _cleanup_monitoring(app, logger)

        # Stop WebSocket manager
        await _cleanup_websocket_manager(app, logger)

        # Stop Redis Pub/Sub
        await _cleanup_redis_pubsub(app, logger)

        # Cleanup session manager
        await _cleanup_session_manager(app, logger)

        # Close Redis connections
        await _cleanup_redis_connections(app, logger)

        # Cleanup other resources
        await _cleanup_other_resources(app, logger)

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

    logger.info("Hormonia Backend System shutdown completed", extra={'event_type': 'application_shutdown'})


async def _initialize_monitoring(app: FastAPI, logger) -> None:
    """Initialize monitoring system."""
    try:
        from app.monitoring.manager import initialize_monitoring, start_monitoring

        logger.info("Initializing monitoring system...")
        monitoring_manager = await initialize_monitoring()
        await start_monitoring()
        app.state.monitoring_manager = monitoring_manager
        logger.info("✓ Monitoring system started successfully")

    except Exception as e:
        logger.error(f"Failed to initialize monitoring system: {e}")
        app.state.monitoring_manager = None


async def _initialize_websocket_manager(app: FastAPI, logger) -> None:
    """Initialize unified WebSocket manager with lifecycle."""
    try:
        from app.services.websocket import get_websocket_manager

        logger.info("Initializing unified WebSocket connection manager...")

        # Get WebSocket manager instance
        ws_manager = get_websocket_manager()

        # Start background tasks (heartbeat, cleanup)
        await ws_manager.start()

        # Store in app state for access during shutdown
        app.state.websocket_manager = ws_manager

        logger.info("✓ Unified WebSocket manager started successfully")
        logger.info("  - Heartbeat monitoring: active")
        logger.info("  - Automatic cleanup: enabled")
        logger.info("  - Firebase + JWT authentication: ready")

    except Exception as e:
        logger.error(f"Failed to initialize WebSocket manager: {e}")
        logger.warning("WebSocket features may be degraded")
        app.state.websocket_manager = None


async def _initialize_redis_websocket_events(app: FastAPI, logger) -> None:
    """Initialize Redis connection and WebSocket events service."""
    redis_client = None

    try:
        # Get Redis manager
        redis_manager = get_redis_manager()

        # Get async Redis client through manager
        redis_client = await redis_manager.get_async_client()

        # Initialize websocket_events service
        await _setup_websocket_events(redis_client, logger)

        # Store both the client and manager in app state
        app.state.redis_client = redis_client
        app.state.redis_manager = redis_manager

        redis_url = settings.REDIS_URL
        masked_url = mask_sensitive_url(redis_url)
        logger.info(f"✓ WebSocket events service initialized with Redis at {masked_url}")

    except redis.ConnectionError as e:
        logger.error(f"Redis connection failed: {e}")
        logger.warning("Continuing without WebSocket events - real-time features unavailable")
        await _cleanup_redis_client(redis_client, logger)

    except redis.TimeoutError as e:
        logger.error(f"Redis connection timeout: {e}")
        logger.warning("Redis timeout - continuing without WebSocket events")
        await _cleanup_redis_client(redis_client, logger)

    except redis.AuthenticationError as e:
        logger.error(f"Redis authentication failed: {e}")
        logger.warning("Redis auth failed - continuing without WebSocket events")
        await _cleanup_redis_client(redis_client, logger)

    except Exception as e:
        logger.error(f"Unexpected error initializing WebSocket events: {e}")
        logger.warning("Continuing without WebSocket events")
        await _cleanup_redis_client(redis_client, logger)


async def _setup_websocket_events(redis_client, logger) -> None:
    """Setup WebSocket events service with Redis client."""
    try:
        from app.services.websocket_events import WebSocketEventService
        import sys

        ws_events_module = sys.modules.get('app.services.websocket_events')
        if ws_events_module:
            ws_events_module.websocket_events = WebSocketEventService(redis_client)
            logger.info("✓ WebSocket events service configured")

    except ImportError as e:
        logger.warning(f"WebSocket events service not available: {e}")
    except Exception as e:
        logger.error(f"Failed to setup WebSocket events service: {e}")


async def _initialize_session_manager(app: FastAPI, logger) -> None:
    """Initialize thread-safe session manager."""
    logger.info("Initializing thread-safe session manager...")

    try:
        # Get Redis client from app state (if available)
        redis_client = getattr(app.state, 'redis_client', None)
        redis_status = "available" if redis_client else "not available"
        logger.info(f"Redis client for session manager: {redis_status}")

        # Initialize session manager with Redis client
        session_manager = initialize_session_manager(redis_client)
        app.state.session_manager = session_manager

        # Validate session manager was properly initialized
        if not session_manager:
            raise RuntimeError("Session manager initialization returned None")

        logger.info("✓ Thread-safe session manager initialized with proper lifecycle management")
        logger.info(f"Session manager instance: {type(session_manager).__name__} (id: {hex(id(session_manager))})")

        # Log session manager health info
        from app.core.session_manager import get_session_health_info
        health_info = get_session_health_info()
        logger.info(f"Session manager health status: {health_info}")

        # Log session manager capabilities
        capabilities = []
        if hasattr(session_manager, 'redis_client') and session_manager.redis_client:
            capabilities.append("Redis integration")
        if hasattr(session_manager, 'get_session'):
            capabilities.append("Context-scoped sessions")
        if hasattr(session_manager, 'get_service_provider'):
            capabilities.append("ServiceProvider factory")

        logger.info(f"Session manager capabilities: {', '.join(capabilities) if capabilities else 'Basic session management'}")

    except Exception as e:
        logger.error(f"Failed to initialize session manager: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error("This will cause database session management issues")
        logger.error("Ensure database is accessible and Redis is properly configured")

        # Log more details for debugging
        try:
            from app.database import SessionLocal, test_connection
            logger.info("Testing database connectivity...")
            db_status = test_connection()
            logger.info(f"Database connectivity test result: {db_status}")
        except Exception as db_error:
            logger.error(f"Database connectivity test failed: {db_error}")
            logger.error(f"Database error type: {type(db_error).__name__}")

        # Log environment information that might help debug
        import os
        db_url = os.getenv('DATABASE_URL', 'NOT SET')
        redis_url = os.getenv('REDIS_URL', 'NOT SET')
        logger.error(f"DATABASE_URL configured: {'Yes' if db_url != 'NOT SET' else 'No'}")
        logger.error(f"REDIS_URL configured: {'Yes' if redis_url != 'NOT SET' else 'No'}")

        # Don't raise exception here - allow app to start in degraded mode
        logger.error("Session manager initialization failed - app will start in degraded mode")
        app.state.session_manager = None


async def _initialize_redis_pubsub(app: FastAPI, logger) -> None:
    """Initialize Redis Pub/Sub for horizontal WebSocket scaling."""
    try:
        from app.services.redis_pubsub_manager import RedisPubSubManager, set_pubsub_manager
        from app.services.websocket import get_websocket_manager
        import uuid

        # Get Redis client from app state
        redis_client = getattr(app.state, 'redis_client', None)

        if not redis_client:
            logger.warning("Redis client not available - Redis Pub/Sub disabled")
            logger.warning("WebSocket scaling will be limited to single instance")
            app.state.pubsub_manager = None
            return

        # Get unified WebSocket manager instance
        ws_manager = get_websocket_manager()

        # Generate unique instance ID for this server
        instance_id = f"fastapi_{uuid.uuid4().hex[:8]}"

        # Create pub/sub manager
        pubsub_manager = RedisPubSubManager(
            redis_client=redis_client,
            connection_manager=ws_manager,
            instance_id=instance_id
        )

        # Start pub/sub listener
        await pubsub_manager.start()

        # Store in app state and set global
        app.state.pubsub_manager = pubsub_manager
        set_pubsub_manager(pubsub_manager)

        logger.info(f"✓ Redis Pub/Sub initialized (instance: {instance_id})")
        logger.info("✓ WebSocket horizontal scaling enabled")

    except Exception as e:
        logger.error(f"Failed to initialize Redis Pub/Sub: {e}")
        logger.warning("Continuing without Redis Pub/Sub - single instance mode only")
        app.state.pubsub_manager = None


async def _initialize_ai_services(app: FastAPI, logger) -> None:
    """Initialize AI services and integrations."""
    try:
        from app.services.quiz_question_humanizer_integration import integrate_humanization_into_quiz_service

        integrate_humanization_into_quiz_service()
        logger.info("✓ AI question humanization integration initialized")

    except Exception as e:
        logger.error(f"Failed to initialize AI services: {e}")
        logger.info("Continuing without AI humanization features")


async def _initialize_enum_validation(app: FastAPI, logger) -> None:
    """Initialize enum validation middleware."""
    try:
        from app.middleware.enum_validation import setup_enum_validation

        setup_enum_validation()
        logger.info("✓ Enum validation middleware initialized")

    except Exception as e:
        logger.error(f"Failed to initialize enum validation: {e}")
        logger.warning("Continuing without enum validation - database enum errors may occur")


async def _cleanup_session_manager(app: FastAPI, logger) -> None:
    """Cleanup session manager and database connections."""
    logger.info("Cleaning up session manager...")

    try:
        # Cleanup session manager if it exists
        if hasattr(app.state, 'session_manager'):
            session_manager = app.state.session_manager
            session_manager_id = hex(id(session_manager)) if session_manager else "None"
            logger.info(f"Cleaning up session manager instance: {session_manager_id}")

            try:
                from app.core.session_manager import cleanup_request_context, get_session_health_info

                # Get health status before cleanup
                health_before = get_session_health_info()
                logger.debug(f"Session health before cleanup: {health_before}")

                # Perform cleanup
                cleanup_request_context()
                logger.info("✓ Session manager request context cleaned up")

                # Get health status after cleanup
                health_after = get_session_health_info()
                logger.debug(f"Session health after cleanup: {health_after}")

                # Clear from app state
                app.state.session_manager = None
                logger.info("✓ Session manager removed from app state")

            except Exception as session_error:
                logger.error(f"Error cleaning up session manager: {session_error}")
        else:
            logger.info("No session manager found in app state (already cleaned up)")

    except Exception as e:
        logger.error(f"Session manager cleanup error: {e}")
        logger.error("Some database connections may not have been properly closed")


async def _cleanup_monitoring(app: FastAPI, logger) -> None:
    """Cleanup monitoring system."""
    try:
        if hasattr(app.state, 'monitoring_manager') and app.state.monitoring_manager:
            from app.monitoring.manager import stop_monitoring

            logger.info("Stopping monitoring system...")
            await stop_monitoring()
            logger.info("✓ Monitoring system stopped")

    except Exception as e:
        logger.error(f"Error stopping monitoring system: {e}")


async def _cleanup_websocket_manager(app: FastAPI, logger) -> None:
    """Cleanup unified WebSocket manager."""
    try:
        if hasattr(app.state, 'websocket_manager') and app.state.websocket_manager:
            logger.info("Stopping unified WebSocket manager...")
            ws_manager = app.state.websocket_manager

            # Graceful shutdown - stop background tasks
            await ws_manager.stop()

            # Disconnect all active connections
            active_count = len(ws_manager.connections)
            if active_count > 0:
                logger.info(f"Disconnecting {active_count} active WebSocket connections...")
                for connection_id in list(ws_manager.connections.keys()):
                    await ws_manager.disconnect(connection_id, reason="Server shutdown")

            app.state.websocket_manager = None
            logger.info("✓ Unified WebSocket manager stopped gracefully")

    except Exception as e:
        logger.error(f"Error stopping WebSocket manager: {e}")


async def _cleanup_redis_pubsub(app: FastAPI, logger) -> None:
    """Cleanup Redis Pub/Sub manager."""
    try:
        if hasattr(app.state, 'pubsub_manager') and app.state.pubsub_manager:
            logger.info("Stopping Redis Pub/Sub manager...")
            await app.state.pubsub_manager.stop()
            app.state.pubsub_manager = None
            logger.info("✓ Redis Pub/Sub manager stopped")

    except Exception as e:
        logger.error(f"Error stopping Redis Pub/Sub manager: {e}")


async def _cleanup_redis_connections(app: FastAPI, logger) -> None:
    """Cleanup Redis connections."""
    try:
        # Close WebSocket events Redis connection first
        await _cleanup_websocket_events_redis(logger)

        # Use Redis manager for proper cleanup
        await cleanup_redis_connections()
        logger.info("✓ All Redis connections closed via manager")

    except Exception as e:
        logger.error(f"Error closing Redis connections: {e}")


async def _cleanup_websocket_events_redis(logger) -> None:
    """Cleanup WebSocket events Redis connection."""
    try:
        import app.services.websocket_events as ws_events_module

        if (ws_events_module and
            hasattr(ws_events_module, 'websocket_events') and
            ws_events_module.websocket_events and
            hasattr(ws_events_module.websocket_events, 'redis') and
            ws_events_module.websocket_events.redis):

            ws_events_module.websocket_events.redis.close()
            logger.info("✓ WebSocket events Redis connection closed")

    except ImportError:
        logger.debug("WebSocket events module not available during cleanup")
    except Exception as e:
        logger.error(f"Error closing WebSocket events Redis connection: {e}")


async def _cleanup_other_resources(app: FastAPI, logger) -> None:
    """Cleanup other application resources."""
    try:
        # Add cleanup for other resources as needed
        # This is where you'd add cleanup for additional services
        pass

    except Exception as e:
        logger.error(f"Error cleaning up other resources: {e}")


async def _cleanup_redis_client(redis_client, logger) -> None:
    """Helper to cleanup a Redis client safely."""
    if redis_client:
        try:
            redis_client.close()
        except Exception as e:
            logger.error(f"Error closing Redis client: {e}")

    # Reset websocket_events service
    try:
        import sys
        ws_events_module = sys.modules.get('app.services.websocket_events')
        if ws_events_module:
            ws_events_module.websocket_events = None
    except Exception as e:
        logger.error(f"Error resetting websocket_events: {e}")