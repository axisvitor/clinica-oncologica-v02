"""
Phone number validation utilities for Brazilian and E.164 formats.

This module provides standardized phone validation across all API versions
to ensure consistency and prevent bugs from format mismatches.

Supported Formats:
    - E.164: International format with country code (+5511987654321)
    - Brazilian: Local format with DDD (11987654321 or (11) 98765-4321)

Examples:
    >>> validate_phone_e164("+5511987654321")
    '+5511987654321'

    >>> validate_phone_br("11987654321")
    '11987654321'

    >>> normalize_phone("(11) 98765-4321", mode=PhoneValidationMode.BR_TO_E164)
    '+5511987654321'

References:
    - E.164: ITU-T Recommendation E.164
    - Brazilian phone format: ANATEL regulations
"""

import re
from enum import Enum
from typing import Optional


class PhoneValidationMode(str, Enum):
    """Phone validation modes for different use cases."""

    E164_STRICT = "e164_strict"  # Requires E.164 format (+ prefix)
    BR_FLEXIBLE = "br_flexible"  # Accepts Brazilian format with/without formatting
    HYBRID = "hybrid"  # Accepts both E.164 and Brazilian formats
    BR_TO_E164 = "br_to_e164"  # Converts Brazilian format to E.164


def validate_phone_e164(phone: str, allow_none: bool = False) -> Optional[str]:
    """
    Validate phone number in strict E.164 format.

    E.164 format requirements:
        - Must start with + followed by country code
        - Contains only digits after the +
        - Total length: 10-15 digits (after removing +)
        - No spaces, dashes, or parentheses

    Args:
        phone: Phone number to validate
        allow_none: If True, returns None for empty/None values

    Returns:
        Normalized E.164 phone number (e.g., '+5511987654321')

    Raises:
        ValueError: If phone number doesn't match E.164 format

    Examples:
        >>> validate_phone_e164("+5511987654321")
        '+5511987654321'

        >>> validate_phone_e164("+55 11 98765-4321")  # Will normalize
        '+5511987654321'

        >>> validate_phone_e164("11987654321")  # Raises ValueError
        ValueError: Phone number must start with country code (+)
    """
    if not phone:
        if allow_none:
            return None
        raise ValueError("Phone number is required")

    # Remove common formatting characters for validation
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)

    # Check if starts with +
    if not cleaned.startswith("+"):
        raise ValueError("Phone number must start with country code (+)")

    # Extract digits after +
    digits_only = cleaned[1:]

    # Validate digits only
    if not digits_only.isdigit():
        raise ValueError("Phone number must contain only + and digits")

    # Validate length (E.164 allows 10-15 digits)
    if len(digits_only) < 10 or len(digits_only) > 15:
        raise ValueError(
            f"Phone number must have 10-15 digits, got {len(digits_only)}"
        )

    # Return normalized format
    return cleaned


def validate_phone_br(phone: str, allow_none: bool = False) -> Optional[str]:
    """
    Validate phone number in Brazilian format (with or without formatting).

    Brazilian phone format:
        - DDD (2 digits) + Number (8-9 digits)
        - Total: 10-11 digits
        - Accepts formats: 11987654321, (11) 98765-4321, 11 98765-4321

    Args:
        phone: Phone number to validate
        allow_none: If True, returns None for empty/None values

    Returns:
        Phone number with original formatting preserved

    Raises:
        ValueError: If phone number doesn't match Brazilian format

    Examples:
        >>> validate_phone_br("11987654321")
        '11987654321'

        >>> validate_phone_br("(11) 98765-4321")
        '(11) 98765-4321'

        >>> validate_phone_br("+5511987654321")  # Raises ValueError
        ValueError: Brazilian phone format should not include country code
    """
    if not phone:
        if allow_none:
            return None
        raise ValueError("Phone number is required")

    # Remove common formatting characters for validation
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)

    # Check it doesn't start with + (should be local format)
    if cleaned.startswith("+"):
        raise ValueError("Brazilian phone format should not include country code")

    # Extract only digits
    digits_only = re.sub(r"\D", "", phone)

    # Validate length (Brazilian DDD + number = 10 or 11 digits)
    if len(digits_only) < 10 or len(digits_only) > 11:
        raise ValueError(
            f"Brazilian phone must have 10-11 digits (DDD + number), got {len(digits_only)}"
        )

    # Validate DDD (area code) is valid (11-99)
    ddd = int(digits_only[:2])
    if ddd < 11 or ddd > 99:
        raise ValueError(f"Invalid DDD (area code): {ddd}. Must be between 11-99")

    # Return original format to preserve user formatting
    return phone


