"""
A/B Testing API Schemas for Hormonia Healthcare System

Pydantic models for API requests and responses with healthcare compliance
validation and safety checks.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from uuid import UUID

from pydantic import BaseModel, Field, validator, root_validator
from enum import Enum

from app.models.ab_experiment import ExperimentStatus, VariantType, PatientSafetyLevel


class ExperimentStatusEnum(str, Enum):
    """Experiment status for API."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class VariantTypeEnum(str, Enum):
    """Variant type for API."""
    CONTROL = "control"
    TREATMENT = "treatment"


class PatientSafetyLevelEnum(str, Enum):
    """Patient safety level for API."""
    SAFE = "safe"
    RESTRICTED = "restricted"
    EXCLUDED = "excluded"


class StatisticalTestTypeEnum(str, Enum):
    """Statistical test types."""
    T_TEST = "t_test"
    MANN_WHITNEY_U = "mann_whitney_u"
    CHI_SQUARE = "chi_square"
    FISHER_EXACT = "fisher_exact"


# Request Schemas

class ExperimentTargetPopulation(BaseModel):
    """Target population criteria for experiment."""
    min_age: Optional[int] = Field(None, ge=0, le=120, description="Minimum age")
    max_age: Optional[int] = Field(None, ge=0, le=120, description="Maximum age")
    treatment_types: Optional[List[str]] = Field(None, description="Treatment types to include")
    exclude_critical_patients: bool = Field(True, description="Exclude patients with critical conditions")
    exclude_recent_surgery: bool = Field(True, description="Exclude patients with recent surgery")
    include_safety_levels: List[PatientSafetyLevelEnum] = Field(
        default=[PatientSafetyLevelEnum.SAFE, PatientSafetyLevelEnum.RESTRICTED],
        description="Safety levels to include in experiment"
    )

    @validator('max_age')
    def validate_age_range(cls, v, values):
        if v is not None and 'min_age' in values and values['min_age'] is not None:
            if v <= values['min_age']:
                raise ValueError('max_age must be greater than min_age')
        return v


class ExperimentStatisticalConfig(BaseModel):
    """Statistical configuration for experiment."""
    alpha: float = Field(0.05, gt=0, lt=1, description="Significance level")
    min_sample_size: int = Field(100, ge=50, le=10000, description="Minimum sample size per variant")
    min_effect_size: float = Field(0.1, gt=0, le=1, description="Minimum detectable effect size")
    power: float = Field(0.8, gt=0, lt=1, description="Statistical power")
    preferred_test: Optional[StatisticalTestTypeEnum] = Field(None, description="Preferred statistical test")


class ExperimentSafetyConfig(BaseModel):
    """Safety configuration for experiment."""
    medical_keyword_check: bool = Field(True, description="Enable medical keyword safety check")
    manual_review_required: bool = Field(True, description="Require manual review for critical content")
    emergency_stop_enabled: bool = Field(True, description="Enable emergency stop mechanism")
    performance_monitoring: bool = Field(True, description="Enable real-time performance monitoring")
    response_rate_threshold: float = Field(0.2, gt=0, le=1, description="Response rate drop threshold for emergency stop")
    error_rate_threshold: float = Field(0.1, gt=0, le=1, description="Error rate spike threshold for emergency stop")


class CreateExperimentRequest(BaseModel):
    """Request to create a new A/B experiment."""
    name: str = Field(..., min_length=3, max_length=255, description="Experiment name")
    description: str = Field(..., min_length=10, max_length=1000, description="Experiment description")
    message_template: str = Field(..., min_length=1, max_length=100, description="Message template type to test")
    target_population: Optional[ExperimentTargetPopulation] = Field(None, description="Target population criteria")
    duration_days: int = Field(30, ge=1, le=90, description="Experiment duration in days")
    traffic_split: float = Field(0.5, gt=0.1, lt=0.9, description="Traffic percentage to treatment variant")
    primary_metric: str = Field("response_rate", description="Primary success metric")
    secondary_metrics: List[str] = Field(default=[], description="Additional metrics to track")
    statistical_config: Optional[ExperimentStatisticalConfig] = Field(None, description="Statistical configuration")
    safety_config: Optional[ExperimentSafetyConfig] = Field(None, description="Safety configuration")

    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Experiment name cannot be empty')
        # Check for potentially confusing names
        forbidden_words = ['test', 'prod', 'production', 'live']
        if any(word in v.lower() for word in forbidden_words):
            raise ValueError(f'Experiment name should not contain: {", ".join(forbidden_words)}')
        return v.strip()

    @validator('message_template')
    def validate_message_template(cls, v):
        # Validate against allowed templates
        allowed_templates = [
            'quiz_introduction', 'quiz_question', 'quiz_completion',
            'flow_message', 'monthly_quiz_link_invitation', 'monthly_quiz_link_reminder'
        ]
        if v not in allowed_templates:
            raise ValueError(f'Message template must be one of: {", ".join(allowed_templates)}')
        return v

    @validator('secondary_metrics')
    def validate_secondary_metrics(cls, v):
        allowed_metrics = [
            'response_rate', 'delivery_rate', 'engagement_score',
            'response_time', 'error_rate', 'completion_rate'
        ]
        for metric in v:
            if metric not in allowed_metrics:
                raise ValueError(f'Secondary metric "{metric}" not allowed. Choose from: {", ".join(allowed_metrics)}')
        return v


