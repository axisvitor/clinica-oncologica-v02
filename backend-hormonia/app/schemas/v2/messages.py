"""
Message management schemas for API v2
Enhanced message models with cursor pagination, field selection, and eager loading support.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator

from .common import CursorPaginatedResponse, ErrorResponse


# ============================================================================
# Enums
# ============================================================================

class MessageStatusV2(str, Enum):
    """Message status enumeration for V2 API"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageTypeV2(str, Enum):
    """Message type enumeration"""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    INTERACTIVE = "interactive"
    TEMPLATE = "template"


class MessageDirectionV2(str, Enum):
    """Message direction enumeration"""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessagingModeV2(str, Enum):
    """Messaging mode for patient communication"""
    CONVERSATIONAL = "conversational"
    BROADCAST = "broadcast"
    AUTOMATED = "automated"
    INTERACTIVE = "interactive"


# ============================================================================
# Brief Models (for nested relationships)
# ============================================================================

class PatientV2Brief(BaseModel):
    """Brief patient information for message responses"""

    id: str
    name: str
    phone: Optional[str] = None

    class Config:
        from_attributes = True


class TemplateV2Brief(BaseModel):
    """Brief template information for message responses"""

    id: str
    name: str
    version: Optional[str] = None

    class Config:
        from_attributes = True


# ============================================================================
# Message Base Models
# ============================================================================

class MessageV2Base(BaseModel):
    """Base message schema"""

    patient_id: str = Field(..., description="Patient ID")
    content: str = Field(..., min_length=1, max_length=4096, description="Message content")
    type: MessageTypeV2 = Field(MessageTypeV2.TEXT, description="Message type")
    direction: MessageDirectionV2 = Field(..., description="Message direction")
    message_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Message metadata")

    @validator("content")
    def validate_content(cls, v):
        """Validate content is not empty"""
        if not v or not v.strip():
            raise ValueError("Content cannot be empty")
        return v.strip()


class MessageV2Create(MessageV2Base):
    """Schema for creating a message"""

    scheduled_for: Optional[datetime] = Field(None, description="Scheduled delivery time")
    template_id: Optional[str] = Field(None, description="Template ID if using template")
    template_variables: Optional[Dict[str, str]] = Field(None, description="Template variable values")
    priority: str = Field("normal", description="Message priority: low, normal, high, urgent")

    @validator("priority")
    def validate_priority(cls, v):
        """Validate priority level"""
        allowed = ["low", "normal", "high", "urgent"]
        if v not in allowed:
            raise ValueError(f"Priority must be one of: {', '.join(allowed)}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "pat_456def",
                "content": "Olá! Lembre-se de tomar seu medicamento hoje às 9h.",
                "type": "text",
                "direction": "outbound",
                "scheduled_for": "2025-11-08T09:00:00Z",
                "priority": "normal",
                "message_metadata": {
                    "campaign": "medication_reminder",
                    "flow_day": 7
                }
            }
        }


class MessageV2Update(BaseModel):
    """Schema for updating a message"""

    content: Optional[str] = Field(None, min_length=1, max_length=4096)
    scheduled_for: Optional[datetime] = None
    status: Optional[MessageStatusV2] = None
    message_metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "content": "Updated message content",
                "scheduled_for": "2025-11-08T10:00:00Z"
            }
        }


class MessageV2Response(MessageV2Base):
    """Full message response with metadata"""

    id: str
    status: MessageStatusV2
    scheduled_for: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    whatsapp_id: Optional[str] = Field(None, description="WhatsApp message ID")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(0, ge=0, description="Number of retry attempts")
    created_at: datetime
    updated_at: datetime

    # Optional eager-loaded relationships
    patient: Optional[PatientV2Brief] = None
    template: Optional[TemplateV2Brief] = None

    # Computed fields
    delivery_time_seconds: Optional[float] = Field(None, description="Time to deliver (sent to delivered)")
    read_time_seconds: Optional[float] = Field(None, description="Time to read (delivered to read)")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "msg_123abc",
                "patient_id": "pat_456def",
                "content": "Olá! Lembre-se de tomar seu medicamento.",
                "type": "text",
                "direction": "outbound",
                "status": "delivered",
                "scheduled_for": "2025-11-08T09:00:00Z",
                "sent_at": "2025-11-08T09:00:05Z",
                "delivered_at": "2025-11-08T09:00:08Z",
                "whatsapp_id": "wamid.HBgNNTU5ODc2NTQzMjEwFQIAEhgUM0E...",
                "created_at": "2025-11-07T10:00:00Z",
                "updated_at": "2025-11-08T09:00:08Z",
                "patient": {
                    "id": "pat_456def",
                    "name": "João Silva",
                    "phone": "+5511987654321"
                },
                "delivery_time_seconds": 3.2
            }
        }


