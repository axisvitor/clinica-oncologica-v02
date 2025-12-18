"""
Quiz response processing and medical report generation service.
Handles quiz response collection, validation, trend analysis, and automated report generation.
"""

from app.services.reporting.quiz_report_generator.models import (
    TrendDirection,
    ConcernLevel,
    QuizMetrics,
    ResponseTrend,
    MedicalInsight,
    QuizAnalysisResult,
)
from app.services.reporting.quiz_report_generator.processor import QuizResponseProcessor
from app.services.reporting.quiz_report_generator.generator import QuizReportGenerator


def get_quiz_response_processor(db) -> QuizResponseProcessor:
    """Get quiz response processor instance."""
    return QuizResponseProcessor(db)


def get_quiz_report_generator(db) -> QuizReportGenerator:
    """Get quiz report generator instance."""
    return QuizReportGenerator(db)


__all__ = [
    "TrendDirection",
    "ConcernLevel",
    "QuizMetrics",
    "ResponseTrend",
    "MedicalInsight",
    "QuizAnalysisResult",
    "QuizResponseProcessor",
    "QuizReportGenerator",
    "get_quiz_response_processor",
    "get_quiz_report_generator",
]
