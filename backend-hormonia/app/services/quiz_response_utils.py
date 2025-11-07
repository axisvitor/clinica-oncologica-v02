"""
DEPRECATED: This module has been moved to app.domain.quizzes.utils

This file is kept for backward compatibility only.
Please update your imports to:
    from app.domain.quizzes.utils import normalize_other_value, ...
"""
import warnings

warnings.warn(
    "quiz_response_utils has been moved to app.domain.quizzes.utils. "
    "Please update your imports.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from app.domain.quizzes.utils import (
    normalize_other_value,
    serialize_response_value,
    deserialize_response_value,
    validate_multi_select_response,
    extract_other_text_requirement
)

__all__ = [
    "normalize_other_value",
    "serialize_response_value",
    "deserialize_response_value",
    "validate_multi_select_response",
    "extract_other_text_requirement"
]
