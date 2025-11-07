"""
DEPRECATED: This module has been moved to app.domain.quizzes.templates

This file is kept for backward compatibility only.
Please update your imports to:
    from app.domain.quizzes.templates import QuizTemplateService
"""
import warnings

warnings.warn(
    "quiz_template_service has been moved to app.domain.quizzes.templates. "
    "Please update your imports.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from app.domain.quizzes.templates import (
    QuizTemplateService,
    QuizTemplateLoadError,
    get_quiz_template_service
)

__all__ = ["QuizTemplateService", "QuizTemplateLoadError", "get_quiz_template_service"]
