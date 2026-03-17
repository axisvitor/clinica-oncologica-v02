"""
Taskiq report tasks — async-native replacements for Celery reports tasks (M009-S04).

2 tasks migrated from Celery to Taskiq:
  1. generate_patient_report   — on-demand, retry-enabled
  2. generate_scheduled_reports — interval 3600s

Key translation patterns from Celery → Taskiq:
  - `run_async()` bridge removed: ReportService.generate_report() called with `await` directly
  - `self.retry(exc=exc, countdown=300)` → SmartRetryMiddleware handles retry
  - `.apply_async(args=[pid, rtype])` → `await generate_patient_report.kiq(pid, rtype)`
  - Pure helpers imported from app.tasks.reports (no duplication)
  - `get_scoped_session()` preserved for sync ORM (ReportService constructor, PDF gen)
  - Structured logging via log_task_start/success/error from taskiq_base

Schedule labels (1 of 2 tasks is periodic):
  - generate_scheduled_reports: interval 3600s
"""

import logging
from datetime import date, timedelta
from pathlib import Path
from uuid import UUID

from app.config import settings
from app.database import get_scoped_session
from app.schemas.report import ReportGenerationRequest
from app.services.reporting import ReportService
from app.taskiq_broker import broker
from app.tasks.taskiq_base import log_task_error, log_task_start, log_task_success

# Pure helpers imported from Celery module — zero logic duplication (D007).
from app.tasks.helpers.reports_helpers import (
    _build_safe_report_path,
    _get_system_actor_uuid,
    _sanitize_report_type,
)

logger = logging.getLogger("app.tasks.reports_taskiq")


# ===========================================================================
# 1. generate_patient_report — on-demand (no schedule label)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=300,
)
async def generate_patient_report(patient_id: str, report_type: str) -> dict:
    """Generate report for a specific patient.

    Async-native Taskiq replacement for the Celery generate_patient_report task.
    Calls ReportService.generate_report() with await directly (no run_async bridge).

    Args:
        patient_id: Patient UUID as string.
        report_type: Type of report to generate (e.g., 'medical', 'summary').

    Returns:
        Dict with report status, report_id, and output_path.
    """
    start_time = log_task_start(
        "generate_patient_report", patient_id=patient_id, report_type=report_type
    )

    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        logger.warning(
            "Invalid patient_id for report generation",
            extra={"patient_id": patient_id},
        )
        log_task_error(
            "generate_patient_report",
            ValueError("invalid_patient_id"),
            start_time,
            patient_id=patient_id,
        )
        return {"status": "failed", "error": "invalid_patient_id", "patient_id": patient_id}

    try:
        with get_scoped_session() as db:
            service = ReportService(db)
            request = ReportGenerationRequest(
                patient_id=patient_uuid,
                period_start=date.today() - timedelta(days=30),
                period_end=date.today(),
            )
            # ReportService.generate_report is async — call directly (no run_async bridge)
            report = await service.generate_report(
                request,
                _get_system_actor_uuid(),
            )
            pdf_content = service.generate_pdf_report(report.id)
            reports_dir = Path(settings.UPLOAD_DIRECTORY) / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            output_path = _build_safe_report_path(reports_dir, patient_uuid, report_type)
            with open(output_path, "wb") as f:
                f.write(pdf_content)

            result = {
                "status": "completed",
                "report_id": str(report.id),
                "output_path": str(output_path),
            }

            log_task_success(
                "generate_patient_report",
                start_time,
                patient_id=patient_id,
                report_id=result["report_id"],
            )
            return result

    except Exception as exc:
        log_task_error(
            "generate_patient_report",
            exc,
            start_time,
            patient_id=patient_id,
            report_type=report_type,
        )
        raise


# ===========================================================================
# 2. generate_scheduled_reports — periodic (interval 3600s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=600,
    schedule=[{"interval": {"seconds": 3600}}],
)
async def generate_scheduled_reports() -> dict:
    """Generate all scheduled reports.

    Fetches scheduled reports from ReportService and dispatches
    generate_patient_report for each via .kiq() (Taskiq cross-dispatch).

    Returns:
        Dict with scheduling status and count.
    """
    start_time = log_task_start("generate_scheduled_reports")

    try:
        with get_scoped_session() as db:
            service = ReportService(db)
            scheduled = service.get_scheduled_reports()

            dispatched_count = 0
            for item in scheduled:
                pid = str(item.get("patient_id"))
                rtype = item.get("report_type", "medical")
                await generate_patient_report.kiq(pid, rtype)
                dispatched_count += 1

            result = {
                "status": "scheduled",
                "count": dispatched_count,
            }

            log_task_success(
                "generate_scheduled_reports",
                start_time,
                dispatched_count=dispatched_count,
            )
            return result

    except Exception as exc:
        log_task_error("generate_scheduled_reports", exc, start_time)
        raise


__all__ = ["generate_patient_report", "generate_scheduled_reports"]
