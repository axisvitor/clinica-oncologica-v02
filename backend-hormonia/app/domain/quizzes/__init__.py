"""
Domain layer for quiz management.

This package contains all quiz-related business logic organized by subdomain:
- templates: Quiz template management
- evaluation: Response evaluation and alerting
- resilience: Link resilience and fallback mechanisms
- security: Token rotation and authentication
- utils: Shared utility functions
- integration: Integration with flows and other systems

Consolidated Services (from /app/services migration):
- QuizTemplateService (templates/)
- QuizMetricsCollector (analytics/quiz/)
- QuizLinkResilienceService (resilience/)
- QuizResponseEvaluator (evaluation/)
- Response utilities (utils/)
- Token rotation (security/)
"""

# Main quiz service (already migrated)
from .monthly_quiz_service import MonthlyQuizService

# Template management
from .templates import QuizTemplateService, QuizTemplateLoadError, get_quiz_template_service

# Response evaluation
from .evaluation import QuizResponseEvaluator

# Link resilience
from .resilience import (
    QuizLinkResilienceService,
    FailureReason,
    CircuitBreakerState,
    ResilienceMetrics
)

# Utilities
from .utils import (
    normalize_other_value,
    serialize_response_value,
    deserialize_response_value,
    validate_multi_select_response,
    extract_other_text_requirement
)

# Security (token rotation)
from .security import (
    _validate_token_with_grace_period,
    submit_quiz_response_with_rotation
)

# Session management (renamed to avoid collision with core.session_manager)
from .quiz_session_manager import QuizSessionManager
from .question_renderer import QuizQuestionRenderer
from .answer_validator import QuizAnswerValidator
from .score_calculator import QuizScoreCalculator
from .report_generator import QuizReportGenerator

__all__ = [
    # Main service
    "MonthlyQuizService",

    # Template management
    "QuizTemplateService",
    "QuizTemplateLoadError",
    "get_quiz_template_service",

    # Evaluation
    "QuizResponseEvaluator",

    # Resilience
    "QuizLinkResilienceService",
    "FailureReason",
    "CircuitBreakerState",
    "ResilienceMetrics",

    # Utilities
    "normalize_other_value",
    "serialize_response_value",
    "deserialize_response_value",
    "validate_multi_select_response",
    "extract_other_text_requirement",

    # Security
    "_validate_token_with_grace_period",
    "submit_quiz_response_with_rotation",

    # Session components
    "QuizSessionManager",
    "QuizQuestionRenderer",
    "QuizAnswerValidator",
    "QuizScoreCalculator",
    "QuizReportGenerator",
]
