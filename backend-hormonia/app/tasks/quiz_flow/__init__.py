"""
Quiz Flow Tasks Package.

Backward compatibility layer - re-exports all tasks for existing imports.
"""

from __future__ import annotations

from app.tasks.quiz_flow.question_tasks import (
    send_quiz_question_task,
    send_quiz_progress_update_task,
)
from app.tasks.quiz_flow.response_tasks import (
    process_quiz_response_task,
    generate_quiz_report_task,
)
from app.tasks.quiz_flow.monitoring_tasks import (
    check_quiz_triggers_task,
    monitor_quiz_links_task,
    send_quiz_link_reminder_task,
)
from app.tasks.quiz_flow.cleanup_tasks import (
    cleanup_expired_quiz_sessions_task,
    _notify_doctor_of_expired_session,
    _resume_patient_flow_after_expiration,
)
from app.tasks.quiz_flow.helpers import (
    _trigger_whatsapp_fallback,
    _notify_providers_of_quiz_completion,
)

__all__ = [
    # Question tasks
    "send_quiz_question_task",
    "send_quiz_progress_update_task",
    # Response tasks
    "process_quiz_response_task",
    "generate_quiz_report_task",
    # Monitoring tasks
    "check_quiz_triggers_task",
    "monitor_quiz_links_task",
    "send_quiz_link_reminder_task",
    # Cleanup tasks
    "cleanup_expired_quiz_sessions_task",
    # Helper functions (for backward compatibility)
    "_notify_doctor_of_expired_session",
    "_resume_patient_flow_after_expiration",
    "_trigger_whatsapp_fallback",
    "_notify_providers_of_quiz_completion",
]
