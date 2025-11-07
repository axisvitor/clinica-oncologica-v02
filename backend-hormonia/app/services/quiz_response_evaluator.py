"""
DEPRECATED: This module has been moved to app.domain.quizzes.evaluation

This file is kept for backward compatibility only.
Please update your imports to:
    from app.domain.quizzes.evaluation import QuizResponseEvaluator
"""
import warnings

warnings.warn(
    "quiz_response_evaluator has been moved to app.domain.quizzes.evaluation. "
    "Please update your imports.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from app.domain.quizzes.evaluation import QuizResponseEvaluator

__all__ = ["QuizResponseEvaluator"]
