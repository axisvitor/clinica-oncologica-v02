"""
Evolution API integration module.
WhatsApp Business integration for Hormonia system.
"""

from .client import EvolutionClient, get_evolution_client, close_evolution_client
from .models import (
    MessageType,
    TextMessage,
    ButtonMessage,
    ListMessage,
    MediaMessage,
    WebhookEvent,
    EvolutionAPIError,
)

__all__ = [
    # Main client
    "EvolutionClient",
    "get_evolution_client",
    "close_evolution_client",
    # Enums
    "MessageType",
    # Message models
    "TextMessage",
    "ButtonMessage",
    "ListMessage",
    "MediaMessage",
    # Webhook
    "WebhookEvent",
    # Exceptions
    "EvolutionAPIError",
]
