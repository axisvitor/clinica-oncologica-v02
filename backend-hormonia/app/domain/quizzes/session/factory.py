"""Factory for creating quiz sessions."""

from __future__ import annotations

from datetime import datetime
import secrets
import string
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.quiz import QuizSession
from app.schemas.monthly_quiz import DeliveryMethod, QuizLinkStatus
from app.repositories.quiz import QuizSessionRepository
from app.utils.timezone import now_sao_paulo, to_sao_paulo

from .token_manager import TokenManager

import logging

logger = logging.getLogger(__name__)

_SHORT_CODE_ALPHABET = string.ascii_lowercase + string.digits
_SHORT_CODE_LENGTH = 8
_SHORT_CODE_MAX_ATTEMPTS = 5


def generate_unique_short_code(
    db: Session,
    length: int = _SHORT_CODE_LENGTH,
    attempts: int = _SHORT_CODE_MAX_ATTEMPTS,
) -> str:
    """Generate a short, unique code for quiz link shortening."""
    for _ in range(attempts):
        code = "".join(secrets.choice(_SHORT_CODE_ALPHABET) for _ in range(length))
        exists = (
            db.query(QuizSession.id)
            .filter(QuizSession.session_metadata["short_code"].astext == code)
            .first()
        )
        if not exists:
            return code
    raise RuntimeError("Failed to generate a unique short code")


class SessionFactory:
    """Creates and initializes quiz sessions with proper metadata."""

    def __init__(self, db: Session):
        self.db = db
        self.token_manager = TokenManager()
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
        expires_at = to_sao_paulo(expires_at)

        # Create session with canonical expiration field.
        session_model = QuizSession(
            patient_id=patient_id,
            quiz_template_id=quiz_template_id,
            status="started",
            started_at=now_sao_paulo(),
            expiration_date=expires_at,
        )
        self.db.add(session_model)
        self.db.flush()

        # Generate token after session exists (embed session_id).
        token = self.token_manager.generate_token(
            patient_id=patient_id,
            quiz_template_id=quiz_template_id,
            expires_at=expires_at,
            session_id=session_model.id,
            token_type="quiz_access",
        )

        # Update session metadata with link information
        short_code = generate_unique_short_code(self.db)
        session_model.session_metadata = {
            "delivery_method": delivery_method.value,
            "token_hash": self.token_manager.hash_token(token),
            "expires_at": expires_at.isoformat(),
            "link_status": QuizLinkStatus.ACTIVE.value,
            "access_count": 0,
            "custom_message": custom_message,
            "delivery_attempts": [],
            "short_code": short_code,
        }

        self.db.commit()
        self.db.refresh(session_model)

        return session_model, token
