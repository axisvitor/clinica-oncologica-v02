"""
Main error handler orchestrator for flow operations.
Coordinates error classification, recovery strategies, retry management, and audit logging.
"""

import logging
import traceback
from datetime import datetime
from uuid import UUID
from typing import Optional, Callable, List
from sqlalchemy.orm import Session

from app.repositories.flow import FlowStateRepository
from app.repositories.message import MessageRepository
from app.repositories.patient import PatientRepository
from app.services.conversation_memory import get_conversation_memory

from .classifier import (
    ErrorCategory,
    ErrorSeverity,
    RecoveryStrategy,
    ErrorHandlerConfig,
    ErrorClassifier,
    RecoveryStrategySelector,
)
from .retry_manager import ErrorContext, ErrorRecord, RecoveryResult, RetryManager
from .recovery_strategy import RecoveryActionFactory
from .audit_logger import ErrorAuditLogger

logger = logging.getLogger(__name__)


class FlowErrorHandler:
    """Comprehensive error handler for flow operations."""

    def __init__(
        self,
        db: Session,
        config: Optional[ErrorHandlerConfig] = None,
        classifier: Optional[ErrorClassifier] = None,
        strategy_selector: Optional[RecoveryStrategySelector] = None,
    ):
        """
        Initialize flow error handler.

        Args:
            db: Database session
            config: Error handler configuration
            classifier: Error classifier instance
            strategy_selector: Recovery strategy selector instance
        """
        self.db = db
        self.flow_repo = FlowStateRepository(db)
        self.message_repo = MessageRepository(db)
        self.patient_repo = PatientRepository(db)
        self.memory = get_conversation_memory()

        # Injected dependencies
        self.config = config or ErrorHandlerConfig()
        self.classifier = classifier or ErrorClassifier()
        self.strategy_selector = strategy_selector or RecoveryStrategySelector()

        # Initialize managers
        self.retry_manager = RetryManager(
            redis_client=self.memory.redis, retry_delays=self.config.retry_delays
        )
        self.audit_logger = ErrorAuditLogger(redis_client=self.memory.redis)

        # Error tracking
        self.error_records: dict[str, ErrorRecord] = {}
        self.recovery_callbacks: dict[ErrorCategory, List[Callable]] = {}

        logger.info("Flow error handler initialized")

    def _validate_error_context(self, context: ErrorContext) -> None:
        """
        Validate error context.

        Args:
            context: Error context to validate

        Raises:
            ValueError: If context is invalid
        """
        if not isinstance(context.patient_id, UUID):
            raise ValueError("patient_id must be a valid UUID")

        if not context.operation or not context.operation.strip():
            raise ValueError("operation cannot be empty")

        if context.flow_state_id is not None and not isinstance(
            context.flow_state_id, UUID
        ):
            raise ValueError("flow_state_id must be a valid UUID or None")

        if context.message_id is not None and not isinstance(context.message_id, UUID):
            raise ValueError("message_id must be a valid UUID or None")

    def _generate_error_id(self, context: ErrorContext) -> str:
        """
        Generate unique error ID.

        Args:
            context: Error context

        Returns:
            Unique error ID
        """
        timestamp = int(datetime.utcnow().timestamp())
        operation_hash = hash(context.operation) % 10000  # Keep it short
        return f"{str(context.patient_id)[:8]}_{operation_hash}_{timestamp}"

    async def handle_error(
        self,
        error: Exception,
        context: ErrorContext,
        recovery_strategy: Optional[RecoveryStrategy] = None,
    ) -> RecoveryResult:
        """
        Handle flow operation error with appropriate recovery strategy.

        Args:
            error: The exception that occurred
            context: Error context information
            recovery_strategy: Optional specific recovery strategy

        Returns:
            Recovery result

        Raises:
            ValueError: If error or context is invalid
        """
        if not isinstance(error, Exception):
            raise ValueError("error must be an Exception instance")

        if not isinstance(context, ErrorContext):
            raise ValueError("context must be an ErrorContext instance")

        try:
            # Validate context
            self._validate_error_context(context)

            # Classify error
            category, severity = self.classifier.classify_error(error)

            # Create error record
            error_record = ErrorRecord(
                id=self._generate_error_id(context),
                error_type=type(error).__name__,
                category=category,
                severity=severity,
                message=str(error)[:1000],  # Limit message length
                context=context,
                stack_trace=traceback.format_exc()[:5000],  # Limit stack trace length
                max_recovery_attempts=self.config.max_retry_attempts.get(category, 3),
                recovery_strategy=recovery_strategy
                or self.strategy_selector.determine_recovery_strategy(
                    category, severity
                ),
            )

            # Store error record
            self.error_records[error_record.id] = error_record
            await self.audit_logger.store_error(error_record)

            # Log error
            logger.error(
                f"Flow error occurred: {error_record.error_type} - {error_record.message}"
            )
            logger.error(f"Context: {context}")

            # Attempt recovery
            recovery_result = await self._attempt_recovery(error_record)

            # Publish error event
            await self.audit_logger.publish_error_event(error_record, recovery_result)

            # Escalate if critical or recovery failed
            if severity == ErrorSeverity.CRITICAL or not recovery_result.success:
                await self.audit_logger.escalate_error(error_record, recovery_result)

            return recovery_result

        except Exception as e:
            logger.error(f"Error in error handler: {e}")
            # Return basic failure result
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.ESCALATE_MANUAL,
                attempts_made=0,
                error_resolved=False,
                message="Error handler failed",
            )

    async def _attempt_recovery(self, error_record: ErrorRecord) -> RecoveryResult:
        """
        Attempt error recovery using specified strategy.

        Args:
            error_record: Error record to recover

        Returns:
            Recovery result
        """
        try:
            action = RecoveryActionFactory.create_action(error_record.recovery_strategy)
            return await action.execute(error_record, self)

        except Exception as e:
            logger.error(f"Recovery attempt failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=error_record.recovery_strategy,
                attempts_made=error_record.recovery_attempts,
                error_resolved=False,
                message=f"Recovery failed: {str(e)}",
            )

    async def get_error_statistics(
        self, timeframe_hours: int = 24, use_cache: bool = True
    ) -> dict:
        """
        Get error statistics for monitoring.

        Args:
            timeframe_hours: Hours to look back
            use_cache: Whether to use cached statistics

        Returns:
            Statistics dictionary
        """
        return await self.audit_logger.get_error_statistics(timeframe_hours, use_cache)

    async def cleanup_old_errors(self, days_old: int = 7) -> int:
        """
        Clean up old error records.

        Args:
            days_old: Age threshold in days

        Returns:
            Number of cleaned records
        """
        return await self.audit_logger.cleanup_old_errors(self.error_records, days_old)

    def register_recovery_callback(
        self, category: ErrorCategory, callback: Callable
    ) -> None:
        """
        Register callback for error category.

        Args:
            category: Error category
            callback: Callback function
        """
        if category not in self.recovery_callbacks:
            self.recovery_callbacks[category] = []
        self.recovery_callbacks[category].append(callback)

    def get_error_record(self, error_id: str) -> Optional[ErrorRecord]:
        """
        Get error record by ID.

        Args:
            error_id: Error ID

        Returns:
            Error record or None
        """
        return self.error_records.get(error_id)

    def get_all_error_records(self) -> dict[str, ErrorRecord]:
        """
        Get all error records.

        Returns:
            Dictionary of error records
        """
        return self.error_records.copy()


