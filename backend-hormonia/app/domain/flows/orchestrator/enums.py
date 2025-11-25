"""
Flow Orchestrator - Enumerations

Contains all enum definitions for flow execution states and operation types.
"""

from enum import Enum


class FlowExecutionState(str, Enum):
    """Flow execution states."""
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FlowOperationType(str, Enum):
    """Types of flow operations."""
    START = "start"
    ADVANCE = "advance"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    RESTART = "restart"
