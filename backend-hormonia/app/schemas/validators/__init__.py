"""
Shared validators for schema validation across API versions.

This module provides consistent validation logic for common fields
like phone numbers, CPF, email, etc.
"""

from .phone import (
    validate_phone_e164,
    validate_phone_br,
    normalize_phone,
    PhoneValidationMode,
)

__all__ = [
    "validate_phone_e164",
    "validate_phone_br",
    "normalize_phone",
    "PhoneValidationMode",
]
