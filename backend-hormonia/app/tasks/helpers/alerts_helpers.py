"""Alerts helpers extracted from app.tasks.alerts."""

import logging
from typing import Any, Dict
from uuid import UUID

from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


_ALERT_METADATA_REDACTED_FIELDS = {
    "patient_name",
    "patient_email",
    "patient_phone",
    "patient_document",
    "cpf",
}


def _sanitize_alert_metadata(alert_data: Dict[str, Any]) -> Dict[str, Any]:
    """Drop high-risk PII fields before storing arbitrary task metadata."""
    if not isinstance(alert_data, dict):
        return {}
    return {
        key: value
        for key, value in alert_data.items()
        if key not in _ALERT_METADATA_REDACTED_FIELDS
    }


def _build_patient_context(db, patient_id: UUID) -> Dict[str, Any]:
    """Build context data for alert evaluation."""
    try:
        from app.repositories.message import MessageRepository
        from app.repositories.quiz import QuizResponseRepository

        message_repo = MessageRepository(db)
        quiz_repo = QuizResponseRepository(db)

        recent_messages = message_repo.get_recent_for_patient(
            patient_id, limit=10, days=7
        )

        recent_quizzes = quiz_repo.get_recent_for_patient(patient_id, limit=5, days=30)

        return {
            "patient_id": str(patient_id),
            "recent_messages": [
                {
                    "id": str(m.id),
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in (recent_messages or [])
            ],
            "recent_quizzes": [
                {
                    "id": str(q.id),
                    "score": getattr(q, "score", None),
                    "completed_at": q.completed_at.isoformat()
                    if hasattr(q, "completed_at") and q.completed_at
                    else None,
                }
                for q in (recent_quizzes or [])
            ],
            "evaluation_time": now_sao_paulo().isoformat(),
        }

    except Exception as e:
        logger.warning(f"Failed to build patient context: {e}")
        return {
            "patient_id": str(patient_id),
            "evaluation_time": now_sao_paulo().isoformat(),
            "error": str(e),
        }
