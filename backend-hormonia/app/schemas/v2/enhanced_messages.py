"""
Enhanced Message Management Schemas for API v2

Advanced messaging schemas with template management, scheduling, analytics,
A/B testing, and performance tracking.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel, Field, validator, field_validator
from uuid import UUID

from .common import CursorPaginatedResponse, ErrorResponse
from .messages import MessageV2Response, MessageTypeV2, MessageStatusV2


# ============================================================================
# Enums
# ============================================================================

class TemplateVersionStatus(str, Enum):
    """Template version status"""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class TemplateCategoryV2(str, Enum):
    """Template categories"""
    REMINDER = "reminder"
    APPOINTMENT = "appointment"
    MEDICATION = "medication"
    CHECKUP = "checkup"
    WELCOME = "welcome"
    FOLLOW_UP = "follow_up"
    ALERT = "alert"
    PROMOTION = "promotion"
    EDUCATIONAL = "educational"


class RecurrenceType(str, Enum):
    """Message recurrence types"""
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class ABTestStatus(str, Enum):
    """A/B test status"""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DeliveryOptimizationStrategy(str, Enum):
    """Delivery optimization strategies"""
    IMMEDIATE = "immediate"
    BEST_TIME = "best_time"
    RATE_LIMITED = "rate_limited"
    ENGAGEMENT_BASED = "engagement_based"


# ============================================================================
# Template Management
# ============================================================================

class TemplateVariableV2(BaseModel):
    """Template variable definition"""

    name: str = Field(..., description="Variable name (e.g., patient_name)")
    description: Optional[str] = Field(None, description="Variable description")
    type: str = Field("string", description="Variable type: string, number, date")
    required: bool = Field(True, description="Whether variable is required")
    default_value: Optional[str] = Field(None, description="Default value if not provided")
    validation_regex: Optional[str] = Field(None, description="Regex for validation")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "patient_name",
                "description": "Patient's full name",
                "type": "string",
                "required": True,
                "default_value": None,
                "validation_regex": "^[A-Za-z\\s]+$"
            }
        }


class TemplateConditionalV2(BaseModel):
    """Conditional content in templates"""

    condition: str = Field(..., description="Condition expression")
    content: str = Field(..., description="Content to show if condition is true")
    else_content: Optional[str] = Field(None, description="Content to show if condition is false")

    class Config:
        json_schema_extra = {
            "example": {
                "condition": "{{treatment_phase}} == 'active'",
                "content": "Continue with your current treatment.",
                "else_content": "Please consult your doctor."
            }
        }


class MessageTemplateV2Create(BaseModel):
    """Create a new message template"""

    name: str = Field(..., min_length=3, max_length=100, description="Template name")
    content: str = Field(..., min_length=1, max_length=4096, description="Template content with {{variables}}")
    category: TemplateCategoryV2
    language: str = Field("pt_BR", description="Template language (ISO 639-1)")
    variables: List[TemplateVariableV2] = Field(default_factory=list, description="Template variables")
    conditionals: List[TemplateConditionalV2] = Field(default_factory=list, description="Conditional content")
    tags: List[str] = Field(default_factory=list, description="Template tags for organization")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Template metadata")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate template content"""
        if not v or not v.strip():
            raise ValueError("Content cannot be empty")
        return v.strip()

    @field_validator("variables")
    @classmethod
    def validate_variables(cls, v: List[TemplateVariableV2], values) -> List[TemplateVariableV2]:
        """Validate that all variables in content are defined"""
        import re
        content = values.data.get("content", "")
        # Extract variables from content
        var_pattern = r'\{\{(\w+)\}\}'
        content_vars = set(re.findall(var_pattern, content))
        defined_vars = {var.name for var in v}

        # Check if all content variables are defined
        undefined_vars = content_vars - defined_vars
        if undefined_vars:
            raise ValueError(f"Undefined variables in content: {', '.join(undefined_vars)}")

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Medication Reminder V2",
                "content": "Olá {{patient_name}}, lembre-se de tomar seu medicamento {{medication_name}} às {{time}}.",
                "category": "medication",
                "language": "pt_BR",
                "variables": [
                    {
                        "name": "patient_name",
                        "description": "Patient's name",
                        "type": "string",
                        "required": True
                    },
                    {
                        "name": "medication_name",
                        "description": "Medication name",
                        "type": "string",
                        "required": True
                    },
                    {
                        "name": "time",
                        "description": "Time to take medication",
                        "type": "string",
                        "required": True
                    }
                ],
                "tags": ["medication", "reminder", "daily"]
            }
        }


