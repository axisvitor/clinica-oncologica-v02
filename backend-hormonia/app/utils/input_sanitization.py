"""
Input sanitization and validation utilities.
"""

import re
import html
import bleach
from typing import Any, List, Optional
from urllib.parse import urlparse

from app.utils.logging import get_logger

logger = get_logger(__name__)


class InputSanitizer:
    """Comprehensive input sanitization utilities."""

    # Allowed HTML tags for rich text content
    ALLOWED_TAGS = [
        "p",
        "br",
        "strong",
        "em",
        "u",
        "ol",
        "ul",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "blockquote",
    ]

    # Allowed HTML attributes
    ALLOWED_ATTRIBUTES = {
        "*": ["class"],
        "a": ["href", "title"],
        "img": ["src", "alt", "width", "height"],
    }

    # Common XSS patterns
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"vbscript:",
        r"onload\s*=",
        r"onerror\s*=",
        r"onclick\s*=",
        r"onmouseover\s*=",
        r"onfocus\s*=",
        r"onblur\s*=",
        r"onchange\s*=",
        r"onsubmit\s*=",
        r"<iframe[^>]*>.*?</iframe>",
        r"<object[^>]*>.*?</object>",
        r"<embed[^>]*>.*?</embed>",
        r"<form[^>]*>.*?</form>",
    ]

    # SQL injection patterns
    SQL_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)",
        r"(\b(UNION|OR|AND)\s+\d+\s*=\s*\d+)",
        r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
        r"(\'|\")(\s*)(OR|AND)(\s*)(\d+)(\s*)(=)(\s*)(\d+)",
        r"(\'|\")(\s*)(;)(\s*)(DROP|DELETE|INSERT|UPDATE)",
        r"(\-\-|\#|\/\*)",
    ]

    def __init__(self):
        self.xss_regex = re.compile(
            "|".join(self.XSS_PATTERNS), re.IGNORECASE | re.DOTALL
        )
        self.sql_regex = re.compile("|".join(self.SQL_PATTERNS), re.IGNORECASE)

    def sanitize_string(
        self,
        value: str,
        max_length: Optional[int] = None,
        allow_html: bool = False,
        strip_whitespace: bool = True,
    ) -> str:
        """
        Sanitize string input.

        Args:
            value: Input string to sanitize
            max_length: Maximum allowed length
            allow_html: Whether to allow safe HTML tags
            strip_whitespace: Whether to strip leading/trailing whitespace

        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            value = str(value)

        # Strip whitespace if requested
        if strip_whitespace:
            value = value.strip()

        # Truncate if max_length specified
        if max_length and len(value) > max_length:
            value = value[:max_length]
            logger.warning(
                f"Input truncated to {max_length} characters",
                extra={"event_type": "input_truncated", "original_length": len(value)},
            )

        # Handle HTML content
        if allow_html:
            # Use bleach to clean HTML
            value = bleach.clean(
                value,
                tags=self.ALLOWED_TAGS,
                attributes=self.ALLOWED_ATTRIBUTES,
                strip=True,
            )
        else:
            # Escape HTML entities
            value = html.escape(value)

        # Check for XSS patterns
        if self.xss_regex.search(value):
            logger.warning(
                "Potential XSS attempt detected",
                extra={
                    "event_type": "xss_attempt",
                    "input_sample": value[:100] + "..." if len(value) > 100 else value,
                },
            )
            # Remove suspicious patterns
            value = self.xss_regex.sub("", value)

        # Check for SQL injection patterns
        if self.sql_regex.search(value):
            logger.warning(
                "Potential SQL injection attempt detected",
                extra={
                    "event_type": "sql_injection_attempt",
                    "input_sample": value[:100] + "..." if len(value) > 100 else value,
                },
            )
            # Remove suspicious patterns
            value = self.sql_regex.sub("", value)

        return value

    def sanitize_email(self, email: str) -> str:
        """Sanitize email address."""
        email = self.sanitize_string(email, max_length=254, strip_whitespace=True)
        email = email.lower()

        # Basic email validation pattern
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            raise ValueError("Invalid email format")

        return email

    def sanitize_phone(self, phone: str) -> str:
        """Sanitize phone number."""
        # Remove all non-digit characters except +
        phone = re.sub(r"[^\d+]", "", phone)

        # Ensure it starts with + for international format
        if not phone.startswith("+"):
            phone = "+" + phone

        # Basic phone validation (8-15 digits after country code)
        if not re.match(r"^\+\d{8,15}$", phone):
            raise ValueError("Invalid phone number format")

        return phone

    def sanitize_url(self, url: str, allowed_schemes: List[str] = None) -> str:
        """Sanitize URL."""
        if allowed_schemes is None:
            allowed_schemes = ["http", "https"]

        url = self.sanitize_string(url, max_length=2048, strip_whitespace=True)

        try:
            parsed = urlparse(url)

            if parsed.scheme not in allowed_schemes:
                raise ValueError(f"URL scheme not allowed: {parsed.scheme}")

            if not parsed.netloc:
                raise ValueError("Invalid URL: missing domain")

            return url
        except Exception as e:
            raise ValueError(f"Invalid URL: {str(e)}")

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage."""
        # Remove path separators and dangerous characters
        filename = re.sub(r'[<>:"/\\|?*]', "", filename)
        filename = re.sub(r"\.\.", "", filename)  # Remove directory traversal
        filename = filename.strip(". ")  # Remove leading/trailing dots and spaces

        if not filename:
            raise ValueError("Invalid filename")

        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            max_name_length = 255 - len(ext) - 1 if ext else 255
            filename = name[:max_name_length] + ("." + ext if ext else "")

        return filename

    def sanitize_dict(
        self,
        data: dict[str, Any],
        field_rules: Optional[dict[str, dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """
        Sanitize dictionary data based on field rules.

        Args:
            data: Dictionary to sanitize
            field_rules: Rules for each field {field_name: {rule_name: rule_value}}

        Returns:
            Sanitized dictionary
        """
        if field_rules is None:
            field_rules = {}

        sanitized = {}

        for key, value in data.items():
            if key in field_rules:
                rules = field_rules[key]

                if isinstance(value, str):
                    sanitized[key] = self.sanitize_string(
                        value,
                        max_length=rules.get("max_length"),
                        allow_html=rules.get("allow_html", False),
                        strip_whitespace=rules.get("strip_whitespace", True),
                    )
                elif isinstance(value, dict):
                    sanitized[key] = self.sanitize_dict(
                        value, rules.get("nested_rules")
                    )
                elif isinstance(value, list):
                    sanitized[key] = [
                        self.sanitize_string(item) if isinstance(item, str) else item
                        for item in value
                    ]
                else:
                    sanitized[key] = value
            else:
                # Default sanitization for unknown fields
                if isinstance(value, str):
                    sanitized[key] = self.sanitize_string(value)
                elif isinstance(value, dict):
                    sanitized[key] = self.sanitize_dict(value)
                else:
                    sanitized[key] = value

        return sanitized

    def validate_json_structure(
        self, data: dict[str, Any], max_depth: int = 10, max_keys: int = 1000
    ) -> bool:
        """
        Validate JSON structure to prevent DoS attacks.

        Args:
            data: JSON data to validate
            max_depth: Maximum nesting depth
            max_keys: Maximum number of keys

        Returns:
            True if valid, raises ValueError if invalid
        """

        def count_keys_and_depth(obj, current_depth=0):
            if current_depth > max_depth:
                raise ValueError(f"JSON nesting too deep (max: {max_depth})")

            key_count = 0

            if isinstance(obj, dict):
                key_count += len(obj)
                for value in obj.values():
                    key_count += count_keys_and_depth(value, current_depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    key_count += count_keys_and_depth(item, current_depth + 1)

            return key_count

        total_keys = count_keys_and_depth(data)
        if total_keys > max_keys:
            raise ValueError(f"Too many keys in JSON (max: {max_keys})")

        return True


# Global sanitizer instance
_sanitizer: Optional[InputSanitizer] = None


def get_sanitizer() -> InputSanitizer:
    """Get global sanitizer instance."""
    global _sanitizer
    if _sanitizer is None:
        _sanitizer = InputSanitizer()
    return _sanitizer


def sanitize_input(value: Any, field_type: str = "string", **kwargs) -> Any:
    """
    Convenience function for sanitizing input.

    Args:
        value: Value to sanitize
        field_type: Type of field (string, email, phone, url, filename)
        **kwargs: Additional arguments for sanitization

    Returns:
        Sanitized value
    """
    sanitizer = get_sanitizer()

    if field_type == "email":
        return sanitizer.sanitize_email(value)
    elif field_type == "phone":
        return sanitizer.sanitize_phone(value)
    elif field_type == "url":
        return sanitizer.sanitize_url(value, **kwargs)
    elif field_type == "filename":
        return sanitizer.sanitize_filename(value)
    else:
        return sanitizer.sanitize_string(value, **kwargs)
