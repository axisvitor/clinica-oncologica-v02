"""
JSONB Utilities for Quiz Response Value Handling.

This module provides utilities for working with the quiz_responses.response_value
JSONB column, including serialization, deserialization, validation, and querying.

Migration: HIGH-003 - response_value Text to JSONB conversion
"""

import json
from typing import Any, Dict, List, Optional, Union
from enum import Enum


class ResponseValueFormat(str, Enum):
    """Supported JSONB formats for response_value."""

    PLAIN_TEXT = "plain_text"  # Simple string: "response"
    TEXT_OBJECT = "text_object"  # {"text": "response"}
    ARRAY = "array"  # ["option1", "option2"]
    SELECTIONS_OBJECT = "selections"  # {"selections": ["A", "B"]}
    SCALE = "scale"  # {"value": 7, "type": "scale"}
    BOOLEAN = "boolean"  # {"text": "yes", "boolean": true}
    STRUCTURED = "structured"  # Complex object with metadata


class ResponseValueSerializer:
    """Serialize Python objects to JSONB format for response_value."""

    @staticmethod
    def to_plain_text(text: str) -> str:
        """
        Serialize plain text response.

        Args:
            text: Response text

        Returns:
            String value for JSONB storage
        """
        return text

    @staticmethod
    def to_text_object(text: str, **metadata) -> Dict[str, Any]:
        """
        Serialize text with metadata.

        Args:
            text: Response text
            **metadata: Additional metadata fields

        Returns:
            Dictionary with text and metadata
        """
        result = {"text": text}
        if metadata:
            result.update(metadata)
        return result

    @staticmethod
    def to_array(selections: List[str]) -> List[str]:
        """
        Serialize multiple choice selections as array.

        Args:
            selections: List of selected options

        Returns:
            List of selections
        """
        return selections

    @staticmethod
    def to_selections_object(selections: List[str], **metadata) -> Dict[str, Any]:
        """
        Serialize selections with metadata.

        Args:
            selections: List of selected options
            **metadata: Additional metadata

        Returns:
            Dictionary with selections and metadata
        """
        result = {"selections": selections}
        if metadata:
            result.update(metadata)
        return result

    @staticmethod
    def to_scale(
        value: Union[int, float], min_value: int = 1, max_value: int = 10
    ) -> Dict[str, Any]:
        """
        Serialize scale response.

        Args:
            value: Scale value
            min_value: Minimum scale value
            max_value: Maximum scale value

        Returns:
            Scale object with value and metadata
        """
        return {
            "value": value,
            "type": "scale",
            "range": {"min": min_value, "max": max_value},
        }

    @staticmethod
    def to_boolean(text: str, boolean_value: bool) -> Dict[str, Any]:
        """
        Serialize boolean response with original text.

        Args:
            text: Original response text
            boolean_value: Interpreted boolean value

        Returns:
            Boolean object with text and value
        """
        return {"text": text, "boolean": boolean_value}

    @staticmethod
    def auto_serialize(
        value: Any, response_type: str = "open_text"
    ) -> Union[str, List, Dict]:
        """
        Automatically serialize based on value type and response type.

        Args:
            value: Value to serialize
            response_type: Type of quiz response

        Returns:
            Serialized value in appropriate JSONB format
        """
        # Handle None
        if value is None:
            return ""

        # Handle string
        if isinstance(value, str):
            # Check if it's already JSON
            if value.startswith(("[", "{")):
                try:
                    parsed = json.loads(value)
                    return parsed
                except json.JSONDecodeError:
                    pass

            # Handle comma-separated values for multiple choice
            if response_type == "multiple_choice" and "," in value:
                return [v.strip() for v in value.split(",")]

            # Handle boolean-like responses
            if value.lower() in ("true", "false", "yes", "no", "sim", "não"):
                boolean_value = value.lower() in ("true", "yes", "sim")
                return ResponseValueSerializer.to_boolean(value, boolean_value)

            # Plain text
            return value

        # Handle list/array
        if isinstance(value, (list, tuple)):
            return list(value)

        # Handle dict
        if isinstance(value, dict):
            return value

        # Handle numeric
        if isinstance(value, (int, float)):
            if response_type == "scale":
                return ResponseValueSerializer.to_scale(value)
            return {"value": value}

        # Handle boolean
        if isinstance(value, bool):
            text = "yes" if value else "no"
            return ResponseValueSerializer.to_boolean(text, value)

        # Fallback to string conversion
        return str(value)