class MessageTemplateV2Update(BaseModel):
    """Update a message template"""

    name: Optional[str] = Field(None, min_length=3, max_length=100)
    content: Optional[str] = Field(None, min_length=1, max_length=4096)
    category: Optional[TemplateCategoryV2] = None
    language: Optional[str] = None
    variables: Optional[List[TemplateVariableV2]] = None
    conditionals: Optional[List[TemplateConditionalV2]] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Updated Template Name",
                "is_active": True
            }
        }


class MessageTemplateV2Response(BaseModel):
    """Message template response"""

    id: str
    name: str
    content: str
    category: TemplateCategoryV2
    language: str
    variables: List[TemplateVariableV2]
    conditionals: List[TemplateConditionalV2]
    tags: List[str]
    metadata: Dict[str, Any]
    version: int = Field(..., description="Template version number")
    status: TemplateVersionStatus
    is_active: bool
    usage_count: int = Field(0, description="Number of times template was used")
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "tpl_123abc",
                "name": "Medication Reminder V2",
                "content": "Olá {{patient_name}}, lembre-se de tomar seu medicamento.",
                "category": "medication",
                "language": "pt_BR",
                "variables": [],
                "conditionals": [],
                "tags": ["medication", "reminder"],
                "metadata": {},
                "version": 2,
                "status": "active",
                "is_active": True,
                "usage_count": 145,
                "created_at": "2025-01-01T10:00:00Z",
                "updated_at": "2025-11-07T10:00:00Z"
            }
        }


class MessageTemplateV2List(CursorPaginatedResponse[MessageTemplateV2Response]):
    """Paginated list of message templates"""

    total_active: int = Field(0, description="Total active templates")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [],
                "next_cursor": None,
                "has_more": False,
                "total": 25,
                "total_active": 20
            }
        }


# ============================================================================
# Message Scheduling & Recurrence
# ============================================================================

