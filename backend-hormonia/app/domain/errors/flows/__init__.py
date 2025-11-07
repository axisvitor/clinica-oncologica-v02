"""
Flow error handling modules.

This package provides comprehensive error handling and recovery mechanisms
for flow operations, including classification, recovery strategies, retry
management, and audit logging.

Main Components:
    - FlowErrorHandler: Main error orchestrator
    - ErrorClassifier: Error classification and categorization
    - RecoveryStrategySelector: Recovery strategy selection
    - RetryManager: Retry scheduling and backoff management
    - ErrorAuditLogger: Error logging and statistics

Usage:
    from app.domain.errors.flows import FlowErrorHandler, ErrorContext

    handler = FlowErrorHandler(db)
    result = await handler.handle_error(error, context)
"""

# Main error handler
from .error_handler import (
    FlowErrorHandler,
    FlowErrorHandlerFactory,
    get_flow_error_handler
)

# Classification
from .classifier import (
    ErrorCategory,
    ErrorSeverity,
    RecoveryStrategy,
    ErrorClassifier,
    RecoveryStrategySelector,
    ErrorHandlerConfig,
    ErrorHandlerConstants
)

# Retry management
from .retry_manager import (
    ErrorContext,
    ErrorRecord,
    RecoveryResult,
    RetryManager
)

# Recovery strategies
from .recovery_strategy import (
    RecoveryAction,
    RecoveryActionFactory,
    ExponentialBackoffRetry,
    LinearBackoffRetry,
    FallbackMessageAction,
    SkipAndContinueAction,
    PauseFlowAction,
    ResetFlowAction,
    EscalateManualAction
)

# Audit logging
from .audit_logger import (
    ErrorAuditLogger,
    ErrorStatisticsCache
)

__all__ = [
    # Main handler
    "FlowErrorHandler",
    "FlowErrorHandlerFactory",
    "get_flow_error_handler",

    # Enums
    "ErrorCategory",
    "ErrorSeverity",
    "RecoveryStrategy",

    # Classification
    "ErrorClassifier",
    "RecoveryStrategySelector",
    "ErrorHandlerConfig",
    "ErrorHandlerConstants",

    # Data structures
    "ErrorContext",
    "ErrorRecord",
    "RecoveryResult",

    # Managers
    "RetryManager",
    "ErrorAuditLogger",
    "ErrorStatisticsCache",

    # Recovery actions
    "RecoveryAction",
    "RecoveryActionFactory",
    "ExponentialBackoffRetry",
    "LinearBackoffRetry",
    "FallbackMessageAction",
    "SkipAndContinueAction",
    "PauseFlowAction",
    "ResetFlowAction",
    "EscalateManualAction",
]