class FlowErrorHandlerFactory:
    """Factory for creating FlowErrorHandler instances."""

    @staticmethod
    def create_default(db: Session) -> FlowErrorHandler:
        """
        Create FlowErrorHandler with default configuration.

        Args:
            db: Database session

        Returns:
            FlowErrorHandler instance
        """
        return FlowErrorHandler(db)

    @staticmethod
    def create_with_config(
        db: Session,
        config: ErrorHandlerConfig,
        classifier: Optional[ErrorClassifier] = None,
        strategy_selector: Optional[RecoveryStrategySelector] = None,
    ) -> FlowErrorHandler:
        """
        Create FlowErrorHandler with custom configuration.

        Args:
            db: Database session
            config: Error handler configuration
            classifier: Optional error classifier
            strategy_selector: Optional strategy selector

        Returns:
            FlowErrorHandler instance
        """
        return FlowErrorHandler(
            db=db,
            config=config,
            classifier=classifier,
            strategy_selector=strategy_selector,
        )

    @staticmethod
    def create_for_testing(
        db: Session, mock_memory=None, mock_repos=None
    ) -> FlowErrorHandler:
        """
        Create FlowErrorHandler for testing with mocked dependencies.

        Args:
            db: Database session
            mock_memory: Mock memory service
            mock_repos: Mock repositories

        Returns:
            FlowErrorHandler instance
        """
        handler = FlowErrorHandler(db)

        if mock_memory:
            handler.memory = mock_memory

        if mock_repos:
            if "flow_repo" in mock_repos:
                handler.flow_repo = mock_repos["flow_repo"]
            if "message_repo" in mock_repos:
                handler.message_repo = mock_repos["message_repo"]
            if "patient_repo" in mock_repos:
                handler.patient_repo = mock_repos["patient_repo"]

        return handler


def get_flow_error_handler(db: Session) -> FlowErrorHandler:
    """
    Get flow error handler instance.

    Args:
        db: Database session

    Returns:
        FlowErrorHandler instance
    """
    return FlowErrorHandlerFactory.create_default(db)
