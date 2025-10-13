"""
Flow Analytics model for tracking flow performance metrics.
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Boolean, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class FlowAnalytics(BaseModel):
    """Analytics data for patient flow tracking."""
    __tablename__ = "flow_analytics"
    
    # References
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    flow_template_version_id = Column(UUID(as_uuid=True), ForeignKey("flow_template_versions.id"), nullable=True)
    
    # Metrics
    total_messages_sent = Column(Integer, default=0, nullable=False)
    total_messages_received = Column(Integer, default=0, nullable=False)
    total_interactions = Column(Integer, default=0, nullable=False)
    
    # Response metrics
    avg_response_time_minutes = Column(Float, nullable=True)
    completion_rate = Column(Float, nullable=True)  # 0.0 to 1.0
    engagement_score = Column(Float, nullable=True)  # 0.0 to 100.0
    
    # Quiz metrics
    quiz_completion_rate = Column(Float, nullable=True)
    avg_quiz_score = Column(Float, nullable=True)
    
    # Timing
    first_interaction_at = Column(DateTime(timezone=True), nullable=True)
    last_interaction_at = Column(DateTime(timezone=True), nullable=True)
    
    # Additional analytics data
    analytics_data = Column("interaction_patterns", JSONB, nullable=True, default=dict)
    
    # Period tracking
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    success_rate = Column(Numeric, nullable=True)
    completed_steps = Column(Integer, nullable=True)
    total_steps = Column(Integer, nullable=True)
    step_analytics = Column(JSONB, nullable=True)
    avg_response_time_seconds = Column(Integer, nullable=True)
    
    # Relationships
    patient = relationship("Patient", back_populates="analytics", lazy="select")
    
    def __repr__(self):
        return f"<FlowAnalytics(patient_id='{self.patient_id}', engagement={self.engagement_score})>"


class FlowMessage(BaseModel):
    """Messages specific to flow templates."""
    __tablename__ = "flow_messages"
    
    # References
    flow_template_id = Column(UUID(as_uuid=True), ForeignKey("flow_templates.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=True)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)
    
    # Message details
    step_name = Column(String(100), nullable=False)
    message_type = Column(String(50), nullable=False)  # text, image, video, quiz
    content = Column(String, nullable=False)
    
    # Scheduling
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    status = Column(String(50), default="pending")  # pending, sent, delivered, read, failed
    
    # Message metadata (renamed from metadata to avoid SQLAlchemy reserved word)
    message_metadata = Column("metadata", JSONB, nullable=True, default=dict)
    
    def __repr__(self):
        return f"<FlowMessage(step='{self.step_name}', status='{self.status}')>"


class QuizQuestion(BaseModel):
    """Individual quiz question model."""
    __tablename__ = "quiz_questions"
    
    # References
    quiz_template_id = Column(UUID(as_uuid=True), ForeignKey("quiz_templates.id"), nullable=False)
    
    # Question details
    question_text = Column(String, nullable=False)
    question_type = Column(String(50), nullable=False)  # multiple_choice, text, scale, yes_no
    question_order = Column(Integer, nullable=False)
    
    # Options for multiple choice
    options = Column(JSONB, nullable=True)  # Array of options
    correct_answer = Column(String, nullable=True)
    
    # Scoring
    points = Column(Integer, default=1)
    is_required = Column(Boolean, default=False)
    
    # Question metadata (renamed from metadata to avoid SQLAlchemy reserved word)
    question_metadata = Column("metadata", JSONB, nullable=True, default=dict)
    
    def __repr__(self):
        return f"<QuizQuestion(text='{self.question_text[:50]}...', type='{self.question_type}')>"
