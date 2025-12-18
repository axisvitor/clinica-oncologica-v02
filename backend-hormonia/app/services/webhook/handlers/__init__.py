"""
Webhook handlers for different event types.

Handlers:
- MessageWebhookHandler: Processes incoming WhatsApp messages
- StatusWebhookHandler: Processes message delivery status updates
- ConnectionWebhookHandler: Processes connection and QR code events
"""

from app.services.webhook.handlers.message_handler import MessageWebhookHandler
from app.services.webhook.handlers.status_handler import StatusWebhookHandler
from app.services.webhook.handlers.connection_handler import ConnectionWebhookHandler

__all__ = [
    "MessageWebhookHandler",
    "StatusWebhookHandler",
    "ConnectionWebhookHandler",
]
