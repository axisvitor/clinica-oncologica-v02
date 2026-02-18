"""
Shared payload builders for monthly quiz message factories.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from app.domain.messaging.core.message_service.config import MessageTemplate


def build_monthly_quiz_reminder_payload(
    *,
    sanitize_context: Callable[[Dict[str, Any]], Dict[str, Any]],
    templates: Dict[str, str],
    patient_name: str,
    link: str,
    quiz_session_id: str,
    hours_remaining: int,
    delivery_method: str,
    link_metadata_key: str,
) -> tuple[str, Dict[str, Any]]:
    """Build reminder message content and metadata consistently."""
    safe_context = sanitize_context(
        {
            "patient_name": patient_name,
            "link": link,
            "hours_remaining": hours_remaining,
        }
    )
    content = templates["reminder"].format(**safe_context)
    metadata = {
        "quiz_session_id": quiz_session_id,
        link_metadata_key: link,
        "hours_remaining": hours_remaining,
        "message_type": "monthly_quiz_reminder",
        "template_type": MessageTemplate.MONTHLY_QUIZ_LINK_REMINDER.value,
        "delivery_method": delivery_method,
    }
    return content, metadata
