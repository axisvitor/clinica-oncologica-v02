"""
Celery tasks for flow processing - modular package structure.

This package exports all Celery tasks for backward compatibility and autodiscovery.
"""

from .base import FlowTaskBase, send_critical_alert_sync
from .flow_tasks import (
    process_daily_flows,
    process_daily_flows_async,
)
from .monthly_tasks import (
    process_monthly_quizzes,
    generate_quiz_report,
)
from .batch_tasks import (
    _process_single_patient_flow,
    _get_message_template_for_day,
)
from .cleanup_tasks import cleanup_old_flow_data
from .followup_retry import retry_failed_followup_send
from .monitoring import monitor_flow_task_health, evaluate_flow_alerts
from .send_retry import retry_failed_flow_send
from .stuck_detection import detect_stuck_flows

# Export all for Celery autodiscovery
__all__ = [
    # Base classes and helpers
    "FlowTaskBase",
    "send_critical_alert_sync",
    # Flow processing tasks
    "process_daily_flows",
    "process_daily_flows_async",
    # Monthly quiz tasks
    "process_monthly_quizzes",
    "generate_quiz_report",
    # Batch processing helpers
    "_process_single_patient_flow",
    "_get_message_template_for_day",
    # Cleanup tasks
    "cleanup_old_flow_data",
    # Monitoring tasks
    "monitor_flow_task_health",
    "evaluate_flow_alerts",
    # Retry tasks
    "retry_failed_followup_send",
    "retry_failed_flow_send",
    "detect_stuck_flows",
]