def normalize_phone(
    phone: str,
    mode: PhoneValidationMode = PhoneValidationMode.HYBRID,
    allow_none: bool = False
) -> Optional[str]:
    """
    Normalize phone number according to specified mode.

    This is the main validation function that should be used in schemas.
    It provides flexible validation and normalization based on the mode.

    Args:
        phone: Phone number to normalize
        mode: Validation mode (E164_STRICT, BR_FLEXIBLE, HYBRID, BR_TO_E164)
        allow_none: If True, returns None for empty/None values

    Returns:
        Normalized phone number according to mode

    Raises:
        ValueError: If phone number is invalid for the specified mode

    Examples:
        >>> normalize_phone("+5511987654321", PhoneValidationMode.E164_STRICT)
        '+5511987654321'

        >>> normalize_phone("11987654321", PhoneValidationMode.BR_FLEXIBLE)
        '11987654321'

        >>> normalize_phone("11987654321", PhoneValidationMode.HYBRID)
        '11987654321'

        >>> normalize_phone("(11) 98765-4321", PhoneValidationMode.BR_TO_E164)
        '+5511987654321'
    """
    if not phone:
        if allow_none:
            return None
        raise ValueError("Phone number is required")

    # Remove common formatting for processing
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)

    if mode == PhoneValidationMode.E164_STRICT:
        # Strict E.164 validation
        return validate_phone_e164(phone, allow_none=allow_none)

    elif mode == PhoneValidationMode.BR_FLEXIBLE:
        # Brazilian format only
        return validate_phone_br(phone, allow_none=allow_none)

    elif mode == PhoneValidationMode.BR_TO_E164:
        # Convert Brazilian to E.164
        if cleaned.startswith("+"):
            # Already in E.164, validate and return
            return validate_phone_e164(phone, allow_none=allow_none)
        else:
            # Brazilian format, convert to E.164
            digits_only = re.sub(r"\D", "", phone)

            # Validate Brazilian format first
            if len(digits_only) < 10 or len(digits_only) > 11:
                raise ValueError(
                    f"Brazilian phone must have 10-11 digits, got {len(digits_only)}"
                )

            # Convert to E.164 with +55 (Brazil country code)
            e164_phone = f"+55{digits_only}"

            # Validate the resulting E.164 format
            return validate_phone_e164(e164_phone, allow_none=allow_none)

    elif mode == PhoneValidationMode.HYBRID:
        # Accept both E.164 and Brazilian formats
        if cleaned.startswith("+"):
            # E.164 format
            return validate_phone_e164(phone, allow_none=allow_none)
        else:
            # Brazilian format
            return validate_phone_br(phone, allow_none=allow_none)

    else:
        raise ValueError(f"Invalid validation mode: {mode}")


def format_phone_display(phone: str) -> str:
    """
    Format phone number for display (Brazilian format with mask).

    Args:
        phone: Phone number in any format

    Returns:
        Formatted phone for display: (11) 98765-4321

    Examples:
        >>> format_phone_display("+5511987654321")
        '(11) 98765-4321'

        >>> format_phone_display("11987654321")
        '(11) 98765-4321'
    """
    # Extract only digits
    digits_only = re.sub(r"\D", "", phone)

    # Remove country code if present
    if digits_only.startswith("55") and len(digits_only) > 11:
        digits_only = digits_only[2:]  # Remove +55

    # Brazilian phone: DDD (2) + Number (8-9 digits)
    if len(digits_only) == 11:  # Mobile with 9 digits
        return f"({digits_only[:2]}) {digits_only[2:7]}-{digits_only[7:]}"
    elif len(digits_only) == 10:  # Landline with 8 digits
        return f"({digits_only[:2]}) {digits_only[2:6]}-{digits_only[6:]}"
    else:
        # Return original if can't format
        return phone
