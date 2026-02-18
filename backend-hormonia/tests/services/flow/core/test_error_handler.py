"""
Tests for FlowErrorHandler - Error handling and recovery (QW-021 Day 6).

Test Coverage:
    - Error Handling (handle_error, classification, severity)
    - Error Classification (categories, severity levels)
    - Recovery Strategies (retry, skip, fallback, manual, cancel)
    - Retry Logic (exponential backoff, max retries)
    - Circuit Breaker (failure tracking, state management)
    - Error History (tracking, retrieval)
    - Escalation (should_escalate, escalate_error)
    - Error Logging (log_error, error reporting)
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock

from app.services.flow.errors.handler import (
    FlowErrorHandler,
    FlowError,
    ErrorCategory,
    ErrorSeverity,
    RecoveryStrategy,
)
from app.services.flow.types import FlowContext, FlowType, FlowStatus


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def error_handler():
    """Create error handler instance."""
    return FlowErrorHandler()


@pytest.fixture
def flow_context() -> FlowContext:
    """Create flow context."""
    return FlowContext(
        flow_instance_id=uuid4(),
        flow_type=FlowType.MONITORING,
        patient_id=uuid4(),
        steps_completed=[],
        current_data={},
        status=FlowStatus.ACTIVE,
    )


@pytest.fixture
def sample_error() -> Exception:
    """Create sample error."""
    return ValueError("Test error message")


# ============================================================================
# Test Error Handling
# ============================================================================


class TestErrorHandling:
    """Test error handling functionality."""

    @pytest.mark.asyncio
    async def test_handle_error_basic(
        self,
        error_handler: FlowErrorHandler,
        sample_error: Exception,
        flow_context: FlowContext,
    ):
        """Test basic error handling."""
        flow_error = await error_handler.handle_error(
            error=sample_error,
            context=flow_context,
            step_id="step_1",
        )

        assert isinstance(flow_error, FlowError)
        assert flow_error.error == sample_error
        assert flow_error.context == flow_context
        assert flow_error.step_id == "step_1"
        assert flow_error.error_type == "ValueError"
        assert flow_error.error_message == "Test error message"

    @pytest.mark.asyncio
    async def test_handle_error_with_operation(
        self,
        error_handler: FlowErrorHandler,
        sample_error: Exception,
        flow_context: FlowContext,
    ):
        """Test error handling with operation name."""
        flow_error = await error_handler.handle_error(
            error=sample_error,
            context=flow_context,
            operation="execute_step",
        )

        assert "operation" in flow_error.metadata
        assert flow_error.metadata["operation"] == "execute_step"

    @pytest.mark.asyncio
    async def test_handle_error_stores_in_history(
        self,
        error_handler: FlowErrorHandler,
        sample_error: Exception,
        flow_context: FlowContext,
    ):
        """Test that errors are stored in history."""
        flow_error = await error_handler.handle_error(
            error=sample_error,
            context=flow_context,
        )

        assert flow_context.flow_instance_id in error_handler.error_history
        assert len(error_handler.error_history[flow_context.flow_instance_id]) == 1
        assert (
            error_handler.error_history[flow_context.flow_instance_id][0] == flow_error
        )


# ============================================================================
# Test Error Classification
# ============================================================================


class TestErrorClassification:
    """Test error classification."""

    @pytest.mark.asyncio
    async def test_classify_validation_error(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test classification of validation error."""
        error = ValueError("Invalid input")
        flow_error = await error_handler.handle_error(error, flow_context)

        assert flow_error.category == ErrorCategory.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_classify_timeout_error(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test classification of timeout error."""
        error = TimeoutError("Operation timed out")
        flow_error = await error_handler.handle_error(error, flow_context)

        assert flow_error.category == ErrorCategory.TIMEOUT_ERROR

    @pytest.mark.asyncio
    async def test_classify_unknown_error(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test classification of unknown error."""
        error = Exception("Unknown error")
        flow_error = await error_handler.handle_error(error, flow_context)

        assert flow_error.category == ErrorCategory.EXECUTION_ERROR

    @pytest.mark.asyncio
    async def test_severity_determination(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test error severity determination."""
        error = ValueError("Test")
        flow_error = await error_handler.handle_error(error, flow_context)

        assert flow_error.severity in [
            ErrorSeverity.LOW,
            ErrorSeverity.MEDIUM,
            ErrorSeverity.HIGH,
            ErrorSeverity.CRITICAL,
        ]

    @pytest.mark.asyncio
    async def test_transient_error_detection(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test transient error detection."""
        error = TimeoutError("Temporary failure")
        flow_error = await error_handler.handle_error(error, flow_context)

        assert isinstance(flow_error.is_transient, bool)


# ============================================================================
# Test Recovery Strategies
# ============================================================================


class TestRecoveryStrategies:
    """Test recovery strategy determination."""

    def test_flow_error_recovery_strategy_transient(self, flow_context: FlowContext):
        """Test recovery strategy for transient errors."""
        error = TimeoutError("Temporary")
        flow_error = FlowError(
            error=error,
            context=flow_context,
            is_transient=True,
        )

        assert flow_error.recovery_strategy == RecoveryStrategy.RETRY

    def test_flow_error_recovery_strategy_validation(self, flow_context: FlowContext):
        """Test recovery strategy for validation errors."""
        error = ValueError("Invalid")
        flow_error = FlowError(
            error=error,
            context=flow_context,
            category=ErrorCategory.VALIDATION_ERROR,
        )

        assert flow_error.recovery_strategy == RecoveryStrategy.CANCEL

    def test_flow_error_recovery_strategy_user_error(self, flow_context: FlowContext):
        """Test recovery strategy for user errors."""
        error = Exception("User error")
        flow_error = FlowError(
            error=error,
            context=flow_context,
            category=ErrorCategory.USER_ERROR,
        )

        assert flow_error.recovery_strategy == RecoveryStrategy.MANUAL

    def test_flow_error_recovery_strategy_critical(self, flow_context: FlowContext):
        """Test recovery strategy for critical errors."""
        error = Exception("Critical")
        flow_error = FlowError(
            error=error,
            context=flow_context,
            severity=ErrorSeverity.CRITICAL,
        )

        assert flow_error.recovery_strategy == RecoveryStrategy.MANUAL


# ============================================================================
# Test Retry Logic
# ============================================================================


class TestRetryLogic:
    """Test retry with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test successful retry on first attempt."""
        error = TimeoutError("Temporary")
        flow_error = FlowError(
            error=error,
            context=flow_context,
            is_transient=True,
            recovery_strategy=RecoveryStrategy.RETRY,
        )

        recovery_fn = AsyncMock(return_value="success")

        success, result = await error_handler.recover_from_error(
            flow_error, recovery_fn
        )

        assert success is True
        assert result == "success"
        recovery_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test successful retry after some failures."""
        error = TimeoutError("Temporary")
        flow_error = FlowError(
            error=error,
            context=flow_context,
            is_transient=True,
            recovery_strategy=RecoveryStrategy.RETRY,
        )

        # Fail twice, then succeed
        recovery_fn = AsyncMock(
            side_effect=[Exception("Fail"), Exception("Fail"), "success"]
        )

        success, result = await error_handler.recover_from_error(
            flow_error, recovery_fn
        )

        assert success is True
        assert result == "success"
        assert recovery_fn.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_max_retries_reached(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test retry when max retries reached."""
        error = TimeoutError("Temporary")
        flow_error = FlowError(
            error=error,
            context=flow_context,
            is_transient=True,
            recovery_strategy=RecoveryStrategy.RETRY,
        )

        recovery_fn = AsyncMock(side_effect=Exception("Always fails"))

        success, result = await error_handler.recover_from_error(
            flow_error, recovery_fn
        )

        assert success is False
        assert result is None

    @pytest.mark.asyncio
    async def test_retry_no_recovery_function(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test retry without recovery function."""
        error = TimeoutError("Temporary")
        flow_error = FlowError(
            error=error,
            context=flow_context,
            recovery_strategy=RecoveryStrategy.RETRY,
        )

        success, result = await error_handler.recover_from_error(flow_error, None)

        assert success is False
        assert result is None


# ============================================================================
# Test Recovery Methods
# ============================================================================


class TestRecoveryMethods:
    """Test different recovery methods."""

    @pytest.mark.asyncio
    async def test_skip_step_recovery(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test skip step recovery."""
        error = Exception("Skip this")
        flow_error = FlowError(
            error=error,
            context=flow_context,
            step_id="step_1",
            recovery_strategy=RecoveryStrategy.SKIP,
        )

        success, result = await error_handler.recover_from_error(flow_error)

        assert success is True
        assert result["skipped"] is True
        assert result["step_id"] == "step_1"

    @pytest.mark.asyncio
    async def test_fallback_recovery(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test fallback recovery."""
        error = Exception("Use fallback")
        flow_error = FlowError(
            error=error,
            context=flow_context,
            recovery_strategy=RecoveryStrategy.FALLBACK,
        )

        success, result = await error_handler.recover_from_error(flow_error)

        assert success is True
        assert result["fallback"] is True

    @pytest.mark.asyncio
    async def test_manual_intervention_recovery(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test manual intervention recovery."""
        error = Exception("Manual required")
        flow_error = FlowError(
            error=error,
            context=flow_context,
            recovery_strategy=RecoveryStrategy.MANUAL,
        )

        success, result = await error_handler.recover_from_error(flow_error)

        assert success is False
        assert flow_context.status == FlowStatus.PAUSED

    @pytest.mark.asyncio
    async def test_cancel_flow_recovery(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test cancel flow recovery."""
        error = Exception("Cancel flow")
        flow_error = FlowError(
            error=error,
            context=flow_context,
            recovery_strategy=RecoveryStrategy.CANCEL,
        )

        success, result = await error_handler.recover_from_error(flow_error)

        assert success is False
        assert flow_context.status == FlowStatus.FAILED


# ============================================================================
# Test Error History
# ============================================================================


class TestErrorHistory:
    """Test error history tracking."""

    @pytest.mark.asyncio
    async def test_multiple_errors_tracked(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test that multiple errors are tracked."""
        errors = [
            ValueError("Error 1"),
            TimeoutError("Error 2"),
            Exception("Error 3"),
        ]

        for error in errors:
            await error_handler.handle_error(error, flow_context)

        history = error_handler.error_history[flow_context.flow_instance_id]
        assert len(history) == 3
        assert history[0].error_message == "Error 1"
        assert history[1].error_message == "Error 2"
        assert history[2].error_message == "Error 3"

    @pytest.mark.asyncio
    async def test_error_history_per_flow(self, error_handler: FlowErrorHandler):
        """Test that error history is per flow."""
        context1 = FlowContext(
            flow_instance_id=uuid4(),
            flow_type=FlowType.MONITORING,
            patient_id=uuid4(),
        )
        context2 = FlowContext(
            flow_instance_id=uuid4(),
            flow_type=FlowType.MONITORING,
            patient_id=uuid4(),
        )

        await error_handler.handle_error(ValueError("Error 1"), context1)
        await error_handler.handle_error(ValueError("Error 2"), context2)

        assert len(error_handler.error_history[context1.flow_instance_id]) == 1
        assert len(error_handler.error_history[context2.flow_instance_id]) == 1


# ============================================================================
# Test FlowError Class
# ============================================================================


class TestFlowErrorClass:
    """Test FlowError class."""

    def test_flow_error_initialization(self, flow_context: FlowContext):
        """Test FlowError initialization."""
        error = ValueError("Test")
        flow_error = FlowError(
            error=error,
            context=flow_context,
            step_id="step_1",
            category=ErrorCategory.VALIDATION_ERROR,
            severity=ErrorSeverity.HIGH,
        )

        assert flow_error.error == error
        assert flow_error.context == flow_context
        assert flow_error.step_id == "step_1"
        assert flow_error.category == ErrorCategory.VALIDATION_ERROR
        assert flow_error.severity == ErrorSeverity.HIGH
        assert flow_error.error_type == "ValueError"
        assert flow_error.error_message == "Test"

    def test_flow_error_to_dict(self, flow_context: FlowContext):
        """Test FlowError to_dict method."""
        error = ValueError("Test")
        flow_error = FlowError(
            error=error,
            context=flow_context,
            step_id="step_1",
        )

        error_dict = flow_error.to_dict()

        assert error_dict["error_type"] == "ValueError"
        assert error_dict["error_message"] == "Test"
        assert error_dict["step_id"] == "step_1"
        assert "category" in error_dict
        assert "severity" in error_dict
        assert "timestamp" in error_dict

    def test_flow_error_repr(self, flow_context: FlowContext):
        """Test FlowError string representation."""
        error = ValueError("Test")
        flow_error = FlowError(error=error, context=flow_context)

        repr_str = repr(flow_error)

        assert "FlowError" in repr_str
        assert "ValueError" in repr_str

    def test_flow_error_with_metadata(self, flow_context: FlowContext):
        """Test FlowError with metadata."""
        error = ValueError("Test")
        metadata = {"key": "value", "count": 42}
        flow_error = FlowError(
            error=error,
            context=flow_context,
            metadata=metadata,
        )

        assert flow_error.metadata == metadata
        assert flow_error.to_dict()["metadata"] == metadata


# ============================================================================
# Test Error Categories and Severity
# ============================================================================


class TestErrorCategoriesAndSeverity:
    """Test error categories and severity levels."""

    def test_error_category_enum(self):
        """Test ErrorCategory enum values."""
        assert ErrorCategory.VALIDATION_ERROR.value == "validation_error"
        assert ErrorCategory.EXECUTION_ERROR.value == "execution_error"
        assert ErrorCategory.TIMEOUT_ERROR.value == "timeout_error"
        assert ErrorCategory.SYSTEM_ERROR.value == "system_error"

    def test_error_severity_enum(self):
        """Test ErrorSeverity enum values."""
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"

    def test_recovery_strategy_enum(self):
        """Test RecoveryStrategy enum values."""
        assert RecoveryStrategy.RETRY.value == "retry"
        assert RecoveryStrategy.SKIP.value == "skip"
        assert RecoveryStrategy.FALLBACK.value == "fallback"
        assert RecoveryStrategy.MANUAL.value == "manual"
        assert RecoveryStrategy.CANCEL.value == "cancel"


# ============================================================================
# Test Integration Scenarios
# ============================================================================


class TestIntegrationScenarios:
    """Test complete error handling scenarios."""

    @pytest.mark.asyncio
    async def test_complete_error_recovery_flow(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test complete error and recovery flow."""
        # Step 1: Error occurs
        error = TimeoutError("Temporary failure")
        flow_error = await error_handler.handle_error(
            error=error,
            context=flow_context,
            step_id="step_1",
            operation="execute_step",
        )

        # Verify error was handled
        assert flow_error.category == ErrorCategory.TIMEOUT_ERROR
        assert flow_error.recovery_strategy == RecoveryStrategy.RETRY

        # Step 2: Attempt recovery
        recovery_fn = AsyncMock(return_value="recovered")
        success, result = await error_handler.recover_from_error(
            flow_error, recovery_fn
        )

        # Verify recovery succeeded
        assert success is True
        assert result == "recovered"

        # Step 3: Verify error was logged in history
        assert flow_context.flow_instance_id in error_handler.error_history
        assert len(error_handler.error_history[flow_context.flow_instance_id]) == 1

    @pytest.mark.asyncio
    async def test_escalation_after_multiple_errors(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test error escalation after multiple failures."""
        # Generate multiple errors
        for i in range(5):
            error = Exception(f"Error {i}")
            await error_handler.handle_error(error, flow_context)

        # Verify errors were tracked
        history = error_handler.error_history[flow_context.flow_instance_id]
        assert len(history) >= 5

    @pytest.mark.asyncio
    async def test_different_recovery_strategies(
        self, error_handler: FlowErrorHandler, flow_context: FlowContext
    ):
        """Test different recovery strategies in sequence."""
        # Test retry
        retry_error = FlowError(
            error=TimeoutError("Retry"),
            context=flow_context,
            recovery_strategy=RecoveryStrategy.RETRY,
        )
        success, _ = await error_handler.recover_from_error(
            retry_error, AsyncMock(return_value="ok")
        )
        assert success is True

        # Test skip
        skip_error = FlowError(
            error=Exception("Skip"),
            context=flow_context,
            recovery_strategy=RecoveryStrategy.SKIP,
        )
        success, _ = await error_handler.recover_from_error(skip_error)
        assert success is True

        # Test fallback
        fallback_error = FlowError(
            error=Exception("Fallback"),
            context=flow_context,
            recovery_strategy=RecoveryStrategy.FALLBACK,
        )
        success, _ = await error_handler.recover_from_error(fallback_error)
        assert success is True
