from typing import Optional, Any
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.models.message import MessageDirection, MessageType, MessageStatus
from app.security.data_protection import get_data_protection_service


class MessageBase(BaseModel):
    """Base message schema with data protection"""

    patient_id: UUID = Field(..., description="Patient ID")
    direction: MessageDirection = Field(..., description="Message direction")
    type: MessageType = Field(default=MessageType.TEXT, description="Message type")
    content: Optional[str] = Field(None, description="Message content")
    message_metadata: Optional[dict[str, Any]] = Field(
        default_factory=dict, description="Message metadata"
    )

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v):
        """Sanitize message content for data protection."""
        if v:
            protection_service = get_data_protection_service()
            return protection_service.sanitize_for_logging(v)
        return v

    @field_validator("message_metadata")
    @classmethod
    def sanitize_metadata(cls, v):
        """Sanitize metadata for data protection."""
        if v:
            protection_service = get_data_protection_service()
            return protection_service.sanitize_for_logging(v)
        return v


class MessageCreate(MessageBase):
    """Schema for creating a message"""

    scheduled_for: Optional[datetime] = Field(
        None, description="Scheduled delivery time"
    )
    status: Optional[MessageStatus] = Field(
        None, description="Initial message status (optional, defaults to PENDING)"
    )


class MessageUpdate(BaseModel):
    """Schema for updating a message"""

    content: Optional[str] = None
    message_metadata: Optional[dict[str, Any]] = None
    whatsapp_id: Optional[str] = None
    status: Optional[MessageStatus] = None
    scheduled_for: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v):
        """Sanitize message content for data protection."""
        if v:
            protection_service = get_data_protection_service()
            return protection_service.sanitize_for_logging(v)
        return v

    @field_validator("message_metadata")
    @classmethod
    def sanitize_metadata(cls, v):
        """Sanitize metadata for data protection."""
        if v:
            protection_service = get_data_protection_service()
            return protection_service.sanitize_for_logging(v)
        return v


class MessageResponse(MessageBase):
    """Schema for message response with enhanced security"""

    id: UUID
    whatsapp_id: Optional[str]
    status: MessageStatus
    scheduled_for: Optional[datetime]
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    read_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    def model_dump(self, **kwargs):
        """Override model_dump method to apply data protection."""
        data = super().model_dump(**kwargs)
        protection_service = get_data_protection_service()
        return protection_service.sanitize_for_logging(data)


class MessageListResponse(BaseModel):
    """Schema for message list response"""

    messages: list[MessageResponse]
    total: int
    skip: int
    limit: int


class ScheduleMessageRequest(BaseModel):
    """Schema for scheduling a message"""

    patient_id: UUID
    content: str
    scheduled_for: datetime
    type: MessageType = MessageType.TEXT
    message_metadata: Optional[dict[str, Any]] = None

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v):
        """Sanitize message content for data protection."""
        if v:
            protection_service = get_data_protection_service()
            return protection_service.sanitize_for_logging(v)
        return v


class InboundMessageRequest(BaseModel):
    """Schema for processing inbound messages"""

    patient_phone: str
    content: str
    whatsapp_id: str
    type: MessageType = MessageType.TEXT
    message_metadata: Optional[dict[str, Any]] = None

    @field_validator("patient_phone")
    @classmethod
    def mask_phone(cls, v):
        """Mask phone number for security."""
        if v:
            protection_service = get_data_protection_service()
            return protection_service.mask_phone(v)
        return v

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v):
        """Sanitize message content for data protection."""
        if v:
            protection_service = get_data_protection_service()
            return protection_service.sanitize_for_logging(v)
        return v


class BulkMessageCreate(BaseModel):
    """Schema for bulk message creation."""

    patient_ids: list[UUID]
    content: str
    type: MessageType = MessageType.TEXT
    priority: str = "normal"
    scheduled_for: Optional[datetime] = None
    message_metadata: Optional[dict[str, Any]] = None

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v):
        """Sanitize message content for data protection."""
        if v:
            protection_service = get_data_protection_service()
            return protection_service.sanitize_for_logging(v)
        return v


class MessageTemplate(BaseModel):
    """Message template schema."""

    id: UUID
    name: str
    content: str
    variables: list[str] = []
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v):
        """Sanitize template content for data protection."""
        if v:
            protection_service = get_data_protection_service()
            return protection_service.sanitize_for_logging(v)
        return v
