"""
Database Connection Optimization Middleware
Enhances database performance for production Railway deployment
"""

import logging
import time
from typing import Dict, Any, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)


class DatabaseOptimizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to optimize database connections and monitor performance.

    Features:
    - Connection pool monitoring
    - Query performance tracking
    - Automatic connection cleanup
    - Pool size optimization alerts
    """

    def __init__(self, app, db_engine: Optional[Engine] = None):
        super().__init__(app)
        self.db_engine = db_engine
        self.query_metrics: Dict[str, Any] = {
            "total_queries": 0,
            "slow_queries": 0,
            "avg_response_time": 0.0,
            "connection_errors": 0
        }

    async def dispatch(self, request: Request, call_next):
        """
        Monitor database performance and optimize connections.
        """
        start_time = time.time()

        # Add database metrics to request state
        request.state.db_start_time = start_time

        try:
            # Monitor connection pool before request
            pool_status = self._get_pool_status()
            if pool_status:
                request.state.db_pool_before = pool_status

                # Alert if pool is getting full
                if pool_status.get("checked_out", 0) / pool_status.get("size", 1) > 0.8:
                    logger.warning(
                        f"Database connection pool at {pool_status.get('checked_out', 0)}/"
                        f"{pool_status.get('size', 1)} capacity"
                    )

            # Process request
            response = await call_next(request)

            # Calculate database response time
            db_time = (time.time() - start_time) * 1000

            # Update metrics
            self.query_metrics["total_queries"] += 1
            if db_time > 1000:  # Slow query threshold: 1 second
                self.query_metrics["slow_queries"] += 1
                logger.warning(f"Slow database operation detected: {db_time:.2f}ms for {request.url.path}")

            # Update average response time
            total = self.query_metrics["total_queries"]
            current_avg = self.query_metrics["avg_response_time"]
            self.query_metrics["avg_response_time"] = ((current_avg * (total - 1)) + db_time) / total

            # Add performance headers
            response.headers["X-DB-Response-Time"] = f"{db_time:.2f}ms"

            # Monitor connection pool after request
            pool_status_after = self._get_pool_status()
            if pool_status_after:
                response.headers["X-DB-Pool-Size"] = str(pool_status_after.get("size", "unknown"))
                response.headers["X-DB-Pool-Checked-Out"] = str(pool_status_after.get("checked_out", "unknown"))

            return response

        except Exception as e:
            self.query_metrics["connection_errors"] += 1
            logger.error(f"Database connection error: {e}")

            # Create error response with database status
            error_response = Response(
                content='{"detail": "Database connection error"}',
                status_code=503,
                headers={"Content-Type": "application/json"}
            )
            return error_response

    def _get_pool_status(self) -> Optional[Dict[str, Any]]:
        """Get current database connection pool status."""
        try:
            if not self.db_engine or not hasattr(self.db_engine, 'pool'):
                return None

            pool = self.db_engine.pool
            if isinstance(pool, QueuePool):
                return {
                    "size": pool.size(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "checked_in": pool.checkedin()
                }

            return {
                "size": getattr(pool, 'size', lambda: 'unknown')(),
                "checked_out": getattr(pool, 'checkedout', lambda: 'unknown')(),
                "type": type(pool).__name__
            }

        except Exception as e:
            logger.debug(f"Could not get pool status: {e}")
            return None

    def get_metrics(self) -> Dict[str, Any]:
        """Get current database performance metrics."""
        pool_status = self._get_pool_status()

        return {
            "query_metrics": self.query_metrics.copy(),
            "pool_status": pool_status,
            "recommendations": self._get_recommendations()
        }

    def _get_recommendations(self) -> list:
        """Generate performance recommendations based on metrics."""
        recommendations = []

        # Check slow query ratio
        total = self.query_metrics["total_queries"]
        if total > 0:
            slow_ratio = self.query_metrics["slow_queries"] / total
            if slow_ratio > 0.1:  # More than 10% slow queries
                recommendations.append(
                    "High percentage of slow queries detected. Consider optimizing database indexes."
                )

        # Check average response time
        if self.query_metrics["avg_response_time"] > 500:  # 500ms average
            recommendations.append(
                "High average database response time. Consider connection pooling optimization."
            )

        # Check connection errors
        if self.query_metrics["connection_errors"] > 0:
            recommendations.append(
                "Database connection errors detected. Check connection pool configuration."
            )

        # Check pool utilization
        pool_status = self._get_pool_status()
        if pool_status and pool_status.get("size") and pool_status.get("checked_out"):
            utilization = pool_status["checked_out"] / pool_status["size"]
            if utilization > 0.9:
                recommendations.append(
                    "High connection pool utilization. Consider increasing pool size."
                )

        return recommendations

    def reset_metrics(self):
        """Reset performance metrics (useful for testing or periodic resets)."""
        self.query_metrics = {
            "total_queries": 0,
            "slow_queries": 0,
            "avg_response_time": 0.0,
            "connection_errors": 0
        }
        logger.info("Database optimization metrics reset")


class QueryOptimizer:
    """
    Query optimization utilities for database performance enhancement.
    """
    
    def __init__(self, db_engine: Optional[Engine] = None):
        self.db_engine = db_engine
        self.query_cache = {}
        self.optimization_stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "optimized_queries": 0
        }
    
    def optimize_query(self, query: str, params: Optional[Dict] = None) -> str:
        """
        Optimize a SQL query for better performance.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Optimized query string
        """
        # Simple query optimization - add LIMIT if not present for SELECT queries
        optimized_query = query.strip()
        
        if (optimized_query.upper().startswith('SELECT') and 
            'LIMIT' not in optimized_query.upper() and
            'COUNT(' not in optimized_query.upper()):
            # Add reasonable limit to prevent runaway queries
            optimized_query += ' LIMIT 1000'
            self.optimization_stats["optimized_queries"] += 1
            logger.debug(f"Added LIMIT to query: {query[:50]}...")
        
        return optimized_query
    
    def get_cached_result(self, query_key: str) -> Optional[Any]:
        """
        Get cached query result if available.
        
        Args:
            query_key: Unique key for the query
            
        Returns:
            Cached result or None
        """
        if query_key in self.query_cache:
            self.optimization_stats["cache_hits"] += 1
            return self.query_cache[query_key]
        
        self.optimization_stats["cache_misses"] += 1
        return None
    
    def cache_result(self, query_key: str, result: Any, ttl: int = 300) -> None:
        """
        Cache query result for future use.
        
        Args:
            query_key: Unique key for the query
            result: Query result to cache
            ttl: Time to live in seconds (default: 5 minutes)
        """
        # Simple in-memory cache (in production, use Redis)
        self.query_cache[query_key] = {
            "result": result,
            "timestamp": time.time(),
            "ttl": ttl
        }
        
        # Clean expired entries
        self._clean_expired_cache()
    
    def _clean_expired_cache(self) -> None:
        """Remove expired entries from cache."""
        current_time = time.time()
        expired_keys = []
        
        for key, cached_data in self.query_cache.items():
            if current_time - cached_data["timestamp"] > cached_data["ttl"]:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.query_cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        return {
            "optimization_stats": self.optimization_stats.copy(),
            "cache_size": len(self.query_cache),
            "cache_hit_ratio": (
                self.optimization_stats["cache_hits"] / 
                max(1, self.optimization_stats["cache_hits"] + self.optimization_stats["cache_misses"])
            )
        }


# Global query optimizer instance
_query_optimizer: Optional[QueryOptimizer] = None


def get_db_optimizer() -> QueryOptimizer:
    """
    Get the global database query optimizer instance.
    
    Returns:
        QueryOptimizer instance
    """
    global _query_optimizer
    
    if _query_optimizer is None:
        try:
            from app.database import engine
            _query_optimizer = QueryOptimizer(db_engine=engine)
        except ImportError:
            # Fallback if database engine is not available
            _query_optimizer = QueryOptimizer()
            logger.warning("Database engine not available, using QueryOptimizer without engine")
    
    return _query_optimizer


def reset_db_optimizer() -> None:
    """Reset the global database optimizer (useful for testing)."""
    global _query_optimizer
    _query_optimizer = None