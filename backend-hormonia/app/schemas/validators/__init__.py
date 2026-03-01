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
from .cpf import (
    validate_cpf,
    is_valid_cpf,
    normalize_cpf,
    format_cpf,
    has_valid_cpf_characters,
    CPFValidationError,
)

__all__ = [
    "validate_phone_e164",
    "validate_phone_br",
    "normalize_phone",
    "PhoneValidationMode",
    "validate_cpf",
    "is_valid_cpf",
    "normalize_cpf",
    "format_cpf",
    "has_valid_cpf_characters",
    "CPFValidationError",
]
