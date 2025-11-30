"""Celery tasks for report generation."""
import asyncio
import logging
from datetime import date, timedelta
from pathlib import Path
from uuid import UUID

from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.schemas.report import ReportGenerationRequest
from app.services.reporting import ReportService

logger = logging.getLogger(__name__)


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
    db = SessionLocal()
    try:
        service = ReportService(db)
        request = ReportGenerationRequest(
            patient_id=UUID(patient_id),
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
        )
        report = asyncio.run(service.generate_report(request, UUID("00000000-0000-0000-0000-000000000000")))
        pdf_content = service.generate_pdf_report(report.id)
        reports_dir = Path(settings.UPLOAD_DIRECTORY) / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        output_path = reports_dir / f"{patient_id}_{report_type}.pdf"
        with open(output_path, "wb") as f:
            f.write(pdf_content)
        logger.info(f"Generated report {report.id} for patient {patient_id}")
        return {"status": "completed", "report_id": str(report.id), "output_path": str(output_path)}
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(f"Error generating report for patient {patient_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


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
    db = SessionLocal()
    try:
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
    finally:
        db.close()
