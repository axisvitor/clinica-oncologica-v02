"""
DEPRECATED: This module has been moved to app.domain.analytics.quiz

This file is kept for backward compatibility only.
Please update your imports to:
    from app.domain.analytics.quiz import QuizMetricsCollector
"""
import warnings

warnings.warn(
    "quiz_metrics has been moved to app.domain.analytics.quiz. "
    "Please update your imports.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from app.domain.analytics.quiz import (
    QuizMetricsCollector,
    get_quiz_metrics_collector
)

__all__ = ["QuizMetricsCollector", "get_quiz_metrics_collector"]
