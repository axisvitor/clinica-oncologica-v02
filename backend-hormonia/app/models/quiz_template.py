"""
Backward-compatible module for QuizTemplate.

Historically, QuizTemplate lived in app.models.quiz_template. The model was
moved to app.models.quiz, but some tests and imports still reference the
original path.
"""

from app.models.quiz import QuizTemplate

__all__ = ["QuizTemplate"]