class StartExperimentRequest(BaseModel):
    """Request to start an experiment."""
    confirm_safety_review: bool = Field(..., description="Confirm safety review completed")
    confirm_hipaa_compliance: bool = Field(..., description="Confirm HIPAA compliance review")
    confirm_patient_population: bool = Field(..., description="Confirm target patient population is appropriate")
    override_warnings: bool = Field(False, description="Override non-critical warnings")

    @root_validator
    def validate_confirmations(cls, values):
        required_confirmations = ['confirm_safety_review', 'confirm_hipaa_compliance', 'confirm_patient_population']
        for confirmation in required_confirmations:
            if not values.get(confirmation, False):
                raise ValueError(f'{confirmation} must be confirmed to start experiment')
        return values


class EmergencyStopRequest(BaseModel):
    """Request to emergency stop an experiment."""
    reason: str = Field(..., min_length=10, max_length=500, description="Reason for emergency stop")
    safety_concern: bool = Field(False, description="Is this due to a safety concern?")
    immediate_action_required: bool = Field(False, description="Does this require immediate stakeholder notification?")


class UpdateExperimentRequest(BaseModel):
    """Request to update experiment configuration (only for draft experiments)."""
    name: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, min_length=10, max_length=1000)
    duration_days: Optional[int] = Field(None, ge=1, le=90)
    traffic_split: Optional[float] = Field(None, gt=0.1, lt=0.9)
    target_population: Optional[ExperimentTargetPopulation] = None
    safety_config: Optional[ExperimentSafetyConfig] = None


# Response Schemas

class ExperimentVariant(BaseModel):
    """Experiment variant information."""
    type: VariantTypeEnum
    description: str
    traffic_percentage: float


class ExperimentInfo(BaseModel):
    """Basic experiment information."""
    id: str
    name: str
    description: str
    message_template: str
    status: ExperimentStatusEnum
    created_at: datetime
    created_by: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    duration_days: int
    traffic_split: float
    primary_metric: str
    secondary_metrics: List[str]
    safety_checks_enabled: bool
    total_participants: int
    control_participants: int
    treatment_participants: int

    class Config:
        from_attributes = True


class ExperimentStatistics(BaseModel):
    """Experiment statistical information."""
    sample_size: int
    response_rate: float
    delivery_rate: float
    responded_count: int
    delivered_count: int
    avg_response_time: Optional[float] = None
    error_rate: float
    engagement_score: Optional[float] = None


class StatisticalTestResult(BaseModel):
    """Statistical test results."""
    is_significant: bool
    p_value: Optional[float] = None
    test_type: Optional[str] = None
    alpha: float
    winner: Optional[str] = None
    confidence_interval: Optional[Dict[str, float]] = None
    warning: Optional[str] = None


class EffectSizes(BaseModel):
    """Effect size calculations."""
    cohens_d: float
    absolute_difference: float
    relative_change: float
    magnitude: str  # small, medium, large


class ExperimentResults(BaseModel):
    """Comprehensive experiment results."""
    experiment_id: str
    experiment_name: str
    status: ExperimentStatusEnum
    duration_days: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    analysis_timestamp: datetime

    sample_sizes: Dict[str, int]
    variant_performance: Dict[str, ExperimentStatistics]
    statistical_tests: StatisticalTestResult
    effect_sizes: EffectSizes

    recommendations: List[str]
    confidence_level: float
    is_statistically_significant: bool
    winner: Optional[str] = None

    # Quality indicators
    data_quality_score: Optional[float] = None
    anomalies_detected: List[str] = []
    quality_warnings: List[str] = []


class ExperimentStatus(BaseModel):
    """Current experiment status."""
    experiment_id: str
    name: str
    status: ExperimentStatusEnum
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    total_messages: int
    control_messages: int
    treatment_messages: int
    overall_response_rate: float
    traffic_split: float
    primary_metric: str
    safety_checks_enabled: bool
    days_remaining: Optional[int] = None
    estimated_completion: Optional[datetime] = None


class VariantAssignment(BaseModel):
    """Patient variant assignment information."""
    experiment_id: str
    variant: VariantTypeEnum
    safety_level: PatientSafetyLevelEnum
    assigned_at: datetime
    assignment_reason: Optional[str] = None


class ExperimentMetric(BaseModel):
    """Single experiment metric entry."""
    experiment_id: str
    message_id: Optional[int] = None
    variant: VariantTypeEnum
    event_type: str
    response_time_seconds: Optional[float] = None
    engagement_score: Optional[float] = None
    event_timestamp: datetime
    event_data: Dict[str, Any] = {}


