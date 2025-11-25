"""Celery tasks package for Hormonia Backend System."""

# Configuration and utilities
from .base import BaseTask, DatabaseTask, MessageTask, MonitoringTask, ReportTask, get_db_session
from .config import (
    task_configs, TaskConfig, TaskConfigurations,
    MessagingTaskConfig, AlertTaskConfig, MonitoringTaskConfig,
    QuizTaskConfig, FlowTaskConfig, ReportTaskConfig,
    TASK_ROUTES, TASK_ANNOTATIONS, DB_CONFIG, LOGGING_CONFIG,
    REDIS_CONFIG, MONITORING_CONFIG
)

# Messaging tasks
from app.tasks.messaging import (
    send_scheduled_message,
    process_scheduled_messages,
    retry_failed_messages,
    send_bulk_messages,
    cleanup_old_messages,
    generate_message_analytics
)

# Alert tasks
from app.tasks.alerts import (
    check_patient_alerts,
    process_alert_escalation,
    process_alert_notification,
    cleanup_resolved_alerts,
    generate_alert_metrics,
    periodic_alert_check,
    periodic_escalation_check
)

# Monitoring tasks
from app.tasks.monitoring import (
    system_health_check_task,
    performance_metrics_collection_task,
    bottleneck_detection_task,
    alert_monitoring_task,
    escalation_check_task,
    automated_recovery_task,
    cleanup_old_monitoring_data_task
)

# Quiz flow tasks
from app.tasks.quiz_flow import (
    send_quiz_question_task,
    process_quiz_response_task,
    check_quiz_triggers_task,
    cleanup_expired_quiz_sessions_task,
    send_quiz_progress_update_task,
    generate_quiz_report_task,
    send_quiz_link_reminder_task,
    monitor_quiz_links_task
)

# Flow tasks
from app.tasks.flows import (
    process_daily_flows,
    send_flow_message,
    cleanup_old_flow_data,
    process_monthly_quizzes,
    generate_quiz_report,
    monitor_flow_task_health
)

# Report tasks
from app.tasks.reports import (
    generate_patient_report,
    generate_scheduled_reports
)

# Follow-up tasks (QW-005)
from app.tasks.follow_up import (
    execute_pending_follow_ups,
    process_escalation_alerts,
    cleanup_old_contexts
)

__all__ = [
    # Base classes
    "BaseTask",
    "DatabaseTask",
    "MessageTask",
    "MonitoringTask",
    "ReportTask",
    "get_db_session",
    
    # Configuration
    "task_configs",
    "TaskConfig",
    "TaskConfigurations",
    "MessagingTaskConfig",
    "AlertTaskConfig",
    "MonitoringTaskConfig",
    "QuizTaskConfig",
    "FlowTaskConfig",
    "ReportTaskConfig",
    "TASK_ROUTES",
    "TASK_ANNOTATIONS",
    "DB_CONFIG",
    "LOGGING_CONFIG",
    "REDIS_CONFIG",
    "MONITORING_CONFIG",
    
    # Messaging tasks
    "send_scheduled_message",
    "process_scheduled_messages",
    "retry_failed_messages",
    "send_bulk_messages",
    "cleanup_old_messages",
    "generate_message_analytics",
    
    # Alert tasks
    "check_patient_alerts",
    "process_alert_escalation",
    "process_alert_notification",
    "cleanup_resolved_alerts",
    "generate_alert_metrics",
    "periodic_alert_check",
    "periodic_escalation_check",
    
    # Monitoring tasks
    "system_health_check_task",
    "performance_metrics_collection_task",
    "bottleneck_detection_task",
    "alert_monitoring_task",
    "escalation_check_task",
    "automated_recovery_task",
    "cleanup_old_monitoring_data_task",
    
    # Quiz flow tasks
    "send_quiz_question_task",
    "process_quiz_response_task",
    "check_quiz_triggers_task",
    "cleanup_expired_quiz_sessions_task",
    "send_quiz_progress_update_task",
    "generate_quiz_report_task",
    
    # Flow tasks
    "process_daily_flows",
    "send_flow_message",
    "cleanup_old_flow_data",
    "process_monthly_quizzes",
    "generate_quiz_report",
    "monitor_flow_task_health",
    
    # Report tasks
    "generate_patient_report",
    "generate_scheduled_reports",

    # Follow-up tasks (QW-005)
    "execute_pending_follow_ups",
    "process_escalation_alerts",
    "cleanup_old_contexts"
]