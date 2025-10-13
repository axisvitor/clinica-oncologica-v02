"""
Flow state models for conversation management.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Boolean, Float, Index, UniqueConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import BaseModel


class PatientFlowState(BaseModel):
    """Patient flow state tracking."""
    __tablename__ = "patient_flow_states"  # Changed to match actual table name
    
    # Patient reference
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    
    # Flow details - using versioned system only
    template_version_id = Column(
        "flow_template_version_id",  # actual column name in database
        UUID(as_uuid=True),
        ForeignKey("flow_template_versions.id"),
        nullable=False
    )
    current_step = Column(Integer, nullable=True, default=0)
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # State-specific data
    state_data = Column("step_data", JSONB, nullable=True, default=dict)
    status = Column(String(50), nullable=True)
    next_scheduled_at = Column(DateTime(timezone=True), nullable=True)
    last_interaction_at = Column(DateTime(timezone=True), nullable=True)
    flow_metadata = Column(JSONB, nullable=True)
    
    # Relationships
    patient = relationship("Patient", back_populates="flow_states", cascade="all, delete-orphan")
    template_version = relationship("FlowTemplateVersion", back_populates="flow_states")
    
    # Constraints and indexes to match DB
    __table_args__ = (
        UniqueConstraint('patient_id', 'flow_template_version_id', name='uq_patient_flow_state_unique_version'),
    )

    # Override BaseModel nullability to match DB for this table
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)

    def __repr__(self):
        return f"<PatientFlowState(patient_id='{self.patient_id}', template_version_id='{self.template_version_id}')>"

# New versioning models for template refactoring


class FlowKind(BaseModel):
    """Flow kind definitions - separates flow types from versions."""
    __tablename__ = "flow_kinds"

    # Kind identification
    # Align with DB (kind_key/display_name/is_active)
    flow_type = Column("kind_key", String(100), nullable=False)
    name = Column("display_name", String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=True, default=True)

    # Relationships
    versions = relationship("FlowTemplateVersion", back_populates="kind", foreign_keys="FlowTemplateVersion.kind_id")

    __table_args__ = (
        UniqueConstraint('kind_key', name='flow_kinds_kind_key_key'),
    )

    # Override BaseModel nullability to match DB for this table
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)

    def __repr__(self):
        return f"<FlowKind(flow_type='{self.flow_type}', name='{self.name}')>"


class FlowTemplateVersion(BaseModel):
    """Flow template versions - allows multiple versions per flow type."""
    __tablename__ = "flow_template_versions"

    # Version identification
    kind_id = Column("flow_kind_id", UUID(as_uuid=True), ForeignKey("flow_kinds.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    template_name = Column(String(255), nullable=False)

    # Lifecycle management
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=False)
    is_draft = Column(Boolean, nullable=False, default=True)

    # Template configuration (DB stores steps under 'steps')
    messages = Column("steps", JSONB, nullable=True)
    template_metadata = Column("metadata", JSONB, nullable=True)

    # Audit trail
    created_by = Column(UUID(as_uuid=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    deprecated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)

    # Relationships
    kind = relationship("FlowKind", back_populates="versions", foreign_keys=[kind_id])
    flow_states = relationship("PatientFlowState", back_populates="template_version")

    # Indexes and unique constraints to match DB
    __table_args__ = (
        UniqueConstraint('flow_kind_id', 'version_number', name='unique_flow_version'),
        Index('idx_flow_template_versions_flow_kind', 'flow_kind_id'),
        Index('idx_flow_template_versions_version', 'flow_kind_id', 'version_number'),
        Index('idx_flow_template_versions_active', 'flow_kind_id', 'is_active'),
    )

    def __repr__(self):
        return f"<FlowTemplateVersion(kind_id='{self.kind_id}', version='{self.version_number}', active='{self.is_active}')>"


# FlowAnalytics and FlowMessage are now in flow_analytics.py to avoid duplication