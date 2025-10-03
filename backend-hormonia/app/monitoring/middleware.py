"""
Monitoring Middleware and Decorators.

Automatic instrumentation for requests, database queries, and business operations.
"""

import time
import asyncio
import functools
import logging
from typing import Callable, Any, Dict, Optional
from datetime import datetime
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager

from .apm import APMCollector, RequestMetrics
from .database_monitor import DatabasePerformanceMonitor
from .business_metrics import BusinessMetricsCollector, MetricType


logger = logging.getLogger(__name__)


class MonitoringMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for comprehensive monitoring."""

    def __init__(self, app, apm_collector: APMCollector,
                 db_monitor: DatabasePerformanceMonitor,
                 business_metrics: BusinessMetricsCollector):
        super().__init__(app)
        self.apm_collector = apm_collector
        self.db_monitor = db_monitor
        self.business_metrics = business_metrics

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with comprehensive monitoring."""
        start_time = time.time()

        # Generate request ID if not present
        request_id = request.headers.get("X-Request-ID", f"req_{int(time.time() * 1000000)}")

        # Get user ID from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)

        # Initialize tracking
        request.state.monitoring = {
            "start_time": start_time,
            "request_id": request_id,
            "db_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": []
        }

        try:
            # Process request
            response = await call_next(request)

            # Calculate metrics
            end_time = time.time()
            response_time = end_time - start_time

            # Create APM metrics
            metrics = RequestMetrics(
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                response_time=response_time,
                timestamp=datetime.utcnow(),
                user_id=user_id,
                db_queries=request.state.monitoring.get("db_queries", 0),
                cache_hits=request.state.monitoring.get("cache_hits", 0),
                cache_misses=request.state.monitoring.get("cache_misses", 0)
            )

            # Record APM metrics
            await self.apm_collector.record_request(metrics)

            # Add performance headers
            response.headers["X-Response-Time"] = f"{response_time:.3f}"
            response.headers["X-Request-ID"] = request_id

            # Record business metrics for specific endpoints
            await self._record_business_metrics(request, response, response_time)

            return response

        except Exception as e:
            # Record error metrics
            end_time = time.time()
            response_time = end_time - start_time

            error_metrics = RequestMetrics(
                endpoint=request.url.path,
                method=request.method,
                status_code=500,
                response_time=response_time,
                timestamp=datetime.utcnow(),
                user_id=user_id,
                error_type=type(e).__name__,
                db_queries=request.state.monitoring.get("db_queries", 0),
                cache_hits=request.state.monitoring.get("cache_hits", 0),
                cache_misses=request.state.monitoring.get("cache_misses", 0)
            )

            await self.apm_collector.record_request(error_metrics)

            raise

    async def _record_business_metrics(self, request: Request, response: Response,
                                     response_time: float) -> None:
        """Record business metrics based on endpoint patterns."""
        try:
            path = request.url.path
            method = request.method
            status_code = response.status_code

            # Patient flow metrics
            if "/api/v1/flows" in path and method == "POST":
                patient_id = getattr(request.state, "patient_id", None)
                if patient_id:
                    await self.business_metrics.record_patient_flow_start(
                        patient_id, "general"
                    )

            # Message delivery metrics
            if "/api/v1/messages" in path and method == "POST":
                patient_id = getattr(request.state, "patient_id", None)
                if patient_id:
                    success = status_code < 400
                    await self.business_metrics.record_message_sent(
                        patient_id, "general"
                    )

                    if success:
                        await self.business_metrics.record_message_delivered(
                            patient_id, "general", True, response_time
                        )

            # Quiz completion metrics
            if "/api/v1/quiz" in path and "complete" in path and method == "POST":
                patient_id = getattr(request.state, "patient_id", None)
                if patient_id:
                    completed = status_code < 400
                    await self.business_metrics.record_quiz_completion(
                        patient_id, "general", completed, 0.0, response_time / 60
                    )

            # User engagement metrics
            if method == "GET" and status_code < 400:
                user_id = getattr(request.state, "user_id", None)
                if user_id:
                    # Record page view as engagement
                    await self.business_metrics.record_user_session(
                        user_id, response_time / 60, 1, 0
                    )

        except Exception as e:
            logger.error(f"Failed to record business metrics: {e}")


