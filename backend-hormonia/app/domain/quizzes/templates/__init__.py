"""Quiz template management domain."""

from .template_service import (
    QuizTemplateService,
    QuizTemplateLoadError,
    get_quiz_template_service,
)

__all__ = ["QuizTemplateService", "QuizTemplateLoadError", "get_quiz_template_service"]
