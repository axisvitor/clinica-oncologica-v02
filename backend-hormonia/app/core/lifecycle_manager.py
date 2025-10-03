"""Application Lifecycle Manager - Extracted from main.py complexity"""
import time
import logging
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as redis
from fastapi import FastAPI

from app.config import settings
from app.utils.logging import setup_logging, get_logger
from app.database import get_db, test_connection
from app.services import ServiceProvider
from app.core.session_manager import initialize_session_manager

logger = get_logger(__name__)

class ApplicationLifecycleManager:
    """Manages application startup/shutdown lifecycle (extracted from main.py)"""
    
    def __init__(self):
        self.redis_client = None
        self.monitoring_manager = None
        self.service_provider = None
    
    def get_lifespan(self):
        """Get lifespan context manager for FastAPI"""
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            await self._startup(app)
            yield
            # Shutdown  
            await self._shutdown(app)
        
        return lifespan
    
    async def _startup(self, app: FastAPI):
        """Application startup sequence (extracted from complex main.py)"""
        app.state.start_time = time.time()
        setup_logging()
        logger.info("Starting Hormonia Backend System", extra={'event_type': 'application_startup'})
        
        # Initialize components in order
        await self._initialize_monitoring(app)
        await self._initialize_redis(app)
        await self._initialize_services(app)
        await self._initialize_integrations(app)
    
    async def _initialize_monitoring(self, app: FastAPI):
        """Initialize monitoring system"""
        try:
            from app.monitoring.manager import initialize_monitoring, start_monitoring
            
            logger.info("Initializing monitoring system...")
            self.monitoring_manager = await initialize_monitoring()
            await start_monitoring()
            app.state.monitoring_manager = self.monitoring_manager
            logger.info("Monitoring system started successfully")
        except Exception as e:
            logger.error(f"Failed to initialize monitoring: {e}")
            app.state.monitoring_manager = None
    
    async def _initialize_redis(self, app: FastAPI):
        """Initialize Redis connection with error handling"""
        try:
            redis_url = settings.REDIS_URL
            
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
                retry_on_timeout=True,
                max_connections=50,
                health_check_interval=30
            )
            
            # Test connection
            await self.redis_client.ping()
            
            # Initialize websocket events service
            self._initialize_websocket_events()
            
            app.state.redis_client = self.redis_client
            logger.info("Redis connection established successfully")
            
        except Exception as e:
            logger.error(f"Redis initialization failed: {e}")
            logger.warning("Continuing without Redis - real-time features will be unavailable")
            self._cleanup_failed_redis()
    
    def _initialize_websocket_events(self):
        """Initialize WebSocket events service"""
        try:
            from app.services.websocket_events import websocket_events, WebSocketEventService
            import sys
            
            ws_events_module = sys.modules.get('app.services.websocket_events')
            if ws_events_module:
                ws_events_module.websocket_events = WebSocketEventService(self.redis_client)
                logger.info("WebSocket events service initialized")
        except Exception as e:
            logger.error(f"WebSocket events initialization failed: {e}")
    
    def _cleanup_failed_redis(self):
        """Cleanup failed Redis connection"""
        if self.redis_client:
            try:
                self.redis_client.close()
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up Redis: {cleanup_error}")
        
        # Set websocket_events to None
        try:
            import app.services.websocket_events as ws_events_module
            if ws_events_module and hasattr(ws_events_module, 'websocket_events'):
                ws_events_module.websocket_events = None
        except Exception as error:
            logger.error(f"Error setting websocket_events to None: {error}")
    
    async def _initialize_services(self, app: FastAPI):
        """Initialize thread-safe session management and ServiceProvider"""
        try:
            # Test database connection first
            db_test = test_connection()
            if db_test["status"] != "healthy":
                logger.error(f"Database unhealthy: {db_test.get('error', 'Unknown error')}")
                raise RuntimeError("Database connection failed health check")

            logger.info("Database connection verified")

            # Initialize thread-safe session manager
            session_manager = initialize_session_manager(self.redis_client)
            app.state.session_manager = session_manager
            logger.info("Thread-safe session manager initialized")

            # Keep legacy service provider for backward compatibility during migration
            # This will be removed in a future release
            try:
                db_session = next(get_db())
                self.service_provider = ServiceProvider(db_session, self.redis_client)
                app.state.service_provider = self.service_provider
                logger.info("Legacy ServiceProvider initialized for backward compatibility")
            except Exception as legacy_error:
                logger.warning(f"Legacy ServiceProvider initialization failed: {legacy_error}")
                logger.info("Continuing with thread-safe session management only")

        except Exception as e:
            logger.error(f"Services initialization failed: {e}")
            # Don't raise the exception - allow app to start with partial functionality
            logger.warning("Application starting with reduced functionality")
    
    async def _initialize_integrations(self, app: FastAPI):
        """Initialize additional integrations"""
        try:
            # Initialize question humanization integration
            from app.services.quiz_question_humanizer_integration import integrate_humanization_into_quiz_service
            integrate_humanization_into_quiz_service()
            logger.info("Question humanization integration initialized")
        except Exception as e:
            logger.error(f"Question humanization initialization failed: {e}")
    
    async def _shutdown(self, app: FastAPI):
        """Application shutdown sequence"""
        try:
            # Stop monitoring
            await self._shutdown_monitoring(app)

            # Cleanup session management
            await self._shutdown_session_manager(app)

            # Close Redis connections
            await self._shutdown_redis(app)

            logger.info("Shutting down Hormonia Backend System", extra={'event_type': 'application_shutdown'})

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    async def _shutdown_session_manager(self, app: FastAPI):
        """Cleanup session manager and database connections"""
        try:
            # Close legacy service provider session if it exists
            if hasattr(app.state, 'service_provider') and app.state.service_provider:
                if hasattr(app.state.service_provider, 'db') and app.state.service_provider.db:
                    try:
                        app.state.service_provider.db.close()
                        logger.info("Legacy ServiceProvider database session closed")
                    except Exception as db_error:
                        logger.error(f"Error closing legacy database session: {db_error}")

            # Cleanup session manager if it exists
            if hasattr(app.state, 'session_manager'):
                try:
                    from app.core.session_manager import cleanup_request_context
                    cleanup_request_context()
                    logger.info("Session manager cleaned up")
                except Exception as session_error:
                    logger.error(f"Error cleaning up session manager: {session_error}")

        except Exception as e:
            logger.error(f"Session manager shutdown error: {e}")
    
    async def _shutdown_monitoring(self, app: FastAPI):
        """Shutdown monitoring system"""
        try:
            if hasattr(app.state, 'monitoring_manager') and app.state.monitoring_manager:
                from app.monitoring.manager import stop_monitoring
                logger.info("Stopping monitoring system...")
                await stop_monitoring()
                logger.info("Monitoring system stopped")
        except Exception as e:
            logger.error(f"Monitoring shutdown error: {e}")
    
    async def _shutdown_redis(self, app: FastAPI):
        """Shutdown Redis connections"""
        try:
            # Close main Redis connection
            if hasattr(app.state, 'redis_client') and app.state.redis_client:
                app.state.redis_client.close()
                logger.info("Redis connection closed")
            
            # Close WebSocket events Redis connection
            try:
                import app.services.websocket_events as ws_events_module
                if (ws_events_module and hasattr(ws_events_module, 'websocket_events') 
                    and ws_events_module.websocket_events):
                    if hasattr(ws_events_module.websocket_events, 'redis'):
                        ws_events_module.websocket_events.redis.close()
                        logger.info("WebSocket events Redis connection closed")
            except Exception as ws_error:
                logger.error(f"WebSocket Redis cleanup error: {ws_error}")
                
        except Exception as e:
            logger.error(f"Redis shutdown error: {e}")
