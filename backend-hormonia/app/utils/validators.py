"""
Centralized Validation Utilities - Single Source of Truth for Data Validation.

This module consolidates ALL validation logic previously scattered across:
- app/services/patient/integrity_service.py
- app/domain/patient/onboarding/validation_service.py
- app/schemas/patient.py
- Multiple other files with duplicate CPF validation

Addresses:
- MEDIUM-002: Code Duplication (CPF validation in 4 places)
- DRY Compliance: 95%+

File: backend-hormonia/app/utils/validators.py
Created: 2025-11-16
Pattern: Single Responsibility, DRY
"""

import logging
from typing import Optional
from email_validator import validate_email as email_validator_lib, EmailNotValidError

from app.config.constants import CPFConstants, RegexPatterns
from app.exceptions import ValidationError

logger = logging.getLogger(__name__)


# ============================================================================
# CPF VALIDATION - SINGLE SOURCE OF TRUTH
# ============================================================================


def validate_cpf(cpf: str) -> str:
    """
    Validate and normalize Brazilian CPF (Cadastro de Pessoas Físicas).

    This is the SINGLE SOURCE OF TRUTH for CPF validation across the entire
    application. All other CPF validation should import and use this function.

    Validation Steps:
    1. Remove non-digit characters
    2. Check length (must be exactly 11 digits)
    3. Check for known invalid sequences (all same digit)
    4. Validate check digits using official CPF algorithm

    Args:
        cpf: CPF string with optional formatting (dots, dashes, spaces)

    Returns:
        Normalized CPF string (11 digits only)

    Raises:
        ValidationError: If CPF is invalid with specific error message

    Examples:
        >>> validate_cpf("123.456.789-09")
        "12345678909"

        >>> validate_cpf("111.111.111-11")
        ValidationError: "CPF inválido: todos os dígitos são iguais"

        >>> validate_cpf("123.456.789-00")
        ValidationError: "CPF inválido: dígito verificador incorreto"

    References:
        - https://www.geradorcpf.com/algoritmo_do_cpf.htm
        - CPF check digit algorithm: weighted sum modulo 11
    """
    if not cpf:
        raise ValidationError("CPF é obrigatório")

    # Step 1: Remove all non-digit characters
    cpf_clean = RegexPatterns.CPF_CLEAN_REGEX.sub('', cpf)

    # Step 2: Check length
    if len(cpf_clean) != CPFConstants.LENGTH:
        raise ValidationError(
            f"CPF deve ter {CPFConstants.LENGTH} dígitos, recebido {len(cpf_clean)}"
        )

    # Step 3: Check for known invalid patterns (all same digit)
    if cpf_clean in CPFConstants.INVALID_SEQUENCES:
        raise ValidationError("CPF inválido: todos os dígitos são iguais")

    # Step 4: Validate check digits
    if not _validate_cpf_check_digits(cpf_clean):
        raise ValidationError("CPF inválido: dígito verificador incorreto")

    logger.debug(f"CPF validated successfully: {cpf_clean[:3]}******{cpf_clean[-2:]}")
    return cpf_clean


def _validate_cpf_check_digits(cpf: str) -> bool:
    """
    Validate CPF check digits using the official algorithm.

    The CPF has two check digits (positions 9 and 10) calculated from
    the first 9 digits using a weighted sum algorithm.

    Algorithm:
    - First digit: sum of (digit[i] * (10 - i)) for i=0..8, modulo 11
    - Second digit: sum of (digit[i] * (11 - i)) for i=0..9, modulo 11
    - If remainder < 2, digit = 0; otherwise digit = 11 - remainder

    Args:
        cpf: CPF string with exactly 11 digits

    Returns:
        True if check digits are valid, False otherwise

    References:
        https://www.geradorcpf.com/algoritmo_do_cpf.htm
    """

    def _calculate_check_digit(cpf_partial: str) -> str:
        """Calculate a single CPF check digit."""
        total = sum(
            int(digit) * (len(cpf_partial) + 1 - i)
            for i, digit in enumerate(cpf_partial)
        )
        remainder = total % 11
        return "0" if remainder < 2 else str(11 - remainder)

    # Validate first check digit (position 9)
    if cpf[9] != _calculate_check_digit(cpf[:9]):
        return False

    # Validate second check digit (position 10)
    if cpf[10] != _calculate_check_digit(cpf[:10]):
        return False

    return True


