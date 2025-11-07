"""
Monthly Quiz Service for Hormonia Backend System.

DEPRECATION WARNING:
This module has been refactored into modular components in app.domain.quizzes.
The original MonthlyQuizService is now a backward compatibility wrapper.

NEW LOCATION: app.domain.quizzes
- SessionManager: Quiz session lifecycle and token management
- QuestionRenderer: Question formatting and rendering
- AnswerValidator: Answer validation and normalization
- ScoreCalculator: Score computation and analysis
- ReportGenerator: Report generation and statistics

Please update your imports to use:
    from app.domain.quizzes import MonthlyQuizService

This wrapper will be removed in a future version.
"""
import warnings

# Import refactored service from new location
from app.domain.quizzes import (
    MonthlyQuizService as RefactoredMonthlyQuizService,
    SessionManager,
    QuestionRenderer,
    AnswerValidator,
    ScoreCalculator,
    ReportGenerator
)

# Issue deprecation warning
warnings.warn(
    "Importing MonthlyQuizService from app.services.monthly_quiz_service is deprecated. "
    "Please use 'from app.domain.quizzes import MonthlyQuizService' instead. "
    "The service has been refactored into focused modules: SessionManager, QuestionRenderer, "
    "AnswerValidator, ScoreCalculator, and ReportGenerator.",
    DeprecationWarning,
    stacklevel=2
)


class MonthlyQuizService(RefactoredMonthlyQuizService):
    """
    Backward compatibility wrapper for MonthlyQuizService.

    This class inherits all functionality from the refactored implementation
    in app.domain.quizzes. All methods are available through inheritance.

    DEPRECATED: Use 'from app.domain.quizzes import MonthlyQuizService' instead.
    """
    pass


# Export all public components
__all__ = [
    "MonthlyQuizService",
    "SessionManager",
    "QuestionRenderer",
    "AnswerValidator",
    "ScoreCalculator",
    "ReportGenerator"
]
