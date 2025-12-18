"""
Flow management schemas for API v2
Enhanced flow models with cursor pagination, field selection, and eager loading support.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict

from .common import CursorPaginatedResponse


# ============================================================================
# Enums
# ============================================================================


class FlowStatusV2(str, Enum):
    """Flow status enumeration for V2 API"""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ABTestStatusV2(str, Enum):
    """A/B test status enumeration"""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ============================================================================
# Brief Models (for nested relationships)
# ============================================================================


class PatientV2Brief(BaseModel):
    """Brief patient information for flow responses"""

    id: str
    name: str
    phone: Optional[str] = None
    current_day: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class FlowTemplateV2Brief(BaseModel):
    """Brief template information for flow state responses"""

    id: str
    name: str
    flow_type: str
    version: str
    duration_days: int

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Flow Template Models
# ============================================================================


class FlowTemplateV2Base(BaseModel):
    """Base flow template schema"""

    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    flow_type: str = Field(
        ..., min_length=1, max_length=50, description="Flow type identifier"
    )
    version: str = Field(
        "1.0.0", max_length=20, description="Template version (semver)"
    )
    description: Optional[str] = Field(
        None, max_length=1000, description="Template description"
    )
    duration_days: int = Field(..., ge=1, le=365, description="Flow duration in days")
    is_active: bool = Field(True, description="Whether template is active")
    template_data: Dict[str, Any] = Field(
        ..., description="Template configuration data"
    )

    @field_validator("version")
    @classmethod
    def validate_version(cls, v):
        """Validate semantic versioning format"""
        parts = v.split(".")
        if len(parts) != 3:
            raise ValueError("Version must follow semver format (e.g., 1.0.0)")
        if not all(part.isdigit() for part in parts):
            raise ValueError("Version parts must be numeric")
        return v

    @field_validator("template_data")
    @classmethod
    def validate_template_data(cls, v):
        """Validate template data structure"""
        required_fields = ["steps", "triggers"]
        for field in required_fields:
            if field not in v:
                raise ValueError(f"template_data must contain '{field}' field")

        steps = v.get("steps", [])
        if not isinstance(steps, list) or len(steps) == 0:
            raise ValueError("template_data.steps must be a non-empty list")

        return v


class FlowTemplateV2Create(FlowTemplateV2Base):
    """Schema for creating a flow template"""

    pass


class FlowTemplateV2Update(BaseModel):
    """Schema for updating a flow template"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    duration_days: Optional[int] = Field(None, ge=1, le=365)
    is_active: Optional[bool] = None
    template_data: Optional[Dict[str, Any]] = None

    @field_validator("template_data")
    @classmethod
    def validate_template_data(cls, v):
        if v is not None and "steps" in v:
            if not isinstance(v["steps"], list) or len(v["steps"]) == 0:
                raise ValueError("template_data.steps must be a non-empty list")
        return v


class FlowTemplateV2Response(FlowTemplateV2Base):
    """Full flow template response with metadata"""

    id: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    active_patients: Optional[int] = None
    completion_rate: Optional[float] = Field(None, ge=0, le=100)

    model_config = ConfigDict(from_attributes=True)


class FlowTemplateV2List(CursorPaginatedResponse[FlowTemplateV2Response]):
    """Paginated list of flow templates"""

    pass


# ============================================================================
# Flow State Models
# ============================================================================


class FlowStateV2Response(BaseModel):
    """Current flow state for a patient"""

    id: str
    patient_id: str
    flow_type: str
    template_version: str
    current_step: int = Field(..., ge=0)
    status: FlowStatusV2
    started_at: datetime
    completed_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    state_data: Dict[str, Any] = Field(default_factory=dict)
    patient: Optional[PatientV2Brief] = None
    template: Optional[FlowTemplateV2Brief] = None

    model_config = ConfigDict(from_attributes=True)


class FlowAdvanceV2Request(BaseModel):
    """Request to advance a flow"""

    force_day: Optional[int] = Field(None, ge=1, le=365)
    reason: Optional[str] = Field(None, max_length=500)


class FlowAdvanceV2Response(BaseModel):
    """Response after advancing a flow"""

    success: bool
    patient_id: str
    previous_step: int
    current_step: int
    next_actions: List[str] = Field(default_factory=list)
    message: str


