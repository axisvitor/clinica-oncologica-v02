"""
SQLAlchemy Query Logging Configuration for N+1 Detection

Enables detailed query logging to identify N+1 query patterns in development and staging.
Automatically disabled in production for performance.

Usage:
    from app.core.query_logging import enable_query_logging

    # Enable in development
    enable_query_logging(level="INFO")  # Basic query logging
    enable_query_logging(level="DEBUG") # Detailed with parameters
"""
import hashlib
import logging
import os
from contextlib import contextmanager
from typing import Optional
from sqlalchemy import event
from sqlalchemy.engine import Engine
from time import time


logger = logging.getLogger(__name__)


class QueryLogger:
    """
    Advanced query logger for N+1 detection and performance monitoring.

    Features:
    - Query execution time tracking
    - Duplicate query detection
    - N+1 pattern warnings
    - Slow query alerts
    """

    def __init__(self, slow_query_threshold_ms: float = 100):
        self.slow_query_threshold = slow_query_threshold_ms / 1000.0
        self.query_count = 0
        self.total_time = 0.0
        self.queries = []
        self.duplicate_queries = {}

    def log_query(self, statement: str, duration: float):
        """Log a query execution."""
        self.query_count += 1
        self.total_time += duration
        self.queries.append((statement, duration))

        # Track duplicate queries
        query_key = statement.strip()
        if query_key in self.duplicate_queries:
            self.duplicate_queries[query_key] += 1
            # Warn on potential N+1
            if self.duplicate_queries[query_key] > 5:
                logger.warning(
                    f"Potential N+1 pattern detected: Query executed {self.duplicate_queries[query_key]} times:\n"
                    f"{statement[:200]}..."
                )
        else:
            self.duplicate_queries[query_key] = 1

        # Warn on slow queries
        if duration > self.slow_query_threshold:
            logger.warning(
                f"Slow query detected ({duration*1000:.2f}ms):\n{statement}"
            )

    def get_stats(self) -> dict:
        """Get query statistics."""
        return {
            "total_queries": self.query_count,
            "total_time_seconds": self.total_time,
            "average_time_ms": (self.total_time / self.query_count * 1000) if self.query_count > 0 else 0,
            "duplicate_queries": {k: v for k, v in self.duplicate_queries.items() if v > 1},
            "slow_queries": [(q, d*1000) for q, d in self.queries if d > self.slow_query_threshold]
        }

    def reset(self):
        """Reset query statistics."""
        self.query_count = 0
        self.total_time = 0.0
        self.queries = []
        self.duplicate_queries = {}

    def print_summary(self):
        """Print query statistics summary using structured logging."""
        stats = self.get_stats()

        # Use structured logging instead of print statements
        logger.info(
            "Query statistics summary",
            extra={
                "total_queries": stats['total_queries'],
                "total_time_seconds": stats['total_time_seconds'],
                "average_time_ms": stats['average_time_ms'],
                "duplicate_queries_count": len(stats['duplicate_queries']),
                "slow_queries_count": len(stats['slow_queries'])
            }
        )

        # Log duplicate queries as warnings (potential N+1 problems)
        if stats['duplicate_queries']:
            for query, count in sorted(stats['duplicate_queries'].items(), key=lambda x: x[1], reverse=True)[:5]:
                logger.warning(
                    "Duplicate query detected (potential N+1 problem)",
                    extra={
                        "count": count,
                        "query_preview": query[:100],
                        "query_hash": hashlib.md5(query.encode()).hexdigest()
                    }
                )

        # Log slow queries as warnings
        if stats['slow_queries']:
            for query, duration_ms in stats['slow_queries'][:5]:
                logger.warning(
                    f"Slow query detected (>{self.slow_query_threshold*1000:.0f}ms)",
                    extra={
                        "duration_ms": duration_ms,
                        "query_preview": query[:100],
                        "query_hash": hashlib.md5(query.encode()).hexdigest()
                    }
                )


# Global query logger instance
_query_logger: Optional[QueryLogger] = None


