"""
Quiz response processing service.
Coordinates analysis of quiz responses and generation of comprehensive insights.
"""

import logging
from typing import Any
from uuid import UUID

from app.repositories.quiz import QuizSessionRepository, QuizResponseRepository
from app.repositories.patient import PatientRepository
from app.repositories.report import ReportRepository
from app.exceptions import NotFoundError, ValidationError
from app.services.reporting.quiz_report_generator.models import QuizAnalysisResult
from app.services.reporting.quiz_report_generator.aggregator import QuizDataAggregator
from app.services.reporting.quiz_report_generator.analyzer import QuizAnalyzer

logger = logging.getLogger(__name__)


class QuizResponseProcessor:
    """Service for processing quiz responses and generating insights."""

    def __init__(self, db: Any):
        self.db = db
        self.session_repo = QuizSessionRepository(db)
        self.response_repo = QuizResponseRepository(db)
        self.patient_repo = PatientRepository(db)
        self.report_repo = ReportRepository(db)

        # Initialize helper components
        self.aggregator = QuizDataAggregator(db)
        self.analyzer = QuizAnalyzer(db)

    async def process_completed_quiz(self, session_id: UUID) -> QuizAnalysisResult:
        """
        Process completed quiz session and generate comprehensive analysis.

        Args:
            session_id: Quiz session ID

        Returns:
            Complete quiz analysis result
        """
        try:
            logger.info(f"Processing completed quiz session {session_id}")

            # Get quiz session
            session = self.session_repo.get(session_id)
            if not session:
                raise NotFoundError(f"Quiz session {session_id} not found")

            if session.status != "completed":
                raise ValidationError(f"Quiz session {session_id} is not completed")

            # Get quiz responses
            responses = self.response_repo.get_by_session(session_id)  # type: ignore[attr-defined]

            # Calculate basic metrics
            metrics = await self.aggregator.calculate_quiz_metrics(session, responses)

            # Analyze response trends
            response_trends = await self.aggregator.analyze_response_trends(
                session.patient_id,
                session.quiz_template_id,
                responses,  # type: ignore[arg-type]
            )

            # Generate medical insights
            medical_insights = await self.analyzer.generate_medical_insights(
                session, responses, response_trends
            )

            # Calculate overall health score
            overall_health_score = await self.aggregator.calculate_health_score(
                responses, medical_insights
            )

            # Identify concern flags
            concern_flags = await self.analyzer.identify_concern_flags(
                responses, medical_insights
            )

            # Generate recommendations
            recommendations = await self.analyzer.generate_recommendations(
                medical_insights,
                concern_flags,
                session.patient_id,  # type: ignore[arg-type]
            )

            # Create analysis result
            analysis_result = QuizAnalysisResult(
                session_id=session_id,
                patient_id=session.patient_id,  # type: ignore[arg-type]
                metrics=metrics,
                response_trends=response_trends,
                medical_insights=medical_insights,
                overall_health_score=overall_health_score,
                concern_flags=concern_flags,
                recommendations=recommendations,
            )

            logger.info(f"Quiz analysis completed for session {session_id}")
            return analysis_result

        except Exception as e:
            logger.error(f"Error processing completed quiz: {e}")
            raise
