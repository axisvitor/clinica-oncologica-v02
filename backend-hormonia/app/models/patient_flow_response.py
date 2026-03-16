"""
PatientFlowResponse model for structured patient response storage.

Each row records a single patient free-text response with full flow context
(day number, message index, timestamps, prompt/response message IDs).
Dual-written alongside existing step_data JSONB in process_patient_response().
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class PatientFlowResponse(BaseModel):
    """
    Structured storage for individual patient responses.

    Table: patient_flow_responses
    """

    __tablename__ = "patient_flow_responses"

    flow_state_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patient_flow_states.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_number = Column(Integer, nullable=True)
    message_index = Column(Integer, nullable=True)
    response_text = Column(Text, nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=False)
    prompt_message_id = Column(String(255), nullable=True)
    response_message_id = Column(String(255), nullable=True)

    # Relationships
    flow_state = relationship("PatientFlowState")
    patient = relationship("Patient")

    def __repr__(self) -> str:
        return (
            f"<PatientFlowResponse(patient='{self.patient_id}', "
            f"day={self.day_number}, msg={self.message_index})>"
        )
