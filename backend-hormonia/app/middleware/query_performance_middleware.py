"""
Query Performance Monitoring Middleware.
Integrates query performance monitoring with FastAPI requests.
"""
import logging
import time
from typing import Callable, Optional
from contextlib import asynccontextmanager

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.query_performance_monitor import QueryPerformanceMonitor
from app.core.monitoring_logging import monitoring_logger


logger = logging.getLogger(__name__)


class QueryPerformanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware to monitor query performance for API requests.
    
    Features:
    - Tracks query performance per endpoint
    - Logs slow endpoints
    - Provides performance metrics
    """
    
    SLOW_ENDPOINT_THRESHOLD_MS = 1000
    
    def __init__(self, app, enabled: bool = True):
        """Initialize query performance middleware."""
        super().__init__(app)
        self.enabled = enabled
        self._monitors: dict[str, QueryPerformanceMonitor] = {}
        
        logger.info(f"Query Performance Middleware initialized (enabled: {enabled})")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with query performance monitoring."""
        if not self.enabled:
            return await call_next(request)
        
        # Skip monitoring for non-API endpoints
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        
        start_time = time.time()
        endpoint = f"{request.method} {request.url.path}"
        
        try:
            # Get database session for monitoring
            db_gen = get_db()
            db = next(db_gen)
            
            # Create or get monitor for this request
            monitor = QueryPerformanceMonitor(db)
            
            # Monitor the request
            with monitor.monitor_query(f"endpoint:{endpoint}"):
                response = await call_next(request)
            
            # Calculate total request time
            duration_ms = (time.time() - start_time) * 1000
            
            # Log slow endpoints
            if duration_ms > self.SLOW_ENDPOINT_THRESHOLD_MS:
                monitoring_logger.log_system_event(
                    event_type="slow_endpoint_detected",
                    message=f"Slow endpoint detected: {endpoint} - {duration_ms:.2f}ms",
                    level="WARNING",
                    context={
                        "endpoint": endpoint,
                        "duration_ms": duration_ms,
                        "status_code": response.status_code
                    }
                )
                
                logger.warning(
                    f"Slow endpoint: {endpoint} - {duration_ms:.2f}ms"
                )
            
            # Add performance headers
            response.headers["X-Query-Performance-Ms"] = str(round(duration_ms, 2))
            
            # Get query metrics
            metrics = monitor.get_performance_metrics()
            if metrics.slow_queries > 0:
                response.headers["X-Slow-Queries-Count"] = str(metrics.slow_queries)
            
            return response
            
        except Exception as e:
            logger.error(f"Error in query performance middleware: {e}")
            # Continue with request even if monitoring fails
            return await call_next(request)
        finally:
            # Clean up database session
            try:
                db_gen.close()
            except Exception:
                pass  # Ignore cleanup errors (generator already exhausted)


@asynccontextmanager
async def query_performance_context(db: Session, operation_name: str):
    """
    Async context manager for monitoring query performance.
    
    Args:
        db: Database session
        operation_name: Name of the operation being monitored
    """
    monitor = QueryPerformanceMonitor(db)
    
    try:
        with monitor.monitor_query(operation_name):
            yield monitor
    except Exception as e:
        logger.error(f"Error in query performance context: {e}")
        raise


def get_query_performance_monitor(db: Session) -> QueryPerformanceMonitor:
    """
    Get a QueryPerformanceMonitor instance for the given database session.
    
    Args:
        db: Database session
        
    Returns:
        QueryPerformanceMonitor instance
    """
    return QueryPerformanceMonitor(db)