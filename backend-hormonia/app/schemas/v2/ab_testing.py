"""
A/B Testing API v2 Schemas
Advanced A/B testing with statistical analysis, variant management, and conversion tracking.

Features:
- Weighted randomization (50/50, 70/30, custom)
- Statistical analysis (confidence intervals, p-values, effect sizes)
- Conversion tracking with multiple goal types
- Experiment segmentation by user attributes
- Winner declaration (manual or auto based on confidence)
- Duration control with start/end dates
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


# ============================================================================
# Enums
# ============================================================================

class ExperimentStatus(str, Enum):
    """Experiment lifecycle status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class VariantType(str, Enum):
    """A/B test variant types."""
    CONTROL = "control"
    TREATMENT = "treatment"
    VARIANT_A = "variant_a"
    VARIANT_B = "variant_b"
    VARIANT_C = "variant_c"


class ConversionGoalType(str, Enum):
    """Types of conversion goals."""
    CLICK = "click"
    RESPONSE = "response"
    COMPLETION = "completion"
    ENGAGEMENT = "engagement"
    CUSTOM = "custom"


class StatisticalTest(str, Enum):
    """Statistical test types."""
    T_TEST = "t_test"
    CHI_SQUARE = "chi_square"
    MANN_WHITNEY_U = "mann_whitney_u"
    FISHER_EXACT = "fisher_exact"
    BAYESIAN = "bayesian"


class ConfidenceLevel(str, Enum):
    """Confidence level for statistical tests."""
    NINETY = "90"
    NINETY_FIVE = "95"
    NINETY_NINE = "99"


class WinnerDecisionMode(str, Enum):
    """Winner declaration mode."""
    MANUAL = "manual"
    AUTO = "auto"
    AUTO_WITH_REVIEW = "auto_with_review"


class ExportFormat(str, Enum):
    """Export formats for experiment data."""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"
    PDF = "pdf"


# ============================================================================
# Variant Configuration Schemas
# ============================================================================

class VariantConfig(BaseModel):
    """Configuration for a single variant."""
    name: str = Field(..., min_length=1, max_length=100, description="Variant name")
    type: VariantType = Field(..., description="Variant type")
    description: Optional[str] = Field(None, max_length=500)
    traffic_weight: float = Field(..., gt=0, le=1, description="Traffic allocation (0-1)")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Variant-specific config")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "name": "Treatment - AI Humanized",
                "type": "treatment",
                "description": "Messages humanized using AI",
                "traffic_weight": 0.5,
                "configuration": {"use_ai": True, "model": "gpt-4"}
            }
        })


class VariantPerformance(BaseModel):
    """Performance metrics for a variant."""
    variant_type: VariantType
    variant_name: str
    sample_size: int
    conversion_rate: float = Field(..., ge=0, le=1)
    conversions: int
    views: int
    avg_engagement_time: Optional[float] = None
    error_rate: float = Field(0.0, ge=0, le=1)
    confidence_interval: Optional[Dict[str, float]] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Conversion Tracking Schemas
# ============================================================================

class ConversionGoal(BaseModel):
    """Definition of a conversion goal."""
    goal_name: str = Field(..., min_length=1, max_length=100)
    goal_type: ConversionGoalType
    description: Optional[str] = Field(None, max_length=500)
    target_value: Optional[float] = Field(None, description="Target value for goal")
    is_primary: bool = Field(False, description="Is this the primary goal?")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "goal_name": "message_response",
                "goal_type": "response",
                "description": "Patient responds to message",
                "target_value": 0.3,
                "is_primary": True
            }
        })


class ConversionEventCreate(BaseModel):
    """Track a conversion event."""
    experiment_id: UUID
    user_id: Optional[UUID] = None
    anonymous_id: Optional[str] = Field(None, description="Anonymous user identifier")
    variant_type: VariantType
    goal_name: str
    goal_type: ConversionGoalType
    value: Optional[float] = Field(None, description="Event value")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[datetime] = None

    @model_validator(mode='after')
    def validate_user_identifier(self):
        """Ensure either user_id or anonymous_id is provided."""
        if not self.user_id and not self.anonymous_id:
            raise ValueError("Either user_id or anonymous_id must be provided")
        return self


