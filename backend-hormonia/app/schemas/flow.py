"""
Flow management schemas for conversation flow API validation.
"""
from datetime import datetime
from typing import List, Optional, Any, Union
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, validator


class FlowTemplateBase(BaseModel):
    """Base flow template schema."""
    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    flow_type: str = Field(..., min_length=1, max_length=50, description="Flow type identifier")
    version: str = Field(default="1.0.0", max_length=20, description="Template version")
    description: Optional[str] = Field(None, description="Template description")
    duration_days: int = Field(..., ge=1, le=365, description="Flow duration in days")
    is_active: bool = Field(default=True, description="Whether template is active")
    template_data: dict[str, Any] = Field(..., description="Template configuration data")


class FlowTemplateCreate(FlowTemplateBase):
    """Schema for creating flow templates."""
    
    @validator('template_data')
    def validate_template_data(cls, v):
        """Validate template data structure."""
        if not isinstance(v, dict):
            raise ValueError("template_data must be a dictionary")
        
        # Check for required fields
        required_fields = ['steps', 'triggers']
        for field in required_fields:
            if field not in v:
                raise ValueError(f"template_data must contain '{field}' field")
        
        # Validate steps structure
        steps = v.get('steps', [])
        if not isinstance(steps, list) or len(steps) == 0:
            raise ValueError("template_data.steps must be a non-empty list")
        
        return v


