"""Handle expired tokens and regeneration limits."""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.repositories.quiz import QuizSessionRepository
from app.exceptions import NotFoundError

import logging

logger = logging.getLogger(__name__)


class ExpiryHandler:
    """Handles token expiration and regeneration policies."""

    def __init__(self, db: Session, max_regenerations: int = 2):
        self.db = db
        self.session_repository = QuizSessionRepository(db)
        self.max_regenerations = max_regenerations

    async def handle_expired_token(
        self, session_id: UUID, regenerate_callback, actor_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Handle expired token by checking regeneration limits.

        Args:
            session_id: Session identifier
            regenerate_callback: Async callback to regenerate link
            actor_id: User handling the expiry

        Returns:
            Dictionary with action taken:
                - action: "regenerated" or "fallback_required"
                - session_id: str
                - reason: str (if fallback required)
                - new_token: str (if regenerated)
                - new_expires_at: str (if regenerated)
                - regeneration_count: int

        Raises:
            NotFoundError: Session not found
        """
        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        metadata = session.session_metadata or {}
        regeneration_count = metadata.get("regeneration_count", 0)

        if regeneration_count >= self.max_regenerations:
            # Max regenerations exceeded - mark for fallback
            metadata["fallback_required"] = True
            metadata["fallback_reason"] = "max_regenerations_exceeded"
            session.session_metadata = metadata
            self.db.commit()

            return {
                "action": "fallback_required",
                "session_id": str(session_id),
                "reason": "max_regenerations_exceeded",
                "regeneration_count": regeneration_count,
            }

        # Regenerate token
        new_token, new_expires_at = await regenerate_callback(
            session_id=session_id, actor_id=actor_id
        )

        return {
            "action": "regenerated",
            "session_id": str(session_id),
            "new_token": new_token,
            "new_expires_at": new_expires_at.isoformat(),
            "regeneration_count": regeneration_count + 1,
        }

    def track_failure(
        self,
        session_id: UUID,
        failure_reason: str,
        failure_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track failure for monitoring repeated failures.

        Args:
            session_id: Session identifier
            failure_reason: Reason for failure
            failure_details: Optional additional details
        """
        session = self.session_repository.get(session_id)
        if not session:
            return

        metadata = session.session_metadata or {}

        # Initialize failures tracking
        if "failures" not in metadata:
            metadata["failures"] = []

        failure_count = metadata.get("failure_count", 0)
        metadata["failure_count"] = failure_count + 1

        # Add failure record
        failure_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": failure_reason,
            "details": failure_details or {},
        }
        metadata["failures"].append(failure_record)

        session.session_metadata = metadata
        self.db.commit()
