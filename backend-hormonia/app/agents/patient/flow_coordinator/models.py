"""Flow Coordinator Models - Data models for flow coordination."""

from __future__ import annotations

# Standard library
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

# Local
from app.models.flow import PatientFlowState
from app.models.patient import Patient


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
