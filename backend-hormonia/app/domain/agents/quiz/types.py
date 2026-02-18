"""
Shared quiz agent domain types.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models.patient import Patient
from app.models.quiz import QuizSession, QuizTemplate


class QuizContext:
    """
    Context for quiz conduction and adaptation.

    Contains all state and metadata for an active quiz session,
    including patient data, progress tracking, and adaptation history.
    """

    def __init__(self):
        """Initialize quiz context with default values."""
        self.patient_id: Optional[UUID] = None
        self.session: Optional[QuizSession] = None
        self.template: Optional[QuizTemplate] = None
        self.patient_data: Optional[Patient] = None
        self.current_question: int = 0
        self.responses_so_far: List[Dict] = []
        self.mood_indicators: Dict[str, Any] = {}
        self.stress_level: float = 0.0
        self.engagement_score: float = 1.0
        self.knowledge_context: Dict[str, Any] = {}
        self.adaptation_history: List[Dict] = []
