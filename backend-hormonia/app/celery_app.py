"""
Celery configuration for Hormonia Backend System.
Enhanced with asyncio compatibility for async task management.
"""
import asyncio
import logging
from typing import Optional
from celery import Celery
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
        "app.tasks.reports",
        "app.tasks.alerts",
        "app.tasks.quiz_link_tasks"
    ]
)

# Celery configuration with Redis optimization
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
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
        'retry_on_timeout': True,
        'retry_policy': {
            'timeout': 5.0
        }
    },
    
    # Task routing for flow tasks
    task_routes={
        'app.tasks.flows.process_daily_flows': {'queue': 'flows'},
        'app.tasks.flows.send_flow_message': {'queue': 'flows'},
        'app.tasks.flows.cleanup_old_flow_data': {'queue': 'maintenance'},
        'app.tasks.flows.monitor_flow_task_health': {'queue': 'monitoring'},
        'app.tasks.quiz_link_tasks.check_expired_links': {'queue': 'quiz'},
        'app.tasks.quiz_link_tasks.rotate_expired_token': {'queue': 'quiz'},
        'app.tasks.quiz_link_tasks.send_quiz_reminder': {'queue': 'quiz'},
        'app.tasks.quiz_link_tasks.fallback_to_whatsapp': {'queue': 'quiz'},
        'app.tasks.quiz_link_tasks.process_dead_letter_queue': {'queue': 'maintenance'},
        'app.tasks.quiz_link_tasks.monitor_resilience_metrics': {'queue': 'monitoring'},
    },
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Redis connection health checks
    broker_transport_options={
        'retry_on_timeout': True,
        'health_check_interval': 30,
        'retry_policy': {
            'timeout': 5.0
        }
    }
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "process-scheduled-messages": {
        "task": "process_scheduled_messages",
        "schedule": 30.0,  # Every 30 seconds
        "kwargs": {"limit": 100}
    },
    "retry-failed-messages": {
        "task": "retry_failed_messages", 
        "schedule": 300.0,  # Every 5 minutes
        "kwargs": {"limit": 50, "max_retries": 3}
    },
    "cleanup-old-messages": {
        "task": "cleanup_old_messages",
        "schedule": 86400.0,  # Daily
        "kwargs": {"days_old": 90}
    },
    "generate-message-analytics": {
        "task": "generate_message_analytics",
        "schedule": 3600.0,  # Every hour
        "kwargs": {"days_back": 7}
    },
    "process-daily-flows": {
        "task": "app.tasks.flows.process_daily_flows",
        "schedule": 3600.0,  # Every hour for production (was 60s for dev)
        "kwargs": {"limit": 100}
    },
    "cleanup-old-flow-data": {
        "task": "app.tasks.flows.cleanup_old_flow_data",
        "schedule": 86400.0,  # Daily
        "kwargs": {"days_old": 90}
    },
    "monitor-flow-task-health": {
        "task": "app.tasks.flows.monitor_flow_task_health",
        "schedule": 300.0,  # Every 5 minutes
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
        "kwargs": {"limit": 100}
    },
    "monitor-resilience-metrics": {
        "task": "app.tasks.quiz_link_tasks.monitor_resilience_metrics",
        "schedule": 3600.0,  # Every hour
    },
    "process-quiz-dead-letter-queue": {
        "task": "app.tasks.quiz_link_tasks.process_dead_letter_queue",
        "schedule": 7200.0,  # Every 2 hours
        "kwargs": {"limit": 50}
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
            logger.warning(f"Async context manager import failed for worker {sender}: {e}")
        except Exception as e:
            logger.warning(f"Async context manager initialization failed for worker {sender}: {e}")

        # Initialize session manager for thread-safe database operations
        try:
            from app.core.session_manager import initialize_session_manager
            initialize_session_manager()
            logger.info(f"Session manager initialized for worker {sender}")
        except ImportError as e:
            logger.warning(f"Session manager import failed for worker {sender}: {e}")
        except Exception as e:
            logger.warning(f"Session manager initialization failed for worker {sender}: {e}")

        # Initialize Redis connections with fallback
        try:
            # Try new redis manager first
            try:
                from app.core.redis_manager import get_redis_manager
                manager = get_redis_manager()
                # Test connection
                sync_client = manager.get_sync_client()
                sync_client.ping()
                logger.info(f"Redis manager initialized for worker {sender}")
            except ImportError:
                # Fallback to unified client
                from app.core.redis_unified import get_sync_redis
                # Pre-warm the connection
                get_sync_redis()
                logger.info(f"Redis unified client initialized for worker {sender}")
        except Exception as e:
            logger.warning(f"Redis initialization failed for worker {sender}: {e}")

        # Initialize monitoring if enabled (with graceful degradation)
        try:
            from app.config import settings
            if getattr(settings, 'MONITORING_ENABLED', False):
                try:
                    from app.monitoring.service_health_monitor import ServiceHealthMonitor
                    monitor = ServiceHealthMonitor()
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

        # Cleanup Redis connections (both old and new patterns)
        try:
            # Try new redis manager cleanup first
            try:
                from app.core.redis_manager import cleanup_redis_connections
                import asyncio
                loop = asyncio.get_event_loop()
                if not loop.is_closed():
                    loop.run_until_complete(cleanup_redis_connections())
                logger.info(f"Redis manager cleaned up for worker {sender}")
            except ImportError:
                # Unified client manages cleanup automatically
                logger.info(f"Redis unified client cleanup (auto-managed) for worker {sender}")
        except Exception as e:
            logger.warning(f"Redis cleanup failed for worker {sender}: {e}")

        # Cleanup monitoring resources
        try:
            from app.monitoring.service_health_monitor import ServiceHealthMonitor
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

        # Close event loop
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                # Cancel all tasks
                pending = asyncio.all_tasks(loop)
                if pending:
                    for task in pending:
                        task.cancel()
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

                # Close the loop
                loop.close()
        except RuntimeError:
            pass  # No event loop to close

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
        # Check if we're already in an async context
        try:
            asyncio.get_running_loop()
            logger.error("run_async_in_celery called from async context")
            raise RuntimeError("Cannot call run_async_in_celery from async context")
        except RuntimeError:
            # No running loop, safe to proceed
            pass

        # Import here to avoid circular imports
        from app.core.async_context_manager import safe_run_coroutine
        return safe_run_coroutine(coro, timeout=timeout, fallback_sync=True)
    except ImportError as e:
        logger.error(f"Failed to import async_context_manager: {e}")
        # Fallback to basic asyncio.run
        try:
            if timeout:
                async def timed_coro():
                    return await asyncio.wait_for(coro, timeout=timeout)
                return asyncio.run(timed_coro())
            else:
                return asyncio.run(coro)
        except Exception as fallback_error:
            logger.error(f"Fallback async execution failed: {fallback_error}")
            raise
    except Exception as e:
        logger.error(f"Failed to run async operation in Celery: {e}")
        raise


if __name__ == "__main__":
    celery_app.start()
