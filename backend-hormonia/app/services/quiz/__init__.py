"""
Quiz Services Module - Consolidated Quiz Management (QW-023).

This module consolidates quiz-related services into a unified interface:
- Quiz CRUD operations
- Quiz evaluation and scoring
- Template management
- Response processing
- Metrics and analytics

Consolidation:
    12 files → 3 files (75% reduction)

Legacy Files (Consolidated):
    - app/services/quiz.py
    - app/services/monthly_quiz_service.py
    - app/services/optimized_monthly_quiz_service.py
    - app/services/quiz_response_evaluator.py
    - app/services/quiz_response_utils.py
    - app/services/quiz_template_loader.py
    - app/services/quiz_template_service.py
    - app/services/quiz_metrics.py
    - app/services/quiz_report_generator.py
    - app/services/quiz_link_resilience.py
    - app/services/quiz_question_humanizer_integration.py
    - app/services/quiz_token_rotation_patch.py

New Structure:
    - quiz/quiz_service.py (CRUD + lifecycle logic)
    - quiz/quiz_engine.py (evaluation + scoring)
    - quiz/quiz_templates.py (template management)

Note: Flow integration moved to app/services/flow/integrations/quiz_integration.py (QW-021)

Public API:
    Core Services:
        - QuizService: Quiz CRUD and lifecycle
        - QuizTemplateService: Template management
        - QuizSessionService: Session management
        - QuizResponseService: Response handling

    Evaluation:
        - QuizEvaluator: Response evaluation
        - QuizScorer: Scoring logic
        - QuizAnalyzer: Analytics and insights

    Template Management:
        - TemplateLoader: Load templates
        - TemplateValidator: Validate templates
        - TemplateVersionManager: Version control

    Utilities:
        - QuizMetricsCollector: Metrics collection
        - QuizReportGenerator: Report generation
        - ResponseUtils: Response utilities

Example Usage:
    >>> from app.services.quiz import QuizService, QuizEvaluator
    >>> from sqlalchemy.orm import Session
    >>>
    >>> # Create quiz session
    >>> service = QuizService(db)
    >>> session = service.create_session(patient_id, template_id)
    >>>
    >>> # Submit response
    >>> response = service.submit_response(session_id, question_id, answer)
    >>>
    >>> # Evaluate
    >>> evaluator = QuizEvaluator(db)
    >>> result = evaluator.evaluate_response(response)
    >>>
    >>> # Generate report
    >>> report = service.generate_report(session_id)

Migration Notes:
    Legacy imports will continue to work via adapters:

    Old:
        from app.services.quiz import QuizTemplateService
        from app.services.quiz_response_evaluator import QuizResponseEvaluator

    New (Recommended):
        from app.services.quiz import QuizService, QuizEvaluator

Version: 1.0.0 (QW-023)
Status: Production Ready
"""

from typing import TYPE_CHECKING

# Import quiz services
from .quiz_service import (
    QuizService,
    QuizTemplateService,
    QuizSessionService,
    QuizResponseService,
    MonthlyQuizService,
)

# Import quiz engine
from .quiz_engine import (
    QuizEvaluator,
    QuizScorer,
    QuizAnalyzer,
    ResponseUtils,
    QuizMetricsCollector,
    QuizReportGenerator,
)

# Import template management
from .quiz_templates import (
    TemplateLoader,
    TemplateValidator,
    TemplateVersionManager,
    TemplateCache,
)


# Factory functions
def get_quiz_service(db):
    """
    Get QuizService instance.

    Args:
        db: Database session

    Returns:
        QuizService instance
    """
    return QuizService(db)


def get_quiz_evaluator(db):
    """
    Get QuizEvaluator instance.

    Args:
        db: Database session

    Returns:
        QuizEvaluator instance
    """
    return QuizEvaluator(db)


def get_template_service(db):
    """
    Get QuizTemplateService instance.

    Args:
        db: Database session

    Returns:
        QuizTemplateService instance
    """
    return QuizTemplateService(db)


def get_monthly_quiz_service(db):
    """
    Get MonthlyQuizService instance.

    Args:
        db: Database session

    Returns:
        MonthlyQuizService instance
    """
    return MonthlyQuizService(db)


# Legacy compatibility aliases
QuizAnalyticsService = QuizAnalyzer  # Backward compatibility

# Public API exports
__all__ = [
    # Core Services
    "QuizService",
    "QuizTemplateService",
    "QuizSessionService",
    "QuizResponseService",
    "MonthlyQuizService",
    # Evaluation
    "QuizEvaluator",
    "QuizScorer",
    "QuizAnalyzer",
    "QuizAnalyticsService",  # Legacy alias
    # Template Management
    "TemplateLoader",
    "TemplateValidator",
    "TemplateVersionManager",
    "TemplateCache",
    # Utilities
    "ResponseUtils",
    "QuizMetricsCollector",
    "QuizReportGenerator",
    # Factory Functions
    "get_quiz_service",
    "get_quiz_evaluator",
    "get_template_service",
    "get_monthly_quiz_service",
]

__version__ = "1.0.0"
__consolidation__ = "QW-023"
__status__ = "Production Ready"
__files_consolidated__ = 12
__files_target__ = 3
__reduction__ = "75%"
