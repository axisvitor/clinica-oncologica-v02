"""
Flow state and template models for conversation management.
Standardized to match the AWS RDS PostgreSQL schema.
"""

from datetime import datetime
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
from sqlalchemy.ext.mutable import MutableDict
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


# Backward-compatible alias for legacy imports
FlowTemplate = FlowTemplateVersion


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
    step_data = Column(MutableDict.as_mutable(JSONB), nullable=True, default=dict)
    flow_metadata = Column(MutableDict.as_mutable(JSONB), nullable=True)
    
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

    def _ensure_step_data(self) -> dict:
        if self.step_data is None:
            self.step_data = {}
        return self.step_data

    @staticmethod
    def _parse_datetime(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, dict):
            for key in ("sent_at", "timestamp", "created_at"):
                if key in value:
                    return PatientFlowState._parse_datetime(value[key])
            return None
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    @property
    def current_day(self) -> int:
        step_data = self.step_data or {}
        if "current_flow_day" in step_data:
            try:
                return int(step_data.get("current_flow_day") or 0)
            except (TypeError, ValueError):
                return 0
        return int(self.current_step or 0)

    @current_day.setter
    def current_day(self, value: int) -> None:
        step_data = self._ensure_step_data()
        step_data["current_flow_day"] = value
        self.current_step = value

    @property
    def enrollment_date(self):
        step_data = self.step_data or {}
        value = step_data.get("enrollment_date") or self.started_at
        return self._parse_datetime(value)

    @enrollment_date.setter
    def enrollment_date(self, value) -> None:
        step_data = self._ensure_step_data()
        parsed = self._parse_datetime(value)
        step_data["enrollment_date"] = parsed.isoformat() if parsed else None

    @property
    def last_message_sent(self):
        step_data = self.step_data or {}
        value = step_data.get("last_message_sent") or step_data.get("last_message_sent_at")
        return self._parse_datetime(value)

    @last_message_sent.setter
    def last_message_sent(self, value) -> None:
        step_data = self._ensure_step_data()
        parsed = self._parse_datetime(value)
        iso_value = parsed.isoformat() if parsed else None
        step_data["last_message_sent"] = iso_value
        step_data["last_message_sent_at"] = iso_value

    @property
    def next_message_due(self):
        step_data = self.step_data or {}
        value = step_data.get("next_message_due") or self.next_scheduled_at
        return self._parse_datetime(value)

    @next_message_due.setter
    def next_message_due(self, value) -> None:
        step_data = self._ensure_step_data()
        parsed = self._parse_datetime(value)
        step_data["next_message_due"] = parsed.isoformat() if parsed else None
        self.next_scheduled_at = parsed

    @property
    def is_paused(self) -> bool:
        step_data = self.step_data or {}
        paused = step_data.get("paused")
        if paused is not None:
            return bool(paused)
        return str(self.status or "").lower() == "paused"

    @is_paused.setter
    def is_paused(self, value: bool) -> None:
        step_data = self._ensure_step_data()
        step_data["paused"] = bool(value)
        if value:
            self.status = "paused"
        elif str(self.status or "").lower() == "paused":
            self.status = "active"

    @property
    def pause_reason(self):
        step_data = self.step_data or {}
        if "pause_reason" in step_data:
            return step_data.get("pause_reason")
        if self.flow_metadata:
            return self.flow_metadata.get("pause_reason")
        return None

    @pause_reason.setter
    def pause_reason(self, value) -> None:
        step_data = self._ensure_step_data()
        step_data["pause_reason"] = value
        metadata = dict(self.flow_metadata or {})
        metadata["pause_reason"] = value
        self.flow_metadata = metadata

    @property
    def monthly_cycle(self):
        step_data = self.step_data or {}
        return step_data.get("monthly_cycle")

    @monthly_cycle.setter
    def monthly_cycle(self, value) -> None:
        step_data = self._ensure_step_data()
        step_data["monthly_cycle"] = value

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
