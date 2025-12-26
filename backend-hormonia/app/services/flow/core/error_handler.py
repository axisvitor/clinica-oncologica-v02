"""
Backward compatibility shim for flow error handling.
"""

from __future__ import annotations

"""

Legacy imports reference ``app.services.flow.core.error_handler`` while the
consolidated implementation lives under ``app.services.flow.errors.handler``.
This module simply re-exports the public API so existing code (and tests)
continue to work without modification.
"""

from ..errors.handler import (
    FlowErrorHandler,
    FlowError,
    ErrorCategory,
    ErrorSeverity,
    RecoveryStrategy,
)

__all__ = [
    "FlowErrorHandler",
    "FlowError",
    "ErrorCategory",
    "ErrorSeverity",
    "RecoveryStrategy",
]
