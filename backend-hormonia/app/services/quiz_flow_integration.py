"""
DEPRECATED: This module has been moved to app.domain.quizzes.integration

This file is kept for backward compatibility only.
Please update your imports to:
    from app.domain.quizzes.integration import flow_integration
"""
import warnings

warnings.warn(
    "quiz_flow_integration has been moved to app.domain.quizzes.integration. "
    "Please update your imports.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location (when integration modules are properly set up)
# from app.domain.quizzes.integration import *

__all__ = []
