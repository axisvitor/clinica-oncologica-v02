"""
DEPRECATED: This module has been moved to app.domain.quizzes.resilience

This file is kept for backward compatibility only.
Please update your imports to:
    from app.domain.quizzes.resilience import QuizLinkResilienceService
"""
import warnings

warnings.warn(
    "quiz_link_resilience has been moved to app.domain.quizzes.resilience. "
    "Please update your imports.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from app.domain.quizzes.resilience import (
    QuizLinkResilienceService,
    FailureReason,
    CircuitBreakerState,
    ResilienceMetrics
)

__all__ = [
    "QuizLinkResilienceService",
    "FailureReason",
    "CircuitBreakerState",
    "ResilienceMetrics"
]
