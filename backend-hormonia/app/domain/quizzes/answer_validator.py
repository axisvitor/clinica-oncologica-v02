"""
Answer Validator Module for Monthly Quiz Service.

Handles answer validation, normalization, and response processing.
Responsibilities: Input validation, answer checking, response value normalization,
encryption handling, and validation rules enforcement.
"""
import json
from typing import Any, Dict, Optional, List
from datetime import datetime
from uuid import UUID

from app.models.quiz import QuizTemplate
from app.exceptions import ValidationError, NotFoundError
from app.services.encryption_service import get_encryption_service
from app.core.monthly_quiz_config import get_monthly_quiz_config
from app.schemas.quiz import QuestionType
import logging

logger = logging.getLogger(__name__)


class AnswerValidator:
    """Validates and normalizes quiz responses."""

    def __init__(self):
        self.config = get_monthly_quiz_config()
        self.encryption_service = get_encryption_service()

    def normalize_other_value(self, value: Any, question: Dict[str, Any]) -> Any:
        """
        Normalize various 'other' option aliases to match question options.

        Args:
            value: Response value to normalize
            question: Question dictionary with options

        Returns:
            Normalized value
        """
        if isinstance(value, str):
            value_lower = value.lower().strip()
            # Check if it's an "other" alias
            if value_lower in ['outra', 'other', 'outro', 'otra', 'autre', 'altro']:
                # Find the actual "other" option value in question options
                question_options = question.get("options", [])
                for opt in question_options:
                    if isinstance(opt, dict):
                        opt_value = opt.get("value", "")
                        if opt.get("allow_other") or opt_value.lower() in ['outra', 'other', 'outro', 'otra']:
                            return opt_value
                # Fallback to standardized "other"
                return "other"
        return value

    def validate_and_normalize_response(
        self,
        response_value: Any,
        question: Dict[str, Any]
    ) -> Any:
        """
        Validate and normalize response value based on question type.

        Args:
            response_value: Raw response value from submission
            question: Question dictionary from template

        Returns:
            Normalized and validated response value

        Raises:
            ValidationError: If response is invalid for the question type
        """
        question_type = question.get("type", "open_text")

        if question_type == "multiple_choice":
            return self._validate_multiple_choice(response_value, question)
        elif question_type == "single_choice":
            return self._validate_single_choice(response_value, question)
        elif question_type == "open_text":
            return self._validate_open_text(response_value)
        elif question_type == "numeric":
            return self._validate_numeric(response_value, question)
        elif question_type == "date":
            return self._validate_date(response_value)
        elif question_type == "boolean":
            return self._validate_boolean(response_value)
        else:
            # Unknown question type, accept as-is
            return response_value

    def _validate_multiple_choice(
        self,
        response_value: Any,
        question: Dict[str, Any]
    ) -> List[str]:
        """Validate multiple choice response."""
        if isinstance(response_value, str):
            try:
                # Try to parse JSON string
                response_value = json.loads(response_value)
            except:
                # Single value as list
                response_value = [self.normalize_other_value(response_value, question)]
        elif isinstance(response_value, list):
            # Normalize each value in the list
            response_value = [self.normalize_other_value(v, question) for v in response_value]
        else:
            raise ValidationError("Multiple choice requires array of values")

        # Validate against allowed options
        allowed_options = self._get_allowed_option_values(question)
        if allowed_options:
            for value in response_value:
                if value not in allowed_options:
                    raise ValidationError(f"Invalid option value: {value}")

        return response_value

    def _validate_single_choice(
        self,
        response_value: Any,
        question: Dict[str, Any]
    ) -> str:
        """Validate single choice response."""
        if not isinstance(response_value, str):
            raise ValidationError("Single choice requires a string value")

        # Normalize "other" values
        response_value = self.normalize_other_value(response_value, question)

        # Validate against allowed options
        allowed_options = self._get_allowed_option_values(question)
        if allowed_options and response_value not in allowed_options:
            raise ValidationError(f"Invalid option value: {response_value}")

        return response_value

    def _validate_open_text(self, response_value: Any) -> str:
        """Validate open text response."""
        if not isinstance(response_value, str):
            response_value = str(response_value)

        # Check for minimum length if configured
        min_length = 1
        if len(response_value.strip()) < min_length:
            raise ValidationError(f"Response must be at least {min_length} characters")

        return response_value.strip()

    def _validate_numeric(
        self,
        response_value: Any,
        question: Dict[str, Any]
    ) -> float:
        """Validate numeric response."""
        try:
            numeric_value = float(response_value)
        except (ValueError, TypeError):
            raise ValidationError("Response must be a valid number")

        # Check min/max if specified in question
        validation = question.get("validation", {})
        if "min" in validation and numeric_value < validation["min"]:
            raise ValidationError(f"Value must be at least {validation['min']}")
        if "max" in validation and numeric_value > validation["max"]:
            raise ValidationError(f"Value must be at most {validation['max']}")

        return numeric_value

    def _validate_date(self, response_value: Any) -> str:
        """Validate date response."""
        if isinstance(response_value, str):
            # Try to parse as ISO date
            try:
                datetime.fromisoformat(response_value)
                return response_value
            except ValueError:
                raise ValidationError("Invalid date format. Use ISO format (YYYY-MM-DD)")
        else:
            raise ValidationError("Date must be a string in ISO format")

    def _validate_boolean(self, response_value: Any) -> bool:
        """Validate boolean response."""
        if isinstance(response_value, bool):
            return response_value
        elif isinstance(response_value, str):
            value_lower = response_value.lower()
            if value_lower in ['true', 'yes', 'sim', '1', 'y']:
                return True
            elif value_lower in ['false', 'no', 'não', '0', 'n']:
                return False
            else:
                raise ValidationError("Invalid boolean value")
        elif isinstance(response_value, int):
            return bool(response_value)
        else:
            raise ValidationError("Boolean value required")

    def _get_allowed_option_values(self, question: Dict[str, Any]) -> Optional[List[str]]:
        """Extract allowed option values from question."""
        options = question.get("options", [])
        if not options:
            return None

        allowed = []
        for opt in options:
            if isinstance(opt, dict):
                allowed.append(opt.get("value", ""))
            elif isinstance(opt, str):
                allowed.append(opt)

        return allowed if allowed else None

    def encrypt_response_if_needed(
        self,
        response_value: Any,
        question: Dict[str, Any]
    ) -> tuple[Any, bool]:
        """
        Encrypt response value if question is marked as sensitive.

        Args:
            response_value: Validated response value
            question: Question dictionary

        Returns:
            Tuple of (encrypted_value, is_encrypted)
        """
        is_encrypted = False
        encrypted_value = response_value

        if self.config.MONTHLY_QUIZ_ENABLE_ENCRYPTION:
            # Encrypt if question is marked as sensitive
            if question.get("is_sensitive", False):
                # Convert to string for encryption if it's a list
                value_to_encrypt = json.dumps(response_value) if isinstance(response_value, list) else str(response_value)
                encrypted_value = self.encryption_service.encrypt(value_to_encrypt)
                is_encrypted = True

        return encrypted_value, is_encrypted

    def validate_question_exists(
        self,
        question_id: str,
        template: QuizTemplate
    ) -> Dict[str, Any]:
        """
        Validate that a question exists in the template.

        Args:
            question_id: Question ID to find
            template: Quiz template

        Returns:
            Question dictionary

        Raises:
            NotFoundError: If question not found
        """
        question = next(
            (q for q in template.questions if q.get("id") == question_id),
            None
        )

        if not question:
            raise NotFoundError(f"Question {question_id} not found in template")

        return question

    def build_response_metadata(
        self,
        is_encrypted: bool,
        other_text: Optional[str],
        question_index: int,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build response metadata dictionary.

        Args:
            is_encrypted: Whether response value is encrypted
            other_text: Text for "other" option if applicable
            question_index: Current question index
            additional_metadata: Optional additional metadata

        Returns:
            Complete metadata dictionary
        """
        metadata = {
            "is_encrypted": is_encrypted,
            "question_index": question_index
        }

        # Persist other_text when "Outra" option is selected
        if other_text:
            metadata["other_text"] = other_text

        # Merge additional metadata
        if additional_metadata:
            metadata.update(additional_metadata)

        return metadata

    def validate_response_timing(
        self,
        session_started_at: datetime,
        min_time_seconds: int = 2
    ) -> bool:
        """
        Validate that sufficient time has passed since session start.
        Helps detect bot submissions.

        Args:
            session_started_at: When session was started
            min_time_seconds: Minimum time required

        Returns:
            True if timing is valid

        Raises:
            ValidationError: If submission is too fast
        """
        elapsed = (datetime.utcnow() - session_started_at).total_seconds()
        if elapsed < min_time_seconds:
            raise ValidationError("Response submitted too quickly. Please take time to read the question.")

        return True

    def sanitize_text_input(self, text: str, max_length: int = 5000) -> str:
        """
        Sanitize text input to prevent injection attacks.

        Args:
            text: Input text to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized text
        """
        if not text:
            return ""

        # Truncate to max length
        text = text[:max_length]

        # Remove potentially dangerous characters/patterns
        # (basic sanitization - more comprehensive sanitization may be needed)
        dangerous_patterns = ['<script', 'javascript:', 'onerror=', 'onclick=']
        text_lower = text.lower()

        for pattern in dangerous_patterns:
            if pattern in text_lower:
                logger.warning(f"Potentially dangerous pattern detected: {pattern}")
                text = text.replace(pattern, '')

        return text.strip()
