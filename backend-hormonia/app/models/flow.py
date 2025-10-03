"""
Flow state models for conversation management.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import BaseModel


class PatientFlowState(BaseModel):
    """Patient flow state tracking."""
    __tablename__ = "patient_flow_states"  # Changed to match actual table name
    
    # Patient reference
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    
    # Flow details - using versioned system only
    template_version_id = Column(UUID(as_uuid=True), ForeignKey("flow_template_versions.id"), nullable=False)
    current_step = Column(Integer, default=0, nullable=False)
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # State-specific data
    state_data = Column(JSONB, nullable=True, default=dict)
    
    # Relationships
    patient = relationship("Patient", back_populates="flow_states")
    template_version = relationship("FlowTemplateVersion", back_populates="flow_states")
    
    def __repr__(self):
        return f"<PatientFlowState(patient_id='{self.patient_id}', template_version_id='{self.template_version_id}')>"

# New versioning models for template refactoring


class FlowKind(BaseModel):
    """Flow kind definitions - separates flow types from versions."""
    __tablename__ = "flow_kinds"

    # Kind identification
    flow_type = Column(String(100), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)
    is_active = Column(Boolean, nullable=True, default=True)
    display_order = Column(Integer, nullable=True, default=0)
    flow_metadata = Column("metadata", JSONB, nullable=True, default=dict)  # Renamed to avoid SQLAlchemy reserved word

    # Relationships
    versions = relationship("FlowTemplateVersion", back_populates="kind", foreign_keys="FlowTemplateVersion.kind_id")

    def __repr__(self):
        return f"<FlowKind(flow_type='{self.flow_type}', name='{self.name}')>"


class FlowTemplateVersion(BaseModel):
    """Flow template versions - allows multiple versions per flow type."""
    __tablename__ = "flow_template_versions"

    # Version identification
    kind_id = Column(UUID(as_uuid=True), ForeignKey("flow_kinds.id", ondelete="CASCADE"), nullable=False)
    version = Column(String(20), nullable=False)

    # Lifecycle management
    status = Column(String(20), nullable=False, default='draft')  # draft, published, archived
    is_current = Column(Boolean, nullable=False, default=False)

    # Template configuration (JSONB fields matching real database schema)
    messages = Column(JSONB, nullable=False, default=dict)
    quiz_templates = Column(JSONB, nullable=True, default=dict)
    alerts = Column(JSONB, nullable=True, default=dict)
    changelog = Column(Text, nullable=True)

    # Audit trail
    created_by = Column(UUID(as_uuid=True), nullable=True)
    approved_by = Column(UUID(as_uuid=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    kind = relationship("FlowKind", back_populates="versions", foreign_keys=[kind_id])
    flow_states = relationship("PatientFlowState", back_populates="template_version")

    def __repr__(self):
        return f"<FlowTemplateVersion(kind_id='{self.kind_id}', version='{self.version}', status='{self.status}')>"


# FlowAnalytics and FlowMessage are now in flow_analytics.py to avoid duplication