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

from .services.evolution_client import EvolutionAPIClient, RateLimiter
from .services.message_service import WhatsAppMessageService, MessageQueue
from .services.mock_evolution import MockEvolutionAPIClient, create_evolution_client

from .api.routes import router as whatsapp_router
from .api.webhooks import router as webhook_router

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
    "EvolutionAPIClient",
    "RateLimiter",
    "WhatsAppMessageService",
    "MessageQueue",
    "MockEvolutionAPIClient",
    "create_evolution_client",
    # Routers
    "whatsapp_router",
    "webhook_router",
]
