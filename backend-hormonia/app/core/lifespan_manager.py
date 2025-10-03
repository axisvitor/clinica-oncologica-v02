"""
Application lifespan management.

Handles application startup and shutdown processes including:
- Logging setup
- Monitoring system initialization
- Redis connection for WebSocket events
- ServiceProvider initialization
- Question humanization integration
- Graceful cleanup on shutdown
"""
import time
import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.database import get_db
from app.utils.logging import setup_logging, get_logger
from app.utils.security import mask_sensitive_url


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    from app.services.websocket_events import websocket_events, WebSocketEventService
    from app.monitoring.manager import initialize_monitoring, start_monitoring, stop_monitoring
    from app.services.quiz_question_humanizer_integration import integrate_humanization_into_quiz_service
    from app.services import ServiceProvider

    # Setup logging first
    setup_logging()
    logger = get_logger(__name__)

    # Startup
    app.state.start_time = time.time()
    logger.info("Starting Hormonia Backend System", extra={'event_type': 'application_startup'})

    # Initialize monitoring system
    try:
        logger.info("Initializing monitoring system...")
        monitoring_manager = await initialize_monitoring()
        await start_monitoring()
        app.state.monitoring_manager = monitoring_manager
        logger.info("Monitoring system started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize monitoring system: {e}")
        app.state.monitoring_manager = None
    
    # Initialize Redis connection for websocket events
    redis_client = None
    try:
        # Get Redis URL from settings (Redis Cloud)
        redis_url = settings.REDIS_URL

        redis_client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=3, # Reduced timeout
            socket_timeout=3,
            retry_on_timeout=True,
            max_connections=50, # Increased connection pool
            health_check_interval=30 # Moved from connection_pool_kwargs
        )
        # Test connection
        await redis_client.ping()

        # Initialize websocket_events service
        import sys
        ws_events_module = sys.modules.get('app.services.websocket_events')
        if ws_events_module:
            ws_events_module.websocket_events = WebSocketEventService(redis_client)

        # Store Redis client in app state for cleanup
        app.state.redis_client = redis_client

        masked_url = mask_sensitive_url(redis_url)
        logger.info(f"WebSocket events service initialized successfully with Redis at {masked_url}")

    except redis.ConnectionError as e:
        logger.error(f"Redis connection failed: {e}")
        logger.warning("Continuing without WebSocket events service - real-time features will be unavailable")
        _cleanup_websocket_events()

    except redis.TimeoutError as e:
        logger.error(f"Redis connection timeout: {e}")
        logger.warning("Redis connection timeout - continuing without WebSocket events")
        _cleanup_websocket_events()

    except redis.AuthenticationError as e:
        logger.error(f"Redis authentication failed: {e}")
        logger.warning("Redis authentication failed - continuing without WebSocket events")
        _cleanup_websocket_events()

    except Exception as e:
        logger.error(f"Unexpected error initializing WebSocket events service: {e}")
        logger.warning("Continuing without WebSocket events service - some real-time features may be unavailable")
        # Cleanup partial Redis connection if it exists
        if redis_client:
            try:
                # Note: redis.close() is not async and returns None/bool
                redis_client.close()
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up Redis connection: {cleanup_error}")

        _cleanup_websocket_events()

    # Initialize ServiceProvider
    db_session = next(get_db())
    app.state.service_provider = ServiceProvider(db_session, redis_client)

    # Initialize Redis-backed query caching and invalidation
    try:
        from app.services.cache import init_cache_system
        init_cache_system()
        logger.info("Redis query caching system initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize cache system: {e}")
        logger.warning("Continuing without query caching - database load may be higher")

    # Initialize question humanization integration
    try:
        integrate_humanization_into_quiz_service()
        logger.info("Question humanization integration initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize question humanization: {e}")
        # Non-critical, continue without humanization

    # Start background job scheduler
    try:
        from app.jobs.scheduler import start_scheduler
        start_scheduler()
        logger.info("Background job scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start job scheduler: {e}")
        logger.warning("Continuing without scheduled jobs - audit cleanup will not run automatically")

    yield
    
    # Shutdown
    try:
        # Stop background job scheduler
        try:
            from app.jobs.scheduler import stop_scheduler
            stop_scheduler()
            logger.info("Background job scheduler stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping job scheduler: {e}")

        # Stop monitoring system
        if hasattr(app.state, 'monitoring_manager') and app.state.monitoring_manager:
            logger.info("Stopping monitoring system...")
            await stop_monitoring()
            logger.info("Monitoring system stopped successfully")

        # Close Redis connection if it exists
        if hasattr(app.state, 'redis_client') and app.state.redis_client:
            try:
                # Note: redis.close() is not async and returns None/bool
                app.state.redis_client.close()
                logger.info("Redis connection closed successfully")
            except Exception as redis_close_error:
                logger.error(f"Error closing Redis connection: {redis_close_error}")

        # Also check websocket_events service
        try:
            import app.services.websocket_events as ws_events_module
            if ws_events_module and hasattr(ws_events_module, 'websocket_events') and ws_events_module.websocket_events:
                if hasattr(ws_events_module.websocket_events, 'redis') and ws_events_module.websocket_events.redis:
                    try:
                        # Note: redis.close() is not async and returns None/bool
                        ws_events_module.websocket_events.redis.close()
                        logger.info("WebSocket events Redis connection closed")
                    except Exception as ws_error:
                        logger.error(f"Error closing WebSocket events Redis connection: {ws_error}")
        except ImportError as import_error:
            logger.warning(f"Could not import websocket_events module during cleanup: {import_error}")
        except Exception as cleanup_error:
            logger.error(f"Error during websocket_events cleanup: {cleanup_error}")

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

    logger.info("Shutting down Hormonia Backend System", extra={'event_type': 'application_shutdown'})


def _cleanup_websocket_events():
    """Helper function to clean up websocket_events service."""
    try:
        import sys
        ws_events_module = sys.modules.get('app.services.websocket_events')
        if ws_events_module:
            ws_events_module.websocket_events = None
    except ImportError as import_error:
        logger = get_logger(__name__)
        logger.warning(f"Could not import websocket_events module: {import_error}")
    except Exception as error:
        logger = get_logger(__name__)
        logger.error(f"Error setting websocket_events to None: {error}")
