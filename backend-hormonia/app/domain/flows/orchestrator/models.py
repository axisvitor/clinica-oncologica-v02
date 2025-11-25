"""
Flow Orchestrator - Data Models

Contains dataclass models for flow execution context and results.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from uuid import UUID

from .enums import FlowOperationType


@dataclass
class FlowExecutionContext:
    """Context for flow execution operations."""
    patient_id: UUID
    flow_type: str
    operation: FlowOperationType
    current_day: int
    target_day: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class FlowExecutionResult:
    """Result of flow execution operation."""
    success: bool
    patient_id: UUID
    operation: FlowOperationType
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
