"""Centralized regex patterns for validation.

This module provides a single source of truth for all regex patterns used
throughout the application, improving maintainability and consistency.
"""
import re
from typing import Optional


# ============================================================================
# CPF Patterns
# ============================================================================

CPF_CLEAN = re.compile(r'^\d{11}$')
CPF_FORMATTED = re.compile(r'^\d{3}\.\d{3}\.\d{3}-\d{2}$')
CPF_ANY = re.compile(r'^(\d{3}\.?\d{3}\.?\d{3}-?\d{2})$')


# ============================================================================
# Phone Patterns
# ============================================================================

PHONE_BRAZILIAN = re.compile(r'^\+?55\s?\(?\d{2}\)?\s?\d{4,5}-?\d{4}$')
PHONE_INTERNATIONAL = re.compile(r'^\+?[1-9]\d{1,14}$')


# ============================================================================
# Email Pattern
# ============================================================================

EMAIL = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)


# ============================================================================
# Date Patterns
# ============================================================================

DATE_BR = re.compile(r'^\d{2}/\d{2}/\d{4}$')  # DD/MM/YYYY
DATE_ISO = re.compile(r'^\d{4}-\d{2}-\d{2}$')  # YYYY-MM-DD
DATETIME_ISO = re.compile(
    r'^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(\.\d{1,6})?([+-]\d{2}:\d{2}|Z)?$'
)


# ============================================================================
# Time Patterns
# ============================================================================

TIME_24H = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
TIME_12H = re.compile(r'^(0?\d|1[0-2]):([0-5]\d)\s?(AM|PM)$', re.IGNORECASE)


# ============================================================================
# Medical Patterns
# ============================================================================

CRM_PATTERN = re.compile(r'^CRM/[A-Z]{2}\s?\d{4,6}$')
CID_PATTERN = re.compile(r'^[A-Z]\d{2}(\.\d{1,2})?$')  # CID-10
CNES_PATTERN = re.compile(r'^\d{7}$')  # CNES (Cadastro Nacional de Estabelecimentos de Saúde)


# ============================================================================
# URL Patterns
# ============================================================================

URL_SIMPLE = re.compile(
    r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$'
)
URL_STRICT = re.compile(
    r'^https?://(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
)


# ============================================================================
# Sanitization Patterns
# ============================================================================

NON_DIGITS = re.compile(r'\D')  # Remove non-digits
NON_ALPHANUMERIC = re.compile(r'[^a-zA-Z0-9]')
WHITESPACE = re.compile(r'\s+')
SPECIAL_CHARS = re.compile(r'[<>{}[\]\\\/\'"`;]')  # Potentially dangerous chars


# ============================================================================
# Password Patterns
# ============================================================================

PASSWORD_WEAK = re.compile(r'^.{8,}$')  # At least 8 chars
PASSWORD_MEDIUM = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$')  # Mixed case + digit
PASSWORD_STRONG = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
)  # Mixed case + digit + special char


# ============================================================================
# Brazilian Document Patterns
# ============================================================================

RG_PATTERN = re.compile(r'^\d{1,2}\.?\d{3}\.?\d{3}-?[0-9X]$')
CNS_PATTERN = re.compile(r'^\d{15}$')  # Cartão Nacional de Saúde
CNPJ_PATTERN = re.compile(r'^\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}$')


# ============================================================================
# File Patterns
# ============================================================================

IMAGE_EXTENSION = re.compile(r'\.(jpg|jpeg|png|gif|bmp|webp)$', re.IGNORECASE)
DOCUMENT_EXTENSION = re.compile(r'\.(pdf|doc|docx|txt|rtf)$', re.IGNORECASE)
SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_\-\.]+$')


# ============================================================================
# Validation Helper Functions
# ============================================================================

def is_valid_cpf(cpf: str) -> bool:
    """
    Check if CPF matches pattern.

    Args:
        cpf: CPF string to validate

    Returns:
        True if CPF matches pattern, False otherwise

    Example:
        >>> is_valid_cpf("123.456.789-01")
        True
        >>> is_valid_cpf("12345678901")
        True
    """
    clean = NON_DIGITS.sub('', cpf)
    return bool(CPF_CLEAN.match(clean))


def is_valid_phone(phone: str) -> bool:
    """
    Check if phone matches pattern.

    Args:
        phone: Phone string to validate

    Returns:
        True if phone matches pattern, False otherwise

    Example:
        >>> is_valid_phone("+55 (11) 98765-4321")
        True
    """
    return bool(PHONE_BRAZILIAN.match(phone) or PHONE_INTERNATIONAL.match(phone))


def is_valid_email(email: str) -> bool:
    """
    Check if email matches pattern.

    Args:
        email: Email string to validate

    Returns:
        True if email matches pattern, False otherwise

    Example:
        >>> is_valid_email("user@example.com")
        True
    """
    return bool(EMAIL.match(email))


def is_valid_crm(crm: str) -> bool:
    """
    Check if CRM (medical license) matches pattern.

    Args:
        crm: CRM string to validate

    Returns:
        True if CRM matches pattern, False otherwise

    Example:
        >>> is_valid_crm("CRM/SP 123456")
        True
    """
    return bool(CRM_PATTERN.match(crm))


def is_valid_cid(cid: str) -> bool:
    """
    Check if CID-10 code matches pattern.

    Args:
        cid: CID-10 code to validate

    Returns:
        True if CID matches pattern, False otherwise

    Example:
        >>> is_valid_cid("C50.9")
        True
    """
    return bool(CID_PATTERN.match(cid))


def is_valid_url(url: str, strict: bool = False) -> bool:
    """
    Check if URL matches pattern.

    Args:
        url: URL string to validate
        strict: Use strict URL validation

    Returns:
        True if URL matches pattern, False otherwise

    Example:
        >>> is_valid_url("https://example.com")
        True
    """
    pattern = URL_STRICT if strict else URL_SIMPLE
    return bool(pattern.match(url))


def clean_cpf(cpf: str) -> str:
    """
    Remove formatting from CPF.

    Args:
        cpf: CPF string to clean

    Returns:
        CPF with only digits

    Example:
        >>> clean_cpf("123.456.789-01")
        "12345678901"
    """
    return NON_DIGITS.sub('', cpf)


def clean_phone(phone: str) -> str:
    """
    Remove formatting from phone number.

    Args:
        phone: Phone string to clean

    Returns:
        Phone with only digits

    Example:
        >>> clean_phone("+55 (11) 98765-4321")
        "5511987654321"
    """
    return NON_DIGITS.sub('', phone)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent security issues.

    Args:
        filename: Filename to sanitize

    Returns:
        Sanitized filename

    Example:
        >>> sanitize_filename("my file (1).pdf")
        "my_file_1.pdf"
    """
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    # Remove unsafe characters
    filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '', filename)
    return filename


def validate_password_strength(password: str) -> str:
    """
    Validate password strength.

    Args:
        password: Password to validate

    Returns:
        Password strength level: "weak", "medium", "strong", or "invalid"

    Example:
        >>> validate_password_strength("Abc123!@")
        "strong"
    """
    if len(password) < 8:
        return "invalid"
    elif PASSWORD_STRONG.match(password):
        return "strong"
    elif PASSWORD_MEDIUM.match(password):
        return "medium"
    elif PASSWORD_WEAK.match(password):
        return "weak"
    return "invalid"
