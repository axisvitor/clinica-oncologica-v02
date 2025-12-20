"""
Query Performance Monitor Service.
Tracks slow queries, provides optimization suggestions, and monitors database performance.
"""

import logging
import time
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from functools import wraps
from contextlib import contextmanager
import json

from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.core.redis_unified import get_sync_redis
from app.core.monitoring_logging import monitoring_logger


logger = logging.getLogger(__name__)


@dataclass
class SlowQuery:
    """Represents a slow query with performance metrics."""

    query_hash: str
    query_text: str
    duration_ms: float
    timestamp: datetime
    parameters: Dict[str, Any]
    optimization_suggestions: List[str]
    execution_count: int = 1
    avg_duration_ms: float = 0.0
    max_duration_ms: float = 0.0

    def __post_init__(self):
        if self.avg_duration_ms == 0.0:
            self.avg_duration_ms = self.duration_ms
        if self.max_duration_ms == 0.0:
            self.max_duration_ms = self.duration_ms


@dataclass
class QueryMetrics:
    """Query performance metrics."""

    total_queries: int = 0
    slow_queries: int = 0
    avg_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    queries_per_second: float = 0.0
    cache_hit_rate: float = 0.0


class QueryPerformanceMonitor:
    """
    Monitor and analyze database query performance.

    Features:
    - Track slow queries (>500ms threshold)
    - Generate optimization suggestions
    - Store metrics in Redis for analysis
    - Provide performance insights
    """

    SLOW_QUERY_THRESHOLD_MS = 500
    REDIS_KEY_PREFIX = "query_perf"
    METRICS_RETENTION_HOURS = 24
    MAX_STORED_QUERIES = 1000

    def __init__(self, db: Any):
        """Initialize query performance monitor."""
        self.db = db
        self.redis_client = get_sync_redis()
        self._query_cache: Dict[str, SlowQuery] = {}
        self._metrics = QueryMetrics()
        self._start_time = datetime.now(timezone.utc)

        # Register SQLAlchemy event listeners
        self._register_event_listeners()

        logger.info("Query Performance Monitor initialized")

    def _register_event_listeners(self):
        """Register SQLAlchemy event listeners for automatic query tracking."""

        @event.listens_for(Engine, "before_cursor_execute")
        def receive_before_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ):
            context._query_start_time = time.time()

        @event.listens_for(Engine, "after_cursor_execute")
        def receive_after_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ):
            total_time = time.time() - context._query_start_time
            duration_ms = total_time * 1000

            # Track all queries for metrics
            self._update_metrics(duration_ms)

            # Track slow queries
            if duration_ms > self.SLOW_QUERY_THRESHOLD_MS:
                self.track_query_time(statement, duration_ms, parameters)

    def track_query_time(
        self, query: str, duration_ms: float, parameters: Optional[Dict] = None
    ):
        """
        Track query execution time and identify slow queries.

        Args:
            query: SQL query string
            duration_ms: Query execution time in milliseconds
            parameters: Query parameters
        """
        try:
            if duration_ms <= self.SLOW_QUERY_THRESHOLD_MS:
                return

            # Generate query hash for deduplication
            query_hash = self._generate_query_hash(query)

            # Clean parameters for storage
            clean_params = self._clean_parameters(parameters or {})

            # Get or create slow query record
            if query_hash in self._query_cache:
                slow_query = self._query_cache[query_hash]
                slow_query.execution_count += 1
                slow_query.avg_duration_ms = (
                    slow_query.avg_duration_ms * (slow_query.execution_count - 1)
                    + duration_ms
                ) / slow_query.execution_count
                slow_query.max_duration_ms = max(
                    slow_query.max_duration_ms, duration_ms
                )
                slow_query.timestamp = datetime.now(timezone.utc)
            else:
                slow_query = SlowQuery(
                    query_hash=query_hash,
                    query_text=self._normalize_query(query),
                    duration_ms=duration_ms,
                    timestamp=datetime.now(timezone.utc),
                    parameters=clean_params,
                    optimization_suggestions=self._generate_optimization_suggestions(
                        query
                    ),
                    avg_duration_ms=duration_ms,
                    max_duration_ms=duration_ms,
                )
                self._query_cache[query_hash] = slow_query

            # Store in Redis
            self._store_slow_query(slow_query)

            # Log slow query
            monitoring_logger.log_system_event(
                event_type="slow_query_detected",
                message=f"Slow query detected: {duration_ms:.2f}ms",
                level="WARNING",
                context={
                    "query_hash": query_hash,
                    "duration_ms": duration_ms,
                    "execution_count": slow_query.execution_count,
                    "avg_duration_ms": slow_query.avg_duration_ms,
                },
            )

            logger.warning(
                f"Slow query detected: {duration_ms:.2f}ms - {query[:100]}..."
            )

        except Exception as e:
            logger.error(f"Error tracking query time: {e}")

    def identify_slow_queries(self, limit: int = 50) -> List[SlowQuery]:
        """
        Identify and return slow queries sorted by average duration.

        Args:
            limit: Maximum number of queries to return

        Returns:
            List of slow queries sorted by average duration (descending)
        """
        try:
            # Get from Redis
            stored_queries = self._get_stored_slow_queries()

            # Combine with in-memory cache
            all_queries = {**stored_queries, **self._query_cache}

            # Sort by average duration
            sorted_queries = sorted(
                all_queries.values(), key=lambda q: q.avg_duration_ms, reverse=True
            )

            return sorted_queries[:limit]

        except Exception as e:
            logger.error(f"Error identifying slow queries: {e}")
            return []

    def suggest_optimizations(self, query: str) -> List[str]:
        """
        Generate optimization suggestions for a query.

        Args:
            query: SQL query string

        Returns:
            List of optimization suggestions
        """
        return self._generate_optimization_suggestions(query)

    def get_performance_metrics(self) -> QueryMetrics:
        """
        Get current performance metrics.

        Returns:
            QueryMetrics object with current performance data
        """
        try:
            # Update queries per second
            elapsed_seconds = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            if elapsed_seconds > 0:
                self._metrics.queries_per_second = (
                    self._metrics.total_queries / elapsed_seconds
                )

            return self._metrics

        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return QueryMetrics()

    def get_query_analysis(self, hours_back: int = 1) -> Dict[str, Any]:
        """
        Get comprehensive query analysis for the specified time period.

        Args:
            hours_back: Number of hours to analyze

        Returns:
            Dictionary with query analysis data
        """
        try:
            slow_queries = self.identify_slow_queries()
            metrics = self.get_performance_metrics()

            # Filter queries by time period
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            recent_queries = [q for q in slow_queries if q.timestamp >= cutoff_time]

            # Analyze patterns
            patterns = self._analyze_query_patterns(recent_queries)

            return {
                "time_period_hours": hours_back,
                "metrics": asdict(metrics),
                "slow_queries_count": len(recent_queries),
                "top_slow_queries": [asdict(q) for q in recent_queries[:10]],
                "patterns": patterns,
                "recommendations": self._generate_performance_recommendations(
                    recent_queries
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting query analysis: {e}")
            return {}

    @contextmanager
    def monitor_query(self, query_name: str):
        """
        Context manager to monitor a specific query execution.

        Args:
            query_name: Name/identifier for the query
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start_time) * 1000
            self.track_query_time(f"MONITORED: {query_name}", duration_ms)

    def _update_metrics(self, duration_ms: float):
        """Update internal metrics with query execution data."""
        self._metrics.total_queries += 1

        if duration_ms > self.SLOW_QUERY_THRESHOLD_MS:
            self._metrics.slow_queries += 1

        # Update average duration
        if self._metrics.total_queries == 1:
            self._metrics.avg_duration_ms = duration_ms
        else:
            self._metrics.avg_duration_ms = (
                self._metrics.avg_duration_ms * (self._metrics.total_queries - 1)
                + duration_ms
            ) / self._metrics.total_queries

        # Update max duration
        self._metrics.max_duration_ms = max(self._metrics.max_duration_ms, duration_ms)

    def _generate_query_hash(self, query: str) -> str:
        """Generate a hash for query deduplication."""
        normalized = self._normalize_query(query)
        return hashlib.md5(normalized.encode()).hexdigest()

    def _normalize_query(self, query: str) -> str:
        """Normalize query for consistent hashing."""
        # Remove extra whitespace and convert to lowercase
        normalized = " ".join(query.lower().split())

        # Replace parameter placeholders with generic markers
        import re

        normalized = re.sub(r"\$\d+", "$PARAM", normalized)
        normalized = re.sub(r"%\([^)]+\)s", "%PARAM", normalized)
        normalized = re.sub(r"\?", "?PARAM", normalized)

        return normalized

    def _clean_parameters(self, parameters: Dict) -> Dict[str, Any]:
        """Clean parameters for safe storage."""
        cleaned = {}
        for key, value in parameters.items():
            if isinstance(value, (str, int, float, bool, type(None))):
                cleaned[key] = value
            else:
                cleaned[key] = str(type(value).__name__)
        return cleaned

    def _generate_optimization_suggestions(self, query: str) -> List[str]:
        """Generate optimization suggestions based on query analysis."""
        suggestions = []
        query_lower = query.lower()

        # Check for missing indexes
        if "where" in query_lower and "index" not in query_lower:
            suggestions.append("Consider adding indexes on WHERE clause columns")

        # Check for SELECT *
        if "select *" in query_lower:
            suggestions.append("Avoid SELECT * - specify only needed columns")

        # Check for N+1 queries
        if "join" not in query_lower and (
            "patient" in query_lower or "message" in query_lower
        ):
            suggestions.append(
                "Consider using JOINs or eager loading to prevent N+1 queries"
            )

        # Check for LIMIT usage
        if "limit" not in query_lower and "count" not in query_lower:
            suggestions.append("Consider adding LIMIT clause for large result sets")

        # Check for date range queries
        if "created_at" in query_lower or "updated_at" in query_lower:
            suggestions.append("Ensure date columns have appropriate indexes")

        # Check for OR conditions
        if " or " in query_lower:
            suggestions.append(
                "OR conditions can be slow - consider UNION or separate queries"
            )

        # Check for subqueries
        if query_lower.count("select") > 1:
            suggestions.append("Consider optimizing subqueries with JOINs or CTEs")

        # Check for GROUP BY without indexes
        if "group by" in query_lower:
            suggestions.append("Ensure GROUP BY columns have appropriate indexes")

        return suggestions

    def _store_slow_query(self, slow_query: SlowQuery):
        """Store slow query in Redis."""
        try:
            key = f"{self.REDIS_KEY_PREFIX}:slow_queries:{slow_query.query_hash}"
            data = asdict(slow_query)

            # Convert datetime to ISO string for JSON serialization
            data["timestamp"] = slow_query.timestamp.isoformat()

            self.redis_client.setex(
                key, self.METRICS_RETENTION_HOURS * 3600, json.dumps(data)
            )

        except Exception as e:
            logger.error(f"Error storing slow query in Redis: {e}")

    def _get_stored_slow_queries(self) -> Dict[str, SlowQuery]:
        """Retrieve stored slow queries from Redis."""
        try:
            pattern = f"{self.REDIS_KEY_PREFIX}:slow_queries:*"
            keys = self.redis_client.keys(pattern)

            stored_queries = {}
            for key in keys:
                try:
                    data = json.loads(self.redis_client.get(key))
                    data["timestamp"] = datetime.fromisoformat(data["timestamp"])
                    slow_query = SlowQuery(**data)
                    stored_queries[slow_query.query_hash] = slow_query
                except Exception as e:
                    logger.warning(f"Error loading slow query from Redis: {e}")
                    continue

            return stored_queries

        except Exception as e:
            logger.error(f"Error retrieving slow queries from Redis: {e}")
            return {}

    def _analyze_query_patterns(self, queries: List[SlowQuery]) -> Dict[str, Any]:
        """Analyze patterns in slow queries."""
        if not queries:
            return {}

        patterns = {
            "most_common_tables": {},
            "most_common_operations": {},
            "peak_hours": {},
            "avg_execution_count": 0,
        }

        # Analyze table usage
        for query in queries:
            query_text = query.query_text.lower()

            # Extract table names (simple heuristic)
            tables = ["patient", "message", "quiz", "alert", "user"]
            for table in tables:
                if table in query_text:
                    patterns["most_common_tables"][table] = (
                        patterns["most_common_tables"].get(table, 0) + 1
                    )

            # Extract operations
            operations = ["select", "insert", "update", "delete", "join"]
            for op in operations:
                if op in query_text:
                    patterns["most_common_operations"][op] = (
                        patterns["most_common_operations"].get(op, 0) + 1
                    )

            # Analyze peak hours
            hour = query.timestamp.hour
            patterns["peak_hours"][hour] = patterns["peak_hours"].get(hour, 0) + 1

        # Calculate average execution count
        if queries:
            patterns["avg_execution_count"] = sum(
                q.execution_count for q in queries
            ) / len(queries)

        return patterns

    def _generate_performance_recommendations(
        self, queries: List[SlowQuery]
    ) -> List[str]:
        """Generate performance recommendations based on query analysis."""
        recommendations = []

        if not queries:
            return ["No slow queries detected - performance looks good!"]

        # Check for high execution count queries
        high_exec_queries = [q for q in queries if q.execution_count > 10]
        if high_exec_queries:
            recommendations.append(
                f"Found {len(high_exec_queries)} frequently executed slow queries - "
                "consider caching or optimization"
            )

        # Check for very slow queries
        very_slow_queries = [q for q in queries if q.avg_duration_ms > 2000]
        if very_slow_queries:
            recommendations.append(
                f"Found {len(very_slow_queries)} very slow queries (>2s) - "
                "immediate optimization needed"
            )

        # Check for missing indexes
        missing_index_queries = [
            q
            for q in queries
            if "Consider adding indexes" in " ".join(q.optimization_suggestions)
        ]
        if missing_index_queries:
            recommendations.append(
                f"Found {len(missing_index_queries)} queries that may benefit from indexes"
            )

        # Check for N+1 query patterns
        n_plus_one_queries = [
            q for q in queries if "N+1 queries" in " ".join(q.optimization_suggestions)
        ]
        if n_plus_one_queries:
            recommendations.append(
                f"Found {len(n_plus_one_queries)} potential N+1 query patterns - "
                "consider eager loading"
            )

        return recommendations


def query_performance_decorator(monitor: QueryPerformanceMonitor, operation_name: str):
    """
    Decorator to monitor query performance for specific operations.

    Args:
        monitor: QueryPerformanceMonitor instance
        operation_name: Name of the operation being monitored
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with monitor.monitor_query(f"{operation_name}:{func.__name__}"):
                return func(*args, **kwargs)

        return wrapper

    return decorator
