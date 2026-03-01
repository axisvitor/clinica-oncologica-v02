"""
Phone number validation and formatting utilities.

Phone functions delegate to canonical: app.schemas.validators.phone.
"""

import logging

from app.schemas.validators.phone import (  # noqa: F401
    format_phone_for_whatsapp as format_phone_number,
)

logger = logging.getLogger(__name__)

__all__ = ["format_phone_number", "validate_message_content"]


def validate_message_content(message: str) -> None:
    """
    Validate message content is not empty.

    Args:
        message: Message text to validate

    Raises:
        ValueError: If message is empty or invalid
    """
    if not message or not message.strip():
        raise ValueError(
            f"Cannot send empty message. "
            f"Message parameter is required and must be non-empty. "
            f"Received: {repr(message)}"
        )
