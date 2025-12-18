"""
WhatsApp message models for Evolution API integration.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, Text, JSON, Boolean, Integer
from app.database import Base


class MessageStatus(str, Enum):
    """Message delivery status enumeration."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    EXPIRED = "expired"


class MessageType(str, Enum):
    """Message type enumeration."""

    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    STICKER = "sticker"
    LOCATION = "location"
    CONTACT = "contact"
    TEMPLATE = "template"


class WhatsAppMessage(Base):
    """WhatsApp message database model."""

    __tablename__ = "whatsapp_messages"

    id = Column(String, primary_key=True)
    instance_name = Column(String, nullable=False, index=True)
    chat_id = Column(String, nullable=False, index=True)
    sender_id = Column(String, nullable=False)
    recipient_id = Column(String, nullable=False)
    message_type = Column(String, nullable=False)
    content = Column(Text)
    media_url = Column(String)
    media_caption = Column(Text)
    status = Column(String, default=MessageStatus.PENDING)
    external_id = Column(String, unique=True, index=True)  # Evolution API message ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)
    read_at = Column(DateTime)
    failed_at = Column(DateTime)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)
    message_data = Column(JSON)  # Additional message metadata


class WhatsAppContact(Base):
    """WhatsApp contact database model."""

    __tablename__ = "whatsapp_contacts"

    id = Column(String, primary_key=True)
    instance_name = Column(String, nullable=False, index=True)
    phone_number = Column(String, nullable=False, index=True)
    formatted_number = Column(String, nullable=False)
    name = Column(String)
    profile_picture_url = Column(String)
    is_whatsapp_user = Column(Boolean, default=True)
    last_seen = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    contact_data = Column(JSON)


class WhatsAppInstance(Base):
    """WhatsApp instance database model."""

    __tablename__ = "whatsapp_instances"

    id = Column(String, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)
    status = Column(String, default="disconnected")
    qr_code = Column(Text)
    webhook_url = Column(String)
    phone_number = Column(String)
    profile_name = Column(String)
    profile_picture_url = Column(String)
    is_connected = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_activity = Column(DateTime)
    settings = Column(JSON)  # Instance-specific settings


# Pydantic models for API requests/responses
class MessageRequest(BaseModel):
    """Request model for sending WhatsApp messages."""

    instance_name: str
    to: str
    message_type: MessageType = MessageType.TEXT
    text: Optional[str] = None
    media_url: Optional[str] = None
    media_caption: Optional[str] = None
    filename: Optional[str] = None
    template_name: Optional[str] = None
    template_params: Optional[List[str]] = None
    message_data: Optional[Dict[str, Any]] = None


class MessageResponse(BaseModel):
    """Response model for WhatsApp message operations."""

    id: str
    external_id: Optional[str] = None
    status: MessageStatus
    message: str
    timestamp: datetime
    message_data: Optional[Dict[str, Any]] = None


class ContactRequest(BaseModel):
    """Request model for contact operations."""

    instance_name: str
    phone_number: str
    name: Optional[str] = None


class ContactResponse(BaseModel):
    """Response model for contact operations."""

    id: str
    phone_number: str
    formatted_number: str
    name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    is_whatsapp_user: bool
    last_seen: Optional[datetime] = None


class InstanceStatus(BaseModel):
    """WhatsApp instance status model."""

    name: str
    status: str
    is_connected: bool
    phone_number: Optional[str] = None
    profile_name: Optional[str] = None
    qr_code: Optional[str] = None
    last_activity: Optional[datetime] = None


class WebhookPayload(BaseModel):
    """Webhook payload model for incoming messages."""

    instance: str
    data: Dict[str, Any]
    event: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MessageStatusUpdate(BaseModel):
    """Message status update model."""

    message_id: str
    status: MessageStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
