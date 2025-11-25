"""
Quiz report generator service.
Main service for generating comprehensive medical reports from quiz analysis.
"""
import logging
from typing import Any
from uuid import UUID
from datetime import datetime

from app.models.report import Report, ReportType, ReportStatus
from app.repositories.report import ReportRepository
from app.repositories.patient import PatientRepository
from app.exceptions import NotFoundError
from app.services.websocket_events import websocket_events
from app.schemas.websocket import WebSocketEventType
from app.services.reporting.quiz_report_generator.processor import QuizResponseProcessor
from app.services.reporting.quiz_report_generator.renderer import ReportRenderer
from app.services.reporting.quiz_report_generator.models import QuizAnalysisResult

logger = logging.getLogger(__name__)


class QuizReportGenerator:
    """Service for generating medical reports from quiz analysis."""

    def __init__(self, db: Any):
        self.db = db
        self.report_repo = ReportRepository(db)
        self.patient_repo = PatientRepository(db)

        # Initialize helper components
        self.response_processor = QuizResponseProcessor(db)
        self.renderer = ReportRenderer()

    async def generate_quiz_report(self, session_id: UUID) -> UUID:
        """
        Generate comprehensive medical report from quiz session.

        Args:
            session_id: Quiz session ID

        Returns:
            Generated report ID
        """
        try:
            logger.info(f"Generating quiz report for session {session_id}")

            # Process quiz analysis
            analysis_result = await self.response_processor.process_completed_quiz(session_id)

            # Get patient information
            patient = self.patient_repo.get(analysis_result.patient_id)
            if not patient:
                raise NotFoundError(f"Patient {analysis_result.patient_id} not found")

            # Generate report content
            report_content = await self.renderer.generate_report_content(analysis_result, patient)

            # Generate PDF
            pdf_data = await self.renderer.generate_pdf_report(analysis_result, patient, report_content)

            # Create report record
            report = Report(
                patient_id=analysis_result.patient_id,
                type=ReportType.QUIZ_ANALYSIS,
                title=f"Análise de Questionário - {datetime.now().strftime('%d/%m/%Y')}",
                content=report_content,
                pdf_data=pdf_data,
                status=ReportStatus.COMPLETED,
                generated_at=datetime.utcnow(),
                metadata={
                    "quiz_session_id": str(session_id),
                    "analysis_timestamp": analysis_result.analysis_timestamp.isoformat(),
                    "health_score": analysis_result.overall_health_score,
                    "concern_flags": analysis_result.concern_flags,
                    "insights_count": len(analysis_result.medical_insights)
                }
            )

            created_report = self.report_repo.create(report)
            self.db.commit()

            # Publish WebSocket event
            if websocket_events is not None:  # type: ignore[union-attr]
                await websocket_events.publish_report_event(  # type: ignore[union-attr,attr-defined]
                    event_type=WebSocketEventType.REPORT_GENERATED,  # type: ignore[attr-defined]
                    patient_id=analysis_result.patient_id,
                    report_id=created_report.id,  # type: ignore[arg-type]
                    report_type=ReportType.QUIZ_ANALYSIS.value,
                    title=created_report.title
                )

            # Notify healthcare providers if concerns identified
            if analysis_result.concern_flags:
                await self._notify_healthcare_providers(created_report, analysis_result)

            logger.info(f"Quiz report generated successfully: {created_report.id}")
            return created_report.id  # type: ignore[return-value]

        except Exception as e:
            logger.error(f"Error generating quiz report: {e}")
            raise

    async def _notify_healthcare_providers(self,
                                         report: Report,
                                         analysis_result: QuizAnalysisResult):
        """Notify healthcare providers about concerning findings."""
        try:
            # Determine notification priority
            priority = "normal"
            if "critical_medical_concerns" in analysis_result.concern_flags:
                priority = "critical"
            elif "high_concern_indicators" in analysis_result.concern_flags:
                priority = "high"

            # Create notification data
            notification_data = {
                "patient_id": str(analysis_result.patient_id),
                "report_id": str(report.id),
                "concern_flags": analysis_result.concern_flags,
                "health_score": analysis_result.overall_health_score,
                "priority": priority,
                "summary": f"Questionário completado com {len(analysis_result.concern_flags)} indicadores de atenção"
            }

            # Publish notification event
            if websocket_events is not None:  # type: ignore[union-attr]
                await websocket_events.publish_alert_event(  # type: ignore[union-attr,attr-defined]
                    event_type=WebSocketEventType.ALERT_CREATED,  # type: ignore[attr-defined]
                    patient_id=analysis_result.patient_id,
                    alert_type="quiz_concerns",
                    priority=priority,
                    message=notification_data["summary"],
                    metadata=notification_data
                )

            logger.info(f"Healthcare providers notified about quiz concerns for patient {analysis_result.patient_id}")

        except Exception as e:
            logger.error(f"Error notifying healthcare providers: {e}")
