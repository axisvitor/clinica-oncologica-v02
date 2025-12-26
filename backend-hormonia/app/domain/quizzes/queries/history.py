"""History queries for patient quiz sessions."""

from __future__ import annotations

from typing import List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.quiz import QuizSession
from app.repositories.quiz import QuizSessionRepository
from app.schemas.monthly_quiz import MonthlyQuizLinkResponse

import logging

logger = logging.getLogger(__name__)


class HistoryQuery:
    """Queries for patient quiz session history."""

    def __init__(self, db: Session, status_query):
        """Initialize history query.

        Args:
            db: Database session
            status_query: StatusQuery instance for getting link status
        """
        self.db = db
        self.session_repository = QuizSessionRepository(db)
        self.status_query = status_query

    async def get_patient_history(
        self, patient_id: UUID, limit: int = 10, offset: int = 0
    ) -> List[MonthlyQuizLinkResponse]:
        """Get quiz session history for a specific patient.

        Args:
            patient_id: Patient identifier
            limit: Maximum number of sessions to return
            offset: Offset for pagination

        Returns:
            List of quiz link responses ordered by recency
        """
        # FAST 404 CHECK: Verify patient exists before querying sessions
        if not self.status_query._check_patient_exists_fast(str(patient_id)):
            logger.info(f"Fast 404 for patient history {str(patient_id)[:8]}...")
            return []

        sessions = (
            self.db.query(QuizSession)
            .filter(
                and_(
                    QuizSession.patient_id == patient_id,
                    QuizSession.session_metadata.isnot(None),
                )
            )
            .order_by(QuizSession.started_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        results = []
        for session in sessions:
            try:
                link_response = await self.status_query.get_link_status(session.id)
                results.append(link_response)
            except Exception as e:
                logger.error(f"Error getting status for session {session.id}: {str(e)}")
                continue

        return results
