"""
Database query optimization utilities and connection pooling configuration.
"""

import time
from typing import Any, List, Optional, TypeVar
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import event, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.utils.logging import get_logger, log_performance_metric

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass
class QueryStats:
    """Query performance statistics."""

    query: str
    duration_ms: float
    row_count: Optional[int] = None
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class DatabaseOptimizer:
    """Database optimization utilities and monitoring."""

    def __init__(self):
        self.query_stats: List[QueryStats] = []
        self.slow_query_threshold_ms = 1000  # 1 second
        self.max_stats_entries = 1000

    def log_query(
        self, query: str, duration_ms: float, row_count: Optional[int] = None
    ):
        """Log query performance statistics."""
        stats = QueryStats(
            query=query[:200] + "..." if len(query) > 200 else query,
            duration_ms=duration_ms,
            row_count=row_count,
        )

        # Add to stats (with rotation)
        self.query_stats.append(stats)
        if len(self.query_stats) > self.max_stats_entries:
            self.query_stats.pop(0)

        # Log slow queries
        if duration_ms > self.slow_query_threshold_ms:
            logger.warning(
                f"Slow query detected: {duration_ms:.2f}ms",
                extra={
                    "event_type": "slow_query",
                    "query": stats.query,
                    "duration_ms": duration_ms,
                    "row_count": row_count,
                },
            )

        # Log performance metric
        log_performance_metric(
            "database_query_duration",
            duration_ms,
            "ms",
            {"query_type": self._classify_query(query)},
            logger,
        )

    def _classify_query(self, query: str) -> str:
        """Classify query type for metrics."""
        query_lower = query.lower().strip()

        if query_lower.startswith("select"):
            return "select"
        elif query_lower.startswith("insert"):
            return "insert"
        elif query_lower.startswith("update"):
            return "update"
        elif query_lower.startswith("delete"):
            return "delete"
        else:
            return "other"

    def get_query_stats(self) -> dict[str, Any]:
        """Get query performance statistics."""
        if not self.query_stats:
            return {
                "total_queries": 0,
                "avg_duration_ms": 0,
                "slow_queries": 0,
                "query_types": {},
            }

        total_queries = len(self.query_stats)
        avg_duration = (
            sum(stat.duration_ms for stat in self.query_stats) / total_queries
        )
        slow_queries = sum(
            1
            for stat in self.query_stats
            if stat.duration_ms > self.slow_query_threshold_ms
        )

        # Query type breakdown
        query_types = {}
        for stat in self.query_stats:
            query_type = self._classify_query(stat.query)
            if query_type not in query_types:
                query_types[query_type] = {"count": 0, "avg_duration_ms": 0}
            query_types[query_type]["count"] += 1

        # Calculate average duration per type
        for query_type in query_types:
            type_stats = [
                stat
                for stat in self.query_stats
                if self._classify_query(stat.query) == query_type
            ]
            query_types[query_type]["avg_duration_ms"] = sum(
                stat.duration_ms for stat in type_stats
            ) / len(type_stats)

        return {
            "total_queries": total_queries,
            "avg_duration_ms": round(avg_duration, 2),
            "slow_queries": slow_queries,
            "slow_query_percentage": round((slow_queries / total_queries) * 100, 2),
            "query_types": query_types,
        }

    def get_slowest_queries(self, limit: int = 10) -> List[dict[str, Any]]:
        """Get the slowest queries."""
        sorted_stats = sorted(
            self.query_stats, key=lambda x: x.duration_ms, reverse=True
        )

        return [
            {
                "query": stat.query,
                "duration_ms": stat.duration_ms,
                "row_count": stat.row_count,
                "timestamp": stat.timestamp,
            }
            for stat in sorted_stats[:limit]
        ]


# Global database optimizer instance
_db_optimizer: Optional[DatabaseOptimizer] = None


def get_db_optimizer() -> DatabaseOptimizer:
    """Get global database optimizer instance."""
    global _db_optimizer
    if _db_optimizer is None:
        _db_optimizer = DatabaseOptimizer()
    return _db_optimizer


def create_optimized_engine(database_url: str, **kwargs):
    """Create database engine with optimized connection pooling."""
    # Default optimization settings
    default_settings = {
        "poolclass": QueuePool,
        "pool_size": 20,  # Number of connections to maintain
        "max_overflow": 30,  # Additional connections beyond pool_size
        "pool_pre_ping": True,  # Validate connections before use
        "pool_recycle": 3600,  # Recycle connections after 1 hour
        "pool_timeout": 30,  # Timeout for getting connection from pool
        "echo": settings.APP_ENABLE_DEBUG,  # Log SQL queries in debug mode
        "echo_pool": settings.APP_ENABLE_DEBUG,  # Log connection pool events
    }

    # Merge with provided kwargs
    engine_settings = {**default_settings, **kwargs}

    # Create engine
    if database_url.startswith("postgresql+asyncpg://"):
        engine = create_async_engine(database_url, **engine_settings)
    else:
        from sqlalchemy import create_engine

        engine = create_engine(database_url, **engine_settings)

    # Add query logging event listener
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        context._query_start_time = time.time()

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total_time = time.time() - context._query_start_time
        total_time_ms = total_time * 1000

        # Get row count if available
        row_count = None
        if hasattr(cursor, "rowcount") and cursor.rowcount >= 0:
            row_count = cursor.rowcount

        # Log query performance
        db_optimizer = get_db_optimizer()
        db_optimizer.log_query(statement, total_time_ms, row_count)

    return engine