class MessageV2List(CursorPaginatedResponse[MessageV2Response]):
    """Paginated list of messages"""

    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "id": "msg_123abc",
                        "patient_id": "pat_456def",
                        "content": "Hello message",
                        "type": "text",
                        "status": "delivered",
                        "created_at": "2025-11-07T10:00:00Z"
                    }
                ],
                "next_cursor": "eyJpZCI6Im1zZ18xMjNhYmMifQ==",
                "has_more": True,
                "total": 342
            }
        }


# ============================================================================
# Conversation Models
# ============================================================================

class ConversationV2Response(BaseModel):
    """Conversation thread (grouped messages)"""

    patient_id: str
    patient: Optional[PatientV2Brief] = None
    messages: List[MessageV2Response]
    unread_count: int = Field(0, ge=0, description="Unread messages count")
    last_message_at: Optional[datetime] = None
    messaging_mode: MessagingModeV2

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "pat_456def",
                "patient": {
                    "id": "pat_456def",
                    "name": "João Silva",
                    "phone": "+5511987654321"
                },
                "messages": [
                    {
                        "id": "msg_1",
                        "content": "Hello",
                        "direction": "outbound",
                        "status": "delivered"
                    }
                ],
                "unread_count": 2,
                "last_message_at": "2025-11-07T10:30:00Z",
                "messaging_mode": "conversational"
            }
        }


class ConversationV2List(CursorPaginatedResponse[ConversationV2Response]):
    """Paginated list of conversations"""

    total_unread: int = Field(0, ge=0, description="Total unread messages across all conversations")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "patient_id": "pat_456",
                        "unread_count": 2,
                        "last_message_at": "2025-11-07T10:30:00Z"
                    }
                ],
                "next_cursor": "eyJpZCI6InBhdF80NTYifQ==",
                "has_more": True,
                "total": 48,
                "total_unread": 15
            }
        }


# ============================================================================
# Message Operations
# ============================================================================

class SendMessageV2Request(BaseModel):
    """Request to send an immediate message"""

    patient_id: str
    content: str = Field(..., min_length=1, max_length=4096)
    type: MessageTypeV2 = MessageTypeV2.TEXT
    message_metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "pat_456def",
                "content": "Dr. Silva gostaria de agendar uma consulta com você.",
                "type": "text",
                "message_metadata": {
                    "sent_by": "doctor",
                    "urgent": True
                }
            }
        }


class SendMessageV2Response(BaseModel):
    """Response after sending a message"""

    success: bool
    message: MessageV2Response
    estimated_delivery: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": {
                    "id": "msg_123abc",
                    "status": "sent",
                    "sent_at": "2025-11-07T10:00:00Z"
                },
                "estimated_delivery": "2025-11-07T10:00:03Z"
            }
        }


class ScheduleMessageV2Request(BaseModel):
    """Request to schedule a message"""

    patient_id: str
    content: str = Field(..., min_length=1, max_length=4096)
    scheduled_for: datetime = Field(..., description="When to send the message")
    type: MessageTypeV2 = MessageTypeV2.TEXT
    message_metadata: Optional[Dict[str, Any]] = None

    @validator("scheduled_for")
    def validate_scheduled_for(cls, v):
        """Validate scheduled time is in the future"""
        if v <= datetime.utcnow():
            raise ValueError("Scheduled time must be in the future")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "pat_456def",
                "content": "Lembre-se da consulta amanhã às 14h!",
                "scheduled_for": "2025-11-08T08:00:00Z",
                "type": "text"
            }
        }


class ScheduleMessageV2Response(BaseModel):
    """Response after scheduling a message"""

    success: bool
    message: MessageV2Response
    can_cancel: bool = Field(True, description="Whether message can still be cancelled")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": {
                    "id": "msg_123abc",
                    "status": "scheduled",
                    "scheduled_for": "2025-11-08T08:00:00Z"
                },
                "can_cancel": True
            }
        }


class CancelMessageV2Response(BaseModel):
    """Response after cancelling a scheduled message"""

    success: bool
    message_id: str
    previous_status: MessageStatusV2
    cancelled_at: datetime
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message_id": "msg_123abc",
                "previous_status": "scheduled",
                "cancelled_at": "2025-11-07T10:30:00Z",
                "message": "Message cancelled successfully"
            }
        }


