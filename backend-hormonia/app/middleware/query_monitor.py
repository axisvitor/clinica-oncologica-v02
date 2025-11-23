"""
Query Performance Monitoring Middleware

SQLAlchemy event listeners for tracking query performance, detecting N+1 queries,
and logging slow queries with correlation IDs.

MONITORING FEATURES:
- Query execution time tracking
- Slow query detection (>100ms threshold)
- Query count per request tracking
- N+1 query pattern detection
- Correlation ID logging for request tracing
- Automatic performance warnings
"""

import time
import logging
import uuid
from typing import Any, Dict, Optional
from contextlib import contextmanager
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


@dataclass
class QueryEvent:
    """Single query execution event"""
    statement: str
    parameters: Any
    execution_time_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None


@dataclass
class RequestQueryStats:
    """Query statistics for a single request"""
    correlation_id: str
    total_queries: int = 0
    total_time_ms: float = 0.0
    slow_queries: int = 0
    queries: list = field(default_factory=list)
    n1_detected: bool = False
    duplicate_queries: int = 0


class QueryMonitor:
    """
    Monitor query performance across requests with automatic N+1 detection.

    Features:
    - Track all queries per request
    - Detect slow queries (>100ms)
    - Detect N+1 query patterns
    - Detect duplicate queries
    - Correlation ID tracking
    """

    SLOW_QUERY_THRESHOLD_MS = 100.0
    N1_QUERY_THRESHOLD = 10  # More than 10 queries suggests N+1

    def __init__(self):
        self._request_stats: Dict[str, RequestQueryStats] = {}
        self._query_times: Dict[str, list] = defaultdict(list)
        self._enabled = True

    def start_request(self, correlation_id: str) -> None:
        """Start monitoring queries for a request"""
        if not self._enabled:
            return

        self._request_stats[correlation_id] = RequestQueryStats(
            correlation_id=correlation_id
        )
        logger.debug(f"Started query monitoring for request {correlation_id}")

    def record_query(
        self,
        correlation_id: str,
        statement: str,
        parameters: Any,
        execution_time_ms: float
    ) -> None:
        """Record a query execution"""
        if not self._enabled or correlation_id not in self._request_stats:
            return

        stats = self._request_stats[correlation_id]

        # Create query event
        event = QueryEvent(
            statement=statement,
            parameters=parameters,
            execution_time_ms=execution_time_ms,
            correlation_id=correlation_id
        )

        # Update statistics
        stats.total_queries += 1
        stats.total_time_ms += execution_time_ms
        stats.queries.append(event)

        # Check for slow query
        if execution_time_ms > self.SLOW_QUERY_THRESHOLD_MS:
            stats.slow_queries += 1
            logger.warning(
                f"[{correlation_id}] Slow query detected: {execution_time_ms:.2f}ms - "
                f"{statement[:200]}..."
            )

        # Track query pattern for duplicate detection
        query_signature = self._get_query_signature(statement)
        self._query_times[query_signature].append(execution_time_ms)

        # Detect duplicate queries
        if len(self._query_times[query_signature]) > 1:
            stats.duplicate_queries += 1

    def end_request(self, correlation_id: str) -> Optional[RequestQueryStats]:
        """End monitoring and return statistics"""
        if not self._enabled or correlation_id not in self._request_stats:
            return None

        stats = self._request_stats.pop(correlation_id)

        # Detect N+1 query pattern
        if stats.total_queries > self.N1_QUERY_THRESHOLD:
            stats.n1_detected = True
            logger.warning(
                f"[{correlation_id}] Potential N+1 query pattern detected: "
                f"{stats.total_queries} queries executed in single request. "
                f"Consider using eager loading (joinedload/selectinload)."
            )

        # Log summary
        logger.info(
            f"[{correlation_id}] Request completed: "
            f"{stats.total_queries} queries, "
            f"{stats.total_time_ms:.2f}ms total, "
            f"{stats.slow_queries} slow queries, "
            f"{stats.duplicate_queries} duplicates"
        )

        # Clean up query times for this request
        self._query_times.clear()

        return stats

    def _get_query_signature(self, statement: str) -> str:
        """
        Get normalized query signature for duplicate detection.
        Removes parameter values to identify same query with different params.
        """
        # Simple signature: remove specific values
        # In production, you'd use a more sophisticated normalization
        import re
        normalized = re.sub(r'\b\d+\b', '?', statement)  # Replace numbers
        normalized = re.sub(r"'[^']*'", "'?'", normalized)  # Replace strings
        return normalized[:500]  # Limit length

    def get_stats(self, correlation_id: str) -> Optional[RequestQueryStats]:
        """Get current statistics for a request"""
        return self._request_stats.get(correlation_id)

    def enable(self) -> None:
        """Enable query monitoring"""
        self._enabled = True
        logger.info("Query monitoring enabled")

    def disable(self) -> None:
        """Disable query monitoring"""
        self._enabled = False
        logger.info("Query monitoring disabled")


# Global monitor instance
_global_monitor = QueryMonitor()


def get_query_monitor() -> QueryMonitor:
    """Get global query monitor instance"""
    return _global_monitor


