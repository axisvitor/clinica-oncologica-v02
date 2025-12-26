"""
Flow state and template models for conversation management.
Standardized to match the AWS RDS PostgreSQL schema.
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.models.base import BaseModel
from app.models.enums import FlowState  # Consolidated enum

# Re-export for backward compatibility
# FlowState is now defined in app.models.enums


class FlowKind(BaseModel):
    """
    Definitions of different flow types (Kinds).
    Table: flow_kinds
    """
    __tablename__ = "flow_kinds"

    # Primary Attributes (Matching RDS)
    kind_key = Column(String(100), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, server_default="true")

    # Compatibility Aliases
    @property
    def flow_type(self): return self.kind_key
    @property
    def name(self): return self.display_name

    # Relationships
    versions = relationship(
        "FlowTemplateVersion",
        back_populates="kind",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("kind_key", name="flow_kinds_kind_key_key"),
    )

    def __repr__(self):
        return f"<FlowKind(key='{self.kind_key}', name='{self.display_name}')>"


class FlowTemplateVersion(BaseModel):
    """
    Versions of a specific flow template.
    Table: flow_template_versions
    """
    __tablename__ = "flow_template_versions"

    # Foreign Keys
    flow_kind_id = Column(
        UUID(as_uuid=True),
        ForeignKey("flow_kinds.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Versioning (Matching RDS)
    version_number = Column(Integer, nullable=False)
    template_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Lifecycle
    is_active = Column(Boolean, default=False, server_default="false")

    # Data (Stored as 'steps' in RDS)
    steps = Column("steps", JSONB, nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=True)

    # Audit
    created_by = Column(UUID(as_uuid=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    deprecated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    kind = relationship("FlowKind", back_populates="versions")
    flow_states = relationship("PatientFlowState", back_populates="template_version")

    # Backward Compatibility Aliases
    @property
    def version(self): return str(self.version_number)
    @property
    def messages(self): return self.steps
    @property
    def kind_id(self): return self.flow_kind_id
    @property
    def is_current(self): return self.is_active
    @property
    def status(self): return "published" if self.is_active else "draft"

    __table_args__ = (
        UniqueConstraint("flow_kind_id", "version_number", name="unique_flow_version"),
        Index("idx_ftv_kind_active", "flow_kind_id", "is_active"),
    )

    def __repr__(self):
        return f"<FlowTemplateVersion(kind='{self.flow_kind_id}', v={self.version_number})>"


class PatientFlowState(BaseModel):
    """
    Tracking the progress of a patient in a specific flow version.
    Table: patient_flow_states
    """
    __tablename__ = "patient_flow_states"

    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    flow_template_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("flow_template_versions.id"),
        nullable=False,
        index=True
    )
    
    current_step = Column(Integer, default=0)
    status = Column(String(50), index=True) # onboarding, active, paused...
    
    # State Data
    step_data = Column(JSONB, nullable=True, default=dict)
    flow_metadata = Column(JSONB, nullable=True)
    
    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    next_scheduled_at = Column(DateTime(timezone=True), nullable=True)
    last_interaction_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    patient = relationship("Patient", back_populates="flow_states")
    template_version = relationship("FlowTemplateVersion", back_populates="flow_states")

    __table_args__ = (
        UniqueConstraint("patient_id", "flow_template_version_id", name="uq_patient_flow_state_version"),
    )

    def __repr__(self):
        return f"<PatientFlowState(patient='{self.patient_id}', step={self.current_step})>"