class FlowPauseV2Request(BaseModel):
    """Request to pause a flow"""

    reason: Optional[str] = Field(None, max_length=500)
    duration_hours: Optional[int] = Field(None, ge=1, le=168)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Reason cannot be empty if provided")
        return v.strip() if v else None


class FlowPauseV2Response(BaseModel):
    """Response after pausing a flow"""

    success: bool
    patient_id: str
    paused_at: datetime
    reason: Optional[str] = None
    auto_resume_at: Optional[datetime] = None
    message: str


class FlowResumeV2Response(BaseModel):
    """Response after resuming a flow"""

    success: bool
    patient_id: str
    resumed_at: datetime
    paused_duration_hours: float
    next_message_at: Optional[datetime] = None
    message: str


class FlowHistoryV2Response(CursorPaginatedResponse[FlowStateV2Response]):
    """Flow history for a patient with cursor pagination"""

    patient_id: str
    current_flow: Optional[FlowStateV2Response] = None


# ============================================================================
# Flow Customization Models
# ============================================================================


class FlowCustomizationV2Request(BaseModel):
    """Request to create flow customization"""

    customization_type: str = Field(..., max_length=50)
    customization_data: Dict[str, Any]
    priority: int = Field(1, ge=1, le=10)
    conditions: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None


class FlowCustomizationV2Response(BaseModel):
    """Flow customization response"""

    id: str
    patient_id: str
    customization_type: str
    customization_data: Dict[str, Any]
    priority: int
    conditions: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "custom_123",
                "patient_id": "pat_456def",
                "customization_type": "message_timing",
                "customization_data": {"preferred_time": "09:00"},
                "priority": 5,
                "is_active": True,
                "created_at": "2025-11-01T10:00:00Z",
                "updated_at": "2025-11-07T10:00:00Z",
            }
        },
    )


class FlowCustomizationV2List(CursorPaginatedResponse[FlowCustomizationV2Response]):
    """Paginated list of flow customizations"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [{"id": "custom_123", "customization_type": "message_timing"}],
                "next_cursor": "eyJpZCI6ImN1c3RvbV8xMjMifQ==",
                "has_more": False,
                "total": 5,
            }
        }
    )


# ============================================================================
# Flow Rules Models
# ============================================================================


class FlowRuleV2Base(BaseModel):
    """Base flow rule schema"""

    name: str = Field(..., min_length=1, max_length=100, description="Rule name")
    flow_type: str = Field(
        ..., max_length=50, description="Flow type this rule applies to"
    )
    condition: Dict[str, Any] = Field(..., description="Rule condition logic")
    action: Dict[str, Any] = Field(..., description="Action when condition is met")
    priority: int = Field(1, ge=1, le=10, description="Rule priority (1-10)")
    is_active: bool = Field(True, description="Whether rule is active")
    description: Optional[str] = Field(None, max_length=500)


class FlowRuleV2Create(FlowRuleV2Base):
    """Schema for creating a flow rule"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Skip Weekend Messages",
                "flow_type": "hormonal_treatment",
                "condition": {"day_of_week": ["saturday", "sunday"]},
                "action": {"type": "skip_message", "reschedule": "next_weekday"},
                "priority": 8,
                "is_active": True,
                "description": "Don't send messages on weekends",
            }
        }
    )


class FlowRuleV2Update(BaseModel):
    """Schema for updating a flow rule"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    condition: Optional[Dict[str, Any]] = None
    action: Optional[Dict[str, Any]] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    is_active: Optional[bool] = None
    description: Optional[str] = Field(None, max_length=500)


class FlowRuleV2Response(FlowRuleV2Base):
    """Full flow rule response"""

    id: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "rule_123abc",
                "name": "Skip Weekend Messages",
                "flow_type": "hormonal_treatment",
                "condition": {"day_of_week": ["saturday", "sunday"]},
                "action": {"type": "skip_message"},
                "priority": 8,
                "is_active": True,
                "created_at": "2025-01-01T10:00:00Z",
                "updated_at": "2025-11-07T10:00:00Z",
            }
        },
    )


class FlowRuleV2List(CursorPaginatedResponse[FlowRuleV2Response]):
    """Paginated list of flow rules"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [{"id": "rule_123", "name": "Skip Weekend Messages"}],
                "next_cursor": None,
                "has_more": False,
                "total": 8,
            }
        }
    )


# ============================================================================
# A/B Testing Models
# ============================================================================


