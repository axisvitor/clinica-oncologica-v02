"""Message delivery services."""
from .idempotent_sender import IdempotentMessageSender

# Alias for backward compatibility
MessageSender = IdempotentMessageSender

__all__ = ["IdempotentMessageSender", "MessageSender"]
