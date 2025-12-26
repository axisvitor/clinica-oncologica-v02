"""
Quiz flow state enumerations.
"""

from __future__ import annotations

from enum import Enum


class QuizFlowState(Enum):
    """Quiz flow states."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    AWAITING_RESPONSE = "awaiting_response"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
