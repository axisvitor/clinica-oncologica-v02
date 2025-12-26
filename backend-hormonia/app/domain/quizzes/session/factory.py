"""Factory for creating quiz sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.quiz import QuizSession
from app.schemas.quiz import QuizSessionCreate
from app.schemas.monthly_quiz import DeliveryMethod, QuizLinkStatus
from app.services.quiz import QuizSessionService
from app.repositories.quiz import QuizSessionRepository

from .token_manager import TokenManager

import logging

logger = logging.getLogger(__name__)


class SessionFactory:
    """Creates and initializes quiz sessions with proper metadata."""

    def __init__(self, db: Session):
        self.db = db
        self.token_manager = TokenManager()
        self.quiz_session_service = QuizSessionService(db)
        self.session_repository = QuizSessionRepository(db)

    async def create_session_with_link(
        self,
        patient_id: UUID,
        quiz_template_id: UUID,
        delivery_method: DeliveryMethod,
        expires_at: datetime,
        custom_message: Optional[str] = None,
    ) -> tuple[QuizSession, str]:
        """Create a new quiz session with associated link metadata.

        Args:
            patient_id: Patient identifier
            quiz_template_id: Quiz template identifier
            delivery_method: How the link will be delivered
            expires_at: Link expiration datetime
            custom_message: Optional custom message for delivery

        Returns:
            Tuple of (QuizSession model, token string)
        """
        # Generate token
        token = self.token_manager.generate_token(
            patient_id=patient_id,
            quiz_template_id=quiz_template_id,
            expires_at=expires_at,
        )

        # Create session
        session_data = QuizSessionCreate(
            patient_id=patient_id, quiz_template_id=quiz_template_id
        )

        session = await self.quiz_session_service.start_quiz_session(session_data)

        # Update session metadata with link information
        session_model = self.session_repository.get(session.id)
        session_model.session_metadata = {
            "delivery_method": delivery_method.value,
            "token_hash": self.token_manager.hash_token(token),
            "expires_at": expires_at.isoformat(),
            "link_status": QuizLinkStatus.ACTIVE.value,
            "access_count": 0,
            "custom_message": custom_message,
            "delivery_attempts": [],
        }

        self.db.commit()
        self.db.refresh(session_model)

        return session_model, token
