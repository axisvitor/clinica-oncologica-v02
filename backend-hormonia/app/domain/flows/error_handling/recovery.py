"""
Error Recovery Module - Recovery Strategies

Implements recovery strategies for different error scenarios.
"""

import logging
import asyncio
from typing import Dict, Any, Callable


logger = logging.getLogger(__name__)


class RecoveryStrategy:
    """Base class for recovery strategies."""

    async def execute(self, context: Dict[str, Any]) -> bool:
        """
        Execute recovery strategy.

        Args:
            context: Recovery context

        Returns:
            True if recovery successful
        """
        raise NotImplementedError


class RetryRecoveryStrategy(RecoveryStrategy):
    """Retry operation with exponential backoff."""

    def __init__(
        self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0
    ):
        """
        Initialize RetryRecoveryStrategy.

        Args:
            max_retries: Maximum number of retries
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def execute(self, context: Dict[str, Any]) -> bool:
        """
        Execute retry with exponential backoff.

        Args:
            context: Recovery context with 'operation' callable

        Returns:
            True if retry successful
        """
        operation = context.get("operation")
        if not operation:
            logger.error("No operation provided for retry")
            return False

        for attempt in range(self.max_retries):
            try:
                # Calculate delay
                delay = min(self.base_delay * (2**attempt), self.max_delay)

                if attempt > 0:
                    logger.info(
                        f"Retry attempt {attempt + 1}/{self.max_retries} after {delay}s"
                    )
                    await asyncio.sleep(delay)

                # Execute operation
                await operation() if asyncio.iscoroutinefunction(
                    operation
                ) else operation()

                logger.info(f"Retry successful on attempt {attempt + 1}")
                return True

            except Exception as e:
                logger.warning(f"Retry attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    logger.error("All retry attempts exhausted")
                    return False

        return False


class FallbackRecoveryStrategy(RecoveryStrategy):
    """Use fallback operation on error."""

    def __init__(self, fallback_operation: Callable):
        """
        Initialize FallbackRecoveryStrategy.

        Args:
            fallback_operation: Fallback operation to execute
        """
        self.fallback_operation = fallback_operation

    async def execute(self, context: Dict[str, Any]) -> bool:
        """
        Execute fallback operation.

        Args:
            context: Recovery context

        Returns:
            True if fallback successful
        """
        try:
            if asyncio.iscoroutinefunction(self.fallback_operation):
                await self.fallback_operation(context)
            else:
                self.fallback_operation(context)

            logger.info("Fallback recovery successful")
            return True

        except Exception as e:
            logger.error(f"Fallback recovery failed: {e}")
            return False


class ErrorRecoveryManager:
    """
    Manages error recovery strategies.

    Responsibilities:
    - Select appropriate recovery strategy
    - Execute recovery operations
    - Track recovery success rates
    - Escalate unrecoverable errors
    """

    def __init__(self):
        """Initialize ErrorRecoveryManager."""
        self.recovery_strategies: Dict[str, RecoveryStrategy] = {}
        self.recovery_stats: Dict[str, Dict[str, int]] = {}

        logger.info("ErrorRecoveryManager initialized")

    def register_strategy(self, error_type: str, strategy: RecoveryStrategy):
        """
        Register recovery strategy for error type.

        Args:
            error_type: Error type identifier
            strategy: Recovery strategy
        """
        self.recovery_strategies[error_type] = strategy
        logger.info(f"Recovery strategy registered for {error_type}")

    async def recover(self, error_type: str, context: Dict[str, Any]) -> bool:
        """
        Attempt to recover from error.

        Args:
            error_type: Error type
            context: Recovery context

        Returns:
            True if recovery successful
        """
        strategy = self.recovery_strategies.get(error_type)

        if not strategy:
            logger.warning(f"No recovery strategy for error type: {error_type}")
            return False

        try:
            success = await strategy.execute(context)

            # Track recovery stats
            self._track_recovery(error_type, success)

            return success

        except Exception as e:
            logger.error(f"Recovery execution failed: {e}")
            self._track_recovery(error_type, False)
            return False

    def _track_recovery(self, error_type: str, success: bool):
        """
        Track recovery statistics.

        Args:
            error_type: Error type
            success: Whether recovery was successful
        """
        if error_type not in self.recovery_stats:
            self.recovery_stats[error_type] = {"successful": 0, "failed": 0}

        if success:
            self.recovery_stats[error_type]["successful"] += 1
        else:
            self.recovery_stats[error_type]["failed"] += 1

    def get_recovery_stats(self) -> Dict[str, Any]:
        """
        Get recovery statistics.

        Returns:
            Recovery statistics
        """
        total_attempts = sum(
            stats["successful"] + stats["failed"]
            for stats in self.recovery_stats.values()
        )

        total_successful = sum(
            stats["successful"] for stats in self.recovery_stats.values()
        )

        return {
            "total_attempts": total_attempts,
            "total_successful": total_successful,
            "success_rate": (total_successful / total_attempts * 100)
            if total_attempts > 0
            else 0,
            "by_error_type": self.recovery_stats.copy(),
        }