def enable_query_logging(
    level: str = "INFO",
    slow_query_threshold_ms: float = 100,
    detect_n1: bool = True
) -> QueryLogger:
    """
    Enable SQLAlchemy query logging for N+1 detection.

    Args:
        level: Logging level ("INFO" or "DEBUG")
        slow_query_threshold_ms: Threshold for slow query warnings (default: 100ms)
        detect_n1: Enable N+1 pattern detection (default: True)

    Returns:
        QueryLogger instance for statistics

    Example:
        >>> query_logger = enable_query_logging(level="INFO")
        >>> # ... perform database operations ...
        >>> query_logger.print_summary()
    """
    global _query_logger

    # Don't enable in production
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        logger.info("Query logging disabled in production")
        return None

    # Configure SQLAlchemy logging
    logging.basicConfig()
    sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
    sqlalchemy_logger.setLevel(getattr(logging, level.upper()))

    # Initialize query logger
    if detect_n1:
        _query_logger = QueryLogger(slow_query_threshold_ms=slow_query_threshold_ms)

        @event.listens_for(Engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            conn.info.setdefault('query_start_time', []).append(time())

        @event.listens_for(Engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            total_time = time() - conn.info['query_start_time'].pop(-1)
            _query_logger.log_query(statement, total_time)

        logger.info(
            f"Query logging enabled with N+1 detection "
            f"(slow query threshold: {slow_query_threshold_ms}ms)"
        )
    else:
        logger.info("Basic query logging enabled (no N+1 detection)")

    return _query_logger


def disable_query_logging():
    """Disable query logging."""
    global _query_logger

    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    _query_logger = None
    logger.info("Query logging disabled")


def get_query_logger() -> Optional[QueryLogger]:
    """Get the global query logger instance."""
    return _query_logger


@contextmanager
def query_logging_context(level: str = "INFO", slow_query_threshold_ms: float = 100):
    """
    Context manager for temporary query logging.

    Example:
        >>> with query_logging_context(level="INFO") as logger:
        ...     patients = repo.get_all_active(limit=100)
        ...     logger.print_summary()
    """
    query_logger = enable_query_logging(level=level, slow_query_threshold_ms=slow_query_threshold_ms)
    try:
        yield query_logger
    finally:
        if query_logger:
            query_logger.print_summary()
        disable_query_logging()


@contextmanager
def monitor_n1_queries(threshold: int = 10):
    """
    Context manager to monitor and assert N+1 query patterns.

    Raises AssertionError if query count exceeds threshold.

    Args:
        threshold: Maximum allowed queries (default: 10)

    Example:
        >>> with monitor_n1_queries(threshold=5):
        ...     patients = repo.get_all_active(limit=100, eager_load=True)
        ...     # AssertionError if > 5 queries executed
    """
    query_logger = enable_query_logging(detect_n1=True)
    query_logger.reset()

    try:
        yield query_logger
    finally:
        stats = query_logger.get_stats()
        query_logger.print_summary()
        disable_query_logging()

        if stats['total_queries'] > threshold:
            raise AssertionError(
                f"N+1 query pattern detected: {stats['total_queries']} queries executed "
                f"(threshold: {threshold})"
            )


# ============================================================================
# Development Helpers
# ============================================================================

def print_query_plan(db_session, query):
    """
    Print PostgreSQL EXPLAIN ANALYZE for a query.

    Args:
        db_session: SQLAlchemy session
        query: SQLAlchemy query object

    Example:
        >>> query = db.query(Patient).filter(Patient.doctor_id == doctor_id)
        >>> print_query_plan(db, query)
    """
    from sqlalchemy import text

    # Get query string
    query_str = str(query.statement.compile(
        dialect=db_session.bind.dialect,
        compile_kwargs={"literal_binds": True}
    ))

    # Run EXPLAIN ANALYZE
    result = db_session.execute(text(f"EXPLAIN ANALYZE {query_str}"))

    import logging
    logger = logging.getLogger(__name__)

    plan_lines = ["\n" + "="*80, "QUERY EXECUTION PLAN", "="*80, query_str, "\n" + "-"*80]
    for row in result:
        plan_lines.append(row[0])
    plan_lines.append("="*80 + "\n")

    logger.info("\n".join(plan_lines), extra={"query": query_str, "analysis_type": "execution_plan"})


def analyze_repository_queries(repo_class, method_name: str, *args, **kwargs):
    """
    Analyze queries executed by a repository method.

    Example:
        >>> from app.repositories.patient import PatientRepository
        >>> analyze_repository_queries(PatientRepository, 'get_all_active', limit=100)
    """
    from app.core.database import get_db

    db = next(get_db())
    repo = repo_class(db)

    with query_logging_context() as logger:
        method = getattr(repo, method_name)
        result = method(*args, **kwargs)

        import logging
        log = logging.getLogger(__name__)
        log.info(
            "Repository query analysis",
            extra={
                "repository": repo_class.__name__,
                "method": method_name,
                "args": str(args),
                "kwargs": str(kwargs),
                "result_count": len(result) if hasattr(result, '__len__') else 'N/A'
            }
        )
        logger.print_summary()


if __name__ == "__main__":
    # Example usage
    import logging
    logger = logging.getLogger(__name__)

    logger.info("Query Logging Utilities")
    logger.info("\nExample 1: Enable query logging")
    logger.info("  from app.core.query_logging import enable_query_logging")
    logger.info("  logger = enable_query_logging(level='INFO')")
    logger.info("  # ... perform operations ...")
    logger.info("  logger.print_summary()")

    logger.info("\nExample 2: Context manager")
    logger.info("  with query_logging_context() as logger:")
    logger.info("      patients = repo.get_all_active(limit=100)")
    logger.info("      # Automatically prints summary on exit")

    logger.info("\nExample 3: Monitor N+1 patterns")
    logger.info("  with monitor_n1_queries(threshold=10):")
    logger.info("      patients = repo.get_all_active(limit=100)")
    logger.info("      # Raises AssertionError if > 10 queries")
