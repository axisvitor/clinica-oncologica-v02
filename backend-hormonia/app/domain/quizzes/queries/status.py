"""Status queries for quiz links."""

import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.quiz import QuizSession, QuizTemplate
from app.models.patient import Patient
from app.repositories.quiz import QuizSessionRepository
from app.schemas.monthly_quiz import MonthlyQuizLinkResponse, DeliveryMethod, QuizLinkStatus
from app.exceptions import NotFoundError
from app.core.monthly_quiz_config import get_monthly_quiz_config

from ..delivery.link_builder import LinkBuilder

import logging

logger = logging.getLogger(__name__)


class StatusQuery:
    """Queries for quiz link status and active links."""

    def __init__(self, db: Session):
        self.db = db
        self.config = get_monthly_quiz_config()
        self.session_repository = QuizSessionRepository(db)
        self.link_builder = LinkBuilder()

        # Initialize Redis for fast patient checking
        try:
            from app.core.redis_manager import get_redis_manager
            self.redis_manager = get_redis_manager()
            self.redis_client = self.redis_manager.get_compatible_client('sync')
        except Exception as e:
            logger.warning(f"Redis not available for fast patient checking: {e}")
            self.redis_client = None

    def _check_patient_exists_fast(self, patient_id: str) -> bool:
        """Fast patient existence check using Redis cache.

        Args:
            patient_id: Patient ID string

        Returns:
            True if patient exists, False otherwise
        """
        if not self.redis_client:
            # Fallback to database check
            return self.db.query(Patient).filter(Patient.id == UUID(patient_id)).first() is not None

        try:
            cache_key = f"patient:exists:{patient_id}"
            cached = self.redis_client.get(cache_key)

            if cached is not None:
                return cached == b'1'

            # Check database and cache result
            exists = self.db.query(Patient).filter(Patient.id == UUID(patient_id)).first() is not None
            self.redis_client.setex(cache_key, 300, '1' if exists else '0')  # Cache for 5 minutes

            return exists
        except Exception as e:
            logger.warning(f"Redis check failed, falling back to DB: {e}")
            return self.db.query(Patient).filter(Patient.id == UUID(patient_id)).first() is not None

    async def get_link_status(self, session_id: UUID) -> MonthlyQuizLinkResponse:
        """Get status of a quiz link.

        Args:
            session_id: Session identifier

        Returns:
            MonthlyQuizLinkResponse with link status

        Raises:
            NotFoundError: Session not found
        """
        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        metadata = session.session_metadata or {}

        # Determine status
        status = QuizLinkStatus(metadata.get("link_status", QuizLinkStatus.ACTIVE.value))
        if session.status == 'completed':
            status = QuizLinkStatus.USED
        elif datetime.utcnow() > datetime.fromisoformat(metadata.get("expires_at", datetime.utcnow().isoformat())):
            status = QuizLinkStatus.EXPIRED

        return MonthlyQuizLinkResponse(
            id=session.id,
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            token="[REDACTED]",
            link_url=self.link_builder.build_redacted_link(),
            delivery_method=DeliveryMethod(metadata.get("delivery_method", "whatsapp")),
            status=status,
            expires_at=datetime.fromisoformat(metadata.get("expires_at", datetime.utcnow().isoformat())),
            created_at=session.started_at,
            accessed_at=datetime.fromisoformat(metadata["accessed_at"]) if metadata.get("accessed_at") else None,
            completed_at=session.completed_at,
            access_count=metadata.get("access_count", 0),
            delivery_attempts=metadata.get("delivery_attempts"),
            last_delivery_status=metadata.get("last_delivery_status"),
            last_delivery_method=metadata.get("last_delivery_method")
        )

    async def get_patient_latest_status(self, patient_id: UUID) -> MonthlyQuizLinkResponse:
        """Get the latest quiz link status for a specific patient.

        Args:
            patient_id: Patient identifier

        Returns:
            MonthlyQuizLinkResponse for latest session

        Raises:
            NotFoundError: Patient or sessions not found
        """
        start_time = time.time()

        # FAST 404 CHECK: Verify patient exists before heavy queries
        if not self._check_patient_exists_fast(str(patient_id)):
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"Fast 404 for patient {str(patient_id)[:8]}... ({elapsed:.1f}ms)")
            raise NotFoundError(f"Patient {patient_id} not found")

        # Get the most recent session for the patient
        session = self.db.query(QuizSession).filter(
            and_(
                QuizSession.patient_id == patient_id,
                QuizSession.session_metadata.isnot(None)
            )
        ).order_by(QuizSession.started_at.desc()).first()

        if not session:
            raise NotFoundError(f"No quiz sessions found for patient {patient_id}")

        return await self.get_link_status(session.id)

    async def get_active_links(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[MonthlyQuizLinkResponse]:
        """Get all active (non-expired, uncompleted) quiz links.

        Args:
            limit: Maximum number of links to return
            offset: Offset for pagination

        Returns:
            List of active quiz link responses
        """
        sessions = self.db.query(QuizSession).filter(
            and_(
                QuizSession.status != 'completed',
                QuizSession.session_metadata.isnot(None),
                or_(
                    QuizSession.session_metadata["link_status"].astext == "active",
                    QuizSession.session_metadata["link_status"].astext.is_(None)
                )
            )
        ).order_by(QuizSession.started_at.desc()).offset(offset).limit(limit).all()

        active_links = []
        current_time = datetime.utcnow()

        for session in sessions:
            metadata = session.session_metadata or {}
            expires_at_str = metadata.get("expires_at")

            if expires_at_str:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if (current_time <= expires_at and
                        metadata.get("link_status") != "cancelled" and
                        session.status != 'completed'):

                        try:
                            link_response = await self.get_link_status(session.id)
                            active_links.append(link_response)
                        except Exception as e:
                            logger.error(f"Error getting status for session {session.id}: {str(e)}")
                            continue
                except ValueError:
                    continue

        return active_links

    async def get_active_links_with_details(
        self,
        user_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """Get active quiz links with patient and template details.

        Args:
            user_id: Optional user filter (not currently used)

        Returns:
            List of dictionaries with detailed link information
        """
        query = self.db.query(QuizSession).join(
            Patient,
            QuizSession.patient_id == Patient.id
        ).join(
            QuizTemplate,
            QuizSession.quiz_template_id == QuizTemplate.id
        ).filter(
            QuizSession.status != 'completed',
            QuizSession.session_metadata.isnot(None)
        )

        sessions = query.all()
        results = []
        current_time = datetime.utcnow()

        for session in sessions:
            metadata = session.session_metadata or {}
            expires_at_str = metadata.get("expires_at")

            if not expires_at_str:
                continue

            try:
                expires_at = datetime.fromisoformat(expires_at_str)

                if current_time <= expires_at:
                    access_url = self.link_builder.build_redacted_link()

                    results.append({
                        "id": str(session.id),
                        "session_id": str(session.id),
                        "patient_id": str(session.patient_id),
                        "patient_name": session.patient.name if session.patient else "Unknown",
                        "patient_phone": session.patient.phone if hasattr(session.patient, 'phone') and session.patient.phone else None,
                        "template_id": str(session.quiz_template_id),
                        "template_name": session.quiz_template.name if session.quiz_template else "Unknown",
                        "template_version": session.quiz_template.version if session.quiz_template else "1.0",
                        "access_url": access_url,
                        "created_at": session.started_at.isoformat(),
                        "sent_at": session.started_at.isoformat(),
                        "expires_at": expires_at.isoformat(),
                        "is_active": expires_at > current_time,
                        "status": session.status,
                        "access_count": metadata.get("access_count", 0),
                        "delivery_method": metadata.get("delivery_method", "whatsapp")
                    })
            except (ValueError, AttributeError):
                continue

        return results
