"""
Application lifespan management.

Handles application startup and shutdown processes including:
- Logging setup
- Monitoring system initialization
- Redis connection for WebSocket events
- Question humanization integration
- Graceful cleanup on shutdown
"""

import time
import ssl
from pathlib import Path
import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.utils.logging import setup_logging, get_logger
from app.utils.security import mask_sensitive_url
from app.services.query_caching import init_cache_system

# Path to Redis CA certificate for SSL/TLS connections
REDIS_CA_CERT_PATH = Path(__file__).parent.parent / "certs" / "redis_ca.pem"


def _create_redis_ssl_context() -> ssl.SSLContext:
    """Create SSL context for Redis Cloud connection.

    Respects REDIS_SSL_CERT_REQS setting:
    - "none": No certificate verification (common for Redis Cloud free tier)
    - "required": Full certificate verification with CA cert
    """
    ssl_cert_reqs = getattr(settings, "REDIS_SSL_CERT_REQS", "required").lower()

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

    if ssl_cert_reqs == "none":
        # No certificate verification
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    # Full certificate verification
    if REDIS_CA_CERT_PATH.exists():
        ssl_context.load_verify_locations(cafile=str(REDIS_CA_CERT_PATH))
    else:
        ssl_context.load_default_certs()

    ssl_context.check_hostname = True
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    return ssl_context


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    from app.services.websocket_events import WebSocketEventService
    from app.monitoring.manager import (
        initialize_monitoring,
        start_monitoring,
        stop_monitoring,
    )
    from app.services.quiz_question_humanizer_integration import (
        integrate_humanization_into_quiz_service,
    )

    # Setup logging first
    setup_logging()
    logger = get_logger(__name__)

    # Startup
    app.state.start_time = time.time()
    logger.info(
        "Starting Hormonia Backend System", extra={"event_type": "application_startup"}
    )

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

        # Connection kwargs
        connection_kwargs = {
            "decode_responses": True,
            "socket_connect_timeout": 3,
            "socket_timeout": 3,
            "retry_on_timeout": True,
            "max_connections": 50,
            "health_check_interval": 30,
        }

        # Configure SSL if enabled
        if settings.REDIS_ENABLE_SSL:
            if redis_url.startswith("redis://"):
                redis_url = "rediss://" + redis_url[8:]

            # Detect redis-py version for correct SSL parameter
            redis_version = tuple(int(x) for x in redis.__version__.split(".")[:2])
            ssl_cert_reqs = getattr(settings, "REDIS_SSL_CERT_REQS", "required").lower()

            if redis_version >= (6, 0):
                # redis-py 6.x: use ssl_context parameter
                connection_kwargs["ssl_context"] = _create_redis_ssl_context()
            else:
                # redis-py 5.x: use ssl_cert_reqs parameter
                if ssl_cert_reqs == "none":
                    connection_kwargs["ssl_cert_reqs"] = "none"
                else:
                    connection_kwargs["ssl_cert_reqs"] = "required"

            logger.info(f"Redis connection using SSL (redis-py {redis.__version__})")

        redis_client = redis.from_url(redis_url, **connection_kwargs)
        # Test connection
        await redis_client.ping()

        # Initialize websocket_events service
        import sys

        ws_events_module = sys.modules.get("app.services.websocket_events")
        if ws_events_module:
            ws_events_module.websocket_events = WebSocketEventService(redis_client)

        # Store Redis client in app state for cleanup
        app.state.redis_client = redis_client

        masked_url = mask_sensitive_url(redis_url)
        logger.info(
            f"WebSocket events service initialized successfully with Redis at {masked_url}"
        )

    except redis.ConnectionError as e:
        logger.error(f"Redis connection failed: {e}")
        logger.warning(
            "Continuing without WebSocket events service - real-time features will be unavailable"
        )
        _cleanup_websocket_events()

    except redis.TimeoutError as e:
        logger.error(f"Redis connection timeout: {e}")
        logger.warning("Redis connection timeout - continuing without WebSocket events")
        _cleanup_websocket_events()

    except redis.AuthenticationError as e:
        logger.error(f"Redis authentication failed: {e}")
        logger.warning(
            "Redis authentication failed - continuing without WebSocket events"
        )
        _cleanup_websocket_events()

    except Exception as e:
        logger.error(f"Unexpected error initializing WebSocket events service: {e}")
        logger.warning(
            "Continuing without WebSocket events service - some real-time features may be unavailable"
        )
        # Cleanup partial Redis connection if it exists
        if redis_client:
            try:
                # Note: redis.close() is not async and returns None/bool
                redis_client.close()
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up Redis connection: {cleanup_error}")

        _cleanup_websocket_events()

    # Initialize Redis-backed query caching and invalidation
    try:
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
        logger.warning(
            "Continuing without scheduled jobs - audit cleanup will not run automatically"
        )

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
        if hasattr(app.state, "monitoring_manager") and app.state.monitoring_manager:
            logger.info("Stopping monitoring system...")
            await stop_monitoring()
            logger.info("Monitoring system stopped successfully")

        # Close Redis connection if it exists (redis 5.x async clients use aclose)
        if hasattr(app.state, "redis_client") and app.state.redis_client:
            try:
                await app.state.redis_client.aclose()
                logger.info("Redis connection closed successfully")
            except Exception as redis_close_error:
                logger.error(f"Error closing Redis connection: {redis_close_error}")

        # Also check websocket_events service
        try:
            import app.services.websocket_events as ws_events_module

            if (
                ws_events_module
                and hasattr(ws_events_module, "websocket_events")
                and ws_events_module.websocket_events
            ):
                if (
                    hasattr(ws_events_module.websocket_events, "redis")
                    and ws_events_module.websocket_events.redis
                ):
                    try:
                        # redis 5.x async clients use aclose()
                        await ws_events_module.websocket_events.redis.aclose()
                        logger.info("WebSocket events Redis connection closed")
                    except Exception as ws_error:
                        logger.error(
                            f"Error closing WebSocket events Redis connection: {ws_error}"
                        )
        except ImportError as import_error:
            logger.warning(
                f"Could not import websocket_events module during cleanup: {import_error}"
            )
        except Exception as cleanup_error:
            logger.error(f"Error during websocket_events cleanup: {cleanup_error}")

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

    logger.info(
        "Shutting down Hormonia Backend System",
        extra={"event_type": "application_shutdown"},
    )


def _cleanup_websocket_events():
    """Helper function to clean up websocket_events service."""
    try:
        import sys

        ws_events_module = sys.modules.get("app.services.websocket_events")
        if ws_events_module:
            ws_events_module.websocket_events = None
    except ImportError as import_error:
        logger = get_logger(__name__)
        logger.warning(f"Could not import websocket_events module: {import_error}")
    except Exception as error:
        logger = get_logger(__name__)
        logger.error(f"Error setting websocket_events to None: {error}")