def monitor_database_query(db_monitor: DatabasePerformanceMonitor):
    """Decorator to monitor database queries."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            error = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error = str(e)
                raise
            finally:
                end_time = time.time()
                execution_time = end_time - start_time

                # Extract query information from function name/args
                query_text = f"{func.__name__}({', '.join(str(arg)[:50] for arg in args[:2])})"

                # Record in database monitor
                await db_monitor._record_query_async(
                    statement=query_text,
                    execution_time=execution_time,
                    rows_affected=None
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            error = None

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error = str(e)
                raise
            finally:
                end_time = time.time()
                execution_time = end_time - start_time

                # Extract query information
                query_text = f"{func.__name__}({', '.join(str(arg)[:50] for arg in args[:2])})"

                # Record in database monitor (sync version)
                asyncio.create_task(db_monitor._record_query_async(
                    statement=query_text,
                    execution_time=execution_time,
                    rows_affected=None
                ))

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def monitor_business_operation(business_metrics: BusinessMetricsCollector,
                             metric_type: MetricType):
    """Decorator to monitor business operations."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            success = False

            try:
                result = await func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                success = False
                raise
            finally:
                end_time = time.time()
                duration = end_time - start_time

                # Extract patient/user ID from arguments or kwargs
                patient_id = kwargs.get('patient_id') or (args[0] if args and hasattr(args[0], 'patient_id') else None)
                user_id = kwargs.get('user_id') or (args[0] if args and hasattr(args[0], 'user_id') else None)

                # Record business metric based on type
                if metric_type == MetricType.PATIENT_FLOW:
                    if patient_id:
                        await business_metrics.record_patient_flow_completion(
                            patient_id, func.__name__, success, duration / 60
                        )
                elif metric_type == MetricType.MESSAGE_DELIVERY:
                    if patient_id:
                        await business_metrics.record_message_delivered(
                            patient_id, func.__name__, success, duration
                        )
                elif metric_type == MetricType.AI_RESPONSE:
                    if patient_id:
                        accuracy = 0.8 if success else 0.0  # Default accuracy
                        await business_metrics.record_ai_response(
                            patient_id, func.__name__, accuracy, duration * 1000
                        )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            success = False

            try:
                result = func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                success = False
                raise
            finally:
                end_time = time.time()
                duration = end_time - start_time

                # Extract patient/user ID
                patient_id = kwargs.get('patient_id') or (args[0] if args and hasattr(args[0], 'patient_id') else None)
                user_id = kwargs.get('user_id') or (args[0] if args and hasattr(args[0], 'user_id') else None)

                # Record business metric asynchronously
                if metric_type == MetricType.PATIENT_FLOW and patient_id:
                    asyncio.create_task(business_metrics.record_patient_flow_completion(
                        patient_id, func.__name__, success, duration / 60
                    ))
                elif metric_type == MetricType.MESSAGE_DELIVERY and patient_id:
                    asyncio.create_task(business_metrics.record_message_delivered(
                        patient_id, func.__name__, success, duration
                    ))
                elif metric_type == MetricType.AI_RESPONSE and patient_id:
                    accuracy = 0.8 if success else 0.0
                    asyncio.create_task(business_metrics.record_ai_response(
                        patient_id, func.__name__, accuracy, duration * 1000
                    ))

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


@asynccontextmanager
async def monitor_operation(operation_name: str, business_metrics: BusinessMetricsCollector,
                           metric_type: MetricType, patient_id: Optional[str] = None,
                           user_id: Optional[str] = None):
    """Context manager for monitoring operations."""
    start_time = time.time()
    success = False
    error = None

    try:
        yield
        success = True
    except Exception as e:
        success = False
        error = str(e)
        raise
    finally:
        end_time = time.time()
        duration = end_time - start_time

        # Record appropriate business metric
        try:
            if metric_type == MetricType.PATIENT_FLOW and patient_id:
                await business_metrics.record_patient_flow_completion(
                    patient_id, operation_name, success, duration / 60
                )
            elif metric_type == MetricType.MESSAGE_DELIVERY and patient_id:
                await business_metrics.record_message_delivered(
                    patient_id, operation_name, success, duration
                )
            elif metric_type == MetricType.AI_RESPONSE and patient_id:
                accuracy = 0.8 if success else 0.0
                await business_metrics.record_ai_response(
                    patient_id, operation_name, accuracy, duration * 1000
                )
            elif metric_type == MetricType.USER_ENGAGEMENT and user_id:
                await business_metrics.record_user_session(
                    user_id, duration / 60, 1, 1 if success else 0
                )
        except Exception as e:
            logger.error(f"Failed to record operation metric: {e}")


class DatabaseQueryTracker:
    """Track database queries in request context."""

    def __init__(self, request: Request):
        self.request = request

    def increment_query_count(self):
        """Increment database query count for current request."""
        if hasattr(self.request.state, 'monitoring'):
            self.request.state.monitoring['db_queries'] += 1

    def increment_cache_hit(self):
        """Increment cache hit count for current request."""
        if hasattr(self.request.state, 'monitoring'):
            self.request.state.monitoring['cache_hits'] += 1

    def increment_cache_miss(self):
        """Increment cache miss count for current request."""
        if hasattr(self.request.state, 'monitoring'):
            self.request.state.monitoring['cache_misses'] += 1

    def add_error(self, error: str):
        """Add error to current request tracking."""
        if hasattr(self.request.state, 'monitoring'):
            self.request.state.monitoring['errors'].append(error)


def get_query_tracker(request: Request) -> DatabaseQueryTracker:
    """Get database query tracker for current request."""
    return DatabaseQueryTracker(request)


# Convenience decorators for common operations
def monitor_patient_flow(business_metrics: BusinessMetricsCollector):
    """Decorator for patient flow operations."""
    return monitor_business_operation(business_metrics, MetricType.PATIENT_FLOW)


def monitor_message_delivery(business_metrics: BusinessMetricsCollector):
    """Decorator for message delivery operations."""
    return monitor_business_operation(business_metrics, MetricType.MESSAGE_DELIVERY)


def monitor_ai_response(business_metrics: BusinessMetricsCollector):
    """Decorator for AI response operations."""
    return monitor_business_operation(business_metrics, MetricType.AI_RESPONSE)


def monitor_quiz_completion(business_metrics: BusinessMetricsCollector):
    """Decorator for quiz completion operations."""
    return monitor_business_operation(business_metrics, MetricType.QUIZ_COMPLETION)


def monitor_alert_resolution(business_metrics: BusinessMetricsCollector):
    """Decorator for alert resolution operations."""
    return monitor_business_operation(business_metrics, MetricType.ALERT_RESOLUTION)