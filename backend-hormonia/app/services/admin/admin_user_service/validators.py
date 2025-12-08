"""
Validation utilities for user administration.

Contains email validation, password generation, and other validation functions.
"""
import re
import secrets
import string
import logging
from typing import Dict, List

from app.utils.security import validate_password_strength
from .schemas import EmailValidationRequest, EmailValidationResult

logger = logging.getLogger(__name__)


def validate_email_format(email: str) -> str:
    """
    Enhanced email validation and normalization.

    Args:
        email: Email address to validate

    Returns:
        Normalized email address

    Raises:
        ValueError: If email format is invalid
    """
    try:
        # Basic regex validation for email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValueError("Invalid email format")

        # Normalize email (lowercase domain)
        local, domain = email.split('@')
        normalized_email = f"{local}@{domain.lower()}"
        return normalized_email
    except Exception as e:
        raise ValueError(f"Invalid email format: {str(e)}")


def validate_full_name(name: str) -> str:
    """
    Validate full name format.

    Args:
        name: Full name to validate

    Returns:
        Validated and normalized name

    Raises:
        ValueError: If name format is invalid
    """
    if name is not None:
        # Remove extra whitespace
        name = ' '.join(name.split())
        # Check for valid characters (letters, spaces, hyphens, apostrophes, accented characters)
        if not re.match(r"^[a-zA-Z\s\-\'\u00C0-\u017F]+$", name):
            raise ValueError("Full name can only contain letters, spaces, hyphens, and apostrophes")
    return name


def validate_password(password: str) -> None:
    """
    Validate password strength.

    Args:
        password: Password to validate

    Raises:
        ValueError: If password doesn't meet strength requirements
    """
    validation_result = validate_password_strength(password)
    if not validation_result['is_valid']:
        raise ValueError(f"Password validation failed: {'; '.join(validation_result['issues'])}")


async def validate_email_advanced(email_request: EmailValidationRequest) -> EmailValidationResult:
    """
    Perform advanced email validation with domain checking.

    Args:
        email_request: Email validation request

    Returns:
        Email validation result with issues and suggestions
    """
    issues = []
    suggestions = []

    try:
        # Basic format validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email_request.email):
            issues.append("Invalid email format")

        # Normalize email
        local, domain = email_request.email.split('@')
        normalized_email = f"{local}@{domain.lower()}"

        # Check for common typos in popular domains
        domain_suggestions = {
            'gmail.com': ['gmai.com', 'gmial.com', 'gmail.co'],
            'yahoo.com': ['yaho.com', 'yahoo.co'],
            'hotmail.com': ['hotmai.com', 'hotmal.com'],
            'outlook.com': ['outloo.com', 'outlook.co']
        }

        for correct_domain, typos in domain_suggestions.items():
            if domain in typos:
                suggestions.append(f"Did you mean {local}@{correct_domain}?")

        # Check for disposable email domains (basic list)
        disposable_domains = {
            '10minutemail.com', 'tempmail.org', 'guerrillamail.com',
            'mailinator.com', 'throwaway.email', 'temp-mail.org'
        }
        if domain in disposable_domains:
            issues.append("Disposable email addresses are not allowed")

        # Check email length limits
        if len(local) > 64:
            issues.append("Local part of email is too long (max 64 characters)")
        if len(domain) > 253:
            issues.append("Domain part of email is too long (max 253 characters)")

        is_valid = len(issues) == 0

        return EmailValidationResult(
            email=email_request.email,
            is_valid=is_valid,
            normalized_email=normalized_email,
            issues=issues,
            suggestions=suggestions
        )

    except Exception as e:
        logger.error(f"Email validation error: {e}")
        return EmailValidationResult(
            email=email_request.email,
            is_valid=False,
            normalized_email=email_request.email,
            issues=[f"Validation error: {str(e)}"],
            suggestions=[]
        )


def generate_temporary_password(length: int = 12) -> str:
    """
    Generate a secure temporary password.

    Args:
        length: Length of password (minimum 8)

    Returns:
        Secure random password
    """
    # Use a mix of uppercase, lowercase, numbers, and symbols
    characters = string.ascii_letters + string.digits + "!@#$%^&*"

    # Ensure at least one character from each category
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*")
    ]

    # Fill the rest randomly
    for _ in range(length - 4):
        password.append(secrets.choice(characters))

    # Shuffle the password
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)
