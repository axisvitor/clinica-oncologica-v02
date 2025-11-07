"""
Quiz Conductor Agent - DEPRECATED - Use app.domain.agents.quiz instead.

This module provides backward compatibility for the legacy quiz_conductor.
The functionality has been refactored into 6 focused modules in app.domain.agents.quiz:

- conductor.py: Main orchestration and task routing (~300 lines)
- session_coordinator.py: Session lifecycle management (~250 lines)
- question_presenter.py: Question delivery and personalization (~250 lines)
- response_handler.py: Response processing and interpretation (~250 lines)
- progress_tracker.py: Progress tracking and mood analysis (~200 lines)
- notification_manager.py: Messaging and notifications (~200 lines)

MIGRATION PATH:
Old: from app.agents.communication.quiz_conductor import QuizConductorAgent
New: from app.domain.agents.quiz import QuizConductor

The new implementation provides the same functionality with better:
- Modularity and separation of concerns
- Testability with focused components
- Maintainability with smaller, focused files
- Performance through specialized modules
"""

import warnings
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

# Import from new location
from app.domain.agents.quiz import (
    QuizConductor as NewQuizConductor,
    QuizConductorAgent as NewQuizConductorAgent,
    QuizContext,
    QuizAdaptationType
)


class QuizConductorAgent:
    """
    DEPRECATED: Use app.domain.agents.quiz.QuizConductor instead.

    This wrapper provides backward compatibility but will be removed in a future version.
    All new code should use the modular implementation at app.domain.agents.quiz.

    The new implementation splits the original 1,460-line monolith into 6 focused modules,
    providing the same functionality with better organization and maintainability.
    """

    def __init__(self, db_session: Session, **kwargs):
        """
        Initialize QuizConductorAgent with deprecation warning.

        Args:
            db_session: SQLAlchemy database session
            **kwargs: Additional arguments passed to QuizConductor
        """
        warnings.warn(
            "\n\n"
            "=" * 80 + "\n"
            "DEPRECATION WARNING: app.agents.communication.quiz_conductor.QuizConductorAgent\n"
            "=" * 80 + "\n"
            "This module is deprecated and will be removed in a future version.\n"
            "\n"
            "Please update your imports:\n"
            "  Old: from app.agents.communication.quiz_conductor import QuizConductorAgent\n"
            "  New: from app.domain.agents.quiz import QuizConductor\n"
            "\n"
            "The functionality has been refactored into 6 focused modules:\n"
            "  - conductor.py: Main orchestration\n"
            "  - session_coordinator.py: Session management\n"
            "  - question_presenter.py: Question delivery\n"
            "  - response_handler.py: Response processing\n"
            "  - progress_tracker.py: Progress tracking\n"
            "  - notification_manager.py: Notifications\n"
            "\n"
            "All existing functionality is preserved with improved modularity.\n"
            "=" * 80 + "\n",
            DeprecationWarning,
            stacklevel=2
        )

        # Create instance of new implementation
        self._impl = NewQuizConductorAgent(db_session=db_session, **kwargs)

    def __getattr__(self, name):
        """
        Delegate all attribute access to the new implementation.

        This ensures complete backward compatibility while using the new modular code.
        """
        return getattr(self._impl, name)

    def __repr__(self):
        """Return string representation."""
        return f"<QuizConductorAgent (DEPRECATED) wrapping {self._impl!r}>"


# Also export the context and enum for backward compatibility
__all__ = [
    "QuizConductorAgent",
    "QuizContext",
    "QuizAdaptationType",
]


# Helper function for lazy imports (preserved for compatibility)
def _get_knowledge_graph():
    """Lazy import for KnowledgeGraph to prevent startup failures."""
    import logging
    try:
        from app.memory.knowledge_graph import KnowledgeGraph
        return KnowledgeGraph
    except ImportError as e:
        logging.warning(f"KnowledgeGraph import failed: {e}")
        return None
