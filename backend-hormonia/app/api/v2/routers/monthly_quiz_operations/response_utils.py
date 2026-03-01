"""Shared response serializers for monthly quiz operations."""

from __future__ import annotations

from typing import Any, Optional, Dict


def build_quiz_response_detail(
    response: Any,
    *,
    template: Optional[Any] = None,
    session: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build enriched QuizResponseV2Detail from ORM rows."""
    return {
        "id": response.id,
        "patient_id": response.patient_id,
        "quiz_template_id": response.quiz_template_id,
        "quiz_session_id": response.quiz_session_id,
        "question_id": response.question_id,
        "question_text": response.question_text,
        "response_type": response.response_type,
        "response_value": response.response_value,
        "response_metadata": response.response_metadata or {},
        "other_text": response.other_text,
        "responded_at": response.responded_at,
        "created_at": response.created_at,
        "template_name": template.name if template else None,
        "template_version": template.version if template else None,
        "session_status": session.status if session else None,
    }
