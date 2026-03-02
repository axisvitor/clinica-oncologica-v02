"""
WhatsApp Integration Package for Clinica Oncológica
"""

from .models.message import (
    WhatsAppMessage,
    WhatsAppContact,
    WhatsAppInstance,
    MessageRequest,
    MessageResponse,
    MessageStatus,
    MessageType,
    ContactResponse,
    InstanceStatus,
    WebhookPayload,
    MessageStatusUpdate,
)

from .services.message_service import WhatsAppMessageService, MessageQueue

from .api.routes import router as whatsapp_router

__version__ = "1.0.0"
__author__ = "Hormonia System"

__all__ = [
    # Models
    "WhatsAppMessage",
    "WhatsAppContact",
    "WhatsAppInstance",
    "MessageRequest",
    "MessageResponse",
    "MessageStatus",
    "MessageType",
    "ContactResponse",
    "InstanceStatus",
    "WebhookPayload",
    "MessageStatusUpdate",
    # Services
    "WhatsAppMessageService",
    "MessageQueue",
    # Routers
    "whatsapp_router",
]
