"""
Database Performance Monitoring System.

Tracks query execution times, slow queries, connection pool metrics,
and transaction monitoring.
"""

import time
import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from collections import defaultdict, deque
from datetime import datetime, timedelta
import threading
import redis.asyncio as redis
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool


logger = logging.getLogger(__name__)


@dataclass
class QueryMetrics:
    """Metrics for a database query."""

    query_hash: str
    query_text: str
    execution_time: float
    timestamp: datetime
    table_names: List[str]
    operation_type: str  # SELECT, INSERT, UPDATE, DELETE
    rows_affected: Optional[int] = None
    connection_id: Optional[str] = None
    transaction_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ConnectionPoolStats:
    """Connection pool statistics."""

    pool_size: int = 0
    checked_out: int = 0
    overflow: int = 0
    checked_in: int = 0
    total_connections: int = 0
    invalidated: int = 0


class DatabasePerformanceMonitor:
    """Database performance monitoring system."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.query_stats: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.slow_query_threshold = 1.0  # 1 second
        self.connection_stats = ConnectionPoolStats()
        self._lock = threading.Lock()
        self.query_count = 0
        self.total_query_time = 0.0

        # Track current transactions
        self.active_transactions: Dict[str, datetime] = {}
        self.transaction_stats: Dict[str, List[float]] = defaultdict(list)

    def setup_sqlalchemy_monitoring(self, engine: Engine) -> None:
        """Setup SQLAlchemy event listeners for monitoring."""

        @event.listens_for(engine, "before_cursor_execute")
        def before_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ):
            """Track query start time."""
            context._query_start_time = time.time()
            context._query_statement = statement

        @event.listens_for(engine, "after_cursor_execute")
        def after_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ):
            """Track query completion and metrics."""
            if hasattr(context, "_query_start_time"):
                execution_time = time.time() - context._query_start_time

                asyncio.create_task(
                    self._record_query_async(
                        statement=statement,
                        execution_time=execution_time,
                        rows_affected=cursor.rowcount
                        if hasattr(cursor, "rowcount")
                        else None,
                    )
                )

        @event.listens_for(engine, "dbapi_error")
        def dbapi_error(exception_context):
            """Track database errors."""
            asyncio.create_task(
                self._record_query_error_async(
                    statement=exception_context.statement,
                    error=str(exception_context.original_exception),
                )
            )

        # Pool events
        @event.listens_for(Pool, "connect")
        def pool_connect(dbapi_conn, connection_record):
            """Track pool connections."""
            with self._lock:
                self.connection_stats.total_connections += 1

        @event.listens_for(Pool, "checkout")
        def pool_checkout(dbapi_conn, connection_record, connection_proxy):
            """Track connection checkout."""
            with self._lock:
                self.connection_stats.checked_out += 1

        @event.listens_for(Pool, "checkin")
        def pool_checkin(dbapi_conn, connection_record):
            """Track connection checkin."""
            with self._lock:
                self.connection_stats.checked_in += 1
                if self.connection_stats.checked_out > 0:
                    self.connection_stats.checked_out -= 1

    async def _record_query_async(
        self, statement: str, execution_time: float, rows_affected: Optional[int] = None
    ) -> None:
        """Record query metrics asynchronously."""
        try:
            query_hash = str(hash(self._normalize_query(statement)))
            table_names = self._extract_table_names(statement)
            operation_type = self._get_operation_type(statement)

            metrics = QueryMetrics(
                query_hash=query_hash,
                query_text=statement[:500],  # Truncate for storage
                execution_time=execution_time,
                timestamp=datetime.utcnow(),
                table_names=table_names,
                operation_type=operation_type,
                rows_affected=rows_affected,
            )

            await self.record_query(metrics)
        except Exception as e:
            logger.error(f"Failed to record query metrics: {e}")

    async def _record_query_error_async(self, statement: str, error: str) -> None:
        """Record query error asynchronously."""
        try:
            query_hash = str(hash(self._normalize_query(statement)))
            table_names = self._extract_table_names(statement)
            operation_type = self._get_operation_type(statement)

            metrics = QueryMetrics(
                query_hash=query_hash,
                query_text=statement[:500],
                execution_time=0.0,
                timestamp=datetime.utcnow(),
                table_names=table_names,
                operation_type=operation_type,
                error=error,
            )

            await self.record_query(metrics)
        except Exception as e:
            logger.error(f"Failed to record query error: {e}")

    async def record_query(self, metrics: QueryMetrics) -> None:
        """Record query metrics."""
        with self._lock:
            self.query_stats[metrics.query_hash].append(metrics)
            self.query_count += 1
            self.total_query_time += metrics.execution_time

        # Store in Redis
        if self.redis_client:
            try:
                await self._store_query_redis(metrics)
            except Exception as e:
                logger.error(f"Failed to store query metrics in Redis: {e}")

    async def _store_query_redis(self, metrics: QueryMetrics) -> None:
        """Store query metrics in Redis."""
        timestamp = int(metrics.timestamp.timestamp())

        # Store slow queries
        if metrics.execution_time > self.slow_query_threshold:
            slow_query_data = {
                "query_hash": metrics.query_hash,
                "query_text": metrics.query_text,
                "execution_time": metrics.execution_time,
                "timestamp": timestamp,
                "operation_type": metrics.operation_type,
                "table_names": ",".join(metrics.table_names),
                "error": metrics.error or "",
            }

            await self.redis_client.lpush(
                "db_monitor:slow_queries", str(slow_query_data)
            )

            # Keep only last 1000 slow queries
            await self.redis_client.ltrim("db_monitor:slow_queries", 0, 999)

        # Update query counters
        await self.redis_client.hincrby("db_monitor:counters", "total_queries", 1)
        await self.redis_client.hincrby(
            "db_monitor:counters", f"op_{metrics.operation_type}", 1
        )

        if metrics.error:
            await self.redis_client.hincrby("db_monitor:counters", "errors", 1)

        # Store execution time for averages
        await self.redis_client.lpush(
            "db_monitor:execution_times", metrics.execution_time
        )
        await self.redis_client.ltrim("db_monitor:execution_times", 0, 9999)

        # Set expiration
        await self.redis_client.expire("db_monitor:counters", 86400)
        await self.redis_client.expire("db_monitor:execution_times", 86400)

    def get_query_stats(self) -> Dict[str, Any]:
        """Get overall query statistics."""
        with self._lock:
            if self.query_count == 0:
                return {
                    "total_queries": 0,
                    "avg_execution_time": 0.0,
                    "slow_query_count": 0,
                    "slow_query_percentage": 0.0,
                    "queries_per_second": 0.0,
                    "error_count": 0,
                    "error_percentage": 0.0,
                }

            # Calculate slow queries
            slow_query_count = sum(
                1
                for queries in self.query_stats.values()
                for query in queries
                if query.execution_time > self.slow_query_threshold
            )

            # Calculate errors
            error_count = sum(
                1
                for queries in self.query_stats.values()
                for query in queries
                if query.error is not None
            )

            return {
                "total_queries": self.query_count,
                "avg_execution_time": self.total_query_time / self.query_count,
                "slow_query_count": slow_query_count,
                "slow_query_percentage": (slow_query_count / self.query_count) * 100,
                "queries_per_second": self._calculate_qps(),
                "error_count": error_count,
                "error_percentage": (error_count / self.query_count) * 100,
            }

    def get_slow_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get slowest queries."""
        all_queries = []

        with self._lock:
            for queries in self.query_stats.values():
                all_queries.extend(queries)

        # Sort by execution time and get top slow queries
        slow_queries = sorted(
            [q for q in all_queries if q.execution_time > self.slow_query_threshold],
            key=lambda x: x.execution_time,
            reverse=True,
        )[:limit]

        return [
            {
                "query_hash": q.query_hash,
                "query_text": q.query_text,
                "execution_time": q.execution_time,
                "timestamp": q.timestamp.isoformat(),
                "operation_type": q.operation_type,
                "table_names": q.table_names,
                "rows_affected": q.rows_affected,
                "error": q.error,
            }
            for q in slow_queries
        ]

    def get_connection_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        with self._lock:
            (self.connection_stats.checked_out + self.connection_stats.checked_in)

            utilization = 0.0
            if self.connection_stats.pool_size > 0:
                utilization = (
                    self.connection_stats.checked_out / self.connection_stats.pool_size
                ) * 100

            return {
                "pool_size": self.connection_stats.pool_size,
                "checked_out": self.connection_stats.checked_out,
                "checked_in": self.connection_stats.checked_in,
                "overflow": self.connection_stats.overflow,
                "total_connections": self.connection_stats.total_connections,
                "invalidated": self.connection_stats.invalidated,
                "utilization_percentage": utilization,
                "is_healthy": utilization < 90
                and self.connection_stats.invalidated == 0,
            }

    def get_table_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics by table."""
        table_stats = defaultdict(
            lambda: {
                "query_count": 0,
                "total_time": 0.0,
                "avg_time": 0.0,
                "operations": defaultdict(int),
            }
        )

        with self._lock:
            for queries in self.query_stats.values():
                for query in queries:
                    for table in query.table_names:
                        stats = table_stats[table]
                        stats["query_count"] += 1
                        stats["total_time"] += query.execution_time
                        stats["operations"][query.operation_type] += 1

        # Calculate averages
        for table, stats in table_stats.items():
            if stats["query_count"] > 0:
                stats["avg_time"] = stats["total_time"] / stats["query_count"]
            stats["operations"] = dict(stats["operations"])

        return dict(table_stats)

    def _calculate_qps(self) -> float:
        """Calculate queries per second over the last minute."""
        minute_ago = datetime.utcnow() - timedelta(minutes=1)

        recent_queries = 0
        with self._lock:
            for queries in self.query_stats.values():
                recent_queries += sum(
                    1 for query in queries if query.timestamp >= minute_ago
                )

        return recent_queries / 60.0

    def _normalize_query(self, query: str) -> str:
        """Normalize query for grouping (remove parameters)."""
        # Simple normalization - replace parameters with placeholders
        import re

        # Remove string literals
        query = re.sub(r"'[^']*'", "'?'", query)

        # Remove numeric literals
        query = re.sub(r"\b\d+\b", "?", query)

        # Remove whitespace variations
        query = re.sub(r"\s+", " ", query.strip())

        return query.upper()

    def _extract_table_names(self, query: str) -> List[str]:
        """Extract table names from query."""
        import re

        # Simple regex patterns for table extraction
        patterns = [
            r"FROM\s+(\w+)",
            r"UPDATE\s+(\w+)",
            r"INSERT\s+INTO\s+(\w+)",
            r"DELETE\s+FROM\s+(\w+)",
            r"JOIN\s+(\w+)",
        ]

        tables = set()
        query_upper = query.upper()

        for pattern in patterns:
            matches = re.findall(pattern, query_upper)
            tables.update(matches)

        return list(tables)

    def _get_operation_type(self, query: str) -> str:
        """Get operation type from query."""
        query_upper = query.strip().upper()

        if query_upper.startswith("SELECT"):
            return "SELECT"
        elif query_upper.startswith("INSERT"):
            return "INSERT"
        elif query_upper.startswith("UPDATE"):
            return "UPDATE"
        elif query_upper.startswith("DELETE"):
            return "DELETE"
        elif query_upper.startswith("CREATE"):
            return "CREATE"
        elif query_upper.startswith("DROP"):
            return "DROP"
        elif query_upper.startswith("ALTER"):
            return "ALTER"
        else:
            return "OTHER"

    def reset_stats(self) -> None:
        """Reset all statistics."""
        with self._lock:
            self.query_stats.clear()
            self.query_count = 0
            self.total_query_time = 0.0
            self.connection_stats = ConnectionPoolStats()
            self.active_transactions.clear()
            self.transaction_stats.clear()
