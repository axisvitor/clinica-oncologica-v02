"""
A/B Testing Database Models for Hormonia Healthcare System

Defines database schema for A/B testing experiments with HIPAA compliance
and healthcare safety requirements.
"""

from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.models.base import BaseModel


class ExperimentStatus(enum.Enum):
    """Experiment lifecycle status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class VariantType(enum.Enum):
    """A/B test variant types."""
    CONTROL = "control"
    TREATMENT = "treatment"


class PatientSafetyLevel(enum.Enum):
    """Patient safety classification."""
    SAFE = "safe"
    RESTRICTED = "restricted"
    EXCLUDED = "excluded"


class ABExperiment(BaseModel):
    """A/B Testing Experiment model."""
    __tablename__ = "ab_experiments"

    # Basic experiment info
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    message_template = Column(String(100), nullable=False, index=True)

    # Experiment configuration
    target_population = Column(JSONB, nullable=True, default=dict)
    duration_days = Column(Integer, nullable=False, default=30)
    traffic_split = Column(Float, nullable=False, default=0.5)  # Percentage to treatment

    # Metrics configuration
    primary_metric = Column(String(100), nullable=False, default="response_rate")
    secondary_metrics = Column(JSONB, nullable=True, default=list)

    # Status and lifecycle
    status = Column(ENUM(ExperimentStatus), nullable=False, default=ExperimentStatus.DRAFT, index=True)
    start_date = Column(DateTime(timezone=True), nullable=True, index=True)
    end_date = Column(DateTime(timezone=True), nullable=True, index=True)

    # Safety and compliance
    safety_checks_enabled = Column(Boolean, nullable=False, default=True)
    medical_keyword_check = Column(Boolean, nullable=False, default=True)
    manual_review_required = Column(Boolean, nullable=False, default=True)
    emergency_stop_enabled = Column(Boolean, nullable=False, default=True)

    # Statistical configuration
    statistical_config = Column(JSONB, nullable=True, default=dict)

    # Encrypted experiment configuration
    encrypted_config = Column(Text, nullable=True)  # Stores full encrypted config

    # Audit fields
    created_by = Column(String(255), nullable=False, default="system")
    started_by = Column(String(255), nullable=True)
    terminated_by = Column(String(255), nullable=True)
    termination_reason = Column(Text, nullable=True)
    terminated_at = Column(DateTime(timezone=True), nullable=True)

    # Performance metrics (cached for quick access)
    total_participants = Column(Integer, nullable=False, default=0)
    control_participants = Column(Integer, nullable=False, default=0)
    treatment_participants = Column(Integer, nullable=False, default=0)

    # Results (populated when experiment completes)
    results = Column(JSONB, nullable=True)
    is_statistically_significant = Column(Boolean, nullable=True)
    winner = Column(String(50), nullable=True)
    effect_size = Column(Float, nullable=True)
    p_value = Column(Float, nullable=True)
    confidence_interval = Column(JSONB, nullable=True)

    # Relationships
    variant_assignments = relationship("ABVariantAssignment", back_populates="experiment")
    experiment_metrics = relationship("ABExperimentMetric", back_populates="experiment")

    def __repr__(self):
        return f"<ABExperiment(name='{self.name}', status='{self.status.value}')>"

    @property
    def is_active(self) -> bool:
        """Check if experiment is currently active."""
        return self.status == ExperimentStatus.ACTIVE

    @property
    def can_be_started(self) -> bool:
        """Check if experiment can be started."""
        return self.status == ExperimentStatus.DRAFT

    @property
    def can_be_stopped(self) -> bool:
        """Check if experiment can be stopped."""
        return self.status in [ExperimentStatus.ACTIVE, ExperimentStatus.PAUSED]


class ABVariantAssignment(BaseModel):
    """Patient variant assignments for A/B testing."""
    __tablename__ = "ab_variant_assignments"

    # Experiment reference
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("ab_experiments.id"), nullable=False, index=True)

    # Patient reference (anonymized for privacy)
    anonymous_patient_id = Column(String(32), nullable=False, index=True)  # SHA-256 hash (first 32 chars)

    # Assignment details
    variant = Column(ENUM(VariantType), nullable=False, index=True)
    safety_level = Column(ENUM(PatientSafetyLevel), nullable=False, index=True)

    # Assignment metadata
    assignment_hash = Column(String(64), nullable=False, index=True)  # For deterministic assignment
    assignment_reason = Column(String(100), nullable=True)  # e.g., "safety_restriction"

    # Tracking
    assigned_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)

    # Relationships
    experiment = relationship("ABExperiment", back_populates="variant_assignments")

    __table_args__ = (
        Index('ix_ab_variant_exp_patient', 'experiment_id', 'anonymous_patient_id', unique=True),
        Index('ix_ab_variant_exp_variant', 'experiment_id', 'variant'),
        Index('ix_ab_variant_safety', 'safety_level', 'variant'),
    )

    def __repr__(self):
        return f"<ABVariantAssignment(experiment_id='{self.experiment_id}', variant='{self.variant.value}')>"


class ABExperimentMetric(BaseModel):
    """A/B experiment performance metrics."""
    __tablename__ = "ab_experiment_metrics"

    # Experiment reference
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("ab_experiments.id"), nullable=False, index=True)

    # Message/event tracking
    message_id = Column(Integer, nullable=True, index=True)  # Reference to messages table
    anonymous_patient_id = Column(String(32), nullable=False, index=True)

    # Variant and event details
    variant = Column(ENUM(VariantType), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)  # sent, delivered, read, responded, error

    # Performance data
    response_time_seconds = Column(Float, nullable=True)  # Time to respond
    engagement_score = Column(Float, nullable=True)  # Engagement quality score
    error_details = Column(Text, nullable=True)

    # Event metadata
    event_data = Column(JSONB, nullable=True, default=dict)
    event_timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)

    # Processing flags
    processed = Column(Boolean, nullable=False, default=False, index=True)
    included_in_analysis = Column(Boolean, nullable=False, default=True)
    exclusion_reason = Column(String(255), nullable=True)

    # Relationships
    experiment = relationship("ABExperiment", back_populates="experiment_metrics")

    __table_args__ = (
        Index('ix_ab_metrics_exp_variant', 'experiment_id', 'variant'),
        Index('ix_ab_metrics_event_time', 'event_type', 'event_timestamp'),
        Index('ix_ab_metrics_patient_event', 'anonymous_patient_id', 'event_type'),
        Index('ix_ab_metrics_analysis', 'experiment_id', 'included_in_analysis', 'processed'),
    )

    def __repr__(self):
        return f"<ABExperimentMetric(experiment_id='{self.experiment_id}', event_type='{self.event_type}')>"


class ABExperimentResult(BaseModel):
    """Comprehensive A/B experiment results and analysis."""
    __tablename__ = "ab_experiment_results"

    # Experiment reference
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("ab_experiments.id"), nullable=False, unique=True, index=True)

    # Analysis metadata
    analysis_timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)
    analysis_version = Column(String(50), nullable=False, default="1.0")
    analyst_id = Column(String(255), nullable=True)  # Who ran the analysis

    # Sample sizes
    control_sample_size = Column(Integer, nullable=False)
    treatment_sample_size = Column(Integer, nullable=False)
    total_sample_size = Column(Integer, nullable=False)

    # Primary metric results
    primary_metric_name = Column(String(100), nullable=False)
    control_primary_value = Column(Float, nullable=False)
    treatment_primary_value = Column(Float, nullable=False)
    primary_metric_difference = Column(Float, nullable=False)
    primary_metric_relative_change = Column(Float, nullable=False)

    # Statistical test results
    statistical_test_type = Column(String(100), nullable=False)
    p_value = Column(Float, nullable=False, index=True)
    alpha = Column(Float, nullable=False, default=0.05)
    is_statistically_significant = Column(Boolean, nullable=False, index=True)

    # Effect size measures
    cohens_d = Column(Float, nullable=True)
    effect_size_magnitude = Column(String(50), nullable=True)  # small, medium, large

    # Confidence intervals
    confidence_level = Column(Float, nullable=False, default=0.95)
    ci_lower_bound = Column(Float, nullable=True)
    ci_upper_bound = Column(Float, nullable=True)
    ci_margin_of_error = Column(Float, nullable=True)

    # Winner determination
    winner = Column(String(50), nullable=True, index=True)  # control, treatment, or null (tie)
    winner_confidence = Column(Float, nullable=True)  # Confidence in winner
    recommendation = Column(Text, nullable=True)

    # Secondary metrics (stored as JSON)
    secondary_metrics_results = Column(JSONB, nullable=True, default=dict)

    # Detailed analysis results
    detailed_results = Column(JSONB, nullable=True, default=dict)
    variant_performance = Column(JSONB, nullable=True, default=dict)

    # Quality assurance
    data_quality_score = Column(Float, nullable=True)  # 0-100 score
    anomalies_detected = Column(JSONB, nullable=True, default=list)
    quality_warnings = Column(JSONB, nullable=True, default=list)

    # Business impact
    projected_impact = Column(JSONB, nullable=True, default=dict)
    cost_benefit_analysis = Column(JSONB, nullable=True, default=dict)

    # Relationships
    experiment = relationship("ABExperiment", back_populates="experiment_results")

    def __repr__(self):
        return f"<ABExperimentResult(experiment_id='{self.experiment_id}', winner='{self.winner}')>"

    @property
    def is_conclusive(self) -> bool:
        """Check if results are conclusive (significant with adequate sample size)."""
        return (
            self.is_statistically_significant and
            self.control_sample_size >= 100 and
            self.treatment_sample_size >= 100
        )


# Add relationship back to ABExperiment
ABExperiment.experiment_results = relationship("ABExperimentResult", back_populates="experiment", uselist=False)


class ABExperimentAudit(BaseModel):
    """Audit log for A/B experiment activities."""
    __tablename__ = "ab_experiment_audit"

    # Experiment reference
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("ab_experiments.id"), nullable=False, index=True)

    # Audit details
    action = Column(String(100), nullable=False, index=True)  # created, started, stopped, modified
    actor = Column(String(255), nullable=False)  # User or system performing action
    actor_type = Column(String(50), nullable=False, default="user")  # user, system, automated

    # Action details
    action_details = Column(JSONB, nullable=True, default=dict)
    previous_state = Column(JSONB, nullable=True, default=dict)
    new_state = Column(JSONB, nullable=True, default=dict)

    # Context
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(255), nullable=True)

    # Compliance
    hipaa_logged = Column(Boolean, nullable=False, default=True)
    gdpr_compliant = Column(Boolean, nullable=False, default=True)

    # Timestamp
    timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)

    __table_args__ = (
        Index('ix_ab_audit_exp_action', 'experiment_id', 'action'),
        Index('ix_ab_audit_actor_time', 'actor', 'timestamp'),
        Index('ix_ab_audit_compliance', 'hipaa_logged', 'gdpr_compliant'),
    )

    def __repr__(self):
        return f"<ABExperimentAudit(experiment_id='{self.experiment_id}', action='{self.action}')>"


# Performance monitoring table for real-time alerts
class ABExperimentMonitoring(BaseModel):
    """Real-time monitoring data for A/B experiments."""
    __tablename__ = "ab_experiment_monitoring"

    # Experiment reference
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("ab_experiments.id"), nullable=False, index=True)

    # Monitoring period
    monitoring_period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    monitoring_period_end = Column(DateTime(timezone=True), nullable=False, index=True)

    # Key performance indicators
    control_response_rate = Column(Float, nullable=True)
    treatment_response_rate = Column(Float, nullable=True)
    control_error_rate = Column(Float, nullable=True)
    treatment_error_rate = Column(Float, nullable=True)

    # Safety indicators
    safety_violations_count = Column(Integer, nullable=False, default=0)
    medical_content_alerts = Column(Integer, nullable=False, default=0)
    patient_complaints = Column(Integer, nullable=False, default=0)

    # Performance thresholds status
    response_rate_threshold_breached = Column(Boolean, nullable=False, default=False)
    error_rate_threshold_breached = Column(Boolean, nullable=False, default=False)
    engagement_threshold_breached = Column(Boolean, nullable=False, default=False)

    # Alerts sent
    alerts_sent = Column(JSONB, nullable=True, default=list)
    emergency_stop_triggered = Column(Boolean, nullable=False, default=False)

    # Detailed metrics
    monitoring_data = Column(JSONB, nullable=True, default=dict)

    # Processing status
    processed_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    next_check_at = Column(DateTime(timezone=True), nullable=True, index=True)

    __table_args__ = (
        Index('ix_ab_monitoring_period', 'monitoring_period_start', 'monitoring_period_end'),
        Index('ix_ab_monitoring_alerts', 'emergency_stop_triggered', 'response_rate_threshold_breached'),
        Index('ix_ab_monitoring_next_check', 'next_check_at'),
    )

    def __repr__(self):
        return f"<ABExperimentMonitoring(experiment_id='{self.experiment_id}', period_start='{self.monitoring_period_start}')>"