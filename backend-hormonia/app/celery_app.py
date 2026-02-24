"""
Celery configuration for Hormonia Backend System.
Enhanced with asyncio compatibility for async task management.
"""

import asyncio
import logging
from typing import Optional
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init, worker_process_shutdown
from app.config import settings

logger = logging.getLogger(__name__)

# Create Celery instance
celery_app = Celery(
    "hormonia",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.messaging",
        "app.tasks.flows",
        "app.tasks.flow_automation",
        "app.tasks.reports",
        "app.tasks.alerts",
        "app.tasks.quiz_link_tasks",
        "app.tasks.quiz_flow",
        "app.tasks.quiz_flow.cleanup_tasks",
        "app.tasks.quiz_flow.question_tasks",
        "app.tasks.quiz_flow.response_tasks",
        "app.tasks.quiz_flow.trigger_tasks",
        "app.tasks.saga_retry",
        "app.tasks.saga_monitoring",
        "app.tasks.follow_up",
        "app.tasks.webhook_dlq",
        "app.tasks.monitoring",
        "app.tasks.audit_cleanup",
        "app.tasks.lgpd_tasks",
        "app.tasks.lgpd.reencrypt_patients",
    ],
)

# Celery configuration with Redis optimization
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=settings.CELERY_ENABLE_TZ_NORMALIZATION,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Redis-specific optimizations
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_pool_limit=10,
    # Result backend settings
    result_backend_transport_options={
        "retry_on_timeout": True,
        "retry_policy": {"timeout": 5.0},
    },
    # Simplified task routing - all tasks use default 'celery' queue
    # Note: Railway workers don't use -Q flags, so custom queues would never be consumed
    # task_routes removed for simplicity - tasks go to default queue
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Redis connection health checks
    broker_transport_options={
        "retry_on_timeout": True,
        "health_check_interval": 30,
        "retry_policy": {"timeout": 5.0},
    },
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "process-scheduled-messages": {
        "task": "app.tasks.messaging.process_scheduled_messages",
        "schedule": 60.0,  # Every 60 seconds (reduced burst pressure)
        "kwargs": {"limit": 60},
    },
    "retry-failed-messages": {
        "task": "app.tasks.messaging.retry_failed_messages",
        "schedule": 300.0,  # Every 5 minutes
        "kwargs": {"limit": 50, "max_retries": 3},
    },
    # FIX: Welcome messages can get stuck in PENDING if WhatsApp fails during registration
    "retry-pending-welcome-messages": {
        "task": "app.tasks.messaging.retry_pending_welcome_messages",
        "schedule": 600.0,  # Every 10 minutes
        "kwargs": {"limit": 50, "min_age_minutes": 5, "max_age_hours": 24},
    },
    "cleanup-old-messages": {
        "task": "app.tasks.messaging.cleanup_old_messages",
        "schedule": 86400.0,  # Daily
        "kwargs": {"days_old": 90},
    },
    "generate-message-analytics": {
        "task": "app.tasks.messaging.generate_message_analytics",
        "schedule": 3600.0,  # Every hour
        "kwargs": {"days_back": 7},
    },
    "cleanup-old-flow-data": {
        "task": "app.tasks.flows.cleanup_tasks.cleanup_old_flow_data",
        "schedule": 86400.0,  # Daily
        "kwargs": {"days_old": 90},
    },
    "monitor-flow-task-health": {
        "task": "app.tasks.flows.monitoring.monitor_flow_task_health",
        "schedule": 300.0,  # Every 5 minutes
    },
    "evaluate-flow-alerts": {
        "task": "app.tasks.flows.monitoring.evaluate_flow_alerts",
        "schedule": 900.0,  # Every 15 minutes
    },
    "generate-scheduled-reports": {
        "task": "app.tasks.reports.generate_scheduled_reports",
        "schedule": 3600.0,  # Every hour
    },
    "check-patient-alerts": {
        "task": "app.tasks.alerts.check_patient_alerts",
        "schedule": 300.0,  # Every 5 minutes
    },
    # Quiz link resilience tasks
    "check-expired-quiz-links": {
        "task": "app.tasks.quiz_link_tasks.check_expired_links",
        "schedule": 1800.0,  # Every 30 minutes
        "kwargs": {"limit": 100},
    },
    "monitor-resilience-metrics": {
        "task": "app.tasks.quiz_link_tasks.monitor_resilience_metrics",
        "schedule": 3600.0,  # Every hour
    },
    "process-quiz-dead-letter-queue": {
        "task": "app.tasks.quiz_link_tasks.process_dead_letter_queue",
        "schedule": 7200.0,  # Every 2 hours
        "kwargs": {"limit": 50},
    },
    # Monthly quiz processor: checks eligible patients and triggers monthly quizzes
    "process-monthly-quizzes": {
        "task": "app.tasks.flows.monthly_tasks.process_monthly_quizzes",
        "schedule": 3600.0,  # Every hour
        "kwargs": {"limit": 100},
    },
    # Saga retry tasks
    "scan-and-retry-failed-sagas": {
        "task": "app.tasks.saga_retry.scan_and_retry_failed_sagas",
        "schedule": 300.0,  # Every 5 minutes
    },
    "cleanup-old-completed-sagas": {
        "task": "app.tasks.saga_retry.cleanup_old_completed_sagas",
        "schedule": 86400.0,  # Daily
    },
    # Saga monitoring tasks
    "check-orphaned-sagas": {
        "task": "app.tasks.saga_monitoring.check_orphaned_sagas",
        "schedule": 3600.0,  # Every hour
    },
    "check-long-running-sagas": {
        "task": "app.tasks.saga_monitoring.check_long_running_sagas",
        "schedule": 900.0,  # Every 15 minutes
    },
    "generate-saga-metrics": {
        "task": "app.tasks.saga_monitoring.generate_saga_metrics",
        "schedule": 3600.0,  # Every hour
    },
    # DLQ processing tasks
    "process-whatsapp-dlq": {
        "task": "app.tasks.messaging.process_whatsapp_dlq",
        "schedule": 600.0,  # Every 10 minutes
        "kwargs": {"limit": 50},
    },
    # Quiz session expiration cleanup (HIGH-004)
    "cleanup-expired-quiz-sessions": {
        "task": "app.tasks.quiz_flow.cleanup_tasks.cleanup_expired_quiz_sessions_task",
        "schedule": 7200.0,  # Every 2 hours
        "kwargs": {"max_age_hours": 48},
    },
    # Flow automation tasks (automatic patient engagement)
    "check-pending-flows": {
        "task": "app.tasks.flow_automation.check_and_start_pending_flows",
        "schedule": 900.0,  # Every 15 minutes
    },
    "send-daily-flow-questions": {
        "task": "app.tasks.flows.flow_tasks.process_daily_flows",
        "schedule": crontab(hour=8, minute=0),  # Daily at 08:00 America/Sao_Paulo
    },
    "send-daily-reminders": {
        "task": "app.tasks.flow_automation.send_daily_reminders",
        "schedule": crontab(hour=9, minute=0),  # Daily at 09:00 AM America/Sao_Paulo
    },
    "resume-paused-flows": {
        "task": "app.tasks.flow_automation.resume_paused_flows",
        "schedule": 3600.0,  # Every hour — checks auto_resume_at timestamps on paused flows
    },
    "cleanup-expired-quiz-links": {
        "task": "app.tasks.flow_automation.cleanup_expired_quiz_links",
        "schedule": 86400.0,  # Daily
    },
    # Follow-up system tasks - Patient daily engagement
    "execute-pending-follow-ups": {
        "task": "app.tasks.follow_up.execute_pending_follow_ups",
        "schedule": 300.0,  # Every 5 minutes
    },
    "process-escalation-alerts": {
        "task": "app.tasks.follow_up.process_escalation_alerts",
        "schedule": 600.0,  # Every 10 minutes
    },
    "cleanup-old-contexts": {
        "task": "app.tasks.follow_up.cleanup_old_contexts",
        "schedule": crontab(hour=3, minute=0),  # Daily at 03:00 AM America/Sao_Paulo
    },
    # Webhook DLQ processing (MEDIUM-005)
    "process-webhook-dlq": {
        "task": "app.tasks.webhook_dlq.process_webhook_dlq",
        "schedule": 60.0,  # Every minute
    },
    "cleanup-old-webhook-dlq-events": {
        "task": "app.tasks.webhook_dlq.cleanup_old_dlq_events",
        "schedule": crontab(hour=3, minute=0),  # Daily at 03:00 AM America/Sao_Paulo
        "kwargs": {"days_old": 7},
    },
    "monitor-webhook-dlq-health": {
        "task": "app.tasks.webhook_dlq.monitor_dlq_health",
        "schedule": 300.0,  # Every 5 minutes
    },
    # Monitoring tasks (migrated from Cloud Scheduler)
    "system-health-check": {
        "task": "monitoring.system_health_check",
        "schedule": 300.0,  # Every 5 minutes
    },
    "performance-metrics-collection": {
        "task": "monitoring.performance_metrics_collection",
        "schedule": 600.0,  # Every 10 minutes
    },
    "bottleneck-detection": {
        "task": "monitoring.bottleneck_detection",
        "schedule": 900.0,  # Every 15 minutes
    },
    "alert-monitoring": {
        "task": "monitoring.alert_monitoring",
        "schedule": 300.0,  # Every 5 minutes
    },
    "escalation-check": {
        "task": "monitoring.escalation_check",
        "schedule": 1800.0,  # Every 30 minutes
    },
    "automated-recovery": {
        "task": "monitoring.automated_recovery",
        "schedule": 3600.0,  # Every hour
    },
    "data-integrity-guardrails": {
        "task": "monitoring.data_integrity_guardrails",
        "schedule": 900.0,  # Every 15 minutes
    },
    "cleanup-monitoring-data": {
        "task": "monitoring.cleanup_old_data",
        "schedule": 86400.0,  # Daily
    },
    # Audit cleanup (migrated from APScheduler)
    "audit-cleanup": {
        "task": "audit.cleanup_expired_logs",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    "audit-refresh-performance-metrics": {
        "task": "audit.refresh_performance_metrics",
        "schedule": 3600.0,  # Every hour
    },
    "audit-generate-daily-report": {
        "task": "audit.generate_daily_report",
        "schedule": crontab(hour=2, minute=15),  # Daily at 02:15 AM America/Sao_Paulo
    },
    "audit-check-hipaa-compliance": {
        "task": "audit.check_hipaa_compliance",
        "schedule": crontab(hour=2, minute=45),  # Daily at 02:45 AM America/Sao_Paulo
    },
    "lgpd-audit-cleanup": {
        "task": "lgpd.cleanup_expired_audit_logs",
        "schedule": crontab(hour=2, minute=30),  # Daily at 02:30 AM America/Sao_Paulo
        "kwargs": {"batch_size": 1000},
    },
}


# Celery worker initialization with asyncio support
@worker_process_init.connect
def init_worker_process(signal, sender, **kwargs):
    """Initialize worker process with proper asyncio support and modular architecture."""
    try:
        # Initialize event loop first
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.info(f"Celery worker {sender} initialized with asyncio support")

        # Import here to avoid circular imports - delayed imports for initialization
        try:
            from app.core.async_context_manager import event_loop_context

            # Initialize async context manager
            event_loop_context.get_or_create_event_loop()
            logger.debug(f"Async context manager initialized for worker {sender}")
        except ImportError as e:
            logger.warning(
                f"Async context manager import failed for worker {sender}: {e}"
            )
        except Exception as e:
            logger.warning(
                f"Async context manager initialization failed for worker {sender}: {e}"
            )

        # Initialize session manager for thread-safe database operations
        try:
            from app.core.session_manager import initialize_session_manager

            initialize_session_manager()
            logger.info(f"Session manager initialized for worker {sender}")
        except ImportError as e:
            logger.warning(f"Session manager import failed for worker {sender}: {e}")
        except Exception as e:
            logger.warning(
                f"Session manager initialization failed for worker {sender}: {e}"
            )

        # Initialize Redis connections through the canonical RedisManager.
        try:
            from app.core.redis_manager import get_redis_manager

            manager = get_redis_manager()
            sync_client = manager.get_sync_client()
            sync_client.ping()
            logger.info(f"Redis manager initialized for worker {sender}")
        except Exception as e:
            logger.warning(f"Redis initialization failed for worker {sender}: {e}")

        # Initialize monitoring if enabled (with graceful degradation)
        try:
            from app.config import settings

            if getattr(settings, "MONITORING_ENABLED", False):
                try:
                    from app.monitoring.service_health_monitor import (
                        ServiceHealthMonitor,
                    )

                    ServiceHealthMonitor()
                    logger.info(f"Monitoring initialized for worker {sender}")
                except ImportError:
                    logger.info(f"Monitoring not available for worker {sender}")
        except Exception as e:
            logger.warning(f"Monitoring initialization failed for worker {sender}: {e}")

    except Exception as e:
        logger.error(f"Failed to initialize Celery worker {sender}: {e}")
        # Don't fail the worker startup, just log the error


@worker_process_shutdown.connect
def shutdown_worker_process(signal, sender, **kwargs):
    """Clean shutdown of worker process with proper resource cleanup."""
    try:
        logger.info(f"Shutting down Celery worker {sender}")

        # Cleanup session manager resources
        try:
            from app.core.session_manager import cleanup_session_manager

            cleanup_session_manager()
            logger.info(f"Session manager cleaned up for worker {sender}")
        except Exception as e:
            logger.warning(f"Session manager cleanup failed for worker {sender}: {e}")

        # Cleanup Redis connections.
        try:
            from app.core.redis_manager import cleanup_redis_connections

            cleanup_loop = asyncio.new_event_loop()
            try:
                cleanup_loop.run_until_complete(cleanup_redis_connections())
            finally:
                cleanup_loop.close()
            logger.info(f"Redis manager cleaned up for worker {sender}")
        except Exception as e:
            logger.warning(f"Redis cleanup failed for worker {sender}: {e}")

        # Cleanup monitoring resources
        try:
            # Cleanup monitoring if needed
            logger.info(f"Monitoring cleaned up for worker {sender}")
        except Exception as e:
            logger.warning(f"Monitoring cleanup failed for worker {sender}: {e}")

        # Cleanup async resources
        try:
            from app.core.async_context_manager import cleanup_async_context

            cleanup_async_context()
        except Exception as e:
            logger.warning(f"Async context cleanup failed for worker {sender}: {e}")

        # Close cached async helper loops
        try:
            from app.utils.async_helpers import cleanup_all_event_loops

            closed_loops = cleanup_all_event_loops()
            logger.info("Closed %s cached event loop(s) for worker %s", closed_loops, sender)
        except Exception as e:
            logger.warning(f"Event loop cleanup failed for worker {sender}: {e}")

        logger.info(f"Celery worker {sender} shutdown completed")

    except Exception as e:
        logger.error(f"Error during Celery worker shutdown: {e}")


