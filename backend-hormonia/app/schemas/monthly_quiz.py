"""
Monthly Quiz Schemas for Hormonia Backend System.

Pydantic schemas for monthly quiz via link functionality.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


class DeliveryMethod(str, Enum):
    """Delivery methods for quiz links."""

    WHATSAPP = "whatsapp"
    EMAIL = "email"
    SMS = "sms"
    MANUAL = "manual"


class QuizLinkStatus(str, Enum):
    """Status of quiz link."""

    ACTIVE = "active"
    EXPIRED = "expired"
    USED = "used"
    CANCELLED = "cancelled"


class MonthlyQuizLinkCreate(BaseModel):
    """Schema for creating monthly quiz link."""

    patient_id: UUID = Field(..., description="Patient ID")
    quiz_template_id: UUID = Field(..., description="Quiz template ID")
    delivery_method: DeliveryMethod = Field(
        default=DeliveryMethod.WHATSAPP, description="Delivery method for the quiz link"
    )
    expiry_hours: Optional[int] = Field(
        default=72, description="Link expiry in hours (default: 72)"
    )
    custom_message: Optional[str] = Field(
        None, description="Custom message to send with the link"
    )
    send_immediately: bool = Field(
        default=True,
        description="Automatically send the quiz link to the patient via the configured delivery method",
    )


class MonthlyQuizLinkResponse(BaseModel):
    """Schema for monthly quiz link response."""

    id: UUID = Field(..., description="Link ID")
    patient_id: UUID = Field(..., description="Patient ID")
    quiz_template_id: UUID = Field(..., description="Quiz template ID")
    token: str = Field(..., description="Access token")
    link_url: str = Field(..., description="Full quiz access URL")
    delivery_method: DeliveryMethod = Field(..., description="Delivery method")
    status: QuizLinkStatus = Field(..., description="Link status")
    expires_at: datetime = Field(..., description="Link expiration timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    accessed_at: Optional[datetime] = Field(None, description="First access timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    access_count: int = Field(
        default=0, description="Number of times link was accessed"
    )
    delivery_attempts: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="History of delivery attempts with timestamps and statuses",
    )
    last_delivery_status: Optional[str] = Field(
        default=None, description="Most recent delivery status"
    )
    last_delivery_method: Optional[str] = Field(
        default=None, description="Most recent delivery method used"
    )

    # Dashboard fields
    patient_name: Optional[str] = Field(None, description="Patient name for dashboard")
    patient_phone: Optional[str] = Field(
        None, description="Patient phone for dashboard"
    )
    template_name: Optional[str] = Field(
        None, description="Template name for dashboard"
    )
    template_version: Optional[str] = Field(
        None, description="Template version for dashboard"
    )
    sent_at: Optional[datetime] = Field(
        None, description="Sent timestamp (alias for created_at)"
    )
    session_id: Optional[UUID] = Field(None, description="Session ID for tracking")

    model_config = ConfigDict(from_attributes=True)


class MonthlyQuizAccessRequest(BaseModel):
    """Schema for accessing quiz via token."""

    token: str = Field(..., description="Quiz access token")


class MonthlyQuizAccessResponse(BaseModel):
    """Schema for quiz access response."""

    quiz_session_id: UUID = Field(..., description="Quiz session ID")
    patient_name: str = Field(..., description="Patient name")
    template_name: str = Field(..., description="Quiz template name")
    template_version: str = Field(..., description="Template version")
    questions: List[Dict[str, Any]] = Field(..., description="Quiz questions")
    current_question_index: int = Field(..., description="Current question index")
    total_questions: int = Field(..., description="Total number of questions")
    expires_at: datetime = Field(..., description="Session expiry")
    new_token: Optional[str] = Field(None, description="Rotated token for next request")


class MonthlyQuizSubmitResponse(BaseModel):
    """Schema for submitting quiz response via link."""

    token: str = Field(..., description="Quiz access token")
    question_id: str = Field(..., description="Question ID")
    response_value: Any = Field(
        ..., description="Response value (string or list for multiple choice)"
    )
    other_text: Optional[str] = Field(
        None, description="Custom text for 'other' option"
    )
    response_metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional response metadata"
    )


class MonthlyQuizStats(BaseModel):
    """Schema for monthly quiz statistics."""

    total_links_created: int = Field(..., description="Total links created")
    active_links: int = Field(..., description="Currently active links")
    expired_links: int = Field(..., description="Expired links")
    completed_quizzes: int = Field(..., description="Completed quizzes")
    completion_rate: float = Field(..., description="Completion rate percentage")
    average_completion_time: Optional[float] = Field(
        None, description="Average completion time in minutes"
    )
    delivery_methods_distribution: Dict[str, int] = Field(
        default_factory=dict, description="Distribution of delivery methods"
    )


class BulkQuizLinkCreate(BaseModel):
    """Schema for bulk creating quiz links."""

    patient_ids: List[UUID] = Field(
        ..., min_length=1, description="List of patient IDs"
    )
    quiz_template_id: UUID = Field(..., description="Quiz template ID")
    delivery_method: DeliveryMethod = Field(
        default=DeliveryMethod.WHATSAPP, description="Delivery method for all links"
    )
    expiry_hours: Optional[int] = Field(default=72, description="Link expiry in hours")
    custom_message: Optional[str] = Field(
        None, description="Custom message to send with links"
    )
    send_immediately: bool = Field(
        default=True, description="Automatically send each quiz link after creation"
    )

    @field_validator("patient_ids")
    @classmethod
    def validate_patient_ids(cls, v):
        """Ensure patient_ids list is not empty and has unique values."""
        if not v:
            raise ValueError("patient_ids list cannot be empty")
        if len(v) != len(set(v)):
            raise ValueError("patient_ids must be unique")
        return v


class BulkQuizLinkResponse(BaseModel):
    """Schema for bulk quiz link creation response."""

    total_requested: int = Field(..., description="Total links requested")
    total_created: int = Field(..., description="Total links created")
    total_failed: int = Field(..., description="Total failures")
    links: List[MonthlyQuizLinkResponse] = Field(..., description="Created links")
    failures: List[Dict[str, Any]] = Field(
        default_factory=list, description="Failed creations with reasons"
    )
