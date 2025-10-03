"""
Query performance logging middleware.

Tracks database queries per request and identifies slow endpoints.
Correlates slow queries with API endpoints for performance optimization.

Features:
- Tracks all queries per request with request_id correlation
- Logs slow queries (>1s) with endpoint information
- Detects N+1 query patterns (>50 queries per request)
- Warns on high database time (>50% of total request time)
- Provides endpoint-level performance statistics
- Includes performance metrics in response headers
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time
import logging
import uuid
from typing import List, Dict, Any, Optional
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)

# Thread-local storage for query tracking
_query_storage = threading.local()


class QueryPerformanceTracker:
    """
    Tracks query performance metrics over time.
    Thread-safe tracker for monitoring and alerting.
    """

    def __init__(self):
        self._endpoint_stats: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    def record_request(self, method: str, path: str, query_count: int, db_time: float, total_time: float):
        """
        Record request statistics.

        Args:
            method: HTTP method
            path: Request path
            query_count: Number of queries executed
            db_time: Total database time in seconds
            total_time: Total request time in seconds
        """
        key = f"{method} {path}"

        with self._lock:
            if key not in self._endpoint_stats:
                self._endpoint_stats[key] = {
                    'total_requests': 0,
                    'total_queries': 0,
                    'total_db_time': 0.0,
                    'total_time': 0.0,
                    'slow_requests': 0,
                    'n1_requests': 0,
                    'high_db_time_requests': 0
                }

            stats = self._endpoint_stats[key]
            stats['total_requests'] += 1
            stats['total_queries'] += query_count
            stats['total_db_time'] += db_time
            stats['total_time'] += total_time

            if total_time > 1.0:
                stats['slow_requests'] += 1

            if query_count > 50:
                stats['n1_requests'] += 1

            # Check if DB time is >50% of total time
            if db_time > 0 and total_time > 0 and (db_time / total_time) > 0.5:
                stats['high_db_time_requests'] += 1

    def get_slowest_endpoints(self, limit: int = 10) -> List[Dict]:
        """
        Get endpoints with highest average DB time.

        Args:
            limit: Maximum number of endpoints to return

        Returns:
            List of endpoint statistics sorted by average DB time
        """
        results = []

        with self._lock:
            for endpoint, stats in self._endpoint_stats.items():
                if stats['total_requests'] == 0:
                    continue

                avg_db_time = stats['total_db_time'] / stats['total_requests']
                avg_queries = stats['total_queries'] / stats['total_requests']
                avg_total_time = stats['total_time'] / stats['total_requests']

                results.append({
                    'endpoint': endpoint,
                    'avg_db_time': round(avg_db_time, 3),
                    'avg_total_time': round(avg_total_time, 3),
                    'avg_queries': round(avg_queries, 1),
                    'total_requests': stats['total_requests'],
                    'slow_requests': stats['slow_requests'],
                    'n1_requests': stats['n1_requests'],
                    'high_db_time_requests': stats['high_db_time_requests'],
                    'slow_request_rate': round(stats['slow_requests'] / stats['total_requests'], 3),
                    'n1_pattern_rate': round(stats['n1_requests'] / stats['total_requests'], 3)
                })

        # Sort by average DB time
        results.sort(key=lambda x: x['avg_db_time'], reverse=True)
        return results[:limit]

    def get_stats(self) -> Dict:
        """
        Get overall statistics.

        Returns:
            Dictionary with aggregated performance metrics
        """
        with self._lock:
            total_requests = sum(s['total_requests'] for s in self._endpoint_stats.values())
            total_queries = sum(s['total_queries'] for s in self._endpoint_stats.values())
            total_slow = sum(s['slow_requests'] for s in self._endpoint_stats.values())
            total_n1 = sum(s['n1_requests'] for s in self._endpoint_stats.values())
            total_high_db = sum(s['high_db_time_requests'] for s in self._endpoint_stats.values())

            return {
                'total_requests': total_requests,
                'total_queries': total_queries,
                'avg_queries_per_request': round(total_queries / total_requests, 2) if total_requests > 0 else 0,
                'slow_request_rate': round(total_slow / total_requests, 3) if total_requests > 0 else 0,
                'n1_pattern_rate': round(total_n1 / total_requests, 3) if total_requests > 0 else 0,
                'high_db_time_rate': round(total_high_db / total_requests, 3) if total_requests > 0 else 0,
                'tracked_endpoints': len(self._endpoint_stats)
            }

    def reset_stats(self):
        """Reset all statistics."""
        with self._lock:
            self._endpoint_stats.clear()


# Global tracker instance
_performance_tracker = QueryPerformanceTracker()


def get_performance_tracker() -> QueryPerformanceTracker:
    """Get global performance tracker."""
    return _performance_tracker


class QueryPerformanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware to correlate API requests with database queries.

    Features:
    - Tracks all queries per request with request_id
    - Identifies slow queries and correlates them to endpoints
    - Detects N+1 query patterns
    - Warns on high database time percentage
    - Provides query timing information in headers
    - Tracks endpoint-level performance over time
    """

    def __init__(self, app, slow_request_threshold: float = 1.0, slow_query_threshold: float = 1.0):
        """
        Initialize query performance middleware.

        Args:
            app: FastAPI application
            slow_request_threshold: Request duration threshold in seconds (default: 1.0)
            slow_query_threshold: Query duration threshold in seconds (default: 1.0)
        """
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold
        self.slow_query_threshold = slow_query_threshold
        self.tracker = get_performance_tracker()
        self.setup_query_logging()
        logger.info(f"Query performance middleware initialized (request: {slow_request_threshold}s, query: {slow_query_threshold}s)")

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request and track associated queries.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint in chain

        Returns:
            HTTP response with enhanced query performance headers
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Initialize query storage for this request
        _query_storage.queries = []
        _query_storage.request_id = request_id

        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)

            # Calculate timings
            total_time = time.time() - start_time
            queries = getattr(_query_storage, 'queries', [])
            query_count = len(queries)
            db_time = sum(q['duration'] for q in queries)

            # Add enhanced performance headers
            response.headers['X-Request-ID'] = request_id
            response.headers['X-Query-Count'] = str(query_count)
            response.headers['X-DB-Time-Ms'] = str(int(db_time * 1000))
            response.headers['X-Request-Duration'] = f"{total_time:.3f}s"

            # Record stats for this endpoint
            self.tracker.record_request(
                method=request.method,
                path=request.url.path,
                query_count=query_count,
                db_time=db_time,
                total_time=total_time
            )

            # Log comprehensive request summary
            db_percentage = (db_time / total_time * 100) if total_time > 0 else 0
            logger.info(
                f"REQUEST | {request.method} {request.url.path} | "
                f"Status: {response.status_code} | "
                f"Total: {total_time:.3f}s | "
                f"DB: {db_time:.3f}s ({db_percentage:.1f}%) | "
                f"Queries: {query_count} | "
                f"Request ID: {request_id}"
            )

            # Detect N+1 patterns (>50 queries)
            if query_count > 50:
                logger.error(
                    f"POSSIBLE N+1 PATTERN | "
                    f"{request.method} {request.url.path} | "
                    f"{query_count} queries | "
                    f"Request ID: {request_id}"
                )

            # Warn if DB time is >50% of total time
            if db_time > 0 and (db_time / total_time) > 0.5:
                logger.warning(
                    f"HIGH DB TIME | "
                    f"{request.method} {request.url.path} | "
                    f"DB: {db_time:.3f}s / Total: {total_time:.3f}s ({db_percentage:.1f}%) | "
                    f"Request ID: {request_id}"
                )

            # Log slow requests with their queries
            if total_time > self.slow_request_threshold:
                self._log_slow_request(request, total_time, queries, db_time)

            # Log individual slow queries with endpoint context
            slow_queries = [q for q in queries if q['duration'] > self.slow_query_threshold]
            if slow_queries:
                self._log_slow_queries(request_id, request.method, request.url.path, slow_queries)

            return response

        except Exception as e:
            logger.error(
                f"REQUEST ERROR | {request.method} {request.url.path} | "
                f"Error: {str(e)} | "
                f"Request ID: {request_id}"
            )
            raise
        finally:
            # Cleanup thread-local storage
            if hasattr(_query_storage, 'queries'):
                delattr(_query_storage, 'queries')
            if hasattr(_query_storage, 'request_id'):
                delattr(_query_storage, 'request_id')

    def _log_slow_request(self, request: Request, duration: float, queries: List[Dict[str, Any]], db_time: float):
        """
        Log details of slow requests.

        Args:
            request: HTTP request object
            duration: Total request duration
            queries: List of executed queries
            db_time: Total database time
        """
        query_summary = defaultdict(int)

        for query in queries:
            # Extract query type (SELECT, INSERT, UPDATE, etc.)
            query_type = query['statement'].strip().split()[0].upper()
            query_summary[query_type] += 1

        db_percentage = (db_time / duration * 100) if duration > 0 else 0

        logger.warning(
            f"SLOW REQUEST | {request.method} {request.url.path} | "
            f"Duration: {duration:.2f}s | "
            f"Queries: {len(queries)} | "
            f"DB Time: {db_time:.2f}s ({db_percentage:.1f}%) | "
            f"Query Types: {dict(query_summary)}",
            extra={
                "request_id": request.state.request_id,
                "method": request.method,
                "path": request.url.path,
                "duration": duration,
                "query_count": len(queries),
                "total_query_time": db_time,
                "db_percentage": db_percentage,
                "query_summary": dict(query_summary),
                "queries": queries[:10]  # Log first 10 queries
            }
        )

    def _log_slow_queries(self, request_id: str, method: str, path: str, slow_queries: List[Dict[str, Any]]):
        """
        Log details of slow individual queries with endpoint context.

        Args:
            request_id: Unique request identifier
            method: HTTP method
            path: Request path
            slow_queries: List of slow queries
        """
        for query in slow_queries:
            logger.warning(
                f"SLOW QUERY ({query['duration']:.3f}s) | "
                f"Endpoint: {method} {path} | "
                f"Request ID: {request_id} | "
                f"Query: {query['statement'][:200]}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "duration": query['duration'],
                    "statement": query['statement'],
                    "parameters": query.get('parameters')
                }
            )

    def setup_query_logging(self):
        """Setup SQLAlchemy event listeners for query tracking."""

        @event.listens_for(Engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Track query start time."""
            context._query_start_time = time.time()

        @event.listens_for(Engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Track query completion and store details."""
            duration = time.time() - context._query_start_time

            # Store query information in thread-local storage
            if hasattr(_query_storage, 'queries'):
                query_info = {
                    'statement': statement,
                    'parameters': parameters if not executemany else f"(executemany: {len(parameters)} rows)",
                    'duration': duration,
                    'timestamp': time.time()
                }
                _query_storage.queries.append(query_info)

            # Log individual slow queries immediately
            if duration > self.slow_query_threshold:
                request_id = getattr(_query_storage, 'request_id', 'unknown')
                logger.warning(
                    f"Slow query ({duration:.2f}s): {statement[:200]}...",
                    extra={
                        "request_id": request_id,
                        "duration": duration,
                        "statement": statement,
                        "executemany": executemany
                    }
                )


def get_request_queries() -> List[Dict[str, Any]]:
    """
    Get queries executed in the current request context.

    Returns:
        List of query information dictionaries
    """
    return getattr(_query_storage, 'queries', [])


def get_request_id() -> str:
    """
    Get current request ID.

    Returns:
        Current request ID or 'unknown'
    """
    return getattr(_query_storage, 'request_id', 'unknown')