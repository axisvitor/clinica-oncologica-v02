"""
Error Handler Module - Error Handling and Management

Handles errors and exceptions in flow operations.
"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, field
from uuid import UUID


logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FlowError:
    """Flow error representation."""
    error_type: str
    message: str
    severity: ErrorSeverity
    patient_id: Optional[UUID] = None
    flow_type: Optional[str] = None
    operation: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True


class FlowErrorHandler:
    """
    Handles errors in flow operations.

    Responsibilities:
    - Catch and classify errors
    - Determine error severity
    - Execute error recovery strategies
    - Log errors with context
    - Track error patterns
    """

    def __init__(self):
        """Initialize FlowErrorHandler."""
        self.error_counts: Dict[str, int] = {}
        self.error_callbacks: List[callable] = []

        logger.info("FlowErrorHandler initialized")

    async def handle_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        operation: str
    ) -> FlowError:
        """
        Handle an error that occurred during flow operation.

        Args:
            error: The exception that occurred
            context: Operation context
            operation: Operation being performed

        Returns:
            FlowError object
        """
        flow_error = self._classify_error(error, context, operation)

        # Log the error
        self._log_error(flow_error)

        # Track error count
        self._track_error(flow_error)

        # Execute error callbacks
        await self._execute_error_callbacks(flow_error)

        return flow_error

    def _classify_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        operation: str
    ) -> FlowError:
        """
        Classify error and determine severity.

        Args:
            error: The exception
            context: Operation context
            operation: Operation being performed

        Returns:
            Classified FlowError
        """
        error_type = type(error).__name__
        error_message = str(error)

        # Determine severity based on error type
        if isinstance(error, (ConnectionError, TimeoutError)):
            severity = ErrorSeverity.HIGH
            recoverable = True
        elif isinstance(error, ValueError):
            severity = ErrorSeverity.MEDIUM
            recoverable = True
        elif isinstance(error, KeyError):
            severity = ErrorSeverity.MEDIUM
            recoverable = False
        else:
            severity = ErrorSeverity.MEDIUM
            recoverable = True

        return FlowError(
            error_type=error_type,
            message=error_message,
            severity=severity,
            patient_id=context.get('patient_id'),
            flow_type=context.get('flow_type'),
            operation=operation,
            metadata={
                'context': context,
                'error_details': {
                    'type': error_type,
                    'args': error.args
                }
            },
            recoverable=recoverable
        )

    def _log_error(self, flow_error: FlowError):
        """
        Log error with appropriate level.

        Args:
            flow_error: FlowError object
        """
        log_message = (
            f"Flow error in {flow_error.operation}: {flow_error.message} "
            f"(severity: {flow_error.severity}, patient: {flow_error.patient_id})"
        )

        if flow_error.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message, extra={'flow_error': flow_error})
        elif flow_error.severity == ErrorSeverity.HIGH:
            logger.error(log_message, extra={'flow_error': flow_error})
        elif flow_error.severity == ErrorSeverity.MEDIUM:
            logger.warning(log_message, extra={'flow_error': flow_error})
        else:
            logger.info(log_message, extra={'flow_error': flow_error})

    def _track_error(self, flow_error: FlowError):
        """
        Track error occurrence.

        Args:
            flow_error: FlowError object
        """
        error_key = f"{flow_error.error_type}:{flow_error.operation}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1

        logger.debug(f"Error count for {error_key}: {self.error_counts[error_key]}")

    async def _execute_error_callbacks(self, flow_error: FlowError):
        """
        Execute registered error callbacks.

        Args:
            flow_error: FlowError object
        """
        for callback in self.error_callbacks:
            try:
                await callback(flow_error)
            except Exception as e:
                logger.error(f"Error executing error callback: {e}")

    def register_error_callback(self, callback: callable):
        """
        Register error callback.

        Args:
            callback: Callback function
        """
        self.error_callbacks.append(callback)
        logger.info("Error callback registered")

    def get_error_stats(self) -> Dict[str, Any]:
        """
        Get error statistics.

        Returns:
            Error statistics dictionary
        """
        return {
            'total_errors': sum(self.error_counts.values()),
            'error_counts_by_type': self.error_counts.copy(),
            'unique_error_types': len(self.error_counts)
        }

    def clear_error_stats(self):
        """Clear error statistics."""
        self.error_counts.clear()
        logger.info("Error statistics cleared")
