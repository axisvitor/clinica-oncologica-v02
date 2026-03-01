"""Flow Coordinator Models - Data models for flow coordination."""

from __future__ import annotations

# DDD service agent - no LLM calls, not a pydantic-ai migration target.

# Standard library
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

# Third-party
from typing_extensions import TypedDict

# Local
from app.models.flow import PatientFlowState
from app.models.patient import Patient


class TaskPayload(TypedDict, total=False):
    """Standard task payload for inter-agent communication.

    Defines the canonical format for tasks exchanged between agents
    in the flow coordinator.  All fields are optional so callers can
    provide only the keys relevant to the specific task.

    Attributes:
        task_type: Standardised task identifier (e.g. "send_message").
        patient_id: Patient UUID as string (no PHI).
        flow_id: Associated flow UUID as string.
        data: Arbitrary task-specific payload.
        priority: Priority level ("low", "normal", "high", "critical").
        correlation_id: ID used for tracing a request across agents.
    """

    task_type: str
    patient_id: Optional[str]
    flow_id: Optional[str]
    data: Dict[str, Any]
    priority: str
    correlation_id: Optional[str]


class FlowDecision(Enum):
    """
    Types of flow decisions.

    Defines all possible decisions the flow coordinator
    can make regarding patient treatment flow progression.
    """

    CONTINUE_CURRENT = "continue_current"
    ADVANCE_PHASE = "advance_phase"
    ADJUST_TIMING = "adjust_timing"
    PERSONALIZE_CONTENT = "personalize_content"
    ESCALATE_INTERVENTION = "escalate_intervention"
    PAUSE_FLOW = "pause_flow"
    RESUME_FLOW = "resume_flow"


@dataclass
class FlowContext:
    """
    Represents comprehensive context for flow decision making.

    Aggregates all relevant patient data, flow state, interactions,
    and metrics needed for intelligent flow decisions.

    Attributes:
        patient_id: Patient UUID.
        current_day: Current day in treatment flow.
        flow_state: Current flow state record.
        patient_data: Patient record.
        recent_interactions: Recent patient interactions.
        mood_indicators: Mood tracking data.
        adherence_metrics: Treatment adherence metrics.
        risk_factors: Identified risk factors.
        knowledge_context: Knowledge graph context.
    """

    patient_id: Optional[UUID] = None
    current_day: Optional[int] = None
    flow_state: Optional[PatientFlowState] = None
    patient_data: Optional[Patient] = None
    recent_interactions: List[Dict] = field(default_factory=list)
    mood_indicators: Dict[str, Any] = field(default_factory=dict)
    adherence_metrics: Dict[str, float] = field(default_factory=dict)
    risk_factors: List[str] = field(default_factory=list)
    knowledge_context: Dict[str, Any] = field(default_factory=dict)