# Helper function for async tasks in Celery
def run_async_in_celery(coro, timeout: Optional[float] = 300):
    """
    Helper function to run async coroutines in Celery tasks.

    Args:
        coro: Coroutine to run
        timeout: Timeout in seconds (default 5 minutes)

    Usage:
        @celery_app.task
        def my_task():
            async def async_work():
                # async operations here
                pass
            return run_async_in_celery(async_work())
    """
    try:
        # Disallow nested loop usage from async contexts.
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is not None:
            logger.error("run_async_in_celery called from async context")
            raise RuntimeError("Cannot call run_async_in_celery from async context")

        # Import here to avoid circular imports
        from app.core.async_context_manager import safe_run_coroutine

        return safe_run_coroutine(coro, timeout=timeout, fallback_sync=True)
    except ImportError as e:
        logger.error(f"Failed to import async_context_manager: {e}")
        # Fallback to canonical async helper in sync contexts.
        try:
            from app.utils.async_helpers import run_async

            effective_timeout = int(timeout) if timeout else 300
            return run_async(coro, timeout=effective_timeout)
        except Exception as fallback_error:
            logger.error(f"Fallback async execution failed: {fallback_error}")
            raise
    except Exception as e:
        logger.error(f"Failed to run async operation in Celery: {e}")
        raise


if __name__ == "__main__":
    celery_app.start()
