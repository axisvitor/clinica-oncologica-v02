"""
Quiz trigger and flow integration system.

Handles monthly quiz initiation, conversational quiz presentation, and flow integration.

This package provides:
- QuizFlowState: Enum for quiz flow states
- QuizTriggerService: Service for triggering monthly quizzes
- ConversationalQuizService: Service for conversational quiz presentation
"""

from __future__ import annotations

from .enums import QuizFlowState
from .response_handler import ConversationalQuizService
from .trigger_service import QuizTriggerService

__all__ = [
    # Enums
    "QuizFlowState",
    # Services
    "QuizTriggerService",
    "ConversationalQuizService",
]
