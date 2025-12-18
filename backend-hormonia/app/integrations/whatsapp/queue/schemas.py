"""
Queue message schemas for WhatsApp integration.

Defines the data structures used for queue-based message processing.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class MessageRequest(BaseModel):
    """
    Schema for WhatsApp message requests in queue system.

    Used for routing messages to different Evolution instances
    based on configuration and metadata.
    """

    instance_name: str = Field(
        ..., description="Name of the Evolution instance to route to"
    )
    to: str = Field(..., description="Recipient phone number")
    text: Optional[str] = Field(None, description="Text content for text messages")
    media_url: Optional[str] = Field(None, description="URL for media messages")
    media_type: Optional[str] = Field(
        None, description="Type of media (image, video, audio, document)"
    )
    template_name: Optional[str] = Field(
        None, description="WhatsApp template name for template messages"
    )
    template_params: Optional[Dict[str, Any]] = Field(
        None, description="Template parameters for template messages"
    )
    message_type: str = Field(
        default="text",
        description="Type of message: text, media, template, interactive",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional message metadata"
    )
    priority: int = Field(
        default=1, description="Message priority (1=high, 5=low)", ge=1, le=5
    )
    retry_count: int = Field(default=0, description="Number of retry attempts")
    scheduled_at: Optional[datetime] = Field(
        None, description="Scheduled delivery time"
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat() if v else None}
    )


class MessageResponse(BaseModel):
    """
    Schema for WhatsApp message responses from queue system.
    """

    success: bool = Field(..., description="Whether the message was sent successfully")
    message_id: Optional[str] = Field(
        None, description="External message ID from WhatsApp"
    )
    error_code: Optional[str] = Field(None, description="Error code if message failed")
    error_message: Optional[str] = Field(
        None, description="Error message if message failed"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )
    instance_name: str = Field(
        ..., description="Name of the Evolution instance that processed the message"
    )
    retry_after: Optional[int] = Field(
        None, description="Seconds to wait before retry (if applicable)"
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat() if v else None}
    )


class QueueStatus(BaseModel):
    """
    Schema for queue status information.
    """

    queue_name: str = Field(..., description="Name of the message queue")
    pending_messages: int = Field(
        ..., description="Number of messages pending in queue"
    )
    processing_messages: int = Field(
        ..., description="Number of messages currently being processed"
    )
    failed_messages: int = Field(
        ..., description="Number of messages that failed processing"
    )
    last_activity: Optional[datetime] = Field(
        None, description="Timestamp of last queue activity"
    )
    is_healthy: bool = Field(
        ..., description="Whether the queue is healthy and operational"
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat() if v else None}
    )
