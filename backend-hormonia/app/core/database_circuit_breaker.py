"""
Database Circuit Breaker for protecting database operations.

This module extends the existing circuit breaker pattern specifically for
database operations with configurable failure thresholds and recovery timeouts.
"""

import logging
from typing import Callable, Any, Optional, Dict
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager

from sqlalchemy.exc import SQLAlchemyError

from app.services.circuit_breaker import CircuitBreaker, CircuitState, CircuitOpenError
from app.core.graceful_error_handler import graceful_error_handler
from app.core.database import get_scoped_session


logger = logging.getLogger(__name__)


class DatabaseCircuitBreaker(CircuitBreaker):
    """
    Specialized circuit breaker for database operations.

    Provides database-specific error handling, fallback mechanisms,
    and recovery strategies for database connectivity issues.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: int = 30,
        success_threshold: int = 2,
        enable_fallback: bool = True,
    ):
        """
        Initialize database circuit breaker.

        Args:
            name: Circuit breaker name
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before half-opening
            success_threshold: Successes needed to close from half-open
            enable_fallback: Whether to enable fallback mechanisms
        """
        super().__init__(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=SQLAlchemyError,
            success_threshold=success_threshold,
        )
        self.enable_fallback = enable_fallback
        self._connection_pool_healthy = True
        self._last_health_check = None

    async def execute_query(
        self,
        query_func: Callable,
        *args,
        fallback_data: Optional[Any] = None,
        operation_name: str = "database_operation",
        **kwargs,
    ) -> Any:
        """
        Execute database query with circuit breaker protection.

        Args:
            query_func: Database query function to execute
            *args: Function arguments
            fallback_data: Data to return if circuit is open
            operation_name: Name of the operation for logging
            **kwargs: Function keyword arguments

        Returns:
            Query result or fallback data

        Raises:
            ErrorResponse: If circuit is open and no fallback available
        """

        async def fallback():
            if fallback_data is not None:
                logger.warning(
                    f"Database circuit {self.name} using fallback for {operation_name}"
                )
                return fallback_data

            # Generate appropriate fallback based on operation
            return await self._generate_smart_fallback(operation_name)

        try:
            return await self.call(query_func, *args, fallback=fallback, **kwargs)
        except CircuitOpenError:
            # Circuit is open, handle gracefully
            error_response = await graceful_error_handler.handle_database_error(
                error=Exception(f"Database circuit {self.name} is open"),
                operation=operation_name,
                query_context={
                    "circuit_state": "open",
                    "fallback_enabled": self.enable_fallback,
                },
            )

            if self.enable_fallback and fallback_data is not None:
                return await graceful_error_handler.handle_graceful_degradation(
                    primary_error=Exception(f"Circuit {self.name} open"),
                    fallback_data=fallback_data,
                    operation=operation_name,
                )

            raise await (
                graceful_error_handler.create_http_exception_from_error_response(
                    error_response
                )
            )

    async def execute_transaction(
        self,
        transaction_func: Callable,
        *args,
        rollback_on_circuit_open: bool = True,
        **kwargs,
    ) -> Any:
        """
        Execute database transaction with circuit breaker protection.

        Args:
            transaction_func: Transaction function to execute
            *args: Function arguments
            rollback_on_circuit_open: Whether to rollback on circuit open
            **kwargs: Function keyword arguments

        Returns:
            Transaction result

        Raises:
            ErrorResponse: If transaction fails or circuit is open
        """
        if self.state == CircuitState.OPEN:
            error_response = await graceful_error_handler.handle_database_error(
                error=Exception(f"Database circuit {self.name} is open"),
                operation="database_transaction",
                query_context={"circuit_state": "open", "transaction": True},
            )
            raise await (
                graceful_error_handler.create_http_exception_from_error_response(
                    error_response
                )
            )

        try:
            return await self.call(transaction_func, *args, **kwargs)
        except SQLAlchemyError as e:
            # Handle database-specific errors
            error_response = await graceful_error_handler.handle_database_error(
                error=e,
                operation="database_transaction",
                query_context={
                    "transaction": True,
                    "rollback": rollback_on_circuit_open,
                },
            )
            raise await (
                graceful_error_handler.create_http_exception_from_error_response(
                    error_response
                )
            )

    async def health_check(self) -> bool:
        """
        Perform database health check.

        Returns:
            True if database is healthy, False otherwise
        """
        try:
            with get_scoped_session() as session:
                # Simple health check query
                session.execute("SELECT 1")
                self._connection_pool_healthy = True
                self._last_health_check = datetime.now(timezone.utc)
                return True
        except Exception as e:
            logger.warning(f"Database health check failed for {self.name}: {e}")
            self._connection_pool_healthy = False
            self._last_health_check = datetime.now(timezone.utc)
            return False

    async def _generate_smart_fallback(self, operation_name: str) -> Any:
        """
        Generate intelligent fallback data based on operation type.

        Args:
            operation_name: Name of the operation

        Returns:
            Appropriate fallback data
        """
        operation_lower = operation_name.lower()

        if "list" in operation_lower or "get_all" in operation_lower:
            return []
        elif "count" in operation_lower:
            return 0
        elif "exists" in operation_lower or "check" in operation_lower:
            return False
        elif "get" in operation_lower or "find" in operation_lower:
            return None
        elif "analytics" in operation_lower or "dashboard" in operation_lower:
            return {
                "data": [],
                "total": 0,
                "message": "Analytics temporarily unavailable",
            }
        else:
            return None

    def is_healthy(self) -> bool:
        """
        Check if the database connection is healthy.

        Returns:
            True if healthy, False otherwise
        """
        if self._last_health_check is None:
            return True  # Assume healthy until proven otherwise

        # Consider unhealthy if last check was more than 5 minutes ago
        time_since_check = datetime.now(timezone.utc) - self._last_health_check
        if time_since_check > timedelta(minutes=5):
            return True  # Assume recovered if no recent check

        return self._connection_pool_healthy

    def get_detailed_stats(self) -> Dict[str, Any]:
        """
        Get detailed statistics including health information.

        Returns:
            Detailed statistics dictionary
        """
        stats = self.get_stats()
        stats.update(
            {
                "connection_pool_healthy": self._connection_pool_healthy,
                "last_health_check": (
                    self._last_health_check.isoformat()
                    if self._last_health_check
                    else None
                ),
                "fallback_enabled": self.enable_fallback,
            }
        )
        return stats


class DatabaseCircuitBreakerManager:
    """
    Manager for multiple database circuit breakers.

    Provides centralized management of circuit breakers for different
    database operations and connection pools.
    """

    def __init__(self):
        """Initialize database circuit breaker manager."""
        self.breakers: Dict[str, DatabaseCircuitBreaker] = {}
        self._initialize_default_breakers()

    def _initialize_default_breakers(self):
        """Initialize default circuit breakers for common operations."""
        self.breakers.update(
            {
                "read_operations": DatabaseCircuitBreaker(
                    name="database_read",
                    failure_threshold=5,
                    recovery_timeout=30,
                    enable_fallback=True,
                ),
                "write_operations": DatabaseCircuitBreaker(
                    name="database_write",
                    failure_threshold=3,
                    recovery_timeout=60,
                    enable_fallback=False,  # Don't fallback for writes
                ),
                "analytics_queries": DatabaseCircuitBreaker(
                    name="database_analytics",
                    failure_threshold=3,
                    recovery_timeout=45,
                    enable_fallback=True,
                ),
                "user_operations": DatabaseCircuitBreaker(
                    name="database_users",
                    failure_threshold=3,
                    recovery_timeout=30,
                    enable_fallback=True,
                ),
                "message_operations": DatabaseCircuitBreaker(
                    name="database_messages",
                    failure_threshold=5,
                    recovery_timeout=30,
                    enable_fallback=True,
                ),
            }
        )

    def get_breaker(self, operation_type: str) -> DatabaseCircuitBreaker:
        """
        Get circuit breaker for specific operation type.

        Args:
            operation_type: Type of database operation

        Returns:
            Appropriate circuit breaker
        """
        if operation_type not in self.breakers:
            # Create a default breaker for unknown operations
            self.breakers[operation_type] = DatabaseCircuitBreaker(
                name=f"database_{operation_type}",
                failure_threshold=3,
                recovery_timeout=30,
            )

        return self.breakers[operation_type]

    async def execute_read_operation(
        self, query_func: Callable, *args, fallback_data: Optional[Any] = None, **kwargs
    ) -> Any:
        """Execute read operation with circuit breaker protection."""
        breaker = self.get_breaker("read_operations")
        return await breaker.execute_query(
            query_func,
            *args,
            fallback_data=fallback_data,
            operation_name="read_operation",
            **kwargs,
        )

    async def execute_write_operation(
        self, query_func: Callable, *args, **kwargs
    ) -> Any:
        """Execute write operation with circuit breaker protection."""
        breaker = self.get_breaker("write_operations")
        return await breaker.execute_query(
            query_func, *args, operation_name="write_operation", **kwargs
        )

    async def execute_analytics_query(
        self, query_func: Callable, *args, fallback_data: Optional[Any] = None, **kwargs
    ) -> Any:
        """Execute analytics query with circuit breaker protection."""
        breaker = self.get_breaker("analytics_queries")
        return await breaker.execute_query(
            query_func,
            *args,
            fallback_data=fallback_data or {"data": [], "total": 0},
            operation_name="analytics_query",
            **kwargs,
        )

    async def health_check_all(self) -> Dict[str, bool]:
        """
        Perform health check on all circuit breakers.

        Returns:
            Dictionary of breaker names and their health status
        """
        health_status = {}
        for name, breaker in self.breakers.items():
            health_status[name] = await breaker.health_check()
        return health_status

    def get_all_stats(self) -> Dict[str, Any]:
        """
        Get statistics for all circuit breakers.

        Returns:
            Dictionary of all breaker statistics
        """
        return {
            name: breaker.get_detailed_stats()
            for name, breaker in self.breakers.items()
        }

    def reset_all(self):
        """Reset all circuit breakers."""
        for breaker in self.breakers.values():
            breaker.reset()

    def reset_breaker(self, operation_type: str):
        """Reset specific circuit breaker."""
        if operation_type in self.breakers:
            self.breakers[operation_type].reset()

    @asynccontextmanager
    async def protected_operation(
        self, operation_type: str, fallback_data: Optional[Any] = None
    ):
        """
        Context manager for protected database operations.

        Args:
            operation_type: Type of operation
            fallback_data: Fallback data if circuit is open

        Usage:
            async with db_circuit_manager.protected_operation("read_operations"):
                result = session.query(Model).all()
        """
        breaker = self.get_breaker(operation_type)

        if breaker.state == CircuitState.OPEN:
            if fallback_data is not None:
                yield await graceful_error_handler.handle_graceful_degradation(
                    primary_error=Exception(f"Circuit {operation_type} is open"),
                    fallback_data=fallback_data,
                    operation=operation_type,
                )
                return
            else:
                error_response = await graceful_error_handler.handle_database_error(
                    error=Exception(f"Database circuit {operation_type} is open"),
                    operation=operation_type,
                    query_context={"circuit_state": "open"},
                )
                raise await (
                    graceful_error_handler.create_http_exception_from_error_response(
                        error_response
                    )
                )

        try:
            yield
            await breaker._on_success()
        except SQLAlchemyError as e:
            await breaker._on_failure()
            error_response = await graceful_error_handler.handle_database_error(
                error=e, operation=operation_type
            )
            raise await (
                graceful_error_handler.create_http_exception_from_error_response(
                    error_response
                )
            )


# Global database circuit breaker manager
_db_circuit_manager: Optional[DatabaseCircuitBreakerManager] = None


def get_db_circuit_manager() -> DatabaseCircuitBreakerManager:
    """
    Get or create database circuit breaker manager instance.

    Returns:
        DatabaseCircuitBreakerManager instance
    """
    global _db_circuit_manager

    if _db_circuit_manager is None:
        _db_circuit_manager = DatabaseCircuitBreakerManager()

    return _db_circuit_manager


# Convenience functions
async def protected_read_query(
    query_func: Callable, *args, fallback_data: Optional[Any] = None, **kwargs
) -> Any:
    """Execute protected read query."""
    manager = get_db_circuit_manager()
    return await manager.execute_read_operation(
        query_func, *args, fallback_data=fallback_data, **kwargs
    )


async def protected_write_query(query_func: Callable, *args, **kwargs) -> Any:
    """Execute protected write query."""
    manager = get_db_circuit_manager()
    return await manager.execute_write_operation(query_func, *args, **kwargs)


async def protected_analytics_query(
    query_func: Callable, *args, fallback_data: Optional[Any] = None, **kwargs
) -> Any:
    """Execute protected analytics query."""
    manager = get_db_circuit_manager()
    return await manager.execute_analytics_query(
        query_func, *args, fallback_data=fallback_data, **kwargs
    )
