"""
Flow Core Module - Core execution components for Flow Services (QW-021).

This module contains the fundamental execution logic for flows, including:
- FlowEngine: Step execution and state transitions
- FlowStateMachine: State transition logic
- FlowContextRepository: Context persistence
- FlowLifecycleManager: Lifecycle management
- FlowManager: Main orchestration interface
- FlowValidator: Flow and step validation (backward compatibility)
- FlowErrorHandler: Error handling and recovery (backward compatibility)

These components work together to provide the core flow execution functionality.
"""

from __future__ import annotations

from .context import ContextPersistenceResult, FlowContextRepository
from .engine import FlowEngine
from .error_handler import (
    ErrorCategory,
    ErrorSeverity,
    FlowError,
    FlowErrorHandler,
    RecoveryStrategy,
)
from .lifecycle import FlowLifecycleManager
from .manager import FlowManager
from .state_machine import FlowStateMachine
from .validator import FlowValidator

__all__ = [
    # Core Components
    "FlowEngine",
    "FlowStateMachine",
    "FlowContextRepository",
    "ContextPersistenceResult",
    "FlowLifecycleManager",
    "FlowManager",
    # Backward Compatibility
    "FlowValidator",
    "FlowErrorHandler",
    "FlowError",
    "ErrorCategory",
    "ErrorSeverity",
    "RecoveryStrategy",
]
