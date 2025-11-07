"""
DEPRECATED: This module has been moved to app.domain.quizzes.security

This file is kept for backward compatibility only.
Please update your imports to:
    from app.domain.quizzes.security import token_rotation
"""
import warnings

warnings.warn(
    "quiz_token_rotation_patch has been moved to app.domain.quizzes.security. "
    "Please update your imports.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from app.domain.quizzes.security import (
    _validate_token_with_grace_period,
    submit_quiz_response_with_rotation
)

__all__ = [
    "_validate_token_with_grace_period",
    "submit_quiz_response_with_rotation"
]
