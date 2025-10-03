"""
Job Scheduler

Configures and starts APScheduler for background jobs.

Jobs scheduled:
- audit_cleanup: Daily at 2 AM (clean records > 90 days)
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .audit_cleanup import AuditCleanupJob

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: AsyncIOScheduler = None


def configure_scheduler() -> AsyncIOScheduler:
    """
    Configure and return the job scheduler.

    Returns:
        Configured AsyncIOScheduler instance
    """
    global scheduler

    if scheduler is not None:
        logger.warning("Scheduler already configured")
        return scheduler

    scheduler = AsyncIOScheduler()

    # Add audit cleanup job - runs daily at 2 AM
    scheduler.add_job(
        AuditCleanupJob.run,
        trigger=CronTrigger(hour=2, minute=0),  # 2:00 AM daily
        id="audit_cleanup",
        name="Audit Trail Cleanup (90 days retention)",
        replace_existing=True,
        max_instances=1,  # Only one instance running at a time
    )

    logger.info("Job scheduler configured with %d jobs", len(scheduler.get_jobs()))

    return scheduler


def start_scheduler() -> None:
    """Start the job scheduler"""
    global scheduler

    if scheduler is None:
        scheduler = configure_scheduler()

    if not scheduler.running:
        scheduler.start()
        logger.info("Job scheduler started successfully")
    else:
        logger.warning("Scheduler already running")


def stop_scheduler() -> None:
    """Stop the job scheduler"""
    global scheduler

    if scheduler is not None and scheduler.running:
        scheduler.shutdown()
        logger.info("Job scheduler stopped")
    else:
        logger.warning("Scheduler not running")


def get_scheduler() -> AsyncIOScheduler:
    """
    Get the scheduler instance.

    Returns:
        The global scheduler instance or None if not configured
    """
    return scheduler