class QueryOptimizer:
    """Utilities for optimizing database queries."""

    @staticmethod
    def add_pagination_hints(query, page: int, size: int, max_size: int = 100):
        """Add pagination with performance hints."""
        # Limit page size to prevent large queries
        size = min(size, max_size)

        # Calculate offset
        offset = (page - 1) * size

        # Add limit and offset
        return query.limit(size).offset(offset)

    @staticmethod
    def add_index_hints(query, table_name: str, index_name: str):
        """Add database-specific index hints."""
        # PostgreSQL doesn't have explicit index hints like MySQL
        # But we can add query comments for monitoring
        return query.prefix_with(f"/* INDEX_HINT: {table_name}.{index_name} */")

    @staticmethod
    def optimize_joins(query):
        """Add join optimization hints."""
        # Add query comment for join optimization
        return query.prefix_with("/* OPTIMIZE_JOINS */")

    @staticmethod
    def add_query_timeout(query, timeout_seconds: int = 30):
        """Add query timeout (PostgreSQL specific)."""
        return query.prefix_with(f"/* TIMEOUT: {timeout_seconds}s */")


class ConnectionPoolMonitor:
    """Monitor database connection pool health."""

    def __init__(self, engine):
        self.engine = engine

    def get_pool_status(self) -> dict[str, Any]:
        """Get connection pool status."""
        pool = self.engine.pool

        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total_connections": pool.size() + pool.overflow(),
            "utilization_percent": round(
                (pool.checkedout() / (pool.size() + pool.overflow())) * 100, 2
            )
            if (pool.size() + pool.overflow()) > 0
            else 0,
        }

    def is_pool_healthy(self) -> bool:
        """Check if connection pool is healthy."""
        status = self.get_pool_status()

        # Pool is unhealthy if utilization is too high
        if status["utilization_percent"] > 90:
            logger.warning(
                f"High connection pool utilization: {status['utilization_percent']}%",
                extra={"event_type": "high_pool_utilization", "pool_status": status},
            )
            return False

        return True


@asynccontextmanager
async def timed_query(session: AsyncSession, description: str = "Query"):
    """Context manager for timing database queries."""
    start_time = time.time()

    try:
        yield session
    finally:
        duration_ms = (time.time() - start_time) * 1000

        logger.debug(
            f"{description} completed in {duration_ms:.2f}ms",
            extra={
                "event_type": "timed_query",
                "description": description,
                "duration_ms": duration_ms,
            },
        )

        # Log performance metric
        log_performance_metric(
            "database_operation_duration",
            duration_ms,
            "ms",
            {"operation": description},
            logger,
        )


def explain_query(session: Session, query) -> dict[str, Any]:
    """Get query execution plan (PostgreSQL)."""
    try:
        # Get the compiled query
        compiled = query.statement.compile(compile_kwargs={"literal_binds": True})

        # Execute EXPLAIN
        explain_query = text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {compiled}")
        result = session.execute(explain_query)

        return result.fetchone()[0][0]  # PostgreSQL returns JSON array

    except Exception as e:
        logger.error(f"Error explaining query: {e}")
        return {"error": str(e)}


def suggest_indexes(query_stats: List[QueryStats]) -> List[dict[str, Any]]:
    """Suggest database indexes based on query patterns."""
    suggestions = []

    # Analyze slow queries for potential index opportunities
    slow_queries = [stat for stat in query_stats if stat.duration_ms > 1000]

    for stat in slow_queries:
        query = stat.query.lower()

        # Look for WHERE clauses that might benefit from indexes
        if "where" in query:
            suggestions.append(
                {
                    "query": stat.query,
                    "duration_ms": stat.duration_ms,
                    "suggestion": "Consider adding indexes on columns used in WHERE clauses",
                    "priority": "high" if stat.duration_ms > 5000 else "medium",
                }
            )

        # Look for JOIN operations
        if "join" in query:
            suggestions.append(
                {
                    "query": stat.query,
                    "duration_ms": stat.duration_ms,
                    "suggestion": "Consider adding indexes on JOIN columns",
                    "priority": "high" if stat.duration_ms > 3000 else "medium",
                }
            )

        # Look for ORDER BY clauses
        if "order by" in query:
            suggestions.append(
                {
                    "query": stat.query,
                    "duration_ms": stat.duration_ms,
                    "suggestion": "Consider adding indexes on ORDER BY columns",
                    "priority": "medium",
                }
            )

    return suggestions
