"""
CPF validation utilities for Brazilian CPF numbers.

Canonical module -- every CPF helper in the project should be imported from
``app.schemas.validators.cpf``.
"""

from __future__ import annotations

import re
from typing import Optional

_NON_DIGIT_RE = re.compile(r"\D+")
_VALID_CPF_CHARS_RE = re.compile(r"^[0-9.\-]+$")
_INVALID_REPEATED_CPF = {f"{digit}" * 11 for digit in range(10)}


class CPFValidationError(ValueError):
    """Raised when CPF validation fails."""

    pass


def normalize_cpf(cpf: Optional[str], allow_none: bool = False) -> Optional[str]:
    """Normalize CPF by removing non-digit characters."""
    if cpf is None:
        if allow_none:
            return None
        raise CPFValidationError("CPF is required")

    value = str(cpf).strip()
    if not value:
        if allow_none:
            return None
        raise CPFValidationError("CPF is required")

    return _NON_DIGIT_RE.sub("", value)


def has_valid_cpf_characters(cpf: str) -> bool:
    """Return True when CPF contains only digits, dots, and dashes."""
    if cpf is None:
        return False
    value = str(cpf).strip()
    if not value:
        return False
    return bool(_VALID_CPF_CHARS_RE.fullmatch(value))


def calculate_cpf_check_digit(cpf_partial: str) -> str:
    """Calculate one CPF check digit for the provided partial CPF."""
    total = sum(
        int(digit) * weight
        for digit, weight in zip(cpf_partial, range(len(cpf_partial) + 1, 1, -1))
    )
    remainder = total % 11
    return "0" if remainder < 2 else str(11 - remainder)


def is_valid_cpf(cpf: Optional[str], allow_none: bool = True) -> bool:
    """
    Validate CPF check digits and structure.

    Returns:
        True when CPF is valid.
        When allow_none=True, empty values are considered valid.
    """
    normalized = normalize_cpf(cpf, allow_none=allow_none)
    if normalized is None:
        return True

    if len(normalized) != 11:
        return False

    if normalized in _INVALID_REPEATED_CPF:
        return False

    first_digit = calculate_cpf_check_digit(normalized[:9])
    second_digit = calculate_cpf_check_digit(normalized[:10])
    return normalized[9] == first_digit and normalized[10] == second_digit


def validate_cpf(cpf: Optional[str], allow_none: bool = False) -> Optional[str]:
    """
    Validate CPF and return normalized digits-only value.

    Raises:
        CPFValidationError: If CPF is invalid.
    """
    normalized = normalize_cpf(cpf, allow_none=allow_none)
    if normalized is None:
        return None

    if len(normalized) != 11:
        raise CPFValidationError(f"CPF must have 11 digits, got {len(normalized)}")

    if normalized in _INVALID_REPEATED_CPF:
        raise CPFValidationError("Invalid CPF: all digits are the same")

    if not is_valid_cpf(normalized, allow_none=False):
        raise CPFValidationError("Invalid CPF checksum")

    return normalized


def format_cpf(cpf: str) -> str:
    """Format CPF as XXX.XXX.XXX-XX."""
    normalized = normalize_cpf(cpf, allow_none=False)
    if normalized is None or len(normalized) != 11:
        raise CPFValidationError(
            f"CPF must have 11 digits, got {len(normalized or '')}",
        )
    return f"{normalized[:3]}.{normalized[3:6]}.{normalized[6:9]}-{normalized[9:]}"


def sanitize_persisted_cpf(value: object) -> Optional[str]:
    """
    Sanitize persisted CPF values for response serialization.

    Invalid persisted CPF values are returned as ``None``.
    """
    if not value:
        return None

    cpf_value = normalize_cpf(str(value), allow_none=True)
    if not cpf_value or not is_valid_cpf(cpf_value, allow_none=False):
        return None
    return cpf_value