class ConversionEventResponse(BaseModel):
    """Response for conversion event."""
    id: UUID
    experiment_id: UUID
    variant_type: VariantType
    goal_name: str
    goal_type: ConversionGoalType
    value: Optional[float]
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Statistical Analysis Schemas
# ============================================================================

class StatisticalConfig(BaseModel):
    """Statistical analysis configuration."""
    confidence_level: ConfidenceLevel = Field(ConfidenceLevel.NINETY_FIVE)
    statistical_test: StatisticalTest = Field(StatisticalTest.CHI_SQUARE)
    min_sample_size: int = Field(100, ge=30, le=10000)
    min_effect_size: float = Field(0.05, gt=0, le=1)
    power: float = Field(0.8, gt=0, lt=1)
    early_stopping_enabled: bool = Field(True)

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "confidence_level": "95",
                "statistical_test": "chi_square",
                "min_sample_size": 100,
                "min_effect_size": 0.05,
                "power": 0.8,
                "early_stopping_enabled": True
            }
        })


class ConfidenceInterval(BaseModel):
    """Confidence interval for a metric."""
    lower_bound: float
    upper_bound: float
    confidence_level: float
    margin_of_error: float

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "lower_bound": 0.23,
                "upper_bound": 0.37,
                "confidence_level": 0.95,
                "margin_of_error": 0.07
            }
        })


class StatisticalTestResult(BaseModel):
    """Result of statistical hypothesis test."""
    test_type: StatisticalTest
    test_statistic: float
    p_value: float
    is_significant: bool
    alpha: float
    degrees_of_freedom: Optional[int] = None
    effect_size: Optional[float] = None
    effect_size_interpretation: Optional[Literal["negligible", "small", "medium", "large"]] = None

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "test_type": "chi_square",
                "test_statistic": 4.32,
                "p_value": 0.037,
                "is_significant": True,
                "alpha": 0.05,
                "effect_size": 0.15,
                "effect_size_interpretation": "small"
            }
        })


class ExperimentStatistics(BaseModel):
    """Comprehensive experiment statistics."""
    total_participants: int
    total_conversions: int
    overall_conversion_rate: float
    variants: List[VariantPerformance]
    statistical_test: StatisticalTestResult
    winner: Optional[VariantType] = None
    winner_confidence: Optional[float] = None
    relative_improvement: Optional[float] = None
    absolute_improvement: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Segmentation Schemas
# ============================================================================

class SegmentCriteria(BaseModel):
    """Criteria for user segmentation."""
    attribute_name: str = Field(..., description="Attribute to segment by")
    operator: Literal["equals", "not_equals", "greater_than", "less_than", "contains", "in"] = "equals"
    value: Any = Field(..., description="Value to compare against")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "attribute_name": "age",
                "operator": "greater_than",
                "value": 40
            }
        })


