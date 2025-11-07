"""
Quiz Agent Package - Modular quiz conduction system.

This package provides a refactored, modular quiz conduction system that replaces
the monolithic quiz_conductor.py with 6 focused modules:

- conductor.py: Main orchestration and task routing
- session_coordinator.py: Session lifecycle management
- question_presenter.py: Question delivery and personalization
- response_handler.py: Response processing and interpretation
- progress_tracker.py: Progress tracking and mood analysis
- notification_manager.py: Messaging and notifications

Public API:
    QuizConductor - Main quiz conductor agent
    QuizConductorAgent - Alias for backward compatibility
    SessionCoordinator - Session management
    QuestionPresenter - Question delivery
    ResponseHandler - Response processing
    ProgressTracker - Progress tracking
    NotificationManager - Notification handling
    QuizContext - Quiz context container
    QuizAdaptationType - Adaptation type enum
"""

from .conductor import QuizConductor, QuizConductorAgent
from .session_coordinator import SessionCoordinator, QuizContext
from .question_presenter import QuestionPresenter
from .response_handler import ResponseHandler
from .progress_tracker import ProgressTracker
from .notification_manager import NotificationManager, QuizAdaptationType

__all__ = [
    # Main conductor
    "QuizConductor",
    "QuizConductorAgent",  # Backward compatibility alias

    # Specialized modules
    "SessionCoordinator",
    "QuestionPresenter",
    "ResponseHandler",
    "ProgressTracker",
    "NotificationManager",

    # Context and types
    "QuizContext",
    "QuizAdaptationType",
]

__version__ = "2.0.0"
__author__ = "Hormonia Development Team"
