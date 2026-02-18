"""
Monthly quiz related tasks.

This module contains Celery tasks for processing monthly quizzes and generating
quiz reports for patients.
"""

import logging
from typing import Any
from uuid import UUID
from celery.exceptions import MaxRetriesExceededError

from app.task_queue import task_queue as celery_app
from app.database import get_scoped_session
from app.utils.async_helpers import run_async

from .base import FlowTaskBase
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True, base=FlowTaskBase, max_retries=None, default_retry_delay=None
)
def process_monthly_quizzes(self, limit: int = 50) -> dict[str, Any]:
    """
    Process monthly quiz triggers for eligible patients.

    Args:
        limit: Maximum number of patients to check

    Returns:
        dict[str, Any]: Quiz processing results containing:
            - total_patients: Number of patients eligible for quiz
            - quizzes_sent: Number of quizzes successfully sent
            - failed: Number of failed quiz sends
            - skipped: Number of skipped patients
            - results: List of individual processing results

    Raises:
        Exception: If quiz processing fails
    """
    from app.config.settings.tasks import QUIZ_MAX_RETRIES, QUIZ_PROCESSING_TIMEOUT

    # Apply task limits from settings if not already set
    if not self.max_retries:
        self.max_retries = QUIZ_MAX_RETRIES

    try:
        logger.info(f"Starting monthly quiz processing for up to {limit} patients")

        with get_scoped_session() as db:
            # Initialize quiz trigger service
            from app.domain.quizzes.integration.flow_integration.utils import (
                get_quiz_trigger_service,
            )

            quiz_trigger_service = get_quiz_trigger_service(db)

            results = run_async(
                quiz_trigger_service.check_and_trigger_monthly_quizzes(limit=limit),
                timeout=QUIZ_PROCESSING_TIMEOUT,
            )

            logger.info(f"Monthly quiz processing completed: {results}")
            return results

    except Exception as e:
        logger.error(f"Monthly quiz processing failed: {e}")

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            from app.config.settings.tasks import get_retry_countdown

            retry_delay = get_retry_countdown(
                self.request.retries, QUIZ_PROCESSING_TIMEOUT
            )
            logger.info(
                f"Retrying monthly quiz processing in {retry_delay} seconds (attempt {self.request.retries + 1})"
            )
            raise self.retry(countdown=retry_delay, exc=e)
        else:
            logger.error(
                f"Monthly quiz processing failed after {self.max_retries} attempts"
            )
            raise MaxRetriesExceededError(
                f"Task failed after {self.max_retries} retries: {e}"
            )


@celery_app.task(
    bind=True, base=FlowTaskBase, max_retries=None, default_retry_delay=None
)
def generate_quiz_report(self, session_id: str) -> dict[str, Any]:
    """
    Generate medical report from completed quiz session.

    Args:
        session_id (str): Quiz session ID as string

    Returns:
        dict[str, Any]: Report generation result containing:
            - status: Success or failure status
            - session_id: Quiz session identifier
            - report_id: Generated report identifier
            - generated_at: Timestamp when report was generated

    Raises:
        Exception: If report generation fails after all retries
    """
    from app.config.settings.tasks import (
        QUIZ_MAX_RETRIES,
        QUIZ_REPORT_TIMEOUT,
        QUIZ_REPORT_RETRY_DELAY,
    )

    # Apply task limits from settings if not already set
    if not self.max_retries:
        self.max_retries = QUIZ_MAX_RETRIES

    try:
        logger.info(f"Generating quiz report for session {session_id}")

        with get_scoped_session() as db:
            # Initialize quiz report generator
            from app.services.reporting.quiz_report_generator import (
                get_quiz_report_generator,
            )

            report_generator = get_quiz_report_generator(db)

            report_id = run_async(
                report_generator.generate_quiz_report(UUID(session_id)),
                timeout=QUIZ_REPORT_TIMEOUT,
            )

            result = {
                "status": "success",
                "session_id": session_id,
                "report_id": str(report_id),
                "generated_at": now_sao_paulo().isoformat(),
            }

            logger.info(f"Quiz report generated successfully: {result}")
            return result

    except Exception as e:
        logger.error(f"Quiz report generation failed: {e}")

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            from app.config.settings.tasks import get_retry_countdown

            retry_delay = get_retry_countdown(
                self.request.retries, QUIZ_REPORT_RETRY_DELAY
            )
            logger.info(
                f"Retrying quiz report generation in {retry_delay} seconds (attempt {self.request.retries + 1})"
            )
            raise self.retry(countdown=retry_delay, exc=e)
        else:
            logger.error(
                f"Quiz report generation failed after {self.max_retries} attempts"
            )
            raise MaxRetriesExceededError(
                f"Task failed after {self.max_retries} retries: {e}"
            )