class ABTestVariantV2(BaseModel):
    """A/B test variant definition"""

    name: str = Field(..., max_length=50, description="Variant name")
    template_id: str = Field(..., description="Template ID for this variant")
    allocation_percentage: float = Field(
        ..., ge=0, le=100, description="Allocation percentage"
    )
    description: Optional[str] = Field(None, max_length=200)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Control",
                "template_id": "template_123",
                "allocation_percentage": 50.0,
                "description": "Original message timing",
            }
        }
    )


class ABTestV2Base(BaseModel):
    """Base A/B test schema"""

    name: str = Field(..., min_length=1, max_length=100, description="Test name")
    flow_type: str = Field(..., max_length=50, description="Flow type for testing")
    variants: List[ABTestVariantV2] = Field(..., min_items=2, max_items=5)
    success_metrics: List[str] = Field(..., description="Metrics to measure")
    target_sample_size: int = Field(..., ge=10, description="Target participants")
    duration_days: int = Field(..., ge=1, le=90, description="Test duration")
    description: Optional[str] = Field(None, max_length=500)

    @field_validator("variants")
    @classmethod
    def validate_variants(cls, v):
        """Validate variant allocations sum to 100"""
        total = sum(variant.allocation_percentage for variant in v)
        if abs(total - 100.0) > 0.01:
            raise ValueError("Variant allocations must sum to 100%")
        return v


class ABTestV2Create(ABTestV2Base):
    """Schema for creating an A/B test"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Message Timing Test",
                "flow_type": "hormonal_treatment",
                "variants": [
                    {
                        "name": "Morning",
                        "template_id": "tpl_1",
                        "allocation_percentage": 50.0,
                    },
                    {
                        "name": "Evening",
                        "template_id": "tpl_2",
                        "allocation_percentage": 50.0,
                    },
                ],
                "success_metrics": ["engagement_rate", "completion_rate"],
                "target_sample_size": 100,
                "duration_days": 30,
                "description": "Test optimal message timing",
            }
        }
    )


class ABTestV2Update(BaseModel):
    """Schema for updating an A/B test"""

    name: Optional[str] = Field(None, max_length=100)
    status: Optional[ABTestStatusV2] = None
    description: Optional[str] = Field(None, max_length=500)


class ABTestResultsV2(BaseModel):
    """A/B test results for a variant"""

    variant_name: str
    participants: int
    conversion_rate: float = Field(..., ge=0, le=100)
    engagement_score: float = Field(..., ge=0, le=100)
    statistical_significance: float = Field(..., ge=0, le=1, description="p-value")
    confidence_interval: List[float] = Field(..., min_items=2, max_items=2)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "variant_name": "Morning",
                "participants": 52,
                "conversion_rate": 78.5,
                "engagement_score": 82.3,
                "statistical_significance": 0.03,
                "confidence_interval": [75.2, 81.8],
            }
        }
    )


class ABTestV2Response(ABTestV2Base):
    """Full A/B test response"""

    id: str
    status: ABTestStatusV2
    current_participants: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    results: Optional[List[ABTestResultsV2]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "test_123abc",
                "name": "Message Timing Test",
                "flow_type": "hormonal_treatment",
                "variants": [],
                "success_metrics": ["engagement_rate"],
                "target_sample_size": 100,
                "duration_days": 30,
                "status": "active",
                "current_participants": 52,
                "start_date": "2025-11-01T00:00:00Z",
                "created_at": "2025-11-01T10:00:00Z",
                "updated_at": "2025-11-07T10:00:00Z",
            }
        },
    )


class ABTestV2List(CursorPaginatedResponse[ABTestV2Response]):
    """Paginated list of A/B tests"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {
                        "id": "test_123",
                        "name": "Message Timing Test",
                        "status": "active",
                    }
                ],
                "next_cursor": None,
                "has_more": False,
                "total": 3,
            }
        }
    )


# ============================================================================
# Analytics Models
# ============================================================================


class FlowMetricsV2Response(BaseModel):
    """Flow metrics and KPIs"""

    flow_type: str
    total_patients: int
    active_patients: int
    completed_patients: int
    completion_rate: float = Field(..., ge=0, le=100)
    average_completion_days: Optional[float] = None
    engagement_rate: float = Field(..., ge=0, le=100)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "flow_type": "hormonal_treatment",
                "total_patients": 150,
                "active_patients": 45,
                "completed_patients": 95,
                "completion_rate": 78.5,
                "average_completion_days": 28.3,
                "engagement_rate": 85.2,
            }
        }
    )