class ResponseValueDeserializer:
    """Deserialize JSONB response_value to Python objects."""

    @staticmethod
    def to_text(value: Union[str, List, Dict]) -> str:
        """
        Extract text representation from any JSONB format.

        Args:
            value: JSONB response value

        Returns:
            Text representation
        """
        if value is None:
            return ""

        if isinstance(value, str):
            return value

        if isinstance(value, list):
            return ", ".join(str(v) for v in value)

        if isinstance(value, dict):
            # Try to extract text field
            if "text" in value:
                return value["text"]
            if "value" in value:
                return str(value["value"])
            if "selections" in value:
                return ", ".join(str(v) for v in value["selections"])
            # Fallback to JSON string
            return json.dumps(value)

        return str(value)

    @staticmethod
    def to_array(value: Union[str, List, Dict]) -> List[str]:
        """
        Extract array representation from any JSONB format.

        Args:
            value: JSONB response value

        Returns:
            List of values
        """
        if value is None:
            return []

        if isinstance(value, list):
            return [str(v) for v in value]

        if isinstance(value, str):
            # Check if it's a comma-separated string
            if "," in value:
                return [v.strip() for v in value.split(",")]
            return [value]

        if isinstance(value, dict):
            if "selections" in value:
                return value["selections"]
            if "text" in value:
                return [value["text"]]
            if "value" in value:
                return [str(value["value"])]

        return [str(value)]

    @staticmethod
    def to_numeric(value: Union[str, List, Dict]) -> Optional[float]:
        """
        Extract numeric value from any JSONB format.

        Args:
            value: JSONB response value

        Returns:
            Numeric value or None
        """
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None

        if isinstance(value, dict):
            if "value" in value:
                try:
                    return float(value["value"])
                except (ValueError, TypeError):
                    return None

        return None

    @staticmethod
    def to_boolean(value: Union[str, List, Dict]) -> Optional[bool]:
        """
        Extract boolean value from any JSONB format.

        Args:
            value: JSONB response value

        Returns:
            Boolean value or None
        """
        if value is None:
            return None

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            if value.lower() in ("true", "yes", "sim", "1"):
                return True
            if value.lower() in ("false", "no", "não", "0"):
                return False

        if isinstance(value, dict):
            if "boolean" in value:
                return value["boolean"]
            if "text" in value:
                return ResponseValueDeserializer.to_boolean(value["text"])

        return None


