from __future__ import annotations

from typing import Any

from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.utils.timezone import now_sao_paulo


class FlowContext:
    """Context for flow execution with patient and conversation data."""

    def __init__(
        self,
        patient: Patient,
        flow_state: PatientFlowState,
        current_day: int,
        flow_type: str = None,
        conversation_history: list[str] = None,
        recent_interactions: list[dict[str, Any]] = None,
        communication_preferences: dict[str, Any] = None,
        medical_context: dict[str, Any] = None,
    ):
        self.patient = patient
        self.flow_state = flow_state
        self.current_day = current_day
        self.flow_type = flow_type or "unknown"
        self.conversation_history = conversation_history or []
        self.recent_interactions = recent_interactions or []
        self.communication_preferences = communication_preferences or {}
        self.medical_context = medical_context or {}
        self.timestamp = now_sao_paulo()

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary."""
        state_data = {}
        if self.flow_state:
            try:
                state_data = self.flow_state.state_data or {}
            except Exception:
                state_data = {}
        flow_kind = state_data.get("flow_kind") or self.flow_type
        send_mode = state_data.get("send_mode") or state_data.get("daily_send_mode")
        message_index = state_data.get("current_day_message_index")
        awaiting_response = state_data.get("awaiting_response")

        return {
            "patient_id": str(self.patient.id),
            "patient_name": self.patient.name,
            "flow_type": self.flow_type,
            "flow_kind": flow_kind,
            "current_day": self.current_day,
            "treatment_day": self._calculate_treatment_day(),
            "conversation_history": self.conversation_history,
            "recent_interactions": self.recent_interactions,
            "communication_preferences": self.communication_preferences,
            "medical_context": self.medical_context,
            "send_mode": send_mode or "single",
            "current_day_message_index": message_index,
            "awaiting_response": awaiting_response,
            "timestamp": self.timestamp.isoformat(),
        }

    def _calculate_treatment_day(self) -> int:
        """Calculate treatment day based on enrollment date."""
        if hasattr(self.patient, "treatment_start_date") and self.patient.treatment_start_date:
            delta = now_sao_paulo().date() - self.patient.treatment_start_date
            return delta.days + 1
        return 1


__all__ = ["FlowContext"]
