"""
Flow Coordinator Models - Data models for flow coordination.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID

from app.models.patient import Patient
from app.models.flow import PatientFlowState


class FlowDecision(Enum):
    """Types of flow decisions."""

    CONTINUE_CURRENT = "continue_current"
    ADVANCE_PHASE = "advance_phase"
    ADJUST_TIMING = "adjust_timing"
    PERSONALIZE_CONTENT = "personalize_content"
    ESCALATE_INTERVENTION = "escalate_intervention"
    PAUSE_FLOW = "pause_flow"
    RESUME_FLOW = "resume_flow"


class FlowContext:
    """Context for flow decision making."""

    def __init__(self):
        self.patient_id: Optional[UUID] = None
        self.current_day: Optional[int] = None
        self.flow_state: Optional[PatientFlowState] = None
        self.patient_data: Optional[Patient] = None
        self.recent_interactions: List[Dict] = []
        self.mood_indicators: Dict[str, Any] = {}
        self.adherence_metrics: Dict[str, float] = {}
        self.risk_factors: List[str] = []
        self.knowledge_context: Dict[str, Any] = {}