class ResponseValueValidator:
    """Validate JSONB response_value structures."""

    @staticmethod
    def validate_format(value: Any) -> tuple[bool, Optional[str]]:
        """
        Validate that value is a valid JSONB format.

        Args:
            value: Value to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if value is None:
            return False, "Response value cannot be None"

        # Valid JSON types
        if isinstance(value, (str, int, float, bool, list, dict)):
            return True, None

        return False, f"Invalid JSONB type: {type(value).__name__}"

    @staticmethod
    def validate_multiple_choice(
        value: Any, valid_options: Optional[List[str]] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Validate multiple choice response.

        Args:
            value: Response value
            valid_options: List of valid options

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Extract selections
        selections = ResponseValueDeserializer.to_array(value)

        if not selections:
            return False, "No selections provided"

        # Validate against options if provided
        if valid_options:
            invalid = [s for s in selections if s not in valid_options]
            if invalid:
                return False, f"Invalid selections: {', '.join(invalid)}"

        return True, None

    @staticmethod
    def validate_scale(
        value: Any, min_value: int = 1, max_value: int = 10
    ) -> tuple[bool, Optional[str]]:
        """
        Validate scale response.

        Args:
            value: Response value
            min_value: Minimum valid value
            max_value: Maximum valid value

        Returns:
            Tuple of (is_valid, error_message)
        """
        numeric = ResponseValueDeserializer.to_numeric(value)

        if numeric is None:
            return False, "Scale response must be numeric"

        if numeric < min_value or numeric > max_value:
            return (
                False,
                f"Scale value {numeric} out of range [{min_value}-{max_value}]",
            )

        return True, None

    @staticmethod
    def validate_text(
        value: Any, min_length: int = 1, max_length: int = 10000
    ) -> tuple[bool, Optional[str]]:
        """
        Validate text response.

        Args:
            value: Response value
            min_length: Minimum text length
            max_length: Maximum text length

        Returns:
            Tuple of (is_valid, error_message)
        """
        text = ResponseValueDeserializer.to_text(value)

        if not text:
            return False, "Text response cannot be empty"

        if len(text) < min_length:
            return False, f"Text too short (minimum {min_length} characters)"

        if len(text) > max_length:
            return False, f"Text too long (maximum {max_length} characters)"

        return True, None


class ResponseValueQuery:
    """Build SQLAlchemy queries for JSONB response_value."""

    @staticmethod
    def text_equals(column, text: str):
        """
        Query for exact text match.

        Args:
            column: SQLAlchemy column reference
            text: Text to match

        Returns:
            SQLAlchemy filter expression
        """
        from sqlalchemy import or_, cast, String

        return or_(
            column == cast(text, String),  # Plain text
            column["text"].astext == text,  # Object with text field
        )

    @staticmethod
    def text_contains(column, text: str):
        """
        Query for text containing substring.

        Args:
            column: SQLAlchemy column reference
            text: Substring to search

        Returns:
            SQLAlchemy filter expression
        """
        from sqlalchemy import func

        return func.get_quiz_response_text(column).contains(text)

    @staticmethod
    def array_contains(column, value: str):
        """
        Query for array containing value.

        Args:
            column: SQLAlchemy column reference
            value: Value to search in array

        Returns:
            SQLAlchemy filter expression
        """
        return column.contains([value])

    @staticmethod
    def numeric_range(
        column, min_value: Optional[float] = None, max_value: Optional[float] = None
    ):
        """
        Query for numeric value in range.

        Args:
            column: SQLAlchemy column reference
            min_value: Minimum value
            max_value: Maximum value

        Returns:
            SQLAlchemy filter expression
        """
        from sqlalchemy import and_, Numeric

        filters = []
        numeric_col = column["value"].astext.cast(Numeric)

        if min_value is not None:
            filters.append(numeric_col >= min_value)
        if max_value is not None:
            filters.append(numeric_col <= max_value)

        return and_(*filters) if filters else True


# Convenience functions
def serialize_response(
    value: Any, response_type: str = "open_text"
) -> Union[str, List, Dict]:
    """Serialize response value for JSONB storage."""
    return ResponseValueSerializer.auto_serialize(value, response_type)


def deserialize_to_text(value: Union[str, List, Dict]) -> str:
    """Deserialize JSONB value to text."""
    return ResponseValueDeserializer.to_text(value)


def deserialize_to_array(value: Union[str, List, Dict]) -> List[str]:
    """Deserialize JSONB value to array."""
    return ResponseValueDeserializer.to_array(value)


def deserialize_to_numeric(value: Union[str, List, Dict]) -> Optional[float]:
    """Deserialize JSONB value to numeric."""
    return ResponseValueDeserializer.to_numeric(value)


def validate_response_value(
    value: Any, response_type: str, **constraints
) -> tuple[bool, Optional[str]]:
    """
    Validate response value based on type.

    Args:
        value: Response value
        response_type: Type of response
        **constraints: Additional validation constraints

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Basic format validation
    is_valid, error = ResponseValueValidator.validate_format(value)
    if not is_valid:
        return is_valid, error

    # Type-specific validation
    if response_type == "multiple_choice":
        return ResponseValueValidator.validate_multiple_choice(
            value, valid_options=constraints.get("options")
        )
    elif response_type == "scale":
        return ResponseValueValidator.validate_scale(
            value,
            min_value=constraints.get("min_value", 1),
            max_value=constraints.get("max_value", 10),
        )
    elif response_type in ("open_text", "text"):
        return ResponseValueValidator.validate_text(
            value,
            min_length=constraints.get("min_length", 1),
            max_length=constraints.get("max_length", 10000),
        )

    return True, None
