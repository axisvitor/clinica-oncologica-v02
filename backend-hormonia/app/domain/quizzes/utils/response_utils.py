"""
Utility functions for quiz response processing.
"""

import json
from typing import Union, List, Dict, Any


def normalize_other_value(value: Union[str, List[str]]) -> Union[str, List[str]]:
    """
    Normalize various 'other' option aliases to standard 'other'.

    Args:
        value: Single value or list of values

    Returns:
        Normalized value(s) with 'other' aliases standardized
    """
    other_aliases = ["outra", "outro", "otra", "autre", "altro"]

    def normalize_single(val: str) -> str:
        """Normalize a single value."""
        val_lower = str(val).lower().strip()
        if val_lower in other_aliases:
            return "other"
        return str(val).strip()

    if isinstance(value, list):
        return [normalize_single(v) for v in value]
    else:
        return normalize_single(value)


def serialize_response_value(value: Union[str, List[str]]) -> str:
    """
    Serialize response value for database storage.

    Args:
        value: Single value or list of values

    Returns:
        String representation (JSON for lists, direct string for single values)
    """
    if isinstance(value, list):
        # Store as JSON array for multi-select
        return json.dumps(value)
    else:
        # Store as plain string for single select
        return str(value)


def deserialize_response_value(
    value: str, is_multi_select: bool = False
) -> Union[str, List[str]]:
    """
    Deserialize response value from database storage.

    Args:
        value: Stored string value
        is_multi_select: Whether this is a multi-select question

    Returns:
        Deserialized value (list for multi-select, string otherwise)
    """
    if is_multi_select:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [parsed]
        except (json.JSONDecodeError, TypeError):
            # If not valid JSON, treat as single value wrapped in list
            return [value]
    else:
        return value


def validate_multi_select_response(
    response_values: List[str], question_options: List[Dict[str, Any]]
) -> List[str]:
    """
    Validate multi-select response against question options.

    Args:
        response_values: List of selected values
        question_options: List of valid question options

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    if not response_values:
        errors.append("Multi-select requires at least one selection")
        return errors

    # Extract valid option values and IDs
    valid_values = set()
    allows_other = False

    for option in question_options:
        if option.get("value"):
            valid_values.add(str(option["value"]))
        if option.get("id"):
            valid_values.add(str(option["id"]))
        if option.get("allow_other"):
            allows_other = True

    # Validate each selected value
    for value in response_values:
        normalized = normalize_other_value(value)

        # Check if it's the standardized "other" option
        if normalized == "other" or str(value).lower().strip() == "other":
            if not allows_other:
                errors.append("Option 'other' is not allowed for this question")
            continue

        # Check if value is in valid options
        if str(value) not in valid_values:
            errors.append(f"Invalid option: {value}")

    return errors


def extract_other_text_requirement(
    response_value: Union[str, List[str]], question_options: List[Dict[str, Any]]
) -> bool:
    """
    Check if other_text is required based on response and question options.

    Args:
        response_value: Selected value(s)
        question_options: Question option definitions

    Returns:
        True if other_text is required, False otherwise
    """
    # Check if any option allows "other"
    allows_other = any(opt.get("allow_other", False) for opt in question_options)

    if not allows_other:
        return False

    # Check if "other" is selected
    other_aliases = ["other", "outro", "outra", "otra", "autre", "altro"]

    if isinstance(response_value, list):
        return any(str(val).lower().strip() in other_aliases for val in response_value)
    else:
        return str(response_value).lower().strip() in other_aliases