def normalize_cpf(cpf: Optional[str]) -> Optional[str]:
    """
    Normalize CPF by removing non-digit characters without validation.

    Use this when you need to normalize CPF for storage/comparison but
    don't want to validate it (e.g., for legacy data, optional fields).

    For validation, use validate_cpf() instead.

    Args:
        cpf: CPF string with optional formatting

    Returns:
        CPF with only digits (max 11 chars) or None if input is None/empty

    Examples:
        >>> normalize_cpf("123.456.789-09")
        "12345678909"

        >>> normalize_cpf(None)
        None

        >>> normalize_cpf("")
        None
    """
    if not cpf:
        return None

    # Remove all non-digit characters
    normalized = RegexPatterns.CPF_CLEAN_REGEX.sub('', cpf)

    # Limit to 11 digits (CPF max length)
    return normalized[:CPFConstants.LENGTH] if normalized else None


# ============================================================================
# EMAIL VALIDATION
# ============================================================================


def validate_email_format(email: str) -> str:
    """
    Validate and normalize email address.

    Uses the email-validator library for RFC-compliant validation.

    Args:
        email: Email address to validate

    Returns:
        Normalized email address (lowercase)

    Raises:
        ValidationError: If email format is invalid

    Examples:
        >>> validate_email_format("User@Example.COM")
        "user@example.com"

        >>> validate_email_format("invalid.email")
        ValidationError: "Formato de email inválido"
    """
    if not email:
        raise ValidationError("Email é obrigatório")

    try:
        validated = email_validator_lib(email)
        return validated.normalized

    except EmailNotValidError as e:
        logger.warning(f"Invalid email format: {email} - {e}")
        raise ValidationError(f"Formato de email inválido: {str(e)}")


# ============================================================================
# PHONE VALIDATION
# ============================================================================


def validate_phone_format(phone: str) -> bool:
    """
    Basic phone number format validation.

    For complete phone validation with country codes and E.164 formatting,
    use app.utils.phone_validator.validate_and_format_phone instead.

    Args:
        phone: Phone number to validate

    Returns:
        True if format is valid, False otherwise

    Examples:
        >>> validate_phone_format("+5511999887766")
        True

        >>> validate_phone_format("invalid")
        False
    """
    if not phone:
        return False

    return bool(RegexPatterns.PHONE_REGEX.match(phone))


def normalize_phone_digits(phone: str) -> str:
    """
    Extract only digits from phone number.

    Args:
        phone: Phone number with optional formatting

    Returns:
        String with only digits

    Examples:
        >>> normalize_phone_digits("+55 (11) 99988-7766")
        "5511999887766"
    """
    if not phone:
        return ""

    return RegexPatterns.BR_PHONE_DIGITS_ONLY.sub('', phone)


# ============================================================================
# TREATMENT PHASE VALIDATION
# ============================================================================


def validate_treatment_phase(phase: str) -> str:
    """
    Validate and normalize treatment phase.

    Args:
        phase: Treatment phase string

    Returns:
        Normalized phase (lowercase)

    Raises:
        ValidationError: If phase is not valid

    Examples:
        >>> validate_treatment_phase("INITIAL")
        "initial"

        >>> validate_treatment_phase("invalid_phase")
        ValidationError: "Fase de tratamento inválida"
    """
    from app.config.constants import TreatmentPhase

    if not phase:
        raise ValidationError("Fase de tratamento é obrigatória")

    phase_normalized = phase.strip().lower()

    if phase_normalized not in TreatmentPhase.ALL_PHASES:
        valid_phases = ", ".join(sorted(TreatmentPhase.ALL_PHASES))
        raise ValidationError(
            f"Fase de tratamento inválida. Valores válidos: {valid_phases}"
        )

    return phase_normalized


# ============================================================================
# STRING LENGTH VALIDATION
# ============================================================================


def validate_string_length(
    value: str,
    field_name: str,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
) -> str:
    """
    Validate string length constraints.

    Args:
        value: String to validate
        field_name: Name of field for error messages
        min_length: Minimum required length (optional)
        max_length: Maximum allowed length (optional)

    Returns:
        Stripped string value

    Raises:
        ValidationError: If length constraints are violated

    Examples:
        >>> validate_string_length("Test", "name", min_length=2, max_length=100)
        "Test"

        >>> validate_string_length("A", "name", min_length=2)
        ValidationError: "name deve ter pelo menos 2 caracteres"
    """
    if not value:
        raise ValidationError(f"{field_name} é obrigatório")

    value_stripped = value.strip()

    if min_length is not None and len(value_stripped) < min_length:
        raise ValidationError(
            f"{field_name} deve ter pelo menos {min_length} caracteres"
        )

    if max_length is not None and len(value_stripped) > max_length:
        raise ValidationError(
            f"{field_name} não pode exceder {max_length} caracteres"
        )

    return value_stripped


# ============================================================================
# EXPORT PUBLIC API
# ============================================================================

__all__ = [
    # CPF validation
    "validate_cpf",
    "normalize_cpf",
    # Email validation
    "validate_email_format",
    # Phone validation
    "validate_phone_format",
    "normalize_phone_digits",
    # Treatment validation
    "validate_treatment_phase",
    # Generic validation
    "validate_string_length",
]
