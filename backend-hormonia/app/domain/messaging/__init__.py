"""
Domain layer for messaging and communication.

This package contains all messaging-related business logic organized by subdomain:
- core: Base message services and factories
- scheduling: Message scheduling and queueing
- delivery: Message sending and delivery management
- whatsapp: WhatsApp integration

Consolidated Services (from /app/services migration):
- MessageService (core/)
- WhatsAppService (whatsapp/)
- MessageScheduler (scheduling/)
- MessageSender (delivery/)
- IdempotentMessageSender (delivery/)
"""

# Core messaging
from .core.message_service import MessageService
from .core.message_base import MessageService as MessageBaseService
from .core.message_factory import MessageFactory

# Scheduling
from .scheduling.message_scheduler import MessageScheduler

# Delivery
from .delivery import MessageSender
from .delivery.idempotent_sender import IdempotentMessageSender

# WhatsApp integration
from .whatsapp.whatsapp_service import WhatsAppService

__all__ = [
    # Core
    "MessageService",
    "MessageBaseService",
    "MessageFactory",

    # Scheduling
    "MessageScheduler",

    # Delivery
    "MessageSender",
    "IdempotentMessageSender",

    # WhatsApp
    "WhatsAppService",
]
