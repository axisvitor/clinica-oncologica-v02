"""
Flow Orchestrator Package

Modular package structure for flow orchestration functionality.

This package provides a clean separation of concerns:
- enums: Flow execution states and operation types
- models: Data classes for context and results
- utils: Helper functions and utilities
- lifecycle: Flow lifecycle management (start, pause, resume, stop)
- messaging: Message composition and sending
- scheduling: Quiz and follow-up scheduling
- core: Main FlowOrchestrator class

All public APIs are re-exported from this module for backward compatibility.
"""

# Core orchestrator class
from .core import (
    FlowOrchestrator,
    create_flow_orchestrator,
    get_flow_orchestrator
)

# Enumerations
from .enums import (
    FlowExecutionState,
    FlowOperationType
)

# Data models
from .models import (
    FlowExecutionContext,
    FlowExecutionResult
)

# Utility functions
from .utils import (
    calculate_treatment_day
)

# Submodules - not typically used directly but available if needed
from .lifecycle import FlowLifecycleManager
from .messaging import FlowMessagingOrchestrator
from .scheduling import FlowSchedulingOrchestrator

__all__ = [
    # Main orchestrator
    'FlowOrchestrator',
    'create_flow_orchestrator',
    'get_flow_orchestrator',

    # Enumerations
    'FlowExecutionState',
    'FlowOperationType',

    # Data models
    'FlowExecutionContext',
    'FlowExecutionResult',

    # Utilities
    'calculate_treatment_day',

    # Submodules (optional, for advanced usage)
    'FlowLifecycleManager',
    'FlowMessagingOrchestrator',
    'FlowSchedulingOrchestrator',
]