class RecurrenceRuleV2(BaseModel):
    """Recurrence rule for scheduled messages"""

    type: RecurrenceType
    interval: int = Field(1, ge=1, description="Interval between occurrences")
    days_of_week: Optional[List[int]] = Field(None, description="Days of week (0=Monday, 6=Sunday)")
    days_of_month: Optional[List[int]] = Field(None, ge=1, le=31, description="Days of month")
    time_of_day: str = Field(..., description="Time to send (HH:MM format)")
    end_date: Optional[datetime] = Field(None, description="When to stop recurrence")
    max_occurrences: Optional[int] = Field(None, ge=1, description="Maximum number of occurrences")

    @field_validator("time_of_day")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Validate time format"""
        import re
        if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', v):
            raise ValueError("Time must be in HH:MM format")
        return v

    @field_validator("days_of_week")
    @classmethod
    def validate_days_of_week(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        """Validate days of week"""
        if v is not None:
            if not all(0 <= day <= 6 for day in v):
                raise ValueError("Days of week must be between 0 (Monday) and 6 (Sunday)")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "type": "weekly",
                "interval": 1,
                "days_of_week": [1, 3, 5],
                "time_of_day": "09:00",
                "end_date": "2025-12-31T00:00:00Z",
                "max_occurrences": 50
            }
        }


class ScheduledMessageV2Create(BaseModel):
    """Create a scheduled message"""

    patient_id: str
    content: str = Field(..., min_length=1, max_length=4096)
    type: MessageTypeV2 = MessageTypeV2.TEXT
    scheduled_for: datetime = Field(..., description="When to send the message")
    template_id: Optional[str] = Field(None, description="Template ID")
    template_variables: Optional[Dict[str, str]] = Field(None, description="Template variable values")
    recurrence: Optional[RecurrenceRuleV2] = Field(None, description="Recurrence rule for recurring messages")
    optimization_strategy: DeliveryOptimizationStrategy = DeliveryOptimizationStrategy.IMMEDIATE
    priority: str = Field("normal", description="Message priority")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("scheduled_for")
    @classmethod
    def validate_scheduled_for(cls, v: datetime) -> datetime:
        """Validate scheduled time is in the future"""
        if v <= datetime.utcnow():
            raise ValueError("Scheduled time must be in the future")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "pat_456def",
                "content": "Lembre-se da consulta amanhã!",
                "scheduled_for": "2025-11-08T09:00:00Z",
                "template_id": "tpl_123",
                "template_variables": {
                    "patient_name": "João"
                },
                "recurrence": {
                    "type": "daily",
                    "interval": 1,
                    "time_of_day": "09:00",
                    "max_occurrences": 7
                },
                "optimization_strategy": "best_time"
            }
        }


class ScheduledMessageV2Response(BaseModel):
    """Scheduled message response"""

    id: str
    message_id: Optional[str] = Field(None, description="Actual message ID when sent")
    patient_id: str
    content: str
    type: MessageTypeV2
    scheduled_for: datetime
    actual_sent_at: Optional[datetime] = Field(None, description="When message was actually sent")
    template_id: Optional[str] = None
    recurrence: Optional[RecurrenceRuleV2] = None
    optimization_strategy: DeliveryOptimizationStrategy
    status: str = Field(..., description="pending, sent, cancelled, failed")
    occurrences_sent: int = Field(0, description="Number of recurrences sent")
    next_occurrence: Optional[datetime] = Field(None, description="Next scheduled occurrence")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "sched_789xyz",
                "message_id": "msg_123abc",
                "patient_id": "pat_456def",
                "content": "Daily reminder message",
                "type": "text",
                "scheduled_for": "2025-11-08T09:00:00Z",
                "status": "sent",
                "occurrences_sent": 3,
                "next_occurrence": "2025-11-11T09:00:00Z",
                "created_at": "2025-11-07T10:00:00Z",
                "updated_at": "2025-11-10T09:00:15Z"
            }
        }


class ScheduledMessageV2List(CursorPaginatedResponse[ScheduledMessageV2Response]):
    """Paginated list of scheduled messages"""

    total_pending: int = Field(0, description="Total pending scheduled messages")
    total_recurring: int = Field(0, description="Total recurring messages")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [],
                "next_cursor": None,
                "has_more": False,
                "total": 45,
                "total_pending": 30,
                "total_recurring": 10
            }
        }


# ============================================================================
# A/B Testing
# ============================================================================

class ABTestVariantV2(BaseModel):
    """A/B test variant"""

    name: str = Field(..., description="Variant name (e.g., 'A', 'B', 'Control')")
    content: str = Field(..., min_length=1, max_length=4096, description="Message content")
    template_id: Optional[str] = None
    weight: float = Field(..., ge=0, le=100, description="Traffic percentage (0-100)")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Variant A",
                "content": "Olá! Lembre-se da sua consulta amanhã.",
                "weight": 50.0
            }
        }


class ABTestV2Create(BaseModel):
    """Create an A/B test"""

    name: str = Field(..., min_length=3, max_length=100, description="Test name")
    description: Optional[str] = Field(None, max_length=500)
    variants: List[ABTestVariantV2] = Field(..., min_items=2, description="Test variants")
    patient_ids: List[str] = Field(..., min_items=1, description="Target patients")
    start_date: datetime
    end_date: datetime
    success_metric: str = Field(..., description="Metric to optimize: delivery_rate, read_rate, response_rate")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("variants")
    @classmethod
    def validate_variants_weight(cls, v: List[ABTestVariantV2]) -> List[ABTestVariantV2]:
        """Validate that variant weights sum to 100"""
        total_weight = sum(variant.weight for variant in v)
        if abs(total_weight - 100.0) > 0.01:  # Allow small floating point errors
            raise ValueError(f"Variant weights must sum to 100, got {total_weight}")
        return v

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v: datetime, values) -> datetime:
        """Validate end date is after start date"""
        start_date = values.data.get("start_date")
        if start_date and v <= start_date:
            raise ValueError("End date must be after start date")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Reminder Message Test",
                "description": "Testing different reminder message formats",
                "variants": [
                    {
                        "name": "Short",
                        "content": "Consulta amanhã às 14h",
                        "weight": 50.0
                    },
                    {
                        "name": "Detailed",
                        "content": "Olá! Lembre-se da sua consulta amanhã às 14h com Dr. Silva.",
                        "weight": 50.0
                    }
                ],
                "patient_ids": ["pat_1", "pat_2", "pat_3"],
                "start_date": "2025-11-08T00:00:00Z",
                "end_date": "2025-11-15T23:59:59Z",
                "success_metric": "read_rate"
            }
        }


class ABTestResultsV2(BaseModel):
    """A/B test results"""

    variant_name: str
    messages_sent: int
    messages_delivered: int
    messages_read: int
    responses_received: int
    delivery_rate: float = Field(..., ge=0, le=100)
    read_rate: float = Field(..., ge=0, le=100)
    response_rate: float = Field(..., ge=0, le=100)
    average_response_time_minutes: Optional[float] = None

    class Config:
        json_schema_extra = {
            "example": {
                "variant_name": "Variant A",
                "messages_sent": 100,
                "messages_delivered": 98,
                "messages_read": 85,
                "responses_received": 42,
                "delivery_rate": 98.0,
                "read_rate": 86.7,
                "response_rate": 49.4,
                "average_response_time_minutes": 35.2
            }
        }


class ABTestV2Response(BaseModel):
    """A/B test response"""

    id: str
    name: str
    description: Optional[str]
    variants: List[ABTestVariantV2]
    status: ABTestStatus
    start_date: datetime
    end_date: datetime
    success_metric: str
    results: Optional[List[ABTestResultsV2]] = None
    winning_variant: Optional[str] = Field(None, description="Name of winning variant")
    confidence_level: Optional[float] = Field(None, ge=0, le=100, description="Statistical confidence")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "test_123abc",
                "name": "Reminder Message Test",
                "status": "completed",
                "winning_variant": "Variant A",
                "confidence_level": 95.5
            }
        }


class ABTestV2List(CursorPaginatedResponse[ABTestV2Response]):
    """Paginated list of A/B tests"""

    total_running: int = Field(0, description="Total running tests")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [],
                "next_cursor": None,
                "has_more": False,
                "total": 15,
                "total_running": 3
            }
        }


# ============================================================================
# Message Analytics & Performance
# ============================================================================

class MessageEngagementV2Response(BaseModel):
    """Message engagement metrics"""

    message_id: str
    patient_id: str
    sent_at: datetime
    delivered_at: Optional[datetime]
    read_at: Optional[datetime]
    responded_at: Optional[datetime]
    delivery_time_seconds: Optional[float]
    read_time_seconds: Optional[float]
    response_time_seconds: Optional[float]
    engagement_score: float = Field(..., ge=0, le=100, description="Overall engagement score")

    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "msg_123abc",
                "patient_id": "pat_456def",
                "sent_at": "2025-11-07T10:00:00Z",
                "delivered_at": "2025-11-07T10:00:03Z",
                "read_at": "2025-11-07T10:05:00Z",
                "responded_at": "2025-11-07T10:15:00Z",
                "delivery_time_seconds": 3.2,
                "read_time_seconds": 297.0,
                "response_time_seconds": 900.0,
                "engagement_score": 85.5
            }
        }


class MessagePerformanceV2Response(BaseModel):
    """Message performance analytics"""

    period_start: datetime
    period_end: datetime
    total_messages: int
    sent_count: int
    delivered_count: int
    read_count: int
    failed_count: int
    response_count: int
    delivery_rate: float = Field(..., ge=0, le=100)
    read_rate: float = Field(..., ge=0, le=100)
    response_rate: float = Field(..., ge=0, le=100)
    average_delivery_time_seconds: float
    average_read_time_seconds: float
    average_response_time_seconds: Optional[float]
    peak_hours: List[int] = Field(..., description="Hours with highest engagement (0-23)")
    best_day_of_week: Optional[int] = Field(None, description="Best day for engagement (0=Monday)")

    class Config:
        json_schema_extra = {
            "example": {
                "period_start": "2025-11-01T00:00:00Z",
                "period_end": "2025-11-07T23:59:59Z",
                "total_messages": 450,
                "sent_count": 450,
                "delivered_count": 442,
                "read_count": 398,
                "failed_count": 8,
                "response_count": 225,
                "delivery_rate": 98.2,
                "read_rate": 90.0,
                "response_rate": 50.9,
                "average_delivery_time_seconds": 3.5,
                "average_read_time_seconds": 320.0,
                "average_response_time_seconds": 1850.0,
                "peak_hours": [9, 10, 14, 15],
                "best_day_of_week": 2
            }
        }


class DeliveryOptimizationV2Response(BaseModel):
    """Delivery optimization recommendations"""

    patient_id: str
    recommended_send_time: str = Field(..., description="Recommended time (HH:MM)")
    recommended_days: List[int] = Field(..., description="Recommended days (0=Monday)")
    confidence_score: float = Field(..., ge=0, le=100)
    based_on_messages: int = Field(..., description="Number of messages analyzed")
    average_read_time_minutes: float
    best_response_rate: float = Field(..., ge=0, le=100)

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "pat_456def",
                "recommended_send_time": "09:30",
                "recommended_days": [1, 3, 5],
                "confidence_score": 87.5,
                "based_on_messages": 45,
                "average_read_time_minutes": 8.5,
                "best_response_rate": 65.2
            }
        }


# ============================================================================
# Bulk Operations
# ============================================================================

class BulkMessageV2Create(BaseModel):
    """Create bulk messages"""

    patient_ids: List[str] = Field(..., min_items=1, max_items=1000)
    content: str = Field(..., min_length=1, max_length=4096)
    type: MessageTypeV2 = MessageTypeV2.TEXT
    template_id: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    optimization_strategy: DeliveryOptimizationStrategy = DeliveryOptimizationStrategy.RATE_LIMITED
    batch_size: int = Field(100, ge=1, le=100, description="Messages to send per batch")
    delay_between_batches_seconds: int = Field(5, ge=0, le=60, description="Delay between batches")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "patient_ids": ["pat_1", "pat_2", "pat_3"],
                "content": "Lembrete: consulta esta semana!",
                "type": "text",
                "scheduled_for": "2025-11-08T09:00:00Z",
                "optimization_strategy": "rate_limited",
                "batch_size": 50,
                "delay_between_batches_seconds": 10
            }
        }


class BulkMessageV2Response(BaseModel):
    """Bulk message operation response"""

    job_id: str
    total_patients: int
    scheduled_count: int
    failed_count: int
    failed_patients: List[str]
    estimated_completion: datetime
    status: str = Field(..., description="queued, processing, completed, failed")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "bulk_789xyz",
                "total_patients": 100,
                "scheduled_count": 98,
                "failed_count": 2,
                "failed_patients": ["pat_invalid1", "pat_invalid2"],
                "estimated_completion": "2025-11-08T09:15:00Z",
                "status": "processing"
            }
        }


class BulkJobStatusV2Response(BaseModel):
    """Bulk job status response"""

    job_id: str
    status: str
    total_patients: int
    processed: int
    successful: int
    failed: int
    progress_percentage: float = Field(..., ge=0, le=100)
    started_at: datetime
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "bulk_789xyz",
                "status": "processing",
                "total_patients": 100,
                "processed": 65,
                "successful": 64,
                "failed": 1,
                "progress_percentage": 65.0,
                "started_at": "2025-11-08T09:00:00Z",
                "estimated_completion": "2025-11-08T09:10:00Z"
            }
        }
