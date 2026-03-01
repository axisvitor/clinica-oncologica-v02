"""
Data models for automated recovery operations.
"""

from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass


class RecoveryAction(Enum):
    RESTART_FAILED_FLOWS = "restart_failed_flows"
    CLEAR_STUCK_QUEUES = "clear_stuck_queues"
    RESET_CORRUPTED_STATES = "reset_corrupted_states"
    CLEANUP_ORPHANED_DATA = "cleanup_orphaned_data"
    REFRESH_EXTERNAL_CONNECTIONS = "refresh_external_connections"
    OPTIMIZE_DATABASE_PERFORMANCE = "optimize_database_performance"
    CLEAR_MEMORY_PRESSURE = "clear_memory_pressure"
    REBALANCE_LOAD = "rebalance_load"


class RecoveryResult(Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class RecoveryOperation:
    """Recovery operation result."""

    action: RecoveryAction
    result: RecoveryResult
    description: str
    items_processed: int
    items_recovered: int
    execution_time: float
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