class QueryMonitorMiddleware(BaseHTTPMiddleware):
    """
    Middleware to monitor database queries per HTTP request.

    Automatically:
    - Generates correlation IDs for requests
    - Tracks all queries during request lifecycle
    - Detects slow queries and N+1 patterns
    - Adds query statistics to response headers

    Usage:
        from app.middleware.query_monitor import QueryMonitorMiddleware

        app.add_middleware(QueryMonitorMiddleware)
    """

    async def dispatch(self, request: Request, call_next):
        # Generate correlation ID
        correlation_id = request.headers.get(
            "X-Correlation-ID",
            str(uuid.uuid4())
        )

        # Start monitoring
        _global_monitor.start_request(correlation_id)

        try:
            # Process request
            response = await call_next(request)

            # End monitoring and get stats
            stats = _global_monitor.end_request(correlation_id)

            # Add query statistics to response headers
            if stats:
                response.headers["X-Correlation-ID"] = correlation_id
                response.headers["X-Query-Count"] = str(stats.total_queries)
                response.headers["X-Query-Time-Ms"] = f"{stats.total_time_ms:.2f}"
                response.headers["X-Slow-Queries"] = str(stats.slow_queries)

                if stats.n1_detected:
                    response.headers["X-N1-Detected"] = "true"

                if stats.duplicate_queries > 0:
                    response.headers["X-Duplicate-Queries"] = str(stats.duplicate_queries)

            return response

        except Exception as e:
            # Clean up on error
            _global_monitor.end_request(correlation_id)
            raise


def setup_query_monitoring(engine: Engine) -> None:
    """
    Set up SQLAlchemy event listeners for query monitoring.

    Args:
        engine: SQLAlchemy engine to monitor

    Usage:
        from app.middleware.query_monitor import setup_query_monitoring
        from app.database import engine

        setup_query_monitoring(engine)
    """
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        # Store start time
        conn.info.setdefault('query_start_time', []).append(time.time())

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        # Calculate execution time
        if 'query_start_time' in conn.info and conn.info['query_start_time']:
            start_time = conn.info['query_start_time'].pop()
            execution_time_ms = (time.time() - start_time) * 1000

            # Get correlation ID from context (if available)
            correlation_id = getattr(context, 'correlation_id', None)

            if correlation_id:
                # Record query
                _global_monitor.record_query(
                    correlation_id=correlation_id,
                    statement=statement,
                    parameters=parameters,
                    execution_time_ms=execution_time_ms
                )
            else:
                # Log without correlation ID
                if execution_time_ms > QueryMonitor.SLOW_QUERY_THRESHOLD_MS:
                    logger.warning(
                        f"Slow query (no correlation ID): {execution_time_ms:.2f}ms - "
                        f"{statement[:200]}..."
                    )

    logger.info("Query monitoring event listeners registered")


@contextmanager
def monitor_queries(correlation_id: Optional[str] = None):
    """
    Context manager for monitoring queries in a code block.

    Usage:
        with monitor_queries("my-operation") as stats:
            # Execute queries
            results = db.query(Patient).all()

        logger.info(f"Executed {stats.total_queries} queries in {stats.total_time_ms}ms",
                    extra={"total_queries": stats.total_queries, "total_time_ms": stats.total_time_ms})
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())

    _global_monitor.start_request(correlation_id)

    try:
        yield _global_monitor.get_stats(correlation_id)
    finally:
        _global_monitor.end_request(correlation_id)


def log_query_summary(correlation_id: str) -> None:
    """
    Log a detailed summary of queries for a request.

    Args:
        correlation_id: Request correlation ID
    """
    stats = _global_monitor.get_stats(correlation_id)

    if not stats:
        logger.warning(f"No query statistics found for {correlation_id}")
        return

    # Build detailed log message
    message = [
        f"\n{'=' * 80}",
        f"Query Summary for {correlation_id}",
        f"{'=' * 80}",
        f"Total Queries: {stats.total_queries}",
        f"Total Time: {stats.total_time_ms:.2f}ms",
        f"Slow Queries: {stats.slow_queries}",
        f"Duplicate Queries: {stats.duplicate_queries}",
        f"N+1 Detected: {stats.n1_detected}",
        f"{'-' * 80}"
    ]

    # Add individual query details
    for i, query in enumerate(stats.queries, 1):
        is_slow = query.execution_time_ms > QueryMonitor.SLOW_QUERY_THRESHOLD_MS
        slow_marker = " [SLOW]" if is_slow else ""

        message.append(
            f"Query {i}: {query.execution_time_ms:.2f}ms{slow_marker}\n"
            f"  {query.statement[:200]}..."
        )

    message.append(f"{'=' * 80}\n")

    logger.info('\n'.join(message))


# Convenience functions for external use
def start_monitoring(correlation_id: str) -> None:
    """Start monitoring queries for a correlation ID"""
    _global_monitor.start_request(correlation_id)


def end_monitoring(correlation_id: str) -> Optional[RequestQueryStats]:
    """End monitoring and get statistics"""
    return _global_monitor.end_request(correlation_id)


def get_current_stats(correlation_id: str) -> Optional[RequestQueryStats]:
    """Get current query statistics"""
    return _global_monitor.get_stats(correlation_id)
