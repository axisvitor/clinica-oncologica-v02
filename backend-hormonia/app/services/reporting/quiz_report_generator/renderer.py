"""
Report rendering and PDF generation.
Handles conversion of quiz analysis results into formatted reports.
"""

import logging
from typing import Any, Dict

from app.models.patient import Patient
from app.integrations.pdf_generator import PDFGenerator
from app.services.reporting.quiz_report_generator.models import QuizAnalysisResult

logger = logging.getLogger(__name__)


class ReportRenderer:
    """Renders quiz analysis results into structured reports and PDFs."""

    def __init__(self):
        self.pdf_generator = PDFGenerator()

    async def generate_report_content(
        self, analysis_result: QuizAnalysisResult, patient: Patient
    ) -> Dict[str, Any]:
        """Generate structured report content."""
        try:
            content = {
                "patient_info": {
                    "name": patient.name,
                    "age": getattr(patient, "age", None),
                    "treatment_type": getattr(
                        patient, "treatment_type", "Terapia hormonal"
                    ),
                    "enrollment_date": patient.enrollment_date.isoformat()
                    if patient.enrollment_date
                    else None,
                },
                "quiz_metrics": {
                    "completion_date": analysis_result.metrics.completion_date.isoformat(),
                    "completion_rate": analysis_result.metrics.completion_rate,
                    "total_questions": analysis_result.metrics.total_questions,
                    "answered_questions": analysis_result.metrics.answered_questions,
                    "response_quality_score": analysis_result.metrics.response_quality_score,
                    "average_response_time": analysis_result.metrics.average_response_time,
                },
                "health_assessment": {
                    "overall_health_score": analysis_result.overall_health_score,
                    "concern_flags": analysis_result.concern_flags,
                    "recommendations": analysis_result.recommendations,
                },
                "medical_insights": [
                    {
                        "type": insight.insight_type,
                        "description": insight.description,
                        "concern_level": insight.concern_level.value,
                        "recommendations": insight.recommendations,
                        "confidence_score": insight.confidence_score,
                    }
                    for insight in analysis_result.medical_insights
                ],
                "response_trends": [
                    {
                        "question_id": trend.question_id,
                        "question_text": trend.question_text,
                        "current_value": trend.current_value,
                        "trend_direction": trend.trend_direction.value,
                        "change_percentage": trend.change_percentage,
                        "significance_score": trend.significance_score,
                    }
                    for trend in analysis_result.response_trends
                ],
                "analysis_metadata": {
                    "analysis_timestamp": analysis_result.analysis_timestamp.isoformat(),
                    "session_id": str(analysis_result.session_id),
                },
            }

            return content

        except Exception as e:
            logger.error(f"Error generating report content: {e}")
            raise

    async def generate_pdf_report(
        self,
        analysis_result: QuizAnalysisResult,
        patient: Patient,
        content: Dict[str, Any],
    ) -> bytes:
        """Generate PDF report."""
        try:
            # Prepare data for PDF generation
            pdf_data = {
                "title": f"Relatório de Análise de Questionário - {patient.name}",
                "subtitle": f"Data: {analysis_result.metrics.completion_date.strftime('%d/%m/%Y')}",
                "patient_name": patient.name,
                "health_score": analysis_result.overall_health_score,
                "insights": analysis_result.medical_insights,
                "trends": analysis_result.response_trends,
                "recommendations": analysis_result.recommendations,
                "concern_flags": analysis_result.concern_flags,
                "metrics": analysis_result.metrics,
            }

            # Generate PDF using PDF generator service
            pdf_bytes = await self.pdf_generator.generate_quiz_report(pdf_data)

            return pdf_bytes

        except Exception as e:
            logger.error(f"Error generating PDF report: {e}")
            raise
