"""
Flow Types - Type system for Flow Services (QW-021).

This module defines all types, enums, and models used across the flow system.
Centralized type definitions ensure consistency and type safety.

Migration Note:
    This consolidates types from:
    - enhanced_flow_engine.py (FlowType, FlowStatus)
    - flow_engine.py (StateType, TransitionType)
    - flow.py (FlowState enums)
    - flow_template.py (TemplateType)
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# ============================================================================
# Flow Type Enums
# ============================================================================


class FlowType(str, Enum):
    """
    Types of treatment flows available in the system.

    Each flow type represents a different care pathway with specific
    steps, validations, and business rules.
    """

    ONBOARDING = "onboarding"
    """Initial patient onboarding flow"""

    DAILY_CHECKIN = "daily_checkin"
    """Daily patient check-in flow"""

    MONTHLY_QUIZ = "monthly_quiz"
    """Monthly health assessment flow"""

    TREATMENT_ADHERENCE = "treatment_adherence"
    """Treatment adherence monitoring flow"""

    SYMPTOM_TRACKING = "symptom_tracking"
    """Symptom tracking and reporting flow"""

    MEDICATION_REMINDER = "medication_reminder"
    """Medication reminder flow"""

    APPOINTMENT_PREP = "appointment_prep"
    """Appointment preparation flow"""

    POST_APPOINTMENT = "post_appointment"
    """Post-appointment follow-up flow"""

    EMERGENCY_PROTOCOL = "emergency_protocol"
    """Emergency situation protocol flow"""

    CUSTOM = "custom"
    """Custom flow (user-defined)"""


class FlowStatus(str, Enum):
    """
    Status of a flow instance.

    Represents the lifecycle state of a flow execution.
    """

    PENDING = "pending"
    """Flow created but not started"""

    ACTIVE = "active"
    """Flow is currently running"""

    PAUSED = "paused"
    """Flow execution is paused"""

    COMPLETED = "completed"
    """Flow completed successfully"""

    FAILED = "failed"
    """Flow failed with error"""

    CANCELLED = "cancelled"
    """Flow was cancelled by user/system"""

    EXPIRED = "expired"
    """Flow expired due to timeout"""


class FlowStepType(str, Enum):
    """
    Types of steps within a flow.

    Each step type has different execution logic and validation rules.
    """

    MESSAGE = "message"
    """Send a message to the patient"""

    QUESTION = "question"
    """Ask a question and wait for response"""

    DECISION = "decision"
    """Make a decision based on conditions"""

    ACTION = "action"
    """Execute an action (API call, task, etc.)"""

    WAIT = "wait"
    """Wait for a specified duration"""

    BRANCH = "branch"
    """Branch to different paths based on condition"""

    LOOP = "loop"
    """Loop back to a previous step"""

    END = "end"
    """End the flow"""


class FlowStepStatus(str, Enum):
    """Status of an individual flow step."""

    PENDING = "pending"
    """Step not yet executed"""

    IN_PROGRESS = "in_progress"
    """Step is currently executing"""

    COMPLETED = "completed"
    """Step completed successfully"""

    FAILED = "failed"
    """Step failed"""

    SKIPPED = "skipped"
    """Step was skipped"""


class FlowTransitionType(str, Enum):
    """Types of transitions between flow steps."""

    AUTOMATIC = "automatic"
    """Automatic transition (no user input)"""

    USER_RESPONSE = "user_response"
    """Transition after user response"""

    TIMEOUT = "timeout"
    """Transition after timeout"""

    CONDITIONAL = "conditional"
    """Transition based on condition evaluation"""

    MANUAL = "manual"
    """Manual transition (admin/system)"""


class FlowPriority(str, Enum):
    """Priority levels for flow execution."""

    LOW = "low"
    """Low priority"""

    MEDIUM = "medium"
    """Medium priority (default)"""

    HIGH = "high"
    """High priority"""

    URGENT = "urgent"
    """Urgent priority"""

    CRITICAL = "critical"
    """Critical priority (immediate execution)"""


class FlowEventType(str, Enum):
    """Types of events that can occur during flow execution."""

    FLOW_STARTED = "flow_started"
    """Flow execution started"""

    FLOW_COMPLETED = "flow_completed"
    """Flow execution completed"""

    FLOW_FAILED = "flow_failed"
    """Flow execution failed"""

    FLOW_PAUSED = "flow_paused"
    """Flow execution paused"""

    FLOW_RESUMED = "flow_resumed"
    """Flow execution resumed"""

    FLOW_CANCELLED = "flow_cancelled"
    """Flow execution cancelled"""

    STEP_STARTED = "step_started"
    """Step execution started"""

    STEP_COMPLETED = "step_completed"
    """Step execution completed"""

    STEP_FAILED = "step_failed"
    """Step execution failed"""

    TRANSITION_OCCURRED = "transition_occurred"
    """Transition between steps occurred"""

    DATA_UPDATED = "data_updated"
    """Flow data was updated"""

    ERROR_OCCURRED = "error_occurred"
    """An error occurred during execution"""


# ============================================================================
# Flow Data Models
# ============================================================================


class FlowStepData(BaseModel):
    """
    Data for a single flow step.

    Contains all information needed to execute and track a step.
    """

    step_id: str = Field(..., description="Unique identifier for this step")
    step_type: FlowStepType = Field(..., description="Type of step")
    step_name: str = Field(..., description="Human-readable step name")
    status: FlowStepStatus = Field(
        default=FlowStepStatus.PENDING, description="Current status"
    )

    # Execution data
    input_data: Dict[str, Any] = Field(
        default_factory=dict, description="Input data for step execution"
    )
    output_data: Optional[Dict[str, Any]] = Field(
        default=None, description="Output data from step execution"
    )

    # Timing
    started_at: Optional[datetime] = Field(default=None, description="Step start time")
    completed_at: Optional[datetime] = Field(
        default=None, description="Step completion time"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional step metadata"
    )
    error: Optional[str] = Field(default=None, description="Error message if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "step_id": "step_001",
                "step_type": "question",
                "step_name": "Ask about symptoms",
                "status": "completed",
                "input_data": {"question": "How are you feeling today?"},
                "output_data": {"response": "I'm feeling better"},
                "started_at": "2025-01-22T10:00:00Z",
                "completed_at": "2025-01-22T10:05:00Z",
            }
        }


class FlowContext(BaseModel):
    """
    Context data for flow execution.

    Contains all runtime data and state for a flow instance.
    """

    flow_instance_id: UUID = Field(..., description="Unique flow instance identifier")
    flow_type: FlowType = Field(..., description="Type of flow")
    patient_id: UUID = Field(..., description="Patient this flow is for")

    # State
    current_step_id: Optional[str] = Field(
        default=None, description="Current step being executed"
    )
    status: FlowStatus = Field(default=FlowStatus.PENDING, description="Flow status")

    # Data
    flow_data: Dict[str, Any] = Field(
        default_factory=dict, description="Flow execution data"
    )
    variables: Dict[str, Any] = Field(
        default_factory=dict, description="Flow variables (for conditions)"
    )

    # History
    steps_completed: List[str] = Field(
        default_factory=list, description="List of completed step IDs"
    )
    steps_history: List[FlowStepData] = Field(
        default_factory=list, description="Detailed step execution history"
    )

    # Timing
    started_at: Optional[datetime] = Field(default=None, description="Flow start time")
    completed_at: Optional[datetime] = Field(
        default=None, description="Flow completion time"
    )
    expires_at: Optional[datetime] = Field(default=None, description="Flow expiry time")

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional flow metadata"
    )
    priority: FlowPriority = Field(
        default=FlowPriority.MEDIUM, description="Execution priority"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "flow_instance_id": "550e8400-e29b-41d4-a716-446655440000",
                "flow_type": "daily_checkin",
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "current_step_id": "step_002",
                "status": "active",
                "flow_data": {"checkin_count": 5},
                "variables": {"last_response": "good"},
                "steps_completed": ["step_001"],
            }
        }


class FlowTemplate(BaseModel):
    """
    Template definition for a flow.

    Defines the structure and steps of a flow type.
    """

    template_id: str = Field(..., description="Unique template identifier")
    flow_type: FlowType = Field(..., description="Type of flow this template is for")
    version: str = Field(default="1.0.0", description="Template version")

    # Structure
    steps: List[Dict[str, Any]] = Field(..., description="List of step definitions")
    transitions: List[Dict[str, Any]] = Field(
        default_factory=list, description="Transition rules between steps"
    )

    # Configuration
    default_timeout_minutes: int = Field(
        default=60, description="Default timeout for the flow"
    )
    max_retries: int = Field(default=3, description="Maximum retry attempts")

    # Metadata
    name: str = Field(..., description="Human-readable template name")
    description: str = Field(..., description="Template description")
    is_active: bool = Field(default=True, description="Whether template is active")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional template metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "template_id": "daily_checkin_v1",
                "flow_type": "daily_checkin",
                "version": "1.0.0",
                "name": "Daily Check-in Flow",
                "description": "Standard daily patient check-in",
                "steps": [
                    {
                        "step_id": "greeting",
                        "type": "message",
                        "content": "Good morning! How are you today?",
                    }
                ],
            }
        }


class FlowEvent(BaseModel):
    """
    Event that occurred during flow execution.

    Used for monitoring, auditing, and debugging.
    """

    event_id: str = Field(..., description="Unique event identifier")
    event_type: FlowEventType = Field(..., description="Type of event")
    flow_instance_id: UUID = Field(..., description="Flow instance this event is for")

    # Event data
    step_id: Optional[str] = Field(default=None, description="Step ID if step-related")
    data: Dict[str, Any] = Field(
        default_factory=dict, description="Event-specific data"
    )

    # Timing
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Event timestamp"
    )

    # Metadata
    source: str = Field(default="system", description="Event source")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional event metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "evt_001",
                "event_type": "step_completed",
                "flow_instance_id": "550e8400-e29b-41d4-a716-446655440000",
                "step_id": "step_001",
                "data": {"duration_seconds": 5},
                "timestamp": "2025-01-22T10:05:00Z",
            }
        }


class FlowValidationResult(BaseModel):
    """Result of flow validation."""

    is_valid: bool = Field(..., description="Whether validation passed")
    errors: List[str] = Field(
        default_factory=list, description="List of validation errors"
    )
    warnings: List[str] = Field(
        default_factory=list, description="List of validation warnings"
    )
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Additional validation details"
    )


class FlowMetrics(BaseModel):
    """Metrics for flow execution."""

    total_steps: int = Field(default=0, description="Total steps in flow")
    completed_steps: int = Field(default=0, description="Completed steps")
    failed_steps: int = Field(default=0, description="Failed steps")
    skipped_steps: int = Field(default=0, description="Skipped steps")

    duration_seconds: Optional[float] = Field(
        default=None, description="Total execution duration"
    )
    average_step_duration_seconds: Optional[float] = Field(
        default=None, description="Average step duration"
    )

    retry_count: int = Field(default=0, description="Number of retries")
    error_count: int = Field(default=0, description="Number of errors")


# ============================================================================
# Type Aliases
# ============================================================================

FlowID = UUID
"""Type alias for flow instance ID"""

StepID = str
"""Type alias for step ID"""

TemplateID = str
"""Type alias for template ID"""


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Enums
    "FlowType",
    "FlowStatus",
    "FlowStepType",
    "FlowStepStatus",
    "FlowTransitionType",
    "FlowPriority",
    "FlowEventType",
    # Models
    "FlowStepData",
    "FlowContext",
    "FlowTemplate",
    "FlowEvent",
    "FlowValidationResult",
    "FlowMetrics",
    # Type Aliases
    "FlowID",
    "StepID",
    "TemplateID",
]
