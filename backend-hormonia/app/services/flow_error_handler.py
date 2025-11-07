"""
DEPRECATED: Legacy flow error handler wrapper.

This module is deprecated. Please use app.domain.errors.flows instead.

Migration Guide:
    OLD: from app.services.flow_error_handler import FlowErrorHandler
    NEW: from app.domain.errors.flows import FlowErrorHandler

All functionality has been moved to the new modular structure in
app.domain.errors.flows for better separation of concerns.
"""
import warnings
from typing import Optional

# Import from new location
from app.domain.errors.flows import (
    FlowErrorHandler as NewFlowErrorHandler,
    FlowErrorHandlerFactory as NewFlowErrorHandlerFactory,
    get_flow_error_handler as new_get_flow_error_handler,
    ErrorCategory,
    ErrorSeverity,
    RecoveryStrategy,
    ErrorContext,
    ErrorRecord,
    RecoveryResult,
    ErrorClassifier,
    RecoveryStrategySelector,
    ErrorHandlerConfig,
    ErrorHandlerConstants
)

# Show deprecation warning once at module import
warnings.warn(
    "app.services.flow_error_handler is deprecated. "
    "Use app.domain.errors.flows instead. "
    "This module will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2
)


class FlowErrorHandler:
    """
    DEPRECATED: Backward compatibility wrapper for FlowErrorHandler.

    Please migrate to: from app.domain.errors.flows import FlowErrorHandler
    """

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "app.services.flow_error_handler.FlowErrorHandler is deprecated. "
            "Use app.domain.errors.flows.FlowErrorHandler instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self._impl = NewFlowErrorHandler(*args, **kwargs)

    def __getattr__(self, name):
        """Delegate all attribute access to the new implementation."""
        return getattr(self._impl, name)


class FlowErrorHandlerFactory:
    """
    DEPRECATED: Backward compatibility wrapper for FlowErrorHandlerFactory.

    Please migrate to: from app.domain.errors.flows import FlowErrorHandlerFactory
    """

    @staticmethod
    def create_default(*args, **kwargs):
        warnings.warn(
            "app.services.flow_error_handler.FlowErrorHandlerFactory is deprecated. "
            "Use app.domain.errors.flows.FlowErrorHandlerFactory instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return NewFlowErrorHandlerFactory.create_default(*args, **kwargs)

    @staticmethod
    def create_with_config(*args, **kwargs):
        warnings.warn(
            "app.services.flow_error_handler.FlowErrorHandlerFactory is deprecated. "
            "Use app.domain.errors.flows.FlowErrorHandlerFactory instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return NewFlowErrorHandlerFactory.create_with_config(*args, **kwargs)

    @staticmethod
    def create_for_testing(*args, **kwargs):
        warnings.warn(
            "app.services.flow_error_handler.FlowErrorHandlerFactory is deprecated. "
            "Use app.domain.errors.flows.FlowErrorHandlerFactory instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return NewFlowErrorHandlerFactory.create_for_testing(*args, **kwargs)


def get_flow_error_handler(*args, **kwargs):
    """
    DEPRECATED: Backward compatibility wrapper for get_flow_error_handler.

    Please migrate to: from app.domain.errors.flows import get_flow_error_handler
    """
    warnings.warn(
        "app.services.flow_error_handler.get_flow_error_handler is deprecated. "
        "Use app.domain.errors.flows.get_flow_error_handler instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return new_get_flow_error_handler(*args, **kwargs)


# Re-export all classes and enums for backward compatibility
__all__ = [
    "FlowErrorHandler",
    "FlowErrorHandlerFactory",
    "get_flow_error_handler",
    "ErrorCategory",
    "ErrorSeverity",
    "RecoveryStrategy",
    "ErrorContext",
    "ErrorRecord",
    "RecoveryResult",
    "ErrorClassifier",
    "RecoveryStrategySelector",
    "ErrorHandlerConfig",
    "ErrorHandlerConstants",
]
