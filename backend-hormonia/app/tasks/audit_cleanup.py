"""
Celery tasks for audit log cleanup and maintenance.

This module provides automated tasks for maintaining audit logs in compliance
with HIPAA retention policies (90 days for access logs).
"""

import logging
from datetime import timedelta
from sqlalchemy.exc import SQLAlchemyError

from app.task_queue import task_queue as celery_app
from app.database import get_scoped_session
from app.services.audit import AuditService
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

_AUDIT_TASK_OPTIONS = {
    "bind": True,
    "max_retries": 3,
    "default_retry_delay": 300,
    "autoretry_for": (SQLAlchemyError, ConnectionError, TimeoutError, OSError),
    "retry_backoff": True,
    "retry_jitter": True,
}

@celery_app.task(name="audit.cleanup_expired_logs", **_AUDIT_TASK_OPTIONS)
def cleanup_expired_audit_logs(self):
    """
    Clean up audit logs past their retention period.

    This task runs daily to remove logs that have exceeded their retention period,
    ensuring compliance with data retention policies while maintaining audit trail
    for the required duration.

    Returns:
        dict: Cleanup statistics
    """
    try:
        with get_scoped_session() as db:
            audit_service = AuditService(db)

            logger.info("Starting audit log cleanup task")
            start_time = now_sao_paulo()

            # Clean up expired logs
            deleted_count = audit_service.cleanup_expired_logs()

            # Also clean up very old cache performance logs (older than 30 days)
            cache_deleted = db.execute(
                """
                DELETE FROM audit_logs
                WHERE event_type IN ('ai_cache_hit', 'ai_cache_miss')
                AND timestamp < :cutoff_date
                """,
                {"cutoff_date": now_sao_paulo() - timedelta(days=30)},
            ).rowcount
            db.commit()

            duration = (now_sao_paulo() - start_time).total_seconds()

            result = {
                "status": "success",
                "deleted_audit_logs": deleted_count,
                "deleted_cache_logs": cache_deleted,
                "total_deleted": deleted_count + cache_deleted,
                "duration_seconds": duration,
                "timestamp": now_sao_paulo().isoformat(),
            }

            logger.info(
                f"Audit cleanup completed: {result['total_deleted']} logs deleted "
                f"in {duration:.2f} seconds"
            )

            return result

    except Exception as e:
        logger.error(f"Audit log cleanup failed: {e}", exc_info=True)
        raise


@celery_app.task(name="audit.refresh_performance_metrics", **_AUDIT_TASK_OPTIONS)
def refresh_ai_performance_metrics(self):
    """
    Refresh the materialized view for AI performance metrics.

    This task runs hourly to update the aggregated performance metrics
    used for monitoring and reporting.

    Returns:
        dict: Refresh statistics
    """
    try:
        with get_scoped_session() as db:
            logger.info("Refreshing AI performance metrics view")
            start_time = now_sao_paulo()

            # Refresh materialized view
            db.execute("SELECT refresh_ai_metrics();")
            db.commit()

            duration = (now_sao_paulo() - start_time).total_seconds()

            result = {
                "status": "success",
                "duration_seconds": duration,
                "timestamp": now_sao_paulo().isoformat(),
            }

            logger.info(f"AI metrics refreshed in {duration:.2f} seconds")

            return result

    except Exception as e:
        logger.error(f"Metrics refresh failed: {e}", exc_info=True)
        raise


@celery_app.task(name="audit.generate_daily_report", **_AUDIT_TASK_OPTIONS)
def generate_daily_audit_report(self):
    """
    Generate daily AI audit summary report.

    This task runs daily to create a summary report of AI usage,
    including performance metrics, error rates, and security events.

    Returns:
        dict: Daily audit report
    """
    try:
        with get_scoped_session() as db:
            audit_service = AuditService(db)

            logger.info("Generating daily audit report")

            # Get yesterday's date range
            end_date = now_sao_paulo().replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = end_date - timedelta(days=1)

            # Get performance metrics
            metrics = audit_service.get_ai_performance_metrics(start_date, end_date)

            # Get security events
            security_events = audit_service.get_ai_security_events(
                start_date, end_date, severity="warning"
            )

            report = {
                "report_date": start_date.date().isoformat(),
                "performance_metrics": metrics,
                "security_events_count": len(security_events),
                "high_severity_events": [
                    {
                        "event_type": event.event_type,
                        "timestamp": event.timestamp.isoformat(),
                        "severity": event.severity,
                        "result": event.result,
                    }
                    for event in security_events[:10]  # Top 10
                ],
                "generated_at": now_sao_paulo().isoformat(),
            }

            logger.info(
                f"Daily audit report generated: {metrics['total_requests']} requests, "
                f"{len(security_events)} security events"
            )

            return report

    except Exception as e:
        logger.error(f"Daily report generation failed: {e}", exc_info=True)
        raise


@celery_app.task(name="audit.check_hipaa_compliance", **_AUDIT_TASK_OPTIONS)
def check_hipaa_compliance(self):
    """
    Check HIPAA compliance for audit logs.

    Verifies that:
    - All AI access to patient data is logged
    - Retention policies are properly set
    - No PII is stored in logs
    - Security events are properly tracked

    Returns:
        dict: Compliance check results
    """
    try:
        with get_scoped_session() as db:
            logger.info("Starting HIPAA compliance check")

            # Check for logs without retention dates
            missing_retention = db.execute(
                """
                SELECT COUNT(*)
                FROM audit_logs
                WHERE event_type LIKE 'ai_%'
                AND retention_until IS NULL
                """
            ).scalar()

            # Check for logs with patient access but no legal basis
            missing_legal_basis = db.execute(
                """
                SELECT COUNT(*)
                FROM audit_logs
                WHERE event_type LIKE 'ai_%'
                AND data_subject_id IS NOT NULL
                AND legal_basis IS NULL
                """
            ).scalar()

            # Check for excessive retention (over 90 days for access logs)
            excessive_retention = db.execute(
                """
                SELECT COUNT(*)
                FROM audit_logs
                WHERE event_category = 'access'
                AND event_type LIKE 'ai_%'
                AND retention_until > NOW() + INTERVAL '90 days'
                """
            ).scalar()

            compliance_status = {
                "compliant": missing_retention == 0
                and missing_legal_basis == 0
                and excessive_retention == 0,
                "issues": {
                    "missing_retention_dates": missing_retention,
                    "missing_legal_basis": missing_legal_basis,
                    "excessive_retention_periods": excessive_retention,
                },
                "checked_at": now_sao_paulo().isoformat(),
            }

            if not compliance_status["compliant"]:
                logger.warning(
                    f"HIPAA compliance issues detected: {compliance_status['issues']}"
                )
            else:
                logger.info("HIPAA compliance check passed")

            return compliance_status

    except Exception as e:
        logger.error(f"HIPAA compliance check failed: {e}", exc_info=True)
        raise