class FlowTemplateUpdate(BaseModel):
    """Schema for updating flow templates."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    duration_days: Optional[int] = Field(None, ge=1, le=365, description="Flow duration in days")
    is_active: Optional[bool] = Field(None, description="Whether template is active")
    template_data: Optional[dict[str, Any]] = Field(None, description="Template configuration data")
    
    @validator('template_data')
    def validate_template_data(cls, v):
        """Validate template data structure."""
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError("template_data must be a dictionary")
            
            # Check for required fields if provided
            if 'steps' in v:
                steps = v['steps']
                if not isinstance(steps, list) or len(steps) == 0:
                    raise ValueError("template_data.steps must be a non-empty list")
        
        return v


class FlowTemplateResponse(FlowTemplateBase):
    """Schema for flow template responses."""
    id: UUID = Field(..., description="Template ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class PatientFlowStateBase(BaseModel):
    """Base patient flow state schema."""
    flow_type: str = Field(..., min_length=1, max_length=50, description="Flow type")
    template_version: str = Field(default="1.0.0", max_length=20, description="Template version")
    current_step: int = Field(default=0, ge=0, description="Current step in flow")
    state_data: Optional[dict[str, Any]] = Field(default_factory=dict, description="Flow state data")


class PatientFlowStateCreate(PatientFlowStateBase):
    """Schema for creating patient flow states."""
    patient_id: UUID = Field(..., description="Patient ID")


class PatientFlowStateUpdate(BaseModel):
    """Schema for updating patient flow states."""
    current_step: Optional[int] = Field(None, ge=0, description="Current step in flow")
    state_data: Optional[dict[str, Any]] = Field(None, description="Flow state data")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")


class PatientFlowStateResponse(PatientFlowStateBase):
    """Schema for patient flow state responses."""
    id: UUID = Field(..., description="Flow state ID")
    patient_id: UUID = Field(..., description="Patient ID")
    started_at: datetime = Field(..., description="Flow start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Flow completion timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class FlowProgressionRequest(BaseModel):
    """Schema for manual flow progression."""
    patient_id: UUID = Field(..., description="Patient ID")
    target_step: Optional[int] = Field(None, ge=0, description="Target step (optional)")
    force_advance: bool = Field(default=False, description="Force advancement even if conditions not met")
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class FlowProgressionResponse(BaseModel):
    """Schema for flow progression response."""
    success: bool = Field(..., description="Whether progression was successful")
    previous_step: int = Field(..., description="Previous step number")
    current_step: int = Field(..., description="Current step number")
    next_actions: List[str] = Field(default_factory=list, description="Next scheduled actions")
    message: str = Field(..., description="Progression result message")


class FlowResetRequest(BaseModel):
    """Schema for flow reset request."""
    patient_id: UUID = Field(..., description="Patient ID")
    reset_to_step: int = Field(default=0, ge=0, description="Step to reset to")
    preserve_history: bool = Field(default=True, description="Whether to preserve flow history")
    reason: Optional[str] = Field(None, description="Reason for reset")


class FlowHistoryResponse(BaseModel):
    """Schema for flow history response."""
    patient_id: UUID = Field(..., description="Patient ID")
    flow_states: List[PatientFlowStateResponse] = Field(..., description="Historical flow states")
    total_flows: int = Field(..., description="Total number of flows")
    current_flow: Optional[PatientFlowStateResponse] = Field(None, description="Current active flow")


class FlowStepDefinition(BaseModel):
    """Schema for flow step definition."""
    step_id: int = Field(..., description="Step identifier")
    name: str = Field(..., description="Step name")
    description: Optional[str] = Field(None, description="Step description")
    triggers: List[str] = Field(default_factory=list, description="Step triggers")
    conditions: Optional[dict[str, Any]] = Field(None, description="Step conditions")
    actions: List[dict[str, Any]] = Field(default_factory=list, description="Step actions")
    next_steps: List[int] = Field(default_factory=list, description="Possible next steps")


class FlowTemplateValidationResult(BaseModel):
    """Schema for flow template validation result."""
    is_valid: bool = Field(..., description="Whether template is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    message_count: int = Field(default=0, description="Number of messages in template")
    ai_optimized_count: int = Field(default=0, description="Number of AI-optimized messages")
    flow_type: Optional[str] = Field(None, description="Flow type validated")
    template_version: Optional[str] = Field(None, description="Template version validated")
    validated_at: Optional[str] = Field(None, description="Validation timestamp")
    validated_by: Optional[str] = Field(None, description="Who performed validation")
    step_count: int = Field(default=0, description="Number of steps in template")
    estimated_duration: int = Field(default=0, description="Estimated duration in days")


class FlowAnalytics(BaseModel):
    """Schema for flow analytics."""
    flow_type: str = Field(..., description="Flow type")
    total_patients: int = Field(..., description="Total patients in this flow")
    active_patients: int = Field(..., description="Currently active patients")
    completed_patients: int = Field(..., description="Patients who completed flow")
    average_completion_time: Optional[float] = Field(None, description="Average completion time in days")
    completion_rate: float = Field(..., description="Completion rate percentage")
    step_analytics: List[dict[str, Any]] = Field(default_factory=list, description="Per-step analytics")
    common_exit_points: List[dict[str, Any]] = Field(default_factory=list, description="Common exit points")


class FlowTemplateListResponse(BaseModel):
    """Schema for paginated flow template list."""
    templates: List[FlowTemplateResponse] = Field(..., description="List of flow templates")
    total: int = Field(..., description="Total number of templates")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum number of items returned")


class PatientFlowStateListResponse(BaseModel):
    """Schema for paginated patient flow state list."""
    flow_states: List[PatientFlowStateResponse] = Field(..., description="List of flow states")
    total: int = Field(..., description="Total number of flow states")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum number of items returned")


class FlowOverrideRequest(BaseModel):
    """Schema for flow override request."""
    patient_id: UUID = Field(..., description="Patient ID")
    override_type: str = Field(..., description="Type of override (pause, resume, skip, restart)")
    target_step: Optional[int] = Field(None, description="Target step for skip/restart")
    reason: str = Field(..., description="Reason for override")
    duration_hours: Optional[int] = Field(None, description="Duration for pause (in hours)")


class FlowOverrideResponse(BaseModel):
    """Schema for flow override response."""
    success: bool = Field(..., description="Whether override was successful")
    override_type: str = Field(..., description="Type of override applied")
    previous_state: dict[str, Any] = Field(..., description="Previous flow state")
    new_state: dict[str, Any] = Field(..., description="New flow state")
    message: str = Field(..., description="Override result message")
    expires_at: Optional[datetime] = Field(None, description="When override expires (for temporary overrides)")


# Enums for better type safety
class FlowStatus(str, Enum):
    """Flow status enumeration."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Type aliases for better documentation
FlowStateData = dict[str, Union[str, int, float, bool, List[str], dict[str, Any]]]


# Base response model to reduce duplication
class BaseFlowResponse(BaseModel):
    """Base response model for flow operations."""
    patient_id: UUID = Field(..., description="Patient ID")
    message: str = Field(..., description="Result message")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Response models for flow state endpoints
class FlowStateResponse(BaseModel):
    """Response model for flow state endpoints - consolidated definition."""
    patient_id: UUID = Field(..., description="Patient ID")
    has_active_flow: bool = Field(..., description="Whether patient has an active flow")
    flow_state: Optional[FlowStateData] = Field(None, description="Current flow state data")
    message: Optional[str] = Field(None, description="Additional message")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class FlowAdvancementResponse(BaseFlowResponse):
    """Response model for flow advancement operations."""
    advancement_result: dict[str, Any] = Field(..., description="Advancement operation result")


class FlowPauseResponse(BaseFlowResponse):
    """Response model for flow pause operations."""
    flow_state_id: UUID = Field(..., description="Flow state ID")
    status: FlowStatus = Field(..., description="Current flow status")
    reason: Optional[str] = Field(None, description="Pause reason")
    paused_at: datetime = Field(..., description="Pause timestamp")
    auto_resume_at: Optional[datetime] = Field(None, description="Auto-resume timestamp")


