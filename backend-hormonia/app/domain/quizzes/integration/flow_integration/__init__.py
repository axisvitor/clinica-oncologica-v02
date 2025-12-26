"""
Quiz trigger and flow integration system.

Handles monthly quiz initiation, conversational quiz presentation, and flow integration.

This package provides:
- QuizFlowState: Enum for quiz flow states
- QuizTriggerService: Service for triggering monthly quizzes
- ConversationalQuizService: Service for conversational quiz presentation
- Utility functions for quiz flow operations
"""

from __future__ import annotations

from .enums import QuizFlowState
from .trigger_service import QuizTriggerService
from .response_handler import ConversationalQuizService
from .utils import (
    get_quiz_trigger_service,
    get_conversational_quiz_service,
    trigger_monthly_quiz_via_link,
)

__all__ = [
    # Enums
    "QuizFlowState",
    # Services
    "QuizTriggerService",
    "ConversationalQuizService",
    # Factory functions
    "get_quiz_trigger_service",
    "get_conversational_quiz_service",
    # Utility functions
    "trigger_monthly_quiz_via_link",
]
