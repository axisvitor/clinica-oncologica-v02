"""
Saga Orchestrator Type Definitions.

This module provides type aliases and data structures
used throughout the saga orchestration system.
"""

from typing import TypedDict, Optional, List, Any, Dict


class SagaLogEntry(TypedDict):
    """Log entry structure for saga execution tracking."""

    step: int
    operation: str
    status: str
    error: Optional[str]
    timestamp: str


class SagaStatusInfo(TypedDict):
    """Status information structure for saga monitoring."""

    id: str
    status: Optional[str]
    current_step: int
    patient_id: Optional[str]
    doctor_id: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    failed_at: Optional[str]
    error_message: Optional[str]
    error_type: Optional[str]
    execution_log: Optional[List[Dict[str, Any]]]


class FailedSagaSummary(TypedDict):
    """Summary information for failed saga listing."""

    id: str
    doctor_id: Optional[str]
    current_step: int
    error_message: Optional[str]
    error_type: Optional[str]
    failed_at: Optional[str]
    retry_count: int


class CompensationResult(TypedDict):
    """Result of a compensation step execution."""

    step: int
    step_name: str
    success: bool
    error: Optional[str]


class ResumeResult(TypedDict):
    """Result of saga resume operation."""

    status: str
    message: Optional[str]
    error: Optional[str]
