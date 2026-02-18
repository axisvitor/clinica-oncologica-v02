"""
Flow Error Handler - Centralized error handling for Flow Services (QW-021).

This module implements the FlowErrorHandler class, which provides
centralized error handling, recovery strategies, and error reporting
for flow execution.

Features:
- Error classification (transient, permanent, user error, system error)
- Automatic recovery strategies
- Error escalation
- Error logging and reporting
- Circuit breaker pattern
- Retry logic with exponential backoff

Migration Note:
    This consolidates error handling logic from:
    - flow_error_handler.py (1,444 LOC - main error handler)
    - error_recovery.py (error recovery strategies)
    - automated_recovery.py (automated recovery)
    - Various error handling scattered across flow services
"""

from typing import Dict, Any, Optional, List, Callable, Tuple
from enum import Enum
import logging
import asyncio
from uuid import UUID

from ..types import FlowContext, FlowStatus
from ..config import get_flow_config
from app.utils.pii_redaction import (
    mask_cpf,
    mask_email,
    mask_name,
    mask_phone,
    mask_pii_in_log_message,
)
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Severity levels for flow errors."""

    LOW = "low"
    """Low severity - informational"""

    MEDIUM = "medium"
    """Medium severity - warning"""

    HIGH = "high"
    """High severity - requires attention"""

    CRITICAL = "critical"
    """Critical severity - immediate action required"""


class ErrorCategory(str, Enum):
    """Categories of flow errors."""

    VALIDATION_ERROR = "validation_error"
    """Input validation failed"""

    EXECUTION_ERROR = "execution_error"
    """Step execution failed"""

    TIMEOUT_ERROR = "timeout_error"
    """Operation timed out"""

    RESOURCE_ERROR = "resource_error"
    """Resource unavailable (DB, API, etc.)"""

    PERMISSION_ERROR = "permission_error"
    """Permission denied"""

    DATA_ERROR = "data_error"
    """Data corruption or inconsistency"""

    INTEGRATION_ERROR = "integration_error"
    """External integration failed"""

    SYSTEM_ERROR = "system_error"
    """System/infrastructure error"""

    USER_ERROR = "user_error"
    """User-caused error (invalid input)"""

    UNKNOWN_ERROR = "unknown_error"
    """Unknown error category"""


class RecoveryStrategy(str, Enum):
    """Recovery strategies for errors."""

    RETRY = "retry"
    """Retry the operation"""

    SKIP = "skip"
    """Skip the failed step"""

    FALLBACK = "fallback"
    """Use fallback logic"""

    MANUAL = "manual"
    """Require manual intervention"""

    CANCEL = "cancel"
    """Cancel the flow"""

    NONE = "none"
    """No recovery possible"""


class FlowError:
    """
    Represents a flow execution error.

    Encapsulates all error information including context, classification,
    and recovery recommendations.
    """

    def __init__(
        self,
        error: Exception,
        context: FlowContext,
        step_id: Optional[str] = None,
        category: ErrorCategory = ErrorCategory.UNKNOWN_ERROR,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        is_transient: bool = False,
        recovery_strategy: Optional[RecoveryStrategy] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize flow error.

        Args:
            error: Original exception
            context: Flow context when error occurred
            step_id: Step ID if error occurred in step
            category: Error category
            severity: Error severity
            is_transient: Whether error is transient (retryable)
            recovery_strategy: Recommended recovery strategy
            metadata: Additional error metadata
        """
        self.error = error
        self.context = context
        self.step_id = step_id
        self.category = category
        self.severity = severity
        self.is_transient = is_transient
        self.recovery_strategy = (
            recovery_strategy or self._determine_recovery_strategy()
        )
        self.metadata = metadata or {}
        self.timestamp = now_sao_paulo()

        # Error details
        self.error_type = type(error).__name__
        self.error_message = str(error)

    def _determine_recovery_strategy(self) -> RecoveryStrategy:
        """Determine recovery strategy based on error characteristics."""
        if self.is_transient:
            return RecoveryStrategy.RETRY
        elif self.category == ErrorCategory.USER_ERROR:
            return RecoveryStrategy.MANUAL
        elif self.category == ErrorCategory.VALIDATION_ERROR:
            return RecoveryStrategy.CANCEL
        elif self.severity == ErrorSeverity.CRITICAL:
            return RecoveryStrategy.MANUAL
        else:
            return RecoveryStrategy.FALLBACK

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary."""
        return {
            "error_type": self.error_type,
            "error_message": self.error_message,
            "category": self.category.value,
            "severity": self.severity.value,
            "is_transient": self.is_transient,
            "recovery_strategy": self.recovery_strategy.value,
            "flow_instance_id": str(self.context.flow_instance_id),
            "step_id": self.step_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<FlowError(type={self.error_type}, "
            f"category={self.category.value}, "
            f"severity={self.severity.value})>"
        )


class FlowErrorHandler:
    """
    Centralized error handler for flow execution.

    Provides error classification, recovery strategies, and logging
    for all flow-related errors.

    Example:
        >>> handler = FlowErrorHandler()
        >>> try:
        ...     await execute_step(...)
        ... except Exception as e:
        ...     flow_error = await handler.handle_error(
        ...         error=e,
        ...         context=context,
        ...         step_id="step_001"
        ...     )
        ...     if flow_error.recovery_strategy == RecoveryStrategy.RETRY:
        ...         await retry_operation()
    """

    def __init__(self):
        """Initialize the error handler."""
        self.config = get_flow_config()
        self.error_history: Dict[UUID, List[FlowError]] = {}
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        logger.info("FlowErrorHandler initialized")

    def _sanitize_log_payload(
        self, payload: Any, key_hint: Optional[str] = None
    ) -> Any:
        """Best-effort sanitization to prevent PII leakage in logs."""
        key = (key_hint or "").lower()
        if isinstance(payload, dict):
            return {
                k: self._sanitize_log_payload(v, key_hint=str(k))
                for k, v in payload.items()
            }
        if isinstance(payload, list):
            return [self._sanitize_log_payload(item, key_hint=key_hint) for item in payload]
        if isinstance(payload, tuple):
            return tuple(self._sanitize_log_payload(item, key_hint=key_hint) for item in payload)
        if isinstance(payload, str):
            if key in {"cpf", "document", "documento"}:
                return mask_cpf(payload)
            if key in {"phone", "phone_number", "telefone", "whatsapp"}:
                return mask_phone(payload)
            if key in {"email", "user_email"}:
                return mask_email(payload)
            if key in {"name", "patient_name", "full_name"}:
                return mask_name(payload)
            return mask_pii_in_log_message(payload)
        return payload

    async def handle_error(
        self,
        error: Exception,
        context: FlowContext,
        step_id: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> FlowError:
        """
        Handle a flow error.

        Classifies the error, determines recovery strategy, logs it,
        and returns a FlowError object with recommendations.

        Args:
            error: Exception that occurred
            context: Flow context
            step_id: Optional step ID where error occurred
            operation: Optional operation name

        Returns:
            FlowError object with classification and recovery info

        Example:
            >>> flow_error = await handler.handle_error(
            ...     error=exception,
            ...     context=context,
            ...     step_id="step_001",
            ...     operation="execute_step"
            ... )
        """
        # Classify error
        category = self._classify_error(error)
        severity = self._determine_severity(error, category)
        is_transient = self._is_transient_error(error)

        # Create FlowError object
        flow_error = FlowError(
            error=error,
            context=context,
            step_id=step_id,
            category=category,
            severity=severity,
            is_transient=is_transient,
            metadata={"operation": operation} if operation else {},
        )

        # Log error
        await self._log_error(flow_error)

        # Store in history
        self._add_to_history(flow_error)

        # Check if escalation needed
        if self._should_escalate(flow_error):
            await self._escalate_error(flow_error)

        # Update circuit breaker if applicable
        if operation:
            await self._update_circuit_breaker(operation, success=False)

        logger.info(
            f"Error handled: {flow_error.error_type} "
            f"(category={category.value}, "
            f"strategy={flow_error.recovery_strategy.value})"
        )

        return flow_error

    async def recover_from_error(
        self,
        flow_error: FlowError,
        recovery_fn: Optional[Callable] = None,
    ) -> Tuple[bool, Optional[Any]]:
        """
        Attempt to recover from an error.

        Executes the recommended recovery strategy.

        Args:
            flow_error: FlowError to recover from
            recovery_fn: Optional recovery function

        Returns:
            Tuple of (success, result)

        Example:
            >>> success, result = await handler.recover_from_error(
            ...     flow_error=error,
            ...     recovery_fn=lambda: execute_step(...)
            ... )
        """
        strategy = flow_error.recovery_strategy

        logger.info(f"Attempting recovery with strategy: {strategy.value}")

        if strategy == RecoveryStrategy.RETRY:
            return await self._retry_with_backoff(flow_error, recovery_fn)

        elif strategy == RecoveryStrategy.SKIP:
            return await self._skip_step(flow_error)

        elif strategy == RecoveryStrategy.FALLBACK:
            return await self._use_fallback(flow_error, recovery_fn)

        elif strategy == RecoveryStrategy.MANUAL:
            return await self._require_manual_intervention(flow_error)

        elif strategy == RecoveryStrategy.CANCEL:
            return await self._cancel_flow(flow_error)

        else:  # NONE
            return False, None

    async def _retry_with_backoff(
        self,
        flow_error: FlowError,
        recovery_fn: Optional[Callable],
    ) -> Tuple[bool, Optional[Any]]:
        """Retry with exponential backoff."""
        if not recovery_fn:
            logger.warning("No recovery function provided for retry")
            return False, None

        max_retries = self.config.execution.max_step_retries
        backoff = self.config.execution.retry_backoff_seconds
        multiplier = self.config.execution.retry_backoff_multiplier

        for attempt in range(max_retries):
            try:
                logger.info(f"Retry attempt {attempt + 1}/{max_retries}")

                # Wait with exponential backoff
                if attempt > 0:
                    wait_time = backoff * (multiplier ** (attempt - 1))
                    logger.debug(f"Waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)

                # Attempt recovery
                result = await recovery_fn()
                logger.info(f"Recovery successful on attempt {attempt + 1}")
                return True, result

            except Exception as e:
                logger.warning(f"Retry attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error("Max retries reached, recovery failed")
                    return False, None

        return False, None

    async def _skip_step(self, flow_error: FlowError) -> Tuple[bool, Optional[Any]]:
        """Skip the failed step."""
        logger.info(f"Skipping failed step: {flow_error.step_id}")

        # Mark step as skipped in context
        if flow_error.step_id:
            # In production, would update step status
            pass

        return True, {"skipped": True, "step_id": flow_error.step_id}

    async def _use_fallback(
        self, flow_error: FlowError, recovery_fn: Optional[Callable]
    ) -> Tuple[bool, Optional[Any]]:
        """Use fallback logic."""
        logger.info("Using fallback recovery strategy")

        # In production, would execute fallback logic
        # For now, just mark as handled
        return True, {"fallback": True, "original_error": flow_error.error_message}

    async def _require_manual_intervention(
        self, flow_error: FlowError
    ) -> Tuple[bool, Optional[Any]]:
        """Mark as requiring manual intervention."""
        logger.warning("Manual intervention required")

        # Pause flow for manual review
        flow_error.context.status = FlowStatus.PAUSED
        flow_error.context.metadata["requires_manual_intervention"] = True
        flow_error.context.metadata["intervention_reason"] = flow_error.error_message

        return False, None

    async def _cancel_flow(self, flow_error: FlowError) -> Tuple[bool, Optional[Any]]:
        """Cancel the flow due to unrecoverable error."""
        logger.error("Cancelling flow due to unrecoverable error")

        flow_error.context.status = FlowStatus.FAILED
        flow_error.context.completed_at = now_sao_paulo()
        flow_error.context.metadata["cancellation_reason"] = flow_error.error_message

        return False, None

    def _classify_error(self, error: Exception) -> ErrorCategory:
        """Classify error into a category."""
        type(error).__name__
        error_message = str(error).lower()

        # Validation errors
        if "validation" in error_message or isinstance(error, ValueError):
            return ErrorCategory.VALIDATION_ERROR

        # Timeout errors
        if "timeout" in error_message or isinstance(error, asyncio.TimeoutError):
            return ErrorCategory.TIMEOUT_ERROR

        # Permission errors
        if "permission" in error_message or "forbidden" in error_message:
            return ErrorCategory.PERMISSION_ERROR

        # Resource errors
        if any(
            keyword in error_message
            for keyword in ["connection", "unavailable", "not found"]
        ):
            return ErrorCategory.RESOURCE_ERROR

        # Data errors
        if any(keyword in error_message for keyword in ["data", "corrupt", "invalid"]):
            return ErrorCategory.DATA_ERROR

        # Integration errors
        if any(keyword in error_message for keyword in ["api", "external", "service"]):
            return ErrorCategory.INTEGRATION_ERROR

        # Default to execution error
        return ErrorCategory.EXECUTION_ERROR

    def _determine_severity(
        self, error: Exception, category: ErrorCategory
    ) -> ErrorSeverity:
        """Determine error severity."""
        # Critical categories
        if category in [
            ErrorCategory.DATA_ERROR,
            ErrorCategory.SYSTEM_ERROR,
        ]:
            return ErrorSeverity.CRITICAL

        # High severity
        if category in [
            ErrorCategory.RESOURCE_ERROR,
            ErrorCategory.INTEGRATION_ERROR,
        ]:
            return ErrorSeverity.HIGH

        # Medium severity
        if category in [
            ErrorCategory.EXECUTION_ERROR,
            ErrorCategory.TIMEOUT_ERROR,
        ]:
            return ErrorSeverity.MEDIUM

        # Low severity
        return ErrorSeverity.LOW

    def _is_transient_error(self, error: Exception) -> bool:
        """Determine if error is transient (retryable)."""
        error_message = str(error).lower()

        transient_keywords = [
            "timeout",
            "temporary",
            "unavailable",
            "connection",
            "network",
            "busy",
        ]

        return any(keyword in error_message for keyword in transient_keywords)

    async def _log_error(self, flow_error: FlowError) -> None:
        """Log error with appropriate level."""
        log_data = self._sanitize_log_payload(flow_error.to_dict())

        if flow_error.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"Critical flow error: {log_data}")
        elif flow_error.severity == ErrorSeverity.HIGH:
            logger.error(f"High severity flow error: {log_data}")
        elif flow_error.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"Flow error: {log_data}")
        else:
            logger.info(f"Flow error (low severity): {log_data}")

        # In production, would send to error tracking service (Sentry, etc.)
        if self.config.error_handling.log_detailed_errors:
            logger.debug(
                "Error details: %s",
                self._sanitize_log_payload(str(flow_error.error)),
            )

    def _add_to_history(self, flow_error: FlowError) -> None:
        """Add error to history."""
        flow_id = flow_error.context.flow_instance_id

        if flow_id not in self.error_history:
            self.error_history[flow_id] = []

        self.error_history[flow_id].append(flow_error)

        # Trim history if too large
        from ..constants import FlowEngine

        if len(self.error_history[flow_id]) > FlowEngine.MAX_ERROR_HISTORY:
            self.error_history[flow_id] = self.error_history[flow_id][
                -FlowEngine.MAX_ERROR_HISTORY :
            ]

    def _should_escalate(self, flow_error: FlowError) -> bool:
        """Determine if error should be escalated."""
        if not self.config.error_handling.enable_error_notifications:
            return False

        # Escalate critical errors
        if flow_error.severity == ErrorSeverity.CRITICAL:
            return True

        # Escalate after N failures
        flow_id = flow_error.context.flow_instance_id
        error_count = len(self.error_history.get(flow_id, []))
        threshold = self.config.error_handling.escalate_after_failures

        if error_count >= threshold:
            return True

        return False

    async def _escalate_error(self, flow_error: FlowError) -> None:
        """Escalate error to administrators."""
        logger.critical(
            "Escalating error: %s",
            self._sanitize_log_payload(flow_error.to_dict()),
        )

        # In production, would:
        # - Send email to admins
        # - Create alert in monitoring system
        # - Trigger PagerDuty/OpsGenie
        # - Post to Slack channel

    async def _update_circuit_breaker(self, operation: str, success: bool) -> None:
        """Update circuit breaker state."""
        if operation not in self.circuit_breakers:
            self.circuit_breakers[operation] = {
                "failures": 0,
                "successes": 0,
                "state": "closed",  # closed, open, half-open
                "last_failure": None,
            }

        breaker = self.circuit_breakers[operation]

        if success:
            breaker["successes"] += 1
            breaker["failures"] = 0
            breaker["state"] = "closed"
        else:
            breaker["failures"] += 1
            breaker["last_failure"] = now_sao_paulo()

            # Open circuit breaker after N failures
            if breaker["failures"] >= 5:
                breaker["state"] = "open"
                logger.warning(f"Circuit breaker opened for operation: {operation}")

    def get_error_history(
        self, flow_instance_id: UUID, limit: int = 10
    ) -> List[FlowError]:
        """
        Get error history for a flow.

        Args:
            flow_instance_id: Flow instance ID
            limit: Maximum number of errors to return

        Returns:
            List of FlowError objects
        """
        history = self.error_history.get(flow_instance_id, [])
        return history[-limit:]

    def clear_error_history(self, flow_instance_id: UUID) -> None:
        """
        Clear error history for a flow.

        Args:
            flow_instance_id: Flow instance ID
        """
        if flow_instance_id in self.error_history:
            del self.error_history[flow_instance_id]
            logger.info(f"Cleared error history for flow: {flow_instance_id}")

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<FlowErrorHandler(tracked_flows={len(self.error_history)}, "
            f"circuit_breakers={len(self.circuit_breakers)})>"
        )