class PatientEngagementV2Response(BaseModel):
    """Patient engagement analytics"""

    patient_id: str
    response_rate: float = Field(..., ge=0, le=100)
    average_response_time_minutes: Optional[float] = None
    last_interaction: Optional[datetime] = None
    engagement_score: float = Field(..., ge=0, le=100)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "pat_456def",
                "response_rate": 92.3,
                "average_response_time_minutes": 45.5,
                "last_interaction": "2025-11-07T08:30:00Z",
                "engagement_score": 88.7,
            }
        }
    )


class RiskAssessmentV2Response(BaseModel):
    """Patient risk assessment"""

    patient_id: str
    risk_level: str = Field(..., description="low, medium, high")
    risk_factors: List[str]
    recommended_actions: List[str]
    assessed_at: datetime

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, v):
        """Validate risk level"""
        allowed = ["low", "medium", "high"]
        if v not in allowed:
            raise ValueError(f"Risk level must be one of: {', '.join(allowed)}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "pat_456def",
                "risk_level": "medium",
                "risk_factors": ["low_engagement", "missed_messages"],
                "recommended_actions": ["send_reminder", "doctor_review"],
                "assessed_at": "2025-11-07T10:00:00Z",
            }
        }
    )


class FlowPerformanceV2Response(BaseModel):
    """Flow performance analytics"""

    flow_type: str
    period_start: datetime
    period_end: datetime
    metrics: Dict[str, Any]
    trends: Dict[str, Any]
    insights: List[str]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "flow_type": "hormonal_treatment",
                "period_start": "2025-10-01T00:00:00Z",
                "period_end": "2025-11-07T23:59:59Z",
                "metrics": {"completion_rate": 78.5, "engagement_rate": 85.2},
                "trends": {
                    "completion_rate_change": "+5.3%",
                    "engagement_trend": "increasing",
                },
                "insights": [
                    "Completion rate improved by 5.3% this month",
                    "Peak engagement occurs at 9 AM",
                ],
            }
        }
    )


class PatientJourneyV2Response(BaseModel):
    """Patient journey analytics"""

    patient_id: str
    journey_stages: List[Dict[str, Any]]
    current_stage: str
    completion_percentage: float = Field(..., ge=0, le=100)
    milestones_achieved: List[str]
    upcoming_milestones: List[str]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "pat_456def",
                "journey_stages": [
                    {
                        "stage": "onboarding",
                        "completed": True,
                        "completed_at": "2025-01-01T10:00:00Z",
                    },
                    {"stage": "active_treatment", "completed": False, "current": True},
                ],
                "current_stage": "active_treatment",
                "completion_percentage": 45.5,
                "milestones_achieved": ["first_week", "first_quiz"],
                "upcoming_milestones": ["mid_treatment_review", "second_quiz"],
            }
        }
    )


class FlowInsightsV2Response(BaseModel):
    """Flow insights and recommendations"""

    flow_type: str
    insights: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    generated_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "flow_type": "hormonal_treatment",
                "insights": [
                    {
                        "type": "engagement_pattern",
                        "description": "Patients engage most at 9 AM",
                        "confidence": 0.92,
                    }
                ],
                "recommendations": [
                    {
                        "type": "timing_optimization",
                        "action": "Schedule messages at 9 AM for better engagement",
                        "expected_impact": "+15% engagement",
                    }
                ],
                "generated_at": "2025-11-07T10:00:00Z",
            }
        }
    )


class FlowDashboardV2Response(BaseModel):
    """Comprehensive flow dashboard data"""

    overview: FlowMetricsV2Response
    performance: FlowPerformanceV2Response
    insights: FlowInsightsV2Response
    generated_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "overview": {
                    "flow_type": "hormonal_treatment",
                    "total_patients": 150,
                    "completion_rate": 78.5,
                },
                "performance": {
                    "flow_type": "hormonal_treatment",
                    "metrics": {},
                    "trends": {},
                },
                "insights": {
                    "flow_type": "hormonal_treatment",
                    "insights": [],
                    "recommendations": [],
                },
                "generated_at": "2025-11-07T10:00:00Z",
            }
        }
    )
