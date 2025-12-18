"""Quiz analytics and metrics domain."""

from .metrics_collector import QuizMetricsCollector, get_quiz_metrics_collector

__all__ = ["QuizMetricsCollector", "get_quiz_metrics_collector"]