class Segment(BaseModel):
    """User segment definition."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    criteria: List[SegmentCriteria] = Field(..., min_length=1)
    is_exclusive: bool = Field(False, description="Mutually exclusive with other segments")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "name": "Age 40+",
                "description": "Users aged 40 and above",
                "criteria": [
                    {"attribute_name": "age", "operator": "greater_than", "value": 40}
                ],
                "is_exclusive": False
            }
        })


# ============================================================================
# Experiment CRUD Schemas
# ============================================================================

class ExperimentCreate(BaseModel):
    """Create a new A/B experiment."""
    name: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    hypothesis: Optional[str] = Field(None, max_length=1000, description="Experiment hypothesis")

    # Variants configuration
    variants: List[VariantConfig] = Field(..., min_length=2, max_length=5)

    # Conversion goals
    conversion_goals: List[ConversionGoal] = Field(..., min_length=1, max_length=10)

    # Duration
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    max_duration_days: int = Field(30, ge=1, le=90)

    # Statistical configuration
    statistical_config: StatisticalConfig = Field(default_factory=StatisticalConfig)

    # Segmentation
    segments: Optional[List[Segment]] = Field(None, max_length=10)
    target_population_filter: Optional[Dict[str, Any]] = None

    # Winner declaration
    winner_decision_mode: WinnerDecisionMode = Field(WinnerDecisionMode.MANUAL)
    auto_declare_threshold: Optional[float] = Field(None, ge=0.9, le=0.99, description="Confidence threshold for auto winner")

    @field_validator("variants")
    @classmethod
    def validate_variant_weights(cls, v):
        """Ensure traffic weights sum to 1.0."""
        total_weight = sum(variant.traffic_weight for variant in v)
        if not (0.99 <= total_weight <= 1.01):  # Allow for floating point errors
            raise ValueError(f"Variant traffic weights must sum to 1.0, got {total_weight}")
        return v

    @field_validator("conversion_goals")
    @classmethod
    def validate_primary_goal(cls, v):
        """Ensure exactly one primary goal."""
        primary_goals = [g for g in v if g.is_primary]
        if len(primary_goals) != 1:
            raise ValueError("Exactly one conversion goal must be marked as primary")
        return v

    @model_validator(mode='after')
    def validate_dates(self):
        """Validate start/end dates."""
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValueError("end_date must be after start_date")
        return self


class ExperimentUpdate(BaseModel):
    """Update experiment configuration (draft only)."""
    name: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, min_length=10, max_length=2000)
    hypothesis: Optional[str] = Field(None, max_length=1000)
    end_date: Optional[datetime] = None
    max_duration_days: Optional[int] = Field(None, ge=1, le=90)
    statistical_config: Optional[StatisticalConfig] = None
    winner_decision_mode: Optional[WinnerDecisionMode] = None


class ExperimentResponse(BaseModel):
    """Response for experiment details."""
    id: UUID
    name: str
    description: str
    hypothesis: Optional[str]
    status: ExperimentStatus
    created_at: datetime
    updated_at: datetime
    created_by: UUID

    # Variants
    variants: List[VariantConfig]

    # Goals
    conversion_goals: List[ConversionGoal]

    # Duration
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    max_duration_days: int

    # Stats
    total_participants: int = 0
    total_conversions: int = 0

    # Configuration
    statistical_config: StatisticalConfig
    winner_decision_mode: WinnerDecisionMode

    # Winner (if declared)
    winner: Optional[VariantType] = None
    winner_declared_at: Optional[datetime] = None
    winner_confidence: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class ExperimentListResponse(BaseModel):
    """Paginated list of experiments."""
    data: List[ExperimentResponse]
    next_cursor: Optional[str] = None
    has_more: bool
    total: Optional[int] = None


# ============================================================================
# Variant Assignment Schemas
# ============================================================================

class VariantAssignmentRequest(BaseModel):
    """Request to assign user to variant."""
    experiment_id: UUID
    user_id: Optional[UUID] = None
    anonymous_id: Optional[str] = None
    user_attributes: Optional[Dict[str, Any]] = Field(None, description="User attributes for segmentation")
    force_variant: Optional[VariantType] = Field(None, description="Force specific variant (testing only)")

    @model_validator(mode='after')
    def validate_user_identifier(self):
        """Ensure either user_id or anonymous_id is provided."""
        if not self.user_id and not self.anonymous_id:
            raise ValueError("Either user_id or anonymous_id must be provided")
        return self


class VariantAssignmentResponse(BaseModel):
    """Response for variant assignment."""
    experiment_id: UUID
    variant_type: VariantType
    variant_name: str
    variant_configuration: Dict[str, Any]
    assigned_at: datetime
    is_eligible: bool
    assignment_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Results & Analysis Schemas
# ============================================================================

class ExperimentResultsRequest(BaseModel):
    """Request parameters for experiment results."""
    include_segments: bool = Field(False, description="Include segmented analysis")
    include_time_series: bool = Field(False, description="Include time-series data")
    confidence_level: Optional[ConfidenceLevel] = None


class ExperimentResults(BaseModel):
    """Comprehensive experiment results."""
    experiment_id: UUID
    experiment_name: str
    status: ExperimentStatus

    # Duration
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    duration_days: int

    # Overall statistics
    statistics: ExperimentStatistics

    # Detailed variant performance
    variant_details: List[VariantPerformance]

    # Goals breakdown
    goals_performance: Dict[str, Dict[VariantType, float]]

    # Analysis timestamp
    analyzed_at: datetime

    # Recommendations
    recommendations: List[str]
    confidence_level: float
    is_conclusive: bool

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Winner Declaration Schemas
# ============================================================================

class WinnerDeclarationRequest(BaseModel):
    """Declare experiment winner."""
    experiment_id: UUID
    winner_variant: VariantType
    confidence: float = Field(..., ge=0, le=1)
    notes: Optional[str] = Field(None, max_length=1000)
    override_checks: bool = Field(False, description="Override statistical checks")


class WinnerDeclarationResponse(BaseModel):
    """Response for winner declaration."""
    experiment_id: UUID
    winner_variant: VariantType
    confidence: float
    declared_at: datetime
    declared_by: UUID
    status_change: ExperimentStatus
    rollout_recommendation: str

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Control & Archive Schemas
# ============================================================================

class ExperimentControlRequest(BaseModel):
    """Start, pause, or stop experiment."""
    action: Literal["start", "pause", "resume", "stop"]
    reason: Optional[str] = Field(None, max_length=500)
    emergency_stop: bool = Field(False, description="Emergency stop flag")


class ExperimentControlResponse(BaseModel):
    """Response for control action."""
    experiment_id: UUID
    previous_status: ExperimentStatus
    new_status: ExperimentStatus
    action_timestamp: datetime
    action_by: UUID
    message: str


class ExperimentArchiveRequest(BaseModel):
    """Archive experiment."""
    reason: str = Field(..., min_length=10, max_length=500)
    preserve_data: bool = Field(True, description="Keep conversion data")


# ============================================================================
# Dashboard & Analytics Schemas
# ============================================================================

class ExperimentDashboard(BaseModel):
    """A/B testing dashboard summary."""
    total_experiments: int
    active_experiments: int
    completed_experiments: int
    draft_experiments: int

    # Recent experiments
    recent_experiments: List[ExperimentResponse]

    # Performance summary
    total_participants_all_time: int
    total_conversions_all_time: int
    avg_conversion_rate: float

    # Success metrics
    experiments_with_winner: int
    avg_confidence_level: float

    # Alerts
    experiments_needing_review: int
    experiments_ready_for_winner: int

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "total_experiments": 25,
                "active_experiments": 3,
                "completed_experiments": 18,
                "draft_experiments": 4,
                "total_participants_all_time": 15000,
                "total_conversions_all_time": 4500,
                "avg_conversion_rate": 0.30,
                "experiments_with_winner": 15,
                "avg_confidence_level": 0.95,
                "experiments_needing_review": 2,
                "experiments_ready_for_winner": 1
            }
        })


# ============================================================================
# Export Schemas
# ============================================================================

class ExportRequest(BaseModel):
    """Request to export experiment data."""
    experiment_id: UUID
    format: ExportFormat
    include_raw_data: bool = Field(False, description="Include raw conversion events")
    include_statistics: bool = Field(True, description="Include statistical analysis")
    include_segments: bool = Field(False, description="Include segmented analysis")


class ExportResponse(BaseModel):
    """Response for export request."""
    export_id: UUID
    experiment_id: UUID
    format: ExportFormat
    status: Literal["pending", "processing", "completed", "failed"]
    download_url: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Sample Size Calculation Schemas
# ============================================================================

class SampleSizeCalculationRequest(BaseModel):
    """Calculate required sample size."""
    baseline_conversion_rate: float = Field(..., gt=0, lt=1)
    minimum_detectable_effect: float = Field(..., gt=0, lt=1)
    confidence_level: ConfidenceLevel = ConfidenceLevel.NINETY_FIVE
    power: float = Field(0.8, gt=0, lt=1)
    number_of_variants: int = Field(2, ge=2, le=5)


class SampleSizeCalculationResponse(BaseModel):
    """Sample size calculation result."""
    total_sample_size: int
    sample_size_per_variant: int
    estimated_duration_days: int
    expected_daily_traffic: int = Field(..., description="Based on historical data")
    confidence_level: float
    power: float

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "total_sample_size": 2000,
                "sample_size_per_variant": 1000,
                "estimated_duration_days": 14,
                "expected_daily_traffic": 150,
                "confidence_level": 0.95,
                "power": 0.8
            }
        })
