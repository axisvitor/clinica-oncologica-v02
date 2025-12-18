"""
Phone number validation and formatting utilities.
"""

import logging

logger = logging.getLogger(__name__)


def format_phone_number(phone_number: str) -> str:
    """
    Format phone number for Evolution API.

    Args:
        phone_number: Raw phone number string

    Returns:
        Formatted phone number with country code
    """
    # Remove any non-digit characters
    clean_number = "".join(filter(str.isdigit, phone_number))

    # Ensure Brazilian format (55 + area code + number)
    if not clean_number.startswith("55"):
        if len(clean_number) == 11:  # Area code + 9-digit mobile
            clean_number = "55" + clean_number
        elif len(clean_number) == 10:  # Area code + 8-digit landline
            clean_number = "55" + clean_number

    return clean_number


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
