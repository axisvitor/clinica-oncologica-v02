"""
Webhook processing module for Evolution API integration.

This module provides a modular architecture for processing WhatsApp webhooks,
decomposed from the original monolithic webhook_processor.py (1,291 lines).

Modules:
- handlers: Message, status, and connection webhook handlers
- utils: Phone normalization and message extraction utilities
- persistence: Webhook event storage and retry logic
"""

from app.services.webhook.handlers import (
    MessageWebhookHandler,
    StatusWebhookHandler,
    ConnectionWebhookHandler,
)
from app.services.webhook.persistence import WebhookEventStore

__all__ = [
    "MessageWebhookHandler",
    "StatusWebhookHandler",
    "ConnectionWebhookHandler",
    "WebhookEventStore",
]
