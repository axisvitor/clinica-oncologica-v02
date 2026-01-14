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
import asyncio
import os
import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.utils.logging import setup_logging, get_logger
from app.utils.security import mask_sensitive_url
from app.core.redis_manager import get_redis_manager, cleanup_redis_connections
from app.core.session_manager import initialize_session_manager
from app.utils.structured_logger import (
    configure_logging as configure_structured_logging,
)


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
    Handle application startup procedures with parallel initialization.

    Optimizations:
    - Phase 1: Independent services in parallel (monitoring, Redis, AI, validation)
    - Phase 2: Dependent services (WebSocket, Pub/Sub, sessions, follow-up)
    - Target: <15s startup time (down from 56s)

    Args:
        app: FastAPI application instance

    Returns:
        logger: Logger instance for use during shutdown
    """
    # Setup logging first (must be synchronous)
    setup_logging()
    logger = get_logger(__name__)

    # Configure structured logging with JSON output
    log_level = "DEBUG" if settings.APP_ENABLE_DEBUG else "INFO"
    configure_structured_logging(log_level=log_level)
    logger.info("Structured logging configured", extra={"log_level": log_level})

    # Record startup time
    app.state.start_time = time.time()
    logger.info(
        "Starting Hormonia Backend System (parallel initialization)",
        extra={"event_type": "application_startup"}
    )

    try:
        if _is_test_environment():
            logger.info(
                "Test environment detected - skipping external service initialization"
            )
            app.state.redis_client = None
            app.state.redis_manager = None
            app.state.websocket_manager = None
            app.state.pubsub_manager = None
            app.state.follow_up_service = None
            app.state.monitoring_manager = None
            await _initialize_enum_validation(app, logger)
            await _initialize_session_manager(app, logger)
            return logger

        # PHASE 1: Parallel initialization of independent services
        # These services have no dependencies on each other
        logger.info("Phase 1: Initializing independent services in parallel...")
        phase1_start = time.time()

        await asyncio.gather(
            _initialize_monitoring(app, logger),
            _initialize_redis_websocket_events(app, logger),
            _initialize_ai_services(app, logger),
            _initialize_enum_validation(app, logger),
            _initialize_evolution_api(app, logger),
            return_exceptions=True  # Don't fail entire startup on single service failure
        )

        phase1_time = time.time() - phase1_start
        logger.info(f"Phase 1 completed in {phase1_time:.2f}s")

        # PHASE 2: Initialize services that depend on Phase 1
        # These need Redis client and other Phase 1 services
        logger.info("Phase 2: Initializing dependent services...")
        phase2_start = time.time()

        # WebSocket manager can run in parallel with session manager
        await asyncio.gather(
            _initialize_websocket_manager(app, logger),
            _initialize_session_manager(app, logger),
            return_exceptions=True
        )

        # Redis Pub/Sub needs WebSocket manager, so it runs after
        await _initialize_redis_pubsub(app, logger)

        # Follow-up system needs both database and Redis
        await _initialize_follow_up_system(app, logger)

        phase2_time = time.time() - phase2_start
        logger.info(f"Phase 2 completed in {phase2_time:.2f}s")

        total_time = time.time() - app.state.start_time
        logger.info(
            f"Hormonia Backend System startup completed successfully in {total_time:.2f}s",
            extra={
                "total_time": total_time,
                "phase1_time": phase1_time,
                "phase2_time": phase2_time
            }
        )

    except Exception as e:
        logger.error(f"Critical error during startup: {e}", exc_info=True)
        raise

    return logger


def _is_test_environment() -> bool:
    return bool(
        os.getenv("PYTEST_CURRENT_TEST")
        or os.getenv("TESTING") == "1"
        or settings.APP_ENVIRONMENT.lower() in ("test", "testing")
    )


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

    logger.info(
        "Hormonia Backend System shutdown completed",
        extra={"event_type": "application_shutdown"},
    )


async def _initialize_monitoring(app: FastAPI, logger) -> None:
    """Initialize monitoring system with timing."""
    start = time.time()
    try:
        from app.monitoring.manager import initialize_monitoring, start_monitoring

        logger.info("Monitoring: Starting initialization...")
        monitoring_manager = await initialize_monitoring()
        await start_monitoring()
        app.state.monitoring_manager = monitoring_manager

        elapsed = time.time() - start
        logger.info(f"✓ Monitoring system started successfully ({elapsed:.2f}s)")

    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"Failed to initialize monitoring system ({elapsed:.2f}s): {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        app.state.monitoring_manager = None


async def _initialize_websocket_manager(app: FastAPI, logger) -> None:
    """Initialize unified WebSocket manager with lifecycle and timing."""
    start = time.time()
    try:
        from app.services.websocket import get_websocket_manager

        logger.info("Initializing unified WebSocket connection manager...")

        # Get WebSocket manager instance
        ws_manager = get_websocket_manager()

        # Start background tasks (heartbeat, cleanup)
        await ws_manager.start()

        # Store in app state for access during shutdown
        app.state.websocket_manager = ws_manager

        elapsed = time.time() - start
        logger.info(f"✓ Unified WebSocket manager started successfully ({elapsed:.2f}s)")
        logger.info("  - Heartbeat monitoring: active")
        logger.info("  - Automatic cleanup: enabled")
        logger.info("  - Firebase + JWT authentication: ready")

    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"Failed to initialize WebSocket manager ({elapsed:.2f}s): {e}")
        logger.warning("WebSocket features may be degraded")
        app.state.websocket_manager = None


async def _initialize_redis_websocket_events(app: FastAPI, logger) -> None:
    """Initialize Redis connection and WebSocket events service with timing."""
    from app.core.initialization_helpers import initialize_with_timeout

    start = time.time()
    redis_client = None

    try:
        # Get Redis manager with fast-fail timeout (2s instead of 5s)
        redis_client = await initialize_with_timeout(
            func=lambda: get_redis_manager().get_async_client(),
            timeout=2.0,  # Reduced from implicit 5s to fast-fail 2s
            service_name="Redis",
            logger=logger,
            fallback=None,
            critical=False  # Continue without Redis if it fails
        )

        if redis_client is None:
            logger.warning("Redis initialization returned None - continuing without WebSocket events")
            app.state.redis_client = None
            app.state.redis_manager = None
            return

        # Initialize websocket_events service
        await _setup_websocket_events(redis_client, logger)

        # Store both the client and manager in app state
        app.state.redis_client = redis_client
        app.state.redis_manager = get_redis_manager()

        redis_url = settings.REDIS_URL
        masked_url = mask_sensitive_url(redis_url)
        elapsed = time.time() - start
        logger.info(
            f"✓ WebSocket events service initialized with Redis at {masked_url} ({elapsed:.2f}s)"
        )

    except redis.ConnectionError as e:
        elapsed = time.time() - start
        logger.error(f"Redis connection failed ({elapsed:.2f}s): {e}")
        logger.warning(
            "Continuing without WebSocket events - real-time features unavailable"
        )
        await _cleanup_redis_client(redis_client, logger)

    except redis.TimeoutError as e:
        elapsed = time.time() - start
        logger.error(f"Redis connection timeout ({elapsed:.2f}s): {e}")
        logger.warning("Redis timeout - continuing without WebSocket events")
        await _cleanup_redis_client(redis_client, logger)

    except redis.AuthenticationError as e:
        elapsed = time.time() - start
        logger.error(f"Redis authentication failed ({elapsed:.2f}s): {e}")
        logger.warning("Redis auth failed - continuing without WebSocket events")
        await _cleanup_redis_client(redis_client, logger)

    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"Unexpected error initializing WebSocket events ({elapsed:.2f}s): {e}")
        logger.warning("Continuing without WebSocket events")
        await _cleanup_redis_client(redis_client, logger)


async def _setup_websocket_events(redis_client, logger) -> None:
    """Setup WebSocket events service with Redis client."""
    try:
        from app.services.websocket_events import WebSocketEventService
        import sys

        ws_events_module = sys.modules.get("app.services.websocket_events")
        if ws_events_module:
            ws_events_module.websocket_events = WebSocketEventService(redis_client)
            logger.info("✓ WebSocket events service configured")

    except ImportError as e:
        logger.warning(f"WebSocket events service not available: {e}")
    except Exception as e:
        logger.error(f"Failed to setup WebSocket events service: {e}")


async def _initialize_session_manager(app: FastAPI, logger) -> None:
    """Initialize thread-safe session manager with timing."""
    start = time.time()
    logger.info("Initializing thread-safe session manager...")

    try:
        # Get Redis client from app state (if available)
        redis_client = getattr(app.state, "redis_client", None)
        redis_status = "available" if redis_client else "not available"
        logger.info(f"Redis client for session manager: {redis_status}")

        # Initialize session manager with Redis client
        session_manager = initialize_session_manager(redis_client)
        app.state.session_manager = session_manager

        # Validate session manager was properly initialized
        if not session_manager:
            raise RuntimeError("Session manager initialization returned None")

        elapsed = time.time() - start
        logger.info(
            f"✓ Thread-safe session manager initialized with proper lifecycle management ({elapsed:.2f}s)"
        )
        logger.info(
            f"Session manager instance: {type(session_manager).__name__} (id: {hex(id(session_manager))})"
        )

        # Log session manager health info
        from app.core.session_manager import get_session_health_info

        health_info = get_session_health_info()
        logger.info(f"Session manager health status: {health_info}")

        # Log session manager capabilities
        capabilities = []
        if hasattr(session_manager, "redis_client") and session_manager.redis_client:
            capabilities.append("Redis integration")
        if hasattr(session_manager, "get_session"):
            capabilities.append("Context-scoped sessions")
        if hasattr(session_manager, "get_service_provider"):
            capabilities.append("ServiceProvider factory")

        logger.info(
            f"Session manager capabilities: {', '.join(capabilities) if capabilities else 'Basic session management'}"
        )

    except Exception as e:
        logger.error(f"Failed to initialize session manager: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error("This will cause database session management issues")
        logger.error("Ensure database is accessible and Redis is properly configured")

        # Note: Database connectivity test removed to avoid blocking during startup
        # Use health check endpoint /health/database instead for connectivity testing

        # Log environment information that might help debug
        import os

        db_url = os.getenv("DATABASE_URL", "NOT SET")
        redis_url = os.getenv("REDIS_URL", "NOT SET")
        logger.error(
            f"DATABASE_URL configured: {'Yes' if db_url != 'NOT SET' else 'No'}"
        )
        logger.error(
            f"REDIS_URL configured: {'Yes' if redis_url != 'NOT SET' else 'No'}"
        )

        # Don't raise exception here - allow app to start in degraded mode
        logger.error(
            "Session manager initialization failed - app will start in degraded mode"
        )
        app.state.session_manager = None


async def _initialize_redis_pubsub(app: FastAPI, logger) -> None:
    """Initialize Redis Pub/Sub for horizontal WebSocket scaling with timing."""
    start = time.time()
    try:
        from app.services.redis_pubsub_manager import (
            RedisPubSubManager,
            set_pubsub_manager,
        )
        from app.services.websocket import get_websocket_manager
        import uuid

        # Get Redis client from app state
        redis_client = getattr(app.state, "redis_client", None)

        if not redis_client:
            elapsed = time.time() - start
            logger.warning(f"Redis client not available - Redis Pub/Sub disabled ({elapsed:.2f}s)")
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
            instance_id=instance_id,
        )

        # Start pub/sub listener
        await pubsub_manager.start()

        # Store in app state and set global
        app.state.pubsub_manager = pubsub_manager
        set_pubsub_manager(pubsub_manager)

        elapsed = time.time() - start
        logger.info(f"✓ Redis Pub/Sub initialized (instance: {instance_id}) ({elapsed:.2f}s)")
        logger.info("✓ WebSocket horizontal scaling enabled")

    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"Failed to initialize Redis Pub/Sub ({elapsed:.2f}s): {e}")
        logger.warning("Continuing without Redis Pub/Sub - single instance mode only")
        app.state.pubsub_manager = None


async def _initialize_ai_services(app: FastAPI, logger) -> None:
    """Initialize AI services and integrations with timing."""
    start = time.time()
    try:
        from app.services.quiz_question_humanizer_integration import (
            integrate_humanization_into_quiz_service,
        )

        integrate_humanization_into_quiz_service()
        elapsed = time.time() - start
        logger.info(f"✓ AI question humanization integration initialized ({elapsed:.2f}s)")

    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"Failed to initialize AI services ({elapsed:.2f}s): {e}")
        logger.info("Continuing without AI humanization features")


async def _initialize_enum_validation(app: FastAPI, logger) -> None:
    """Initialize enum validation middleware with timing."""
    start = time.time()
    try:
        from app.middleware.enum_validation import setup_enum_validation

        setup_enum_validation()
        elapsed = time.time() - start
        logger.info(f"✓ Enum validation middleware initialized ({elapsed:.2f}s)")

    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"Failed to initialize enum validation ({elapsed:.2f}s): {e}")
        logger.warning(
            "Continuing without enum validation - database enum errors may occur"
        )


async def _initialize_evolution_api(app: FastAPI, logger) -> None:
    """Bootstrap Evolution API instance/webhook configuration with timing."""
    start = time.time()

    if not settings.WHATSAPP_ENABLE_SERVICE:
        logger.info("Evolution API disabled - skipping bootstrap")
        return

    webhook_url = settings.WHATSAPP_EVOLUTION_WEBHOOK_URL
    api_key = settings.WHATSAPP_EVOLUTION_API_KEY

    if not webhook_url or not api_key:
        logger.warning("Evolution API not configured - skipping bootstrap")
        return

    if "change_this" in api_key.lower() or "your-evolution-api-key" in api_key.lower():
        logger.warning("Evolution API key placeholder detected - skipping bootstrap")
        return

    client = None
    instance_name = settings.WHATSAPP_EVOLUTION_INSTANCE_NAME

    try:
        from app.integrations.whatsapp.services.evolution_client import (
            EvolutionAPIClient,
            DEFAULT_WEBHOOK_EVENTS,
        )

        client = EvolutionAPIClient(
            base_url=settings.WHATSAPP_EVOLUTION_API_URL,
            api_key=api_key,
            global_webhook_url=webhook_url,
        )
        await client.connect()

        instance_ready = False
        try:
            status = await client.get_instance_status(instance_name)
            instance_ready = True
            logger.info(
                "Evolution instance status",
                extra={
                    "instance_name": instance_name,
                    "status": status.status,
                    "is_connected": status.is_connected,
                },
            )
        except Exception as status_error:
            logger.warning(
                "Evolution instance status check failed; attempting create",
                extra={"instance_name": instance_name, "error": str(status_error)},
            )
            try:
                await client.create_instance(
                    instance_name=instance_name,
                    webhook_url=webhook_url,
                    webhook_events=DEFAULT_WEBHOOK_EVENTS,
                )
                instance_ready = True
                logger.info(
                    "Evolution instance created",
                    extra={"instance_name": instance_name},
                )
            except Exception as create_error:
                logger.error(
                    "Evolution instance create failed",
                    extra={"instance_name": instance_name, "error": str(create_error)},
                )

        if instance_ready:
            webhook_ok = await client.set_webhook_url(
                instance_name=instance_name,
                webhook_url=webhook_url,
                events=DEFAULT_WEBHOOK_EVENTS,
            )
            if webhook_ok:
                logger.info(
                    "Evolution webhook configured",
                    extra={"instance_name": instance_name, "webhook_url": webhook_url},
                )
            else:
                logger.warning(
                    "Evolution webhook configuration failed",
                    extra={"instance_name": instance_name, "webhook_url": webhook_url},
                )

        elapsed = time.time() - start
        logger.info(f"✓ Evolution API bootstrap completed ({elapsed:.2f}s)")

    except Exception as e:
        elapsed = time.time() - start
        logger.warning(f"Evolution API bootstrap failed ({elapsed:.2f}s): {e}")
    finally:
        if client:
            try:
                await client.disconnect()
            except Exception:
                logger.debug("Evolution client disconnect failed (non-critical)")


async def _initialize_follow_up_system(app: FastAPI, logger) -> None:
    """Initialize follow-up system with Redis state rehydration and timing."""
    start = time.time()
    try:
        from app.services.follow_up_system.service import FollowUpSystemService
        from app.database import SessionLocal

        logger.info("Initializing follow-up system...")

        db = SessionLocal()
        try:
            follow_up_service = FollowUpSystemService(db)
            result = await follow_up_service.rehydrate_from_redis()
            app.state.follow_up_service = follow_up_service

            elapsed = time.time() - start
            logger.info(
                f"✓ Follow-up system rehydrated: "
                f"{result['pending_actions']} actions, "
                f"{result['active_alerts']} alerts ({elapsed:.2f}s)"
            )
        finally:
            db.close()

    except Exception as e:
        elapsed = time.time() - start
        logger.warning(f"Follow-up system initialization failed ({elapsed:.2f}s): {e}")
        logger.info(
            "Continuing without follow-up system - will initialize on first use"
        )
        app.state.follow_up_service = None


async def _cleanup_session_manager(app: FastAPI, logger) -> None:
    """Cleanup session manager and database connections."""
    logger.info("Cleaning up session manager...")

    try:
        # Cleanup session manager if it exists
        if hasattr(app.state, "session_manager"):
            session_manager = app.state.session_manager
            session_manager_id = hex(id(session_manager)) if session_manager else "None"
            logger.info(f"Cleaning up session manager instance: {session_manager_id}")

            try:
                from app.core.session_manager import (
                    cleanup_request_context,
                    get_session_health_info,
                )

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
        if hasattr(app.state, "monitoring_manager") and app.state.monitoring_manager:
            from app.monitoring.manager import stop_monitoring

            logger.info("Stopping monitoring system...")
            await stop_monitoring()
            logger.info("✓ Monitoring system stopped")

    except Exception as e:
        logger.error(f"Error stopping monitoring system: {e}")


async def _cleanup_websocket_manager(app: FastAPI, logger) -> None:
    """Cleanup unified WebSocket manager."""
    try:
        if hasattr(app.state, "websocket_manager") and app.state.websocket_manager:
            logger.info("Stopping unified WebSocket manager...")
            ws_manager = app.state.websocket_manager

            # Graceful shutdown - stop background tasks
            await ws_manager.stop()

            # Disconnect all active connections
            active_count = len(ws_manager.connections)
            if active_count > 0:
                logger.info(
                    f"Disconnecting {active_count} active WebSocket connections..."
                )
                for connection_id in list(ws_manager.connections.keys()):
                    await ws_manager.disconnect(connection_id, reason="Server shutdown")

            app.state.websocket_manager = None
            logger.info("✓ Unified WebSocket manager stopped gracefully")

    except Exception as e:
        logger.error(f"Error stopping WebSocket manager: {e}")


async def _cleanup_redis_pubsub(app: FastAPI, logger) -> None:
    """Cleanup Redis Pub/Sub manager."""
    try:
        if hasattr(app.state, "pubsub_manager") and app.state.pubsub_manager:
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

        if (
            ws_events_module
            and hasattr(ws_events_module, "websocket_events")
            and ws_events_module.websocket_events
            and hasattr(ws_events_module.websocket_events, "redis")
            and ws_events_module.websocket_events.redis
        ):
            await ws_events_module.websocket_events.redis.aclose()
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
            await redis_client.aclose()
        except Exception as e:
            logger.error(f"Error closing Redis client: {e}")

    # Reset websocket_events service
    try:
        import sys

        ws_events_module = sys.modules.get("app.services.websocket_events")
        if ws_events_module:
            ws_events_module.websocket_events = None
    except Exception as e:
        logger.error(f"Error resetting websocket_events: {e}")
