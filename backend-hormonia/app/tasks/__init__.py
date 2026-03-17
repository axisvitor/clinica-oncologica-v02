"""Taskiq tasks package for Hormonia Backend System.

All task functions are implemented as async Taskiq tasks in *_taskiq.py modules.
This init re-exports the public task names so that ``from app.tasks import X``
continues to work across the codebase.
"""

# --- Messaging tasks ---
from .messaging_taskiq import (
    send_scheduled_message,
    process_scheduled_messages,
    retry_failed_messages,
    send_bulk_messages,
    cleanup_old_messages,
    generate_message_analytics,
    process_whatsapp_dlq,
    process_dlq_messages,
    retry_pending_welcome_messages,
)

# --- Flow tasks ---
from .flows_taskiq import (
    process_daily_flows,
    cleanup_old_flow_data,
    process_monthly_quizzes,
    generate_quiz_report,
    monitor_flow_task_health,
    detect_stuck_flows,
    retry_failed_flow_send,
    retry_failed_followup_send,
    send_daily_reminders,
    send_flow_day_for_patient,
    check_and_start_pending_flows,
    cleanup_expired_quiz_links,
    evaluate_flow_alerts,
    resume_paused_flows,
)

# --- Alert tasks ---
from .alerts_taskiq import (
    check_patient_alerts,
    process_alert_escalation,
    process_alert_notification,
    cleanup_resolved_alerts,
    generate_alert_metrics,
    periodic_alert_check,
    periodic_escalation_check,
)

# --- Follow-up tasks ---
from .follow_up_taskiq import (
    execute_pending_follow_ups,
    process_escalation_alerts,
    cleanup_old_contexts,
)

# --- LGPD compliance tasks ---
from .lgpd_taskiq import (
    persist_lgpd_audit_log,
    cleanup_expired_lgpd_audit_logs,
)

# --- Report tasks ---
from .reports_taskiq import (
    generate_patient_report,
    generate_scheduled_reports,
)

# --- Monitoring tasks ---
from .monitoring_taskiq import (
    system_health_check,
    performance_metrics_collection,
    bottleneck_detection,
    alert_monitoring,
    escalation_check,
    automated_recovery,
    cleanup_old_data,
    data_integrity_guardrails,
)

# --- Quiz flow tasks ---
from .quiz_flow_taskiq import (
    send_quiz_question,
    send_quiz_progress_update,
    process_quiz_response,
    check_quiz_triggers,
    send_quiz_link_reminder,
    monitor_quiz_links,
    cleanup_expired_quiz_sessions,
)

# --- Quiz link tasks ---
from .quiz_link_taskiq import (
    check_expired_links,
    fallback_to_whatsapp,
    monitor_resilience_metrics,
    process_dead_letter_queue,
    rotate_expired_token,
    send_quiz_reminder,
)

# --- Saga retry tasks ---
from .saga_retry_taskiq import (
    scan_and_retry_failed_sagas,
    retry_patient_onboarding_saga,
    cleanup_old_completed_sagas,
)

# --- Saga monitoring tasks ---
from .saga_monitoring_taskiq import (
    check_long_running_sagas,
    check_orphaned_sagas,
    generate_saga_metrics,
)

# --- Audit tasks ---
from .audit_taskiq import (
    generate_daily_report,
    cleanup_expired_logs,
    check_hipaa_compliance,
    refresh_ai_performance_metrics,
)

# --- Webhook DLQ tasks ---
from .webhook_dlq_taskiq import (
    process_webhook_dlq,
    cleanup_old_dlq_events,
    monitor_dlq_health,
)

__all__ = [
    # Messaging
    "send_scheduled_message",
    "process_scheduled_messages",
    "retry_failed_messages",
    "send_bulk_messages",
    "cleanup_old_messages",
    "generate_message_analytics",
    "process_whatsapp_dlq",
    "process_dlq_messages",
    "retry_pending_welcome_messages",
    # Flows
    "process_daily_flows",
    "cleanup_old_flow_data",
    "process_monthly_quizzes",
    "generate_quiz_report",
    "monitor_flow_task_health",
    "detect_stuck_flows",
    "retry_failed_flow_send",
    "retry_failed_followup_send",
    "send_daily_reminders",
    "send_flow_day_for_patient",
    "check_and_start_pending_flows",
    "cleanup_expired_quiz_links",
    "evaluate_flow_alerts",
    "resume_paused_flows",
    # Alerts
    "check_patient_alerts",
    "process_alert_escalation",
    "process_alert_notification",
    "cleanup_resolved_alerts",
    "generate_alert_metrics",
    "periodic_alert_check",
    "periodic_escalation_check",
    # Follow-up
    "execute_pending_follow_ups",
    "process_escalation_alerts",
    "cleanup_old_contexts",
    # LGPD
    "persist_lgpd_audit_log",
    "cleanup_expired_lgpd_audit_logs",
    # Reports
    "generate_patient_report",
    "generate_scheduled_reports",
    # Monitoring
    "system_health_check",
    "performance_metrics_collection",
    "bottleneck_detection",
    "alert_monitoring",
    "escalation_check",
    "automated_recovery",
    "cleanup_old_data",
    "data_integrity_guardrails",
    # Quiz flow
    "send_quiz_question",
    "send_quiz_progress_update",
    "process_quiz_response",
    "check_quiz_triggers",
    "send_quiz_link_reminder",
    "monitor_quiz_links",
    "cleanup_expired_quiz_sessions",
    # Quiz link
    "check_expired_links",
    "fallback_to_whatsapp",
    "monitor_resilience_metrics",
    "process_dead_letter_queue",
    "rotate_expired_token",
    "send_quiz_reminder",
    # Saga retry
    "scan_and_retry_failed_sagas",
    "retry_patient_onboarding_saga",
    "cleanup_old_completed_sagas",
    # Saga monitoring
    "check_long_running_sagas",
    "check_orphaned_sagas",
    "generate_saga_metrics",
    # Audit
    "generate_daily_report",
    "cleanup_expired_logs",
    "check_hipaa_compliance",
    "refresh_ai_performance_metrics",
    # Webhook DLQ
    "process_webhook_dlq",
    "cleanup_old_dlq_events",
    "monitor_dlq_health",
]