class RetryMessageV2Request(BaseModel):
    """Request to retry a failed message"""

    force: bool = Field(False, description="Force retry even if max retries reached")
    new_content: Optional[str] = Field(None, description="Updated content for retry")

    class Config:
        json_schema_extra = {
            "example": {
                "force": False,
                "new_content": "Updated message content"
            }
        }


# ============================================================================
# Message Statistics
# ============================================================================

class MessageStatsV2Response(BaseModel):
    """Message statistics for a patient"""

    patient_id: str
    total_messages: int
    sent_count: int
    delivered_count: int
    read_count: int
    failed_count: int
    delivery_rate: float = Field(..., ge=0, le=100, description="Percentage of delivered messages")
    read_rate: float = Field(..., ge=0, le=100, description="Percentage of read messages")
    average_response_time_minutes: Optional[float] = None
    last_message_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "pat_456def",
                "total_messages": 45,
                "sent_count": 45,
                "delivered_count": 43,
                "read_count": 38,
                "failed_count": 2,
                "delivery_rate": 95.6,
                "read_rate": 88.4,
                "average_response_time_minutes": 32.5,
                "last_message_at": "2025-11-07T10:00:00Z"
            }
        }


class MessageStatusDistributionV2Response(BaseModel):
    """Message status distribution"""

    period_start: datetime
    period_end: datetime
    status_counts: Dict[str, int] = Field(..., description="Count per status")
    total_messages: int
    success_rate: float = Field(..., ge=0, le=100)

    class Config:
        json_schema_extra = {
            "example": {
                "period_start": "2025-11-01T00:00:00Z",
                "period_end": "2025-11-07T23:59:59Z",
                "status_counts": {
                    "sent": 234,
                    "delivered": 228,
                    "read": 198,
                    "failed": 6
                },
                "total_messages": 234,
                "success_rate": 97.4
            }
        }


class FailedMessageV2Response(MessageV2Response):
    """Failed message with additional error details"""

    failure_reason: str = Field(..., description="Human-readable failure reason")
    can_retry: bool = Field(..., description="Whether message can be retried")
    next_retry_at: Optional[datetime] = Field(None, description="Next automatic retry time")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "msg_123abc",
                "status": "failed",
                "error_message": "Invalid phone number",
                "failure_reason": "Phone number is not registered on WhatsApp",
                "can_retry": False,
                "retry_count": 3,
                "failed_at": "2025-11-07T10:05:00Z"
            }
        }


class FailedMessagesV2List(CursorPaginatedResponse[FailedMessageV2Response]):
    """Paginated list of failed messages"""

    total_retryable: int = Field(0, description="Count of messages that can be retried")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "id": "msg_123",
                        "status": "failed",
                        "can_retry": True,
                        "failure_reason": "Network timeout"
                    }
                ],
                "next_cursor": None,
                "has_more": False,
                "total": 8,
                "total_retryable": 5
            }
        }


# ============================================================================
# Inbound Messages
# ============================================================================

class InboundMessageV2Request(BaseModel):
    """Request to process an inbound message (webhook)"""

    patient_phone: str = Field(..., description="Patient phone number (E.164)")
    content: str = Field(..., min_length=1, max_length=4096)
    whatsapp_id: str = Field(..., description="WhatsApp message ID")
    type: MessageTypeV2 = MessageTypeV2.TEXT
    received_at: Optional[datetime] = Field(None, description="When message was received")
    message_metadata: Optional[Dict[str, Any]] = None

    @validator("patient_phone")
    def validate_phone(cls, v):
        """Validate phone number format"""
        # Basic E.164 validation
        if not v.startswith("+"):
            raise ValueError("Phone must be in E.164 format (starting with +)")
        if not v[1:].isdigit():
            raise ValueError("Phone must contain only digits after +")
        if len(v) < 10 or len(v) > 16:
            raise ValueError("Phone must be 10-16 characters")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "patient_phone": "+5511987654321",
                "content": "Sim, estou tomando o medicamento corretamente.",
                "whatsapp_id": "wamid.HBgNNTU5ODc2NTQzMjEwFQIAEhgUM0E...",
                "type": "text",
                "received_at": "2025-11-07T10:30:00Z",
                "message_metadata": {
                    "from_name": "João Silva",
                    "media_url": None
                }
            }
        }


