"""
Taskiq audit tasks — async-native replacements for Celery audit_cleanup tasks (M009-S04).

4 tasks migrated from Celery to Taskiq:
  1. cleanup_expired_logs          — cron 0 5 * * * (daily 02:00 BRT → 05:00 UTC)
  2. refresh_ai_performance_metrics — interval 3600s
  3. generate_daily_report         — cron 15 5 * * * (daily 02:15 BRT → 05:15 UTC)
  4. check_hipaa_compliance        — cron 45 5 * * * (daily 02:45 BRT → 05:45 UTC)

Key translation patterns from Celery → Taskiq:
  - `self` (bind=True) removed: SmartRetryMiddleware handles retries externally
  - `get_scoped_session()` preserved for sync ORM (AuditService, raw SQL)
  - Structured logging via log_task_start/success/error from taskiq_base
  - retry_on_error=True, max_retries=3, delay=300 matching Celery's _AUDIT_TASK_OPTIONS

Schedule labels (all 4 tasks are periodic):
  - cleanup_expired_logs:           cron 0 5 * * * (BRT 02:00 → UTC 05:00)
  - refresh_ai_performance_metrics: interval 3600s
  - generate_daily_report:          cron 15 5 * * * (BRT 02:15 → UTC 05:15)
  - check_hipaa_compliance:         cron 45 5 * * * (BRT 02:45 → UTC 05:45)
"""

import logging
from datetime import timedelta

from app.database import get_scoped_session
from app.services.audit import AuditService
from app.taskiq_broker import broker
from app.tasks.taskiq_base import log_task_error, log_task_start, log_task_success
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger("app.tasks.audit_taskiq")


# ===========================================================================
# 1. cleanup_expired_logs — periodic (cron daily 05:00 UTC = 02:00 BRT)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=300,
    schedule=[{"cron": "0 5 * * *"}],
)
async def cleanup_expired_logs() -> dict:
    """Clean up audit logs past their retention period.

    Removes expired logs and old cache performance logs (>30 days)
    to comply with HIPAA retention policies.

    Returns:
        Dict with cleanup statistics.
    """
    start_time = log_task_start("cleanup_expired_logs")

    try:
        with get_scoped_session() as db:
            audit_service = AuditService(db)

            deleted_count = audit_service.cleanup_expired_logs()

            # Clean up old cache performance logs (>30 days)
            cache_deleted = db.execute(
                """
                DELETE FROM audit_logs
                WHERE event_type IN ('ai_cache_hit', 'ai_cache_miss')
                AND timestamp < :cutoff_date
                """,
                {"cutoff_date": now_sao_paulo() - timedelta(days=30)},
            ).rowcount
            db.commit()

            result = {
                "status": "success",
                "deleted_audit_logs": deleted_count,
                "deleted_cache_logs": cache_deleted,
                "total_deleted": deleted_count + cache_deleted,
                "timestamp": now_sao_paulo().isoformat(),
            }

            log_task_success(
                "cleanup_expired_logs",
                start_time,
                total_deleted=result["total_deleted"],
            )
            return result

    except Exception as exc:
        log_task_error("cleanup_expired_logs", exc, start_time)
        raise


# ===========================================================================
# 2. refresh_ai_performance_metrics — periodic (interval 3600s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=300,
    schedule=[{"interval": {"seconds": 3600}}],
)
async def refresh_ai_performance_metrics() -> dict:
    """Refresh the materialized view for AI performance metrics.

    Runs hourly to update aggregated performance metrics
    used for monitoring and reporting dashboards.

    Returns:
        Dict with refresh statistics.
    """
    start_time = log_task_start("refresh_ai_performance_metrics")

    try:
        with get_scoped_session() as db:
            db.execute("SELECT refresh_ai_metrics();")
            db.commit()

            result = {
                "status": "success",
                "timestamp": now_sao_paulo().isoformat(),
            }

            log_task_success("refresh_ai_performance_metrics", start_time)
            return result

    except Exception as exc:
        log_task_error("refresh_ai_performance_metrics", exc, start_time)
        raise


# ===========================================================================
# 3. generate_daily_report — periodic (cron daily 05:15 UTC = 02:15 BRT)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=300,
    schedule=[{"cron": "15 5 * * *"}],
)
async def generate_daily_report() -> dict:
    """Generate daily AI audit summary report.

    Creates a summary of yesterday's AI usage including performance
    metrics, error rates, and security events.

    Returns:
        Dict with daily audit report data.
    """
    start_time = log_task_start("generate_daily_report")

    try:
        with get_scoped_session() as db:
            audit_service = AuditService(db)

            end_date = now_sao_paulo().replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = end_date - timedelta(days=1)

            metrics = audit_service.get_ai_performance_metrics(start_date, end_date)
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
                    for event in security_events[:10]
                ],
                "generated_at": now_sao_paulo().isoformat(),
            }

            log_task_success(
                "generate_daily_report",
                start_time,
                report_date=report["report_date"],
                security_events_count=report["security_events_count"],
            )
            return report

    except Exception as exc:
        log_task_error("generate_daily_report", exc, start_time)
        raise


# ===========================================================================
# 4. check_hipaa_compliance — periodic (cron daily 05:45 UTC = 02:45 BRT)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=300,
    schedule=[{"cron": "45 5 * * *"}],
)
async def check_hipaa_compliance() -> dict:
    """Check HIPAA compliance for audit logs.

    Verifies that all AI access to patient data is properly logged,
    retention policies are set, no PII is stored in logs, and
    security events are tracked.

    Returns:
        Dict with compliance check results.
    """
    start_time = log_task_start("check_hipaa_compliance")

    try:
        with get_scoped_session() as db:
            missing_retention = db.execute(
                """
                SELECT COUNT(*)
                FROM audit_logs
                WHERE event_type LIKE 'ai_%'
                AND retention_until IS NULL
                """
            ).scalar()

            missing_legal_basis = db.execute(
                """
                SELECT COUNT(*)
                FROM audit_logs
                WHERE event_type LIKE 'ai_%'
                AND data_subject_id IS NOT NULL
                AND legal_basis IS NULL
                """
            ).scalar()

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
                "compliant": (
                    missing_retention == 0
                    and missing_legal_basis == 0
                    and excessive_retention == 0
                ),
                "issues": {
                    "missing_retention_dates": missing_retention,
                    "missing_legal_basis": missing_legal_basis,
                    "excessive_retention_periods": excessive_retention,
                },
                "checked_at": now_sao_paulo().isoformat(),
            }

            if not compliance_status["compliant"]:
                logger.warning(
                    "HIPAA compliance issues detected: %s",
                    compliance_status["issues"],
                )

            log_task_success(
                "check_hipaa_compliance",
                start_time,
                compliant=compliance_status["compliant"],
            )
            return compliance_status

    except Exception as exc:
        log_task_error("check_hipaa_compliance", exc, start_time)
        raise


__all__ = [
    "cleanup_expired_logs",
    "refresh_ai_performance_metrics",
    "generate_daily_report",
    "check_hipaa_compliance",
]