class FlowResumeResponse(BaseFlowResponse):
    """Response model for flow resume operations."""
    flow_state_id: UUID = Field(..., description="Flow state ID")
    status: FlowStatus = Field(..., description="Current flow status")
    resumed_at: datetime = Field(..., description="Resume timestamp")


class FlowHistoryItem(BaseModel):
    """Individual flow history item."""
    flow_state_id: UUID = Field(..., description="Flow state ID")
    flow_type: str = Field(..., description="Flow type")
    current_step: int = Field(..., description="Current step")
    started_at: datetime = Field(..., description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    template_version: str = Field(..., description="Template version")
    is_active: bool = Field(..., description="Whether flow is active")
    is_paused: bool = Field(..., description="Whether flow is paused")
    state_data: FlowStateData = Field(default_factory=dict, description="Flow state data")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class FlowHistoryResponse(BaseModel):
    """Response model for flow history endpoints."""
    patient_id: UUID = Field(..., description="Patient ID")
    flow_history: List[FlowHistoryItem] = Field(..., description="Flow history items")
    current_flow: Optional[FlowHistoryItem] = Field(None, description="Current active flow")
    total_flows: int = Field(..., description="Total number of flows")
    pagination: dict[str, Any] = Field(..., description="Pagination information")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Request models for improved validation
class FlowPauseRequest(BaseModel):
    """
    Request model for pausing flows.
    
    Examples:
        Temporary pause: {"reason": "Patient requested break", "duration_hours": 24}
        Indefinite pause: {"reason": "Medical review needed"}
    """
    reason: Optional[str] = Field(
        None, 
        max_length=500, 
        description="Reason for pausing the flow",
        example="Patient requested temporary break"
    )
    duration_hours: Optional[int] = Field(
        None, 
        ge=1, 
        le=168, 
        description="Duration in hours (1-168). If not provided, pause is indefinite",
        example=24
    )

    @validator('reason')
    def validate_reason(cls, v):
        """Validate reason field."""
        if v is not None and not v.strip():
            raise ValueError('Reason cannot be empty if provided')
        return v.strip() if v else None

    @validator('duration_hours')
    def validate_duration_hours(cls, v):
        """Validate duration hours field."""
        if v is not None:
            if v < 1:
                raise ValueError('Duration must be at least 1 hour')
            if v > 168:  # 1 week
                raise ValueError('Duration cannot exceed 168 hours (1 week)')
        return v


class FlowAdvanceRequest(BaseModel):
    """
    Request model for advancing flows.
    
    Examples:
        Natural advancement: {}
        Force to specific day: {"force_day": 15}
    """
    force_day: Optional[int] = Field(
        None, 
        ge=1, 
        le=365, 
        description="Force advance to specific day (1-365)",
        example=15
    )

    @validator('force_day')
    def validate_force_day(cls, v):
        """Validate force day field."""
        if v is not None:
            if v < 1:
                raise ValueError('Force day must be at least 1')
            if v > 365:
                raise ValueError('Force day cannot exceed 365')
        return v

    is_active: Optional[bool] = Field(None, description="Whether template is active")
    template_data: Optional[dict[str, Any]] = Field(None, description="Template configuration data")


class FlowTemplateResponse(FlowTemplateBase):
    """Schema for flow template responses."""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: UUID
    updated_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True


class FlowCustomizationRequest(BaseModel):
    """Schema for patient flow customization requests."""
    customization_type: str = Field(..., description="Type of customization")
    customization_data: dict[str, Any] = Field(..., description="Customization configuration")
    priority: int = Field(default=1, ge=1, le=10, description="Customization priority")
    conditions: Optional[dict[str, Any]] = Field(None, description="Conditions for applying customization")
    expires_at: Optional[datetime] = Field(None, description="Expiration date for customization")


class FlowCustomizationResponse(BaseModel):
    """Schema for flow customization responses."""
    id: UUID
    patient_id: UUID
    customization_type: str
    customization_data: dict[str, Any]
    priority: int
    conditions: Optional[dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: UUID
    updated_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True


class FlowRuleRequest(BaseModel):
    """Schema for flow rule requests."""
    name: str = Field(..., min_length=1, max_length=100, description="Rule name")
    flow_type: str = Field(..., description="Flow type this rule applies to")
    condition: dict[str, Any] = Field(..., description="Rule condition logic")
    action: dict[str, Any] = Field(..., description="Action to take when condition is met")
    priority: int = Field(default=1, ge=1, le=10, description="Rule priority")
    is_active: bool = Field(default=True, description="Whether rule is active")
    description: Optional[str] = Field(None, description="Rule description")


class FlowRuleResponse(BaseModel):
    """Schema for flow rule responses."""
    id: UUID
    name: str
    flow_type: str
    condition: dict[str, Any]
    action: dict[str, Any]
    priority: int
    is_active: bool
    description: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: UUID
    updated_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True


class ABTestVariant(BaseModel):
    """Schema for A/B test variant."""
    name: str = Field(..., description="Variant name")
    template_id: UUID = Field(..., description="Template ID for this variant")
    allocation_percentage: float = Field(..., ge=0, le=100, description="Percentage of patients for this variant")
    description: Optional[str] = Field(None, description="Variant description")


class ABTestConfigRequest(BaseModel):
    """Schema for A/B test configuration requests."""
    name: str = Field(..., min_length=1, max_length=100, description="Test name")
    flow_type: str = Field(..., description="Flow type for testing")
    variants: List[ABTestVariant] = Field(..., min_items=2, max_items=5, description="Test variants")
    success_metrics: List[str] = Field(..., description="Metrics to measure success")
    target_sample_size: int = Field(..., ge=10, description="Target number of participants")
    duration_days: int = Field(..., ge=1, le=90, description="Test duration in days")
    description: Optional[str] = Field(None, description="Test description")
    
    @validator('variants')
    def validate_variants(cls, v):
        """Validate variant allocation percentages sum to 100."""
        total_allocation = sum(variant.allocation_percentage for variant in v)
        if abs(total_allocation - 100.0) > 0.01:  # Allow for small floating point errors
            raise ValueError("Variant allocation percentages must sum to 100")
        return v


class ABTestResults(BaseModel):
    """Schema for A/B test results."""
    variant_name: str
    participants: int
    conversion_rate: float
    engagement_score: float
    statistical_significance: float
    confidence_interval: List[float]


class ABTestConfigResponse(BaseModel):
    """Schema for A/B test configuration responses."""
    id: UUID
    name: str
    flow_type: str
    variants: List[ABTestVariant]
    success_metrics: List[str]
    target_sample_size: int
    duration_days: int
    description: Optional[str] = None
    status: str  # active, paused, completed, cancelled
    current_participants: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    results: Optional[List[ABTestResults]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: UUID
    updated_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True


class FlowAdvanceRequest(BaseModel):
    """Schema for flow advancement requests."""
    force_day: Optional[int] = Field(None, ge=1, description="Force advance to specific day")
    reason: Optional[str] = Field(None, description="Reason for manual advancement")


class FlowPauseRequest(BaseModel):
    """Schema for flow pause requests."""
    reason: str = Field(..., min_length=1, description="Reason for pausing flow")
    duration_hours: Optional[int] = Field(None, ge=1, description="Auto-resume after hours")


# FlowStateResponse is defined earlier in this file at line 245
# Removed duplicate definition to avoid conflicts


class FlowPauseResponse(BaseModel):
    """Schema for flow pause responses."""
    success: bool
    patient_id: UUID
    paused_at: datetime
    reason: str
    duration_hours: Optional[int] = None
    resume_at: Optional[datetime] = None
    message: str


class FlowResumeResponse(BaseModel):
    """Schema for flow resume responses."""
    success: bool
    patient_id: UUID
    resumed_at: datetime
    paused_duration_hours: float
    next_message_at: Optional[datetime] = None
    message: str


class FlowHistoryItem(BaseModel):
    """Schema for flow history items."""
    id: UUID
    flow_type: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_days: Optional[int] = None
    final_step: Optional[int] = None
    completion_rate: Optional[float] = None
    status: str  # active, completed, paused, cancelled


class FlowHistoryResponse(BaseModel):
    """Schema for flow history responses."""
    patient_id: UUID
    total_flows: int
    flows: List[FlowHistoryItem]
    pagination: dict[str, Any]


class FlowAnalytics(BaseModel):
    """Schema for flow analytics data."""
    flow_type: str
    total_patients: int
    active_patients: int
    completed_patients: int
    completion_rate: float
    average_completion_days: Optional[float] = None
    engagement_metrics: dict[str, Any]
    performance_metrics: dict[str, Any]
    trends: dict[str, Any]
    generated_at: datetime


class StartFlowRequest(BaseModel):
    """Request schema for starting a flow."""
    patient_id: UUID = Field(..., description="Patient UUID")
    flow_type: str = Field(..., description="Type of flow to start")


class ProcessResponseRequest(BaseModel):
    """Request schema for processing patient response."""
    response_text: str = Field(..., description="Patient's response text")
    response_metadata: Optional[dict[str, Any]] = Field(None, description="Additional response metadata")