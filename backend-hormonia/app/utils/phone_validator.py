"""
Phone Number Validation Utilities.

Provides robust E.164 phone number validation and normalization
using the phonenumbers library.
"""

import re
import logging
from typing import Optional, Tuple

try:
    import phonenumbers
    from phonenumbers import NumberParseException

    PHONENUMBERS_AVAILABLE = True
except ImportError:
    PHONENUMBERS_AVAILABLE = False
    logging.warning(
        "phonenumbers library not available. Phone validation will use regex fallback."
    )

logger = logging.getLogger(__name__)


class PhoneValidationError(ValueError):
    """Raised when phone number validation fails."""

    pass


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalize phone number by removing non-digit characters.

    Args:
        phone: Phone number string (may contain formatting)

    Returns:
        Normalized phone with only digits, or None if input is None/empty

    Example:
        >>> normalize_phone("(11) 98765-4321")
        "11987654321"
        >>> normalize_phone("+55 11 98765-4321")
        "5511987654321"
    """
    if not phone:
        return None

    # Remove all non-digit characters except leading '+'
    if phone.startswith("+"):
        return "+" + re.sub(r"\D", "", phone[1:])
    else:
        return re.sub(r"\D", "", phone)


def validate_and_format_phone(
    phone: str, default_region: str = "BR", strict: bool = True
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate and format phone number to E.164 format.

    Args:
        phone: Phone number to validate
        default_region: Default country code (ISO 3166-1 alpha-2)
        strict: If True, raise exception on invalid phone. If False, return error message.

    Returns:
        Tuple of (is_valid, formatted_phone, error_message)

    Examples:
        >>> validate_and_format_phone("11987654321", "BR")
        (True, "+5511987654321", None)

        >>> validate_and_format_phone("+5511987654321", "BR")
        (True, "+5511987654321", None)

        >>> validate_and_format_phone("123", "BR")
        (False, None, "Invalid phone number format")
    """
    if not phone:
        error_msg = "Phone number is required"
        if strict:
            raise PhoneValidationError(error_msg)
        return False, None, error_msg

    # Normalize first
    normalized = normalize_phone(phone)

    if not normalized:
        error_msg = "Phone number cannot be empty after normalization"
        if strict:
            raise PhoneValidationError(error_msg)
        return False, None, error_msg

    # Use phonenumbers library if available
    if PHONENUMBERS_AVAILABLE:
        try:
            # Parse phone number
            parsed = phonenumbers.parse(normalized, default_region)

            # Validate
            if not phonenumbers.is_valid_number(parsed):
                error_msg = f"Invalid phone number: {phone}"
                if strict:
                    raise PhoneValidationError(error_msg)
                return False, None, error_msg

            # Format to E.164
            e164 = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )

            logger.debug(f"Phone validated: {phone} -> {e164}")
            return True, e164, None

        except NumberParseException as e:
            error_msg = f"Failed to parse phone number: {phone} - {str(e)}"
            logger.warning(error_msg)
            if strict:
                raise PhoneValidationError(error_msg)
            return False, None, error_msg

    else:
        # Fallback: Basic regex validation for Brazilian phones
        return _validate_phone_regex_fallback(normalized, strict)


def _validate_phone_regex_fallback(
    normalized: str, strict: bool = True
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Fallback phone validation using regex (when phonenumbers not available).

    Validates Brazilian phone numbers in E.164 format.

    Args:
        normalized: Normalized phone number
        strict: If True, raise exception on invalid phone

    Returns:
        Tuple of (is_valid, formatted_phone, error_message)
    """
    # E.164 format: +[country code][area code][number]
    # Brazilian format: +55 [2 digits area] [8-9 digits number]
    # Examples: +5511987654321, +551133334444

    # Pattern for Brazilian E.164
    pattern = r"^\+55\d{10,11}$"

    if normalized.startswith("+"):
        # Already has country code
        if re.match(pattern, normalized):
            logger.debug(f"Phone validated (regex): {normalized}")
            return True, normalized, None
        else:
            error_msg = f"Invalid Brazilian phone format (E.164): {normalized}"
            if strict:
                raise PhoneValidationError(error_msg)
            return False, None, error_msg
    else:
        # No country code - add +55 (Brazil)
        if len(normalized) in [10, 11]:  # Brazilian phone without country code
            e164 = f"+55{normalized}"
            if re.match(pattern, e164):
                logger.debug(f"Phone validated (regex): {normalized} -> {e164}")
                return True, e164, None

        error_msg = f"Invalid phone format: {normalized}. Expected 10-11 digits or E.164 format."
        if strict:
            raise PhoneValidationError(error_msg)
        return False, None, error_msg


def is_valid_e164(phone: str) -> bool:
    """
    Quick check if phone is in valid E.164 format.

    Args:
        phone: Phone number to check

    Returns:
        True if valid E.164 format, False otherwise

    Example:
        >>> is_valid_e164("+5511987654321")
        True
        >>> is_valid_e164("11987654321")
        False
    """
    if not phone:
        return False

    # E.164 format: starts with '+', followed by 1-15 digits
    pattern = r"^\+[1-9]\d{1,14}$"
    return bool(re.match(pattern, phone))


def format_phone_display(phone: str, format_type: str = "national") -> str:
    """
    Format phone number for display (human-readable).

    Args:
        phone: Phone number in E.164 format
        format_type: "national" or "international"

    Returns:
        Formatted phone number

    Examples:
        >>> format_phone_display("+5511987654321", "national")
        "(11) 98765-4321"

        >>> format_phone_display("+5511987654321", "international")
        "+55 11 98765-4321"
    """
    if not phone:
        return ""

    if PHONENUMBERS_AVAILABLE:
        try:
            parsed = phonenumbers.parse(phone, None)

            if format_type == "national":
                return phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.NATIONAL
                )
            else:
                return phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
                )

        except NumberParseException as e:
            logger.debug(f"Failed to parse phone number '{phone}': {e}")

    # Fallback: Simple Brazilian formatting
    if phone.startswith("+55"):
        digits = phone[3:]  # Remove +55
        if len(digits) == 11:  # Mobile: (11) 98765-4321
            return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
        elif len(digits) == 10:  # Landline: (11) 3333-4444
            return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"

    return phone
