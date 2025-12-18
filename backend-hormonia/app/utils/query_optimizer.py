"""
Query Optimization Framework for SQLAlchemy

This module provides tools for optimizing database queries, detecting N+1 queries,
and providing performance metrics and suggestions.

PERFORMANCE FEATURES:
- @optimized_query decorator for automatic eager loading
- Query plan analysis and optimization suggestions
- Performance metrics collection
- N+1 query detection via SQLAlchemy events
- Slow query logging and analysis
"""

import time
import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, cast
from contextlib import contextmanager
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Query, Session
from sqlalchemy.sql import text

logger = logging.getLogger(__name__)

# Type variable for generic function wrapping
F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class QueryMetrics:
    """Metrics for a single query execution"""

    query_text: str
    execution_time_ms: float
    row_count: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    function_name: str = ""
    is_slow: bool = False
    suggested_indexes: List[str] = field(default_factory=list)
    n1_detected: bool = False


@dataclass
class QueryStats:
    """Aggregated statistics for query optimization"""

    total_queries: int = 0
    total_time_ms: float = 0.0
    slow_queries: int = 0
    n1_queries: int = 0
    avg_execution_time_ms: float = 0.0
    queries_by_table: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    metrics: List[QueryMetrics] = field(default_factory=list)


class QueryOptimizer:
    """
    Query optimization framework with automatic eager loading detection,
    performance metrics, and N+1 query detection.

    Usage:
        optimizer = QueryOptimizer()

        @optimizer.optimized_query(['patient', 'doctor'])
        def get_treatment(db, treatment_id):
            return db.query(Treatment).filter_by(id=treatment_id).first()
    """

    def __init__(self, slow_query_threshold_ms: float = 100.0):
        """
        Initialize query optimizer.

        Args:
            slow_query_threshold_ms: Threshold in milliseconds for slow query detection
        """
        self.slow_query_threshold_ms = slow_query_threshold_ms
        self.stats = QueryStats()
        self._query_count_per_request: Dict[str, int] = defaultdict(int)
        self._n1_patterns: Set[str] = set()
        self._enabled = True

    def optimized_query(
        self, relationships: Optional[List[str]] = None, strategy: str = "auto"
    ) -> Callable[[F], F]:
        """
        Decorator to automatically apply eager loading to queries and track performance.

        OPTIMIZATION STRATEGIES:
        - "auto": Automatically detect and apply best strategy (default)
        - "joined": Use joinedload for all relationships (1:1, many:1)
        - "select": Use selectinload for all relationships (1:many)
        - "mixed": Use joinedload for 1:1, selectinload for 1:many

        Args:
            relationships: List of relationship names to eager load
            strategy: Loading strategy to use

        Usage:
            @optimized_query(['patient', 'doctor'])
            def get_treatment(db, treatment_id):
                return db.query(Treatment).filter_by(id=treatment_id).first()

            @optimized_query(['patient.alerts', 'patient.flow_states'], strategy='select')
            def get_patient_with_details(db, patient_id):
                return db.query(Patient).filter_by(id=patient_id).first()
        """

        def decorator(func: F) -> F:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                if not self._enabled:
                    return func(*args, **kwargs)

                start_time = time.time()
                function_name = func.__name__

                # Track query count for this request
                request_id = f"{function_name}_{id(args)}"
                self._query_count_per_request[request_id] = 0

                try:
                    # Execute the function
                    result = func(*args, **kwargs)

                    # Calculate execution time
                    execution_time_ms = (time.time() - start_time) * 1000

                    # Detect if result is a query and apply optimization
                    if isinstance(result, Query):
                        result = self._apply_eager_loading(
                            result, relationships or [], strategy
                        )

                    # Create metrics
                    row_count = self._get_row_count(result)
                    is_slow = execution_time_ms > self.slow_query_threshold_ms
                    query_count = self._query_count_per_request[request_id]
                    n1_detected = query_count > 5  # More than 5 queries suggests N+1

                    metrics = QueryMetrics(
                        query_text=str(result)
                        if isinstance(result, Query)
                        else function_name,
                        execution_time_ms=execution_time_ms,
                        row_count=row_count,
                        function_name=function_name,
                        is_slow=is_slow,
                        n1_detected=n1_detected,
                    )

                    # Update statistics
                    self._update_stats(metrics)

                    # Log warnings for performance issues
                    if is_slow:
                        logger.warning(
                            f"Slow query detected: {function_name} took {execution_time_ms:.2f}ms "
                            f"(threshold: {self.slow_query_threshold_ms}ms)"
                        )

                    if n1_detected:
                        logger.warning(
                            f"Potential N+1 query detected in {function_name}: "
                            f"{query_count} queries executed. "
                            f"Consider using eager loading with relationships={relationships}"
                        )
                        self._n1_patterns.add(function_name)

                    return result

                finally:
                    # Clean up request tracking
                    if request_id in self._query_count_per_request:
                        del self._query_count_per_request[request_id]

            return cast(F, wrapper)

        return decorator

    def _apply_eager_loading(
        self, query: Query, relationships: List[str], strategy: str
    ) -> Query:
        """
        Apply eager loading to query based on strategy.

        Args:
            query: SQLAlchemy query to optimize
            relationships: List of relationship names to load
            strategy: Loading strategy to use

        Returns:
            Optimized query with eager loading applied
        """
        if not relationships:
            return query

        from sqlalchemy.orm import joinedload, selectinload, subqueryload

        for rel_path in relationships:
            # Parse nested relationships (e.g., 'patient.doctor')
            rel_parts = rel_path.split(".")

            # Determine loading strategy
            if strategy == "joined":
                loader = joinedload
            elif strategy == "select":
                loader = selectinload
            elif strategy == "subquery":
                loader = subqueryload
            else:  # auto or mixed
                # Auto-detect best strategy based on relationship type
                # This is a simplified heuristic - in production, you'd inspect
                # the actual relationship metadata
                loader = joinedload if len(rel_parts) == 1 else selectinload

            # Apply nested loading
            current_loader = loader(rel_parts[0])
            for part in rel_parts[1:]:
                current_loader = current_loader.joinedload(part)

            query = query.options(current_loader)

        return query

    def _get_row_count(self, result: Any) -> int:
        """Get row count from query result"""
        if isinstance(result, list):
            return len(result)
        elif result is not None:
            return 1
        return 0

    def _update_stats(self, metrics: QueryMetrics) -> None:
        """Update aggregated statistics"""
        self.stats.total_queries += 1
        self.stats.total_time_ms += metrics.execution_time_ms
        self.stats.metrics.append(metrics)

        if metrics.is_slow:
            self.stats.slow_queries += 1

        if metrics.n1_detected:
            self.stats.n1_queries += 1

        # Update average
        self.stats.avg_execution_time_ms = (
            self.stats.total_time_ms / self.stats.total_queries
        )

    def get_stats(self) -> QueryStats:
        """Get current query statistics"""
        return self.stats

    def reset_stats(self) -> None:
        """Reset all statistics"""
        self.stats = QueryStats()
        self._query_count_per_request.clear()
        self._n1_patterns.clear()

    def get_optimization_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive optimization report.

        Returns:
            Dictionary containing:
            - Summary statistics
            - Slow queries list
            - N+1 query patterns
            - Optimization suggestions
        """
        slow_queries = [m for m in self.stats.metrics if m.is_slow]
        n1_queries = [m for m in self.stats.metrics if m.n1_detected]

        return {
            "summary": {
                "total_queries": self.stats.total_queries,
                "total_time_ms": round(self.stats.total_time_ms, 2),
                "avg_time_ms": round(self.stats.avg_execution_time_ms, 2),
                "slow_queries_count": self.stats.slow_queries,
                "n1_queries_count": self.stats.n1_queries,
                "queries_by_table": dict(self.stats.queries_by_table),
            },
            "slow_queries": [
                {
                    "function": m.function_name,
                    "time_ms": round(m.execution_time_ms, 2),
                    "rows": m.row_count,
                    "timestamp": m.timestamp.isoformat(),
                }
                for m in sorted(
                    slow_queries, key=lambda x: x.execution_time_ms, reverse=True
                )[:10]
            ],
            "n1_patterns": list(self._n1_patterns),
            "suggestions": self._generate_suggestions(slow_queries, n1_queries),
        }

    def _generate_suggestions(
        self, slow_queries: List[QueryMetrics], n1_queries: List[QueryMetrics]
    ) -> List[str]:
        """Generate optimization suggestions based on detected issues"""
        suggestions = []

        if slow_queries:
            suggestions.append(
                f"Found {len(slow_queries)} slow queries (>{self.slow_query_threshold_ms}ms). "
                "Consider adding database indexes or optimizing query filters."
            )

        if n1_queries:
            suggestions.append(
                f"Detected {len(n1_queries)} potential N+1 query patterns. "
                "Use eager loading with @optimized_query decorator or add "
                "joinedload/selectinload to queries."
            )

        if self.stats.avg_execution_time_ms > 50:
            suggestions.append(
                f"Average query time is {self.stats.avg_execution_time_ms:.2f}ms. "
                "Target is <50ms for optimal performance."
            )

        return suggestions

    def enable(self) -> None:
        """Enable query optimization"""
        self._enabled = True
        logger.info("Query optimization enabled")

    def disable(self) -> None:
        """Disable query optimization"""
        self._enabled = False
        logger.info("Query optimization disabled")


# Global optimizer instance
_global_optimizer = QueryOptimizer()


def optimized_query(
    relationships: Optional[List[str]] = None, strategy: str = "auto"
) -> Callable[[F], F]:
    """
    Convenience function for using global optimizer.

    Usage:
        from app.utils.query_optimizer import optimized_query

        @optimized_query(['patient', 'doctor'])
        def get_treatment(db, treatment_id):
            return db.query(Treatment).filter_by(id=treatment_id).first()
    """
    return _global_optimizer.optimized_query(relationships, strategy)


def get_query_stats() -> QueryStats:
    """Get global query statistics"""
    return _global_optimizer.get_stats()


def reset_query_stats() -> None:
    """Reset global query statistics"""
    _global_optimizer.reset_stats()


def get_optimization_report() -> Dict[str, Any]:
    """Get global optimization report"""
    return _global_optimizer.get_optimization_report()


@contextmanager
def track_queries(session: Session):
    """
    Context manager to track all queries in a session.

    Usage:
        with track_queries(db) as tracker:
            # Execute queries
            results = db.query(Patient).all()

        logger.info(f"Executed {tracker.query_count} queries", extra={"query_count": tracker.query_count})
    """

    class QueryTracker:
        def __init__(self):
            self.query_count = 0
            self.queries = []

    tracker = QueryTracker()

    @event.listens_for(session, "after_cursor_execute")
    def receive_after_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        tracker.query_count += 1
        tracker.queries.append(
            {
                "statement": statement,
                "parameters": parameters,
                "executemany": executemany,
            }
        )

    try:
        yield tracker
    finally:
        event.remove(session, "after_cursor_execute", receive_after_cursor_execute)


def setup_query_logging(engine: Engine, log_all: bool = False) -> None:
    """
    Set up SQLAlchemy event listeners for query logging.

    Args:
        engine: SQLAlchemy engine
        log_all: If True, log all queries. If False, only log slow queries.
    """

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        conn.info.setdefault("query_start_time", []).append(time.time())

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total_time = time.time() - conn.info["query_start_time"].pop()
        total_time_ms = total_time * 1000

        # Update global optimizer
        request_id = f"engine_{id(conn)}"
        _global_optimizer._query_count_per_request[request_id] = (
            _global_optimizer._query_count_per_request.get(request_id, 0) + 1
        )

        # Log based on settings
        if log_all:
            logger.debug(
                f"Query executed in {total_time_ms:.2f}ms: {statement[:100]}..."
            )
        elif total_time_ms > _global_optimizer.slow_query_threshold_ms:
            logger.warning(f"Slow query ({total_time_ms:.2f}ms): {statement[:200]}...")


def analyze_query_plan(session: Session, query: Query) -> Dict[str, Any]:
    """
    Analyze query execution plan (PostgreSQL specific).

    Args:
        session: SQLAlchemy session
        query: Query to analyze

    Returns:
        Dictionary with query plan information
    """
    try:
        # Get query string
        query_str = str(
            query.statement.compile(
                session.bind, compile_kwargs={"literal_binds": True}
            )
        )

        # Execute EXPLAIN ANALYZE
        result = session.execute(
            text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query_str}")
        )

        plan = result.fetchone()[0]

        # Extract key metrics
        if isinstance(plan, list) and len(plan) > 0:
            execution_time = plan[0].get("Execution Time", 0)
            planning_time = plan[0].get("Planning Time", 0)

            return {
                "execution_time_ms": execution_time,
                "planning_time_ms": planning_time,
                "total_time_ms": execution_time + planning_time,
                "plan": plan,
            }

        return {"error": "Unable to parse query plan"}

    except Exception as e:
        logger.error(f"Query plan analysis failed: {e}")
        return {"error": str(e)}
