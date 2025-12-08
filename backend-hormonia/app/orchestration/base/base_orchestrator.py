"""
Base orchestrator providing common infrastructure for all orchestrators.

This module eliminates duplicate database session management, logging setup,
health check logic, and metrics tracking across all orchestrator implementations.

Provides:
- Database session lifecycle management
- Structured logging with correlation IDs
- Health check framework
- Metrics collection and tracking
- Standard error handling patterns
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

from sqlalchemy.orm import Session


class BaseOrchestrator(ABC):
    """
    Base class for all orchestrators providing common infrastructure.

    This abstract base class consolidates duplicate code patterns found across
    FlowOrchestrator, SagaOrchestrator, and FlowManagerAdapter. It provides
    standardized database session management, logging, health checks, and metrics.

    Responsibilities:
    1. Database session lifecycle management
    2. Structured logging with context and correlation IDs
    3. Health check framework with component status
    4. Basic metrics tracking (execution count, errors, timing)
    5. Standard error handling and recovery patterns

    Example:
        >>> class MyOrchestrator(BaseOrchestrator):
        ...     def __init__(self, db: Session):
        ...         super().__init__(db, service_name="MyOrchestrator")
        ...
        ...     async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        ...         self.log_info("Starting execution", extra=context)
        ...         # Use self.db, self.logger
        ...         result = await self._do_work(context)
        ...         self.track_execution()
        ...         return result
        ...
        ...     def validate(self, context: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        ...         if not context.get('required_field'):
        ...             return False, "Missing required_field"
        ...         return True, None

    Attributes:
        db (Session): Database session for orchestrator operations
        service_name (str): Service name for logging and identification
        logger (Logger): Configured logger instance
        enable_health_checks (bool): Whether health checks are enabled
    """

    def __init__(
        self,
        db: Session,
        service_name: Optional[str] = None,
        enable_health_checks: bool = True,
    ):
        """
        Initialize base orchestrator with common infrastructure.

        Args:
            db: SQLAlchemy database session
            service_name: Service name for logging (default: class name)
            enable_health_checks: Enable health check endpoint (default: True)
        """
        self.db = db
        self.service_name = service_name or self.__class__.__name__
        self.logger = logging.getLogger(f"{__name__}.{self.service_name}")
        self.enable_health_checks = enable_health_checks

        # Metrics tracking
        self._execution_count = 0
        self._error_count = 0
        self._last_execution_time: Optional[str] = None
        self._last_error_time: Optional[str] = None

        self.logger.info(
            f"{self.service_name} initialized",
            extra={
                "service": self.service_name,
                "enable_health_checks": enable_health_checks,
            },
        )

    # ===============================
    # Abstract Methods (Must Implement)
    # ===============================

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute orchestrator logic (must implement in subclass).

        Args:
            context: Execution context with required parameters

        Returns:
            Execution result dictionary

        Raises:
            NotImplementedError: If not implemented in subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement execute() method"
        )

    @abstractmethod
    def validate(self, context: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate context before execution (must implement in subclass).

        Args:
            context: Context to validate

        Returns:
            Tuple of (is_valid, error_message)
                - is_valid: True if context is valid
                - error_message: None if valid, error description if invalid

        Raises:
            NotImplementedError: If not implemented in subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement validate() method"
        )

    # ===============================
    # Structured Logging
    # ===============================

    def log_info(self, message: str, extra: Optional[Dict] = None):
        """
        Log informational message with structured context.

        Args:
            message: Log message
            extra: Additional context data
        """
        self.logger.info(
            message, extra={"service": self.service_name, **(extra or {})}
        )

    def log_warning(self, message: str, extra: Optional[Dict] = None):
        """
        Log warning message with structured context.

        Args:
            message: Warning message
            extra: Additional context data
        """
        self.logger.warning(
            message, extra={"service": self.service_name, **(extra or {})}
        )

    def log_error(self, message: str, error: Exception, extra: Optional[Dict] = None):
        """
        Log error with full context and exception information.

        Args:
            message: Error description
            error: Exception that occurred
            extra: Additional context data
        """
        self.logger.error(
            message,
            exc_info=True,
            extra={
                "service": self.service_name,
                "error_type": type(error).__name__,
                "error_message": str(error),
                **(extra or {}),
            },
        )
        self.track_error()

    # ===============================
    # Health Check Framework
    # ===============================

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check of orchestrator and dependencies.

        Returns:
            Health status dictionary with:
                - service: Service name
                - overall_healthy: Boolean overall health status
                - components: Dict of component health statuses
                - metrics: Execution and error metrics
                - timestamp: ISO timestamp of health check

        Example:
            >>> health = await orchestrator.health_check()
            >>> print(health)
            {
                "service": "MyOrchestrator",
                "overall_healthy": True,
                "components": {
                    "database": {"healthy": True}
                },
                "metrics": {
                    "execution_count": 42,
                    "error_count": 1,
                    "last_execution": "2025-11-15T21:00:00"
                },
                "timestamp": "2025-11-15T21:30:00"
            }
        """
        if not self.enable_health_checks:
            return {
                "service": self.service_name,
                "healthy": True,
                "message": "Health checks disabled",
                "timestamp": datetime.utcnow().isoformat(),
            }

        health = {
            "service": self.service_name,
            "overall_healthy": True,
            "components": {},
            "metrics": {
                "execution_count": self._execution_count,
                "error_count": self._error_count,
                "last_execution": self._last_execution_time,
                "last_error": self._last_error_time,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Check database connectivity
        try:
            self.db.execute("SELECT 1")
            health["components"]["database"] = {"healthy": True}
        except Exception as e:
            health["components"]["database"] = {
                "healthy": False,
                "error": str(e),
                "error_type": type(e).__name__,
            }
            health["overall_healthy"] = False

        return health

    # ===============================
    # Metrics Tracking
    # ===============================

    def track_execution(self):
        """
        Track successful execution for metrics.

        Updates:
            - Increments execution count
            - Records timestamp of last execution
        """
        self._execution_count += 1
        self._last_execution_time = datetime.utcnow().isoformat()

    def track_error(self):
        """
        Track error occurrence for metrics.

        Updates:
            - Increments error count
            - Records timestamp of last error
        """
        self._error_count += 1
        self._last_error_time = datetime.utcnow().isoformat()

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current orchestrator metrics.

        Returns:
            Metrics dictionary with execution stats
        """
        return {
            "service": self.service_name,
            "execution_count": self._execution_count,
            "error_count": self._error_count,
            "last_execution_time": self._last_execution_time,
            "last_error_time": self._last_error_time,
            "error_rate": (
                self._error_count / self._execution_count
                if self._execution_count > 0
                else 0
            ),
        }

    def reset_metrics(self):
        """Reset all metrics counters (useful for testing)."""
        self._execution_count = 0
        self._error_count = 0
        self._last_execution_time = None
        self._last_error_time = None
        self.log_info("Metrics reset")