class InboundMessageV2Response(BaseModel):
    """Response after processing inbound message"""

    success: bool
    message: MessageV2Response
    patient: PatientV2Brief
    auto_reply_sent: bool = Field(False, description="Whether an auto-reply was sent")
    auto_reply_message_id: Optional[str] = None
    conversation_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": {
                    "id": "msg_789xyz",
                    "direction": "inbound",
                    "status": "delivered",
                    "content": "Sim, estou tomando o medicamento."
                },
                "patient": {
                    "id": "pat_456def",
                    "name": "João Silva",
                    "phone": "+5511987654321"
                },
                "auto_reply_sent": True,
                "auto_reply_message_id": "msg_790abc",
                "conversation_id": "conv_123"
            }
        }


# ============================================================================
# Bulk Operations
# ============================================================================

class BulkMessageV2Request(BaseModel):
    """Request to send bulk messages"""

    patient_ids: List[str] = Field(..., min_items=1, max_items=1000, description="List of patient IDs")
    content: str = Field(..., min_length=1, max_length=4096)
    type: MessageTypeV2 = MessageTypeV2.TEXT
    scheduled_for: Optional[datetime] = None
    message_metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "patient_ids": ["pat_456def", "pat_789ghi", "pat_012jkl"],
                "content": "Lembrete: Consulta agendada para esta semana.",
                "type": "text",
                "scheduled_for": "2025-11-08T09:00:00Z",
                "message_metadata": {
                    "campaign": "weekly_reminder",
                    "batch_id": "batch_123"
                }
            }
        }


class BulkMessageV2Response(BaseModel):
    """Response after creating bulk messages"""

    success: bool
    batch_id: str
    total_messages: int
    scheduled_count: int
    failed_count: int
    failed_patients: List[str] = Field(default_factory=list, description="Patient IDs that failed")
    estimated_completion: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "batch_id": "batch_123abc",
                "total_messages": 100,
                "scheduled_count": 98,
                "failed_count": 2,
                "failed_patients": ["pat_invalid1", "pat_invalid2"],
                "estimated_completion": "2025-11-08T09:15:00Z"
            }
        }


# ============================================================================
# Message Templates
# ============================================================================

class MessageTemplateV2Response(BaseModel):
    """Message template response"""

    id: str
    name: str
    content: str = Field(..., description="Template content with {{variables}}")
    variables: List[str] = Field(default_factory=list, description="Required variable names")
    category: str = Field(..., description="Template category")
    language: str = Field("pt_BR", description="Template language")
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "tpl_123abc",
                "name": "Medication Reminder",
                "content": "Olá {{patient_name}}, lembre-se de tomar seu medicamento {{medication_name}} às {{time}}.",
                "variables": ["patient_name", "medication_name", "time"],
                "category": "reminder",
                "language": "pt_BR",
                "is_active": True,
                "created_at": "2025-01-01T10:00:00Z",
                "updated_at": "2025-11-07T10:00:00Z"
            }
        }


class MessageTemplateV2List(CursorPaginatedResponse[MessageTemplateV2Response]):
    """Paginated list of message templates"""

    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "id": "tpl_123",
                        "name": "Medication Reminder",
                        "category": "reminder",
                        "is_active": True
                    }
                ],
                "next_cursor": None,
                "has_more": False,
                "total": 15
            }
        }


class MessageTemplateV2Create(BaseModel):
    """Request schema for creating a message template"""

    name: str = Field(..., min_length=1, max_length=100, description="Unique template name")
    content: str = Field(..., min_length=1, description="Template content with {{variables}}")
    variables: List[str] = Field(default_factory=list, description="Variable names used in content")
    category: str = Field("text", description="Template category (text, image, document, etc.)")
    language: str = Field("pt_BR", description="Template language code")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "appointment_reminder",
                "content": "Olá {{patient_name}}, seu agendamento está confirmado para {{date}} às {{time}}.",
                "variables": ["patient_name", "date", "time"],
                "category": "reminder",
                "language": "pt_BR"
            }
        }


class MessageTemplateV2Update(BaseModel):
    """Request schema for updating a message template"""

    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Template name")
    content: Optional[str] = Field(None, min_length=1, description="Template content")
    variables: Optional[List[str]] = Field(None, description="Variable names used in content")
    category: Optional[str] = Field(None, description="Template category")
    language: Optional[str] = Field(None, description="Template language code")
    is_active: Optional[bool] = Field(None, description="Whether template is active")

    class Config:
        json_schema_extra = {
            "example": {
                "content": "Olá {{patient_name}}, sua consulta foi remarcada para {{new_date}}.",
                "variables": ["patient_name", "new_date"],
                "is_active": True
            }
        }
