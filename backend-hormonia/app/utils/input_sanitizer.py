"""
Input Sanitization and Validation Utilities.

Provides utilities for sanitizing and validating user input to prevent
XSS, SQL injection, and other security vulnerabilities.
"""

import re
import bleach
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger(__name__)


class InputSanitizer:
    """Service for sanitizing and validating user input."""

    # Allowed HTML tags for rich text (very restrictive)
    ALLOWED_TAGS = ["p", "br", "strong", "em", "u"]
    ALLOWED_ATTRIBUTES = {}

    # Maximum lengths
    MAX_TEXT_LENGTH = 5000
    MAX_SINGLE_LINE_LENGTH = 500
    MAX_QUIZ_RESPONSE_LENGTH = 2000

    @classmethod
    def sanitize_html(cls, text: str, strict: bool = True) -> str:
        """
        Sanitize HTML input to prevent XSS attacks.

        Args:
            text: Input text that may contain HTML
            strict: If True, strip all HTML. If False, allow safe tags.

        Returns:
            Sanitized text
        """
        if not text:
            return text

        if strict:
            # Strip all HTML
            return bleach.clean(text, tags=[], attributes={}, strip=True)
        else:
            # Allow only safe tags
            return bleach.clean(
                text,
                tags=cls.ALLOWED_TAGS,
                attributes=cls.ALLOWED_ATTRIBUTES,
                strip=True,
            )

    @classmethod
    def sanitize_text(cls, text: str, max_length: Optional[int] = None) -> str:
        """
        Sanitize plain text input.

        Args:
            text: Input text
            max_length: Maximum allowed length

        Returns:
            Sanitized text
        """
        if not text:
            return text

        # Strip HTML
        sanitized = cls.sanitize_html(text, strict=True)

        # Remove control characters
        sanitized = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", sanitized)

        # Normalize whitespace
        sanitized = " ".join(sanitized.split())

        # Truncate if needed
        if max_length and len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        return sanitized.strip()

    @classmethod
    def sanitize_quiz_response(cls, response: str) -> str:
        """Sanitize quiz response input."""
        return cls.sanitize_text(response, max_length=cls.MAX_QUIZ_RESPONSE_LENGTH)

    @classmethod
    def sanitize_email(cls, email: str) -> str:
        """
        Sanitize and validate email address.

        Raises ValueError if invalid.
        """
        # Basic sanitization
        email = email.strip().lower()

        # Email validation regex (RFC 5322 simplified)
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        if not re.match(email_pattern, email):
            raise ValueError("Invalid email format")

        return email

    @classmethod
    def sanitize_phone(cls, phone: str) -> str:
        """
        Sanitize phone number.

        Keeps only digits and common separators.
        """
        # Keep only digits and common separators
        phone = re.sub(r"[^\d\s\-\(\)\+]", "", phone)

        # Normalize whitespace
        phone = " ".join(phone.split())

        return phone.strip()

    @classmethod
    def validate_uuid(cls, uuid_string: str) -> bool:
        """Validate UUID format."""
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        return bool(re.match(uuid_pattern, uuid_string.lower()))

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Sanitize filename to prevent path traversal attacks.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove path separators
        filename = filename.replace("/", "_").replace("\\", "_")

        # Remove dangerous characters
        filename = re.sub(r"[^\w\s\-\.]", "", filename)

        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            filename = name[:250] + ("." + ext if ext else "")

        return filename

    @classmethod
    def sanitize_dict(
        cls, data: Dict[str, Any], text_fields: List[str] = None
    ) -> Dict[str, Any]:
        """
        Sanitize all text fields in a dictionary.

        Args:
            data: Dictionary with potentially unsafe data
            text_fields: List of fields to sanitize (if None, sanitize all strings)

        Returns:
            Sanitized dictionary
        """
        sanitized = {}

        for key, value in data.items():
            if isinstance(value, str):
                # Sanitize if in text_fields or if text_fields is None
                if text_fields is None or key in text_fields:
                    sanitized[key] = cls.sanitize_text(value)
                else:
                    sanitized[key] = value
            elif isinstance(value, dict):
                sanitized[key] = cls.sanitize_dict(value, text_fields)
            elif isinstance(value, list):
                sanitized[key] = [
                    cls.sanitize_dict(item, text_fields)
                    if isinstance(item, dict)
                    else cls.sanitize_text(item)
                    if isinstance(item, str)
                    and (text_fields is None or key in text_fields)
                    else item
                    for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized

    @classmethod
    def detect_sql_injection(cls, text: str) -> bool:
        """
        Detect potential SQL injection attempts.

        Note: This is a defense-in-depth measure. Always use parameterized queries.
        """
        # Common SQL injection patterns
        sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)",
            r"(--|#|\/\*|\*\/)",  # SQL comments
            r"(\bOR\b\s+\d+\s*=\s*\d+)",  # OR 1=1
            r"(\bAND\b\s+\d+\s*=\s*\d+)",  # AND 1=1
            r"(;.*?--)",  # Statement terminator with comment
            r"(\bUNION\b.*?\bSELECT\b)",  # UNION SELECT
        ]

        for pattern in sql_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {pattern}")
                return True

        return False

    @classmethod
    def detect_xss(cls, text: str) -> bool:
        """
        Detect potential XSS attempts.

        Note: This is a defense-in-depth measure. Always sanitize output.
        """
        # Common XSS patterns
        xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",  # Event handlers like onclick=
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
        ]

        for pattern in xss_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"Potential XSS detected: {pattern}")
                return True

        return False

    @classmethod
    def validate_and_sanitize_input(
        cls,
        text: str,
        max_length: Optional[int] = None,
        allow_html: bool = False,
        check_sql: bool = True,
        check_xss: bool = True,
    ) -> str:
        """
        Comprehensive input validation and sanitization.

        Args:
            text: Input text
            max_length: Maximum allowed length
            allow_html: Whether to allow safe HTML tags
            check_sql: Check for SQL injection
            check_xss: Check for XSS

        Returns:
            Sanitized text

        Raises:
            ValueError: If input contains malicious patterns
        """
        if not text:
            return text

        # Check for SQL injection
        if check_sql and cls.detect_sql_injection(text):
            raise ValueError("Input contains potentially malicious SQL patterns")

        # Check for XSS
        if check_xss and cls.detect_xss(text):
            raise ValueError("Input contains potentially malicious script patterns")

        # Sanitize
        if allow_html:
            sanitized = cls.sanitize_html(text, strict=False)
        else:
            sanitized = cls.sanitize_text(text, max_length=max_length)

        return sanitized


# Convenience function
def sanitize_input(text: str, **kwargs) -> str:
    """Convenience function for input sanitization."""
    return InputSanitizer.validate_and_sanitize_input(text, **kwargs)
