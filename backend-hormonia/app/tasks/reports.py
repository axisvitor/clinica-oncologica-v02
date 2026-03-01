"""Celery tasks for report generation."""

import logging
from datetime import date, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from app.task_queue import task_queue as celery_app
from app.config import settings
from app.database import get_scoped_session
from app.schemas.report import ReportGenerationRequest
from app.services.reporting import ReportService
from app.utils.async_helpers import run_async

logger = logging.getLogger(__name__)
_SYSTEM_ACTOR_UUID_SEED = "app.tasks.reports.system-actor"
_DEFAULT_REPORT_TYPE = "medical"


def _get_system_actor_uuid() -> UUID:
    """Return deterministic non-zero UUID for system-triggered report generation."""
    actor_uuid = uuid5(NAMESPACE_URL, _SYSTEM_ACTOR_UUID_SEED)
    return actor_uuid if actor_uuid.int != 0 else UUID(int=1)


def _sanitize_report_type(report_type: str) -> str:
    normalized = "".join(
        char for char in str(report_type).strip().lower() if char.isalnum() or char in {"-", "_"}
    ).strip("-_")
    return normalized or _DEFAULT_REPORT_TYPE


def _build_safe_report_path(base_dir: Path, patient_uuid: UUID, report_type: str) -> Path:
    safe_filename = f"{patient_uuid}_{_sanitize_report_type(report_type)}.pdf"
    output_path = (base_dir / safe_filename).resolve()
    base_dir_resolved = base_dir.resolve()
    if base_dir_resolved not in output_path.parents:
        raise ValueError("Invalid report output path")
    return output_path


@celery_app.task(bind=True, max_retries=3)
def generate_patient_report(self, patient_id: str, report_type: str):
    """
    Generate report for specific patient.

    Args:
        patient_id (str): Patient UUID as string
        report_type (str): Type of report to generate (e.g., 'medical', 'summary')

    Returns:
        dict[str, Any]: Dictionary containing:
            - status: Completion status ('completed')
            - report_id: Generated report UUID as string
            - output_path: Path to generated PDF file

    Raises:
        Exception: If report generation fails after all retries
    """
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        logger.warning("Invalid patient_id for report generation", extra={"patient_id": patient_id})
        return {"status": "failed", "error": "invalid_patient_id", "patient_id": patient_id}

    try:
        with get_scoped_session() as db:
            service = ReportService(db)
            request = ReportGenerationRequest(
                patient_id=patient_uuid,
                period_start=date.today() - timedelta(days=30),
                period_end=date.today(),
            )
            report = run_async(
                service.generate_report(
                    request,
                    _get_system_actor_uuid(),
                )
            )
            pdf_content = service.generate_pdf_report(report.id)
            reports_dir = Path(settings.UPLOAD_DIRECTORY) / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            output_path = _build_safe_report_path(reports_dir, patient_uuid, report_type)
            with open(output_path, "wb") as f:
                f.write(pdf_content)
            logger.info(f"Generated report {report.id} for patient {patient_id}")
            return {
                "status": "completed",
                "report_id": str(report.id),
                "output_path": str(output_path),
            }
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(
            f"Error generating report for patient {patient_id}: {exc}", exc_info=True
        )
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(bind=True, max_retries=3)
def generate_scheduled_reports(self):
    """
    Generate all scheduled reports.

    Returns:
        dict[str, Any]: Dictionary containing:
            - status: Scheduling status ('scheduled')
            - tasks: List of task IDs for queued reports
            - count: Number of reports scheduled

    Raises:
        Exception: If scheduling fails after all retries
    """
    try:
        with get_scoped_session() as db:
            service = ReportService(db)
            scheduled = service.get_scheduled_reports()
            tasks = []
            for item in scheduled:
                pid = str(item.get("patient_id"))
                rtype = item.get("report_type", "medical")
                task = generate_patient_report.apply_async(args=[pid, rtype])
                tasks.append(task.id)
            logger.info(f"Queued {len(tasks)} scheduled reports")
            return {"status": "scheduled", "tasks": tasks, "count": len(tasks)}
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(f"Error generating scheduled reports: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=600)
