"""
Flow Analytics model for tracking flow performance metrics.
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    ForeignKey,
    Numeric,
    DateTime,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import BaseModel


class FlowAnalytics(BaseModel):
    """
    Analytics data for patient flow tracking.
    Table: flow_analytics
    """

    __tablename__ = "flow_analytics"

    # References
    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    flow_template_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("flow_template_versions.id"),
        nullable=True,
        index=True,
    )

    # Metrics (Matching DB Schema)
    total_steps = Column(Integer, nullable=True)
    completed_steps = Column(Integer, nullable=True)
    success_rate = Column(Numeric(5, 2), nullable=True)
    avg_response_time_seconds = Column(Integer, nullable=True)

    # JSONB Data
    step_analytics = Column(JSONB, nullable=True)
    interaction_patterns = Column(JSONB, nullable=True)

    # Period tracking
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)

    # Relationships
    patient = relationship("Patient", back_populates="analytics", lazy="select")
    template_version = relationship("FlowTemplateVersion")

    def __repr__(self):
        return f"<FlowAnalytics(patient_id='{self.patient_id}', calculated_at='{self.calculated_at}')>"


class FlowMessage(BaseModel):
    """
    Messages definitions for flow templates.
    Table: flow_messages
    NOTE: This table stores TEMPLATE definitions, not sent messages.
    """

    __tablename__ = "flow_messages"

    # References
    flow_template_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("flow_template_versions.id"),
        nullable=False,
        index=True,
    )

    # Message structure - matching DB schema
    step_number = Column(Integer, nullable=False)
    message_key = Column(String(100), nullable=False)
    message_text = Column(Text, nullable=False)
    message_type = Column(String(50), default="text", nullable=True)

    # Interactive components
    buttons = Column(JSONB, nullable=True)
    list_items = Column(JSONB, nullable=True)
    conditions = Column(JSONB, nullable=True)

    # Timing configuration
    delay_seconds = Column(Integer, default=0, nullable=True)

    # Relationships
    template_version = relationship("FlowTemplateVersion", backref="flow_messages")

    def __repr__(self):
        return f"<FlowMessage(key='{self.message_key}', step={self.step_number})>"