class ExperimentMonitoring(BaseModel):
    """Real-time experiment monitoring data."""
    experiment_id: str
    monitoring_period_start: datetime
    monitoring_period_end: datetime

    # Performance indicators
    control_response_rate: Optional[float] = None
    treatment_response_rate: Optional[float] = None
    control_error_rate: Optional[float] = None
    treatment_error_rate: Optional[float] = None

    # Safety indicators
    safety_violations_count: int
    medical_content_alerts: int
    patient_complaints: int

    # Threshold status
    response_rate_threshold_breached: bool
    error_rate_threshold_breached: bool
    engagement_threshold_breached: bool

    # Alerts
    alerts_sent: List[str]
    emergency_stop_triggered: bool


class ExperimentAuditEntry(BaseModel):
    """Experiment audit log entry."""
    experiment_id: str
    action: str
    actor: str
    actor_type: str
    timestamp: datetime
    action_details: Dict[str, Any] = {}
    hipaa_logged: bool
    gdpr_compliant: bool


class ExperimentList(BaseModel):
    """List of experiments with pagination."""
    experiments: List[ExperimentInfo]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


# API Response Models

class CreateExperimentResponse(BaseModel):
    """Response for experiment creation."""
    experiment_id: str
    message: str
    experiment: ExperimentInfo


class StartExperimentResponse(BaseModel):
    """Response for starting experiment."""
    experiment_id: str
    message: str
    started_at: datetime
    eligible_patients: int
    estimated_completion: datetime


class EmergencyStopResponse(BaseModel):
    """Response for emergency stop."""
    experiment_id: str
    message: str
    stopped_at: datetime
    reason: str
    final_results: Optional[ExperimentResults] = None


class ExperimentAnalysisResponse(BaseModel):
    """Response for experiment analysis."""
    results: ExperimentResults
    recommendations: List[str]
    next_steps: List[str]
    confidence_level: str  # high, medium, low


# Error Responses

class ExperimentError(BaseModel):
    """Experiment-related error response."""
    error: str
    error_code: str
    experiment_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    suggestions: List[str] = []


# Dashboard and Reporting Schemas

class ExperimentDashboard(BaseModel):
    """Experiment dashboard summary."""
    total_experiments: int
    active_experiments: int
    completed_experiments: int
    terminated_experiments: int

    recent_experiments: List[ExperimentInfo]
    performance_summary: Dict[str, Any]
    alerts: List[str]

    # Key metrics
    average_response_rate: float
    total_participants: int
    successful_experiments: int
    success_rate: float


class ExperimentReport(BaseModel):
    """Comprehensive experiment report."""
    experiment: ExperimentInfo
    results: ExperimentResults
    monitoring_data: List[ExperimentMonitoring]
    audit_trail: List[ExperimentAuditEntry]

    executive_summary: str
    key_findings: List[str]
    recommendations: List[str]
    statistical_summary: Dict[str, Any]

    generated_at: datetime
    generated_by: str
    report_version: str = "1.0"


# Validation Functions

def validate_experiment_name(name: str) -> bool:
    """Validate experiment name for healthcare compliance."""
    if len(name.strip()) < 3:
        return False

    # Check for patient information
    forbidden_patterns = ['patient', 'id', 'name', 'phone', 'email', 'address']
    name_lower = name.lower()

    for pattern in forbidden_patterns:
        if pattern in name_lower:
            return False

    return True


def validate_medical_content_safety(content: str) -> Dict[str, Any]:
    """Validate content for medical safety."""
    medical_keywords = [
        'medicação', 'remédio', 'dosagem', 'mg', 'ml', 'emergência', 'urgente',
        'hospital', 'médico', 'consulta', 'exame', 'resultado', 'tratamento',
        'quimioterapia', 'radioterapia', 'cirurgia', 'dose', 'prescrição'
    ]

    content_lower = content.lower()
    found_keywords = [keyword for keyword in medical_keywords if keyword in content_lower]

    return {
        'is_safe': len(found_keywords) == 0,
        'found_keywords': found_keywords,
        'risk_level': 'high' if len(found_keywords) > 2 else 'medium' if found_keywords else 'low',
        'recommendation': 'manual_review' if found_keywords else 'safe_for_ab_testing'
    }


def calculate_minimum_sample_size(effect_size: float, alpha: float, power: float) -> int:
    """Calculate minimum sample size for statistical significance."""
    # Simplified calculation - in production, use proper statistical libraries
    base_size = 100

    # Adjust for effect size
    if effect_size < 0.1:
        base_size *= 4
    elif effect_size < 0.2:
        base_size *= 2
    elif effect_size > 0.5:
        base_size = int(base_size * 0.5)

    # Adjust for alpha and power
    if alpha < 0.05:
        base_size = int(base_size * 1.5)
    if power > 0.8:
        base_size = int(base_size * 1.2)

    return max(50, base_size)  # Minimum 50 per variant