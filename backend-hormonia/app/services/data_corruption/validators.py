"""
Format Validators
Validates email, phone, and other formatted fields.
"""

import re
import logging
from typing import Any, List
from .types import CorruptionType, CorruptionPattern

logger = logging.getLogger(__name__)


class FormatValidator:
    """Validates formatted fields for corruption"""

    def __init__(self):
        self.corruption_patterns: List[CorruptionPattern] = []

    def validate_email(self, email: str, field_name: str, entity_id: Any) -> None:
        """Analyze email field for corruption patterns"""
        try:
            # Basic email format validation
            email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_pattern, email):
                self._add_pattern(
                    type=CorruptionType.FORMAT_CORRUPTION,
                    field=field_name,
                    pattern="invalid_email_format",
                    severity="medium",
                    description=f"Invalid email format in {field_name}",
                    detection_method="regex_validation",
                    examples=[f"Entity {entity_id}: {email}"],
                    confidence=0.8,
                )

            # Check for suspicious patterns
            if email.count("@") != 1:
                self._add_pattern(
                    type=CorruptionType.FORMAT_CORRUPTION,
                    field=field_name,
                    pattern="multiple_at_symbols",
                    severity="high",
                    description="Multiple @ symbols in email",
                    detection_method="character_count",
                    examples=[f"Entity {entity_id}: {email}"],
                    confidence=0.9,
                )

        except Exception as e:
            logger.error(f"Email field analysis failed: {e}")

    def validate_phone(self, phone: str, field_name: str, entity_id: Any) -> None:
        """Analyze phone field for corruption patterns"""
        try:
            # Remove common formatting characters
            clean_phone = re.sub(r"[\s\-\(\)\+]", "", phone)

            # Check for non-digit characters (excluding + for international)
            if not re.match(r"^[\+]?[\d]+$", clean_phone):
                self._add_pattern(
                    type=CorruptionType.FORMAT_CORRUPTION,
                    field=field_name,
                    pattern="invalid_phone_characters",
                    severity="medium",
                    description="Invalid characters in phone number",
                    detection_method="character_validation",
                    examples=[f"Entity {entity_id}: {phone}"],
                    confidence=0.7,
                )

            # Check phone length (Brazilian phones should be 10-11 digits + country code)
            if len(clean_phone) < 10 or len(clean_phone) > 15:
                self._add_pattern(
                    type=CorruptionType.FORMAT_CORRUPTION,
                    field=field_name,
                    pattern="invalid_phone_length",
                    severity="medium",
                    description="Invalid phone number length",
                    detection_method="length_validation",
                    examples=[
                        f"Entity {entity_id}: {phone} (length: {len(clean_phone)})"
                    ],
                    confidence=0.8,
                )

        except Exception as e:
            logger.error(f"Phone field analysis failed: {e}")

    def _add_pattern(self, **kwargs) -> None:
        """Add corruption pattern to list"""
        pattern = CorruptionPattern(**kwargs)
        self.corruption_patterns.append(pattern)
