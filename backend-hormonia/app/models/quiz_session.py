"""
Backward-compatible module for QuizSession.

QuizSession lives in app.models.quiz, but some tests still import from
app.models.quiz_session.
"""

from app.models.quiz import QuizSession

__all__ = ["QuizSession"]
