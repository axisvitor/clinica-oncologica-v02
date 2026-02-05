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
from sqlalchemy.orm import relationship, object_session
from sqlalchemy.sql import func

from app.models.base import BaseModel

# Re-export for backward compatibility
# FlowState is now defined in app.models.enums


class _FlowTypeProxy(str):
    """String wrapper that exposes a .value attribute for enum-like access."""

    @property
    def value(self) -> str:
        return str(self)


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
    is_draft = Column(Boolean, default=True, server_default="true")

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
    @messages.setter
    def messages(self, value): self.steps = value
    @property
    def kind_id(self): return self.flow_kind_id
    @kind_id.setter
    def kind_id(self, value): self.flow_kind_id = value
    @property
    def is_current(self): return self.is_active
    @property
    def status(self):
        if self.is_draft:
            return "draft"
        if self.is_active:
            return "published"
        return "archived"
    @property
    def template_metadata(self): return self.metadata_json
    @template_metadata.setter
    def template_metadata(self, value): self.metadata_json = value

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
    version = Column(Integer, default=0, nullable=False, server_default="0")
    
    # State Data
    step_data = Column(JSONB, nullable=True, default=dict)
    flow_metadata = Column(JSONB, nullable=True)
    
    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    next_scheduled_at = Column(DateTime(timezone=True), nullable=True)
    last_interaction_at = Column(DateTime(timezone=True), nullable=True)

    # Backward compatibility alias for code using state_data
    @property
    def state_data(self) -> dict:
        """Alias for step_data for backward compatibility.
        
        Initializes step_data to {} if None to prevent lost writes
        when code does `flow_state.state_data['key'] = value`.
        """
        if self.step_data is None:
            self.step_data = {}
        return self.step_data

    @state_data.setter
    def state_data(self, value: dict) -> None:
        """Setter for state_data alias."""
        self.step_data = value

    @property
    def template_version_id(self) -> UUID:
        """Alias for flow_template_version_id for backward compatibility."""
        return self.flow_template_version_id

    @template_version_id.setter
    def template_version_id(self, value: UUID) -> None:
        self.flow_template_version_id = value

    # Relationships
    patient = relationship("Patient", back_populates="flow_states")
    template_version = relationship("FlowTemplateVersion", back_populates="flow_states")

    __table_args__ = (
        UniqueConstraint("patient_id", "flow_template_version_id", name="uq_patient_flow_state_version"),
        Index("idx_patient_flow_states_version", "id", "version"),
    )

    @property
    def flow_type(self) -> str:
        """
        Flow type computed from the related template version and kind.

        Returns an enum-like string wrapper so legacy callers can access .value.
        """
        try:
            if self.template_version and self.template_version.kind:
                return _FlowTypeProxy(self.template_version.kind.kind_key)
        except Exception:
            pass

        session = object_session(self)
        if session and self.flow_template_version_id:
            template_version = session.get(FlowTemplateVersion, self.flow_template_version_id)
            if template_version and template_version.kind:
                return _FlowTypeProxy(template_version.kind.kind_key)
            if template_version:
                flow_kind = session.get(FlowKind, template_version.flow_kind_id)
                if flow_kind:
                    return _FlowTypeProxy(flow_kind.kind_key)

        return _FlowTypeProxy("unknown")

    @flow_type.setter
    def flow_type(self, value) -> None:
        """
        Update flow_template_version_id based on the provided flow type.
        """
        if value is None:
            return

        flow_key = value.value if hasattr(value, "value") else str(value)
        session = object_session(self)
        if session is None:
            raise ValueError("Cannot set flow_type without an active session")

        flow_kind = session.query(FlowKind).filter(FlowKind.kind_key == flow_key).first()
        if not flow_kind:
            raise ValueError(f"No flow kind found for flow type: {flow_key}")

        active_version = (
            session.query(FlowTemplateVersion)
            .filter(
                FlowTemplateVersion.flow_kind_id == flow_kind.id,
                FlowTemplateVersion.is_active,
            )
            .first()
        )
        if not active_version:
            raise ValueError(f"No active template version for flow type: {flow_key}")

        self.flow_template_version_id = active_version.id
        self.template_version = active_version

    def __repr__(self):
        return f"<PatientFlowState(patient='{self.patient_id}', step={self.current_step})>"
