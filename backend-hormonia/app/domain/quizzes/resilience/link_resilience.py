"""
Quiz Link Resilience Service for Hormonia Backend System.

Handles token expiry monitoring, automatic link regeneration,
fallback mechanisms, and retry logic for quiz reminders.
"""

from __future__ import annotations

import logging
import asyncio
import threading
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple, Callable, Awaitable, TypeVar
from uuid import UUID
from enum import Enum
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.quiz import QuizSession
from app.repositories.quiz import QuizSessionRepository
from app.core.monthly_quiz_config import get_monthly_quiz_config
from app.domain.quizzes.delivery import LinkBuilder
from app.domain.quizzes.session.factory import generate_unique_short_code
from app.domain.quizzes.session.token_manager import TokenManager
from app.exceptions import NotFoundError
from app.schemas.monthly_quiz import DeliveryMethod, QuizLinkStatus
from app.monitoring.business_metrics import BusinessMetricsCollector
from app.utils.timezone import now_sao_paulo, to_sao_paulo

logger = logging.getLogger(__name__)

T = TypeVar("T")


class FailureReason(str, Enum):
    """Reasons for quiz link or reminder failures."""

    TOKEN_EXPIRED = "token_expired"
    LINK_ACCESS_FAILED = "link_access_failed"
    DELIVERY_FAILED = "delivery_failed"
    PATIENT_UNREACHABLE = "patient_unreachable"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_TOKEN = "invalid_token"
    SESSION_COMPLETED = "session_completed"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states for delivery channels."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Channel is failing, use alternative
    HALF_OPEN = "half_open"  # Testing if channel recovered


@dataclass
class ResilienceMetrics:
    """Metrics for tracking link and reminder resilience."""

    total_links_created: int = 0
    expired_links_count: int = 0
    regenerated_links_count: int = 0
    fallback_activations: int = 0
    reminder_success_count: int = 0
    reminder_failure_count: int = 0
    average_completion_time_minutes: Optional[float] = None
    link_expiry_rate: float = 0.0
    reminder_success_rate: float = 0.0
    fallback_activation_rate: float = 0.0
    channel_health: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class QuizLinkResilienceService:
    """Service for handling quiz link resilience and fallback behaviors."""

    def __init__(self, db: Session):
        self.db = db
        self.config = get_monthly_quiz_config()
        self.link_builder = LinkBuilder()
        self.token_manager = TokenManager()
        self.session_repository = QuizSessionRepository(db)
        self.metrics_collector = BusinessMetricsCollector()

        # Resilience configuration
        self.MAX_LINK_REGENERATIONS = 2
        self.REMINDER_MAX_RETRIES = 3
        self.FALLBACK_THRESHOLD = 3
        self.REMINDER_RETRY_DELAYS = [3600, 7200, 14400]  # 1h, 2h, 4h in seconds

        # Circuit breaker tracking
        self._channel_failures: Dict[str, List[datetime]] = {}
        self._circuit_breaker_states: Dict[str, CircuitBreakerState] = {}

    def _run_async_safely(self, coroutine_factory: Callable[[], Awaitable[T]]) -> T:
        """Run async code from sync paths without breaking active event loops."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine_factory())

        result_holder: Dict[str, T] = {}
        error_holder: Dict[str, BaseException] = {}

        def _runner() -> None:
            try:
                result_holder["result"] = asyncio.run(coroutine_factory())
            except BaseException as exc:  # noqa: BLE001
                error_holder["error"] = exc

        runner_thread = threading.Thread(target=_runner, daemon=True)
        runner_thread.start()
        runner_thread.join()

        if "error" in error_holder:
            raise error_holder["error"]

        return result_holder["result"]

    def check_expired_links(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Check for expired quiz links and return them for processing.

        Args:
            limit: Maximum number of expired links to return

        Returns:
            List of expired link information dictionaries
        """
        logger.info(f"Checking for expired quiz links (limit: {limit})")

        # Query for sessions with expired tokens
        now = now_sao_paulo()
        sessions = (
            self.db.query(QuizSession)
            .filter(
                and_(
                    QuizSession.status != "completed",
                    QuizSession.session_metadata.isnot(None),
                )
            )
            .limit(limit)
            .all()
        )

        expired_links = []
        for session in sessions:
            metadata = session.session_metadata or {}
            expires_at_str = metadata.get("expires_at")
            expires_at = None

            try:
                if expires_at_str:
                    expires_at = to_sao_paulo(datetime.fromisoformat(expires_at_str))
                elif session.expiration_date:
                    expires_at = to_sao_paulo(session.expiration_date)

                if not expires_at:
                    continue

                if now > expires_at:
                    expired_links.append(
                        {
                            "session_id": session.id,
                            "patient_id": session.patient_id,
                            "quiz_template_id": session.quiz_template_id,
                            "expires_at": expires_at,
                            "regeneration_count": metadata.get("regeneration_count", 0),
                            "failure_count": metadata.get("failure_count", 0),
                            "delivery_method": metadata.get(
                                "delivery_method", "whatsapp"
                            ),
                        }
                    )
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid expires_at format for session {session.id}: {e}")
                continue

        logger.info(f"Found {len(expired_links)} expired quiz links")
        return expired_links

    def handle_expired_token(
        self, session_id: UUID, patient_id: UUID, quiz_template_id: UUID
    ) -> Dict[str, Any]:
        """
        Handle expired token by regenerating or falling back to WhatsApp.

        Args:
            session_id: Quiz session ID
            patient_id: Patient ID
            quiz_template_id: Quiz template ID

        Returns:
            Dictionary with handling result and action taken
        """
        logger.info(f"Handling expired token for session {session_id}")

        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        metadata = session.session_metadata or {}
        regeneration_count = metadata.get("regeneration_count", 0)
        failure_count = metadata.get("failure_count", 0)

        # Check if max regenerations exceeded
        if regeneration_count >= self.MAX_LINK_REGENERATIONS:
            logger.warning(
                f"Max regenerations ({self.MAX_LINK_REGENERATIONS}) exceeded "
                f"for session {session_id}. Falling back to WhatsApp."
            )
            return self._run_async_safely(
                lambda: self._fallback_to_whatsapp(
                    session, patient_id, quiz_template_id
                )
            )

        # Check if failures exceed threshold
        if failure_count >= self.FALLBACK_THRESHOLD:
            logger.warning(
                f"Failure threshold ({self.FALLBACK_THRESHOLD}) exceeded "
                f"for session {session_id}. Falling back to WhatsApp."
            )
            return self._run_async_safely(
                lambda: self._fallback_to_whatsapp(
                    session, patient_id, quiz_template_id
                )
            )

        # Attempt to regenerate link
        try:
            result = self._run_async_safely(
                lambda: self.regenerate_link(session_id, patient_id, quiz_template_id)
            )
            return {
                "action": "regenerated",
                "session_id": str(session_id),
                "new_token": result["token"],
                "new_expires_at": result["expires_at"],
                "regeneration_count": regeneration_count + 1,
            }
        except Exception as e:
            logger.error(f"Failed to regenerate link for session {session_id}: {e}")
            self.track_failure(session_id, FailureReason.LINK_ACCESS_FAILED)
            return self._run_async_safely(
                lambda: self._fallback_to_whatsapp(
                    session, patient_id, quiz_template_id
                )
            )

    async def regenerate_link(
        self, session_id: UUID, patient_id: UUID, quiz_template_id: UUID
    ) -> Dict[str, Any]:
        """
        Regenerate a new token and link for an expired session.

        Args:
            session_id: Quiz session ID
            patient_id: Patient ID
            quiz_template_id: Quiz template ID

        Returns:
            Dictionary with new token and link information
        """
        logger.info(f"Regenerating link for session {session_id}")

        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        metadata = session.session_metadata or {}
        regeneration_count = metadata.get("regeneration_count", 0)

        # Generate new expiry time (extend by configured hours)
        new_expires_at = now_sao_paulo() + timedelta(
            hours=self.config.MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS
        )

        # Generate new token
        new_token = self.token_manager.generate_token(
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            expires_at=new_expires_at,
            rotation_count=regeneration_count + 1,
            session_id=session.id,
            token_type="quiz_access",
        )

        # Update session expiration and metadata
        session.expiration_date = new_expires_at
        metadata["token_hash"] = self.token_manager.hash_token(new_token)
        metadata["expires_at"] = new_expires_at.isoformat()
        metadata["regeneration_count"] = regeneration_count + 1
        metadata["regenerated_at"] = now_sao_paulo().isoformat()
        metadata["link_status"] = QuizLinkStatus.ACTIVE.value
        if not metadata.get("short_code"):
            metadata["short_code"] = generate_unique_short_code(self.db)

        session.session_metadata = metadata
        self.db.commit()

        # Record token rotation metrics
        await self.metrics_collector.record_token_rotated(
            patient_id=str(session.patient_id),
            quiz_session_id=str(session_id),
            old_token_prefix="rotated",  # We don't have the old token here
            new_token_prefix=new_token[:10],
            rotation_count=regeneration_count + 1,
        )

        logger.info(
            f"Successfully regenerated link for session {session_id} "
            f"(regeneration #{regeneration_count + 1})"
        )

        short_code = metadata.get("short_code")
        link_url = self.link_builder.build_preferred_link(new_token, short_code)

        return {
            "token": new_token,
            "expires_at": new_expires_at.isoformat(),
            "regeneration_count": regeneration_count + 1,
            "link_url": link_url,
        }

    def track_failure(
        self,
        session_id: UUID,
        reason: FailureReason,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track failure for monitoring repeated failures.

        Args:
            session_id: Quiz session ID
            reason: Failure reason
            details: Additional failure details
        """
        logger.warning(f"Tracking failure for session {session_id}: {reason}")

        session = self.session_repository.get(session_id)
        if not session:
            logger.error(f"Cannot track failure - session {session_id} not found")
            return

        metadata = session.session_metadata or {}

        # Initialize failures tracking
        if "failures" not in metadata:
            metadata["failures"] = []

        failure_count = metadata.get("failure_count", 0)
        metadata["failure_count"] = failure_count + 1

        # Add failure record
        failure_record = {
            "timestamp": now_sao_paulo().isoformat(),
            "reason": reason.value,
            "details": details or {},
        }
        metadata["failures"].append(failure_record)

        # Track delivery channel failures for circuit breaker
        delivery_method = metadata.get("delivery_method", "whatsapp")
        if reason == FailureReason.DELIVERY_FAILED:
            self._record_channel_failure(delivery_method)

        session.session_metadata = metadata
        self.db.commit()

        logger.info(
            f"Failure tracked for session {session_id}. "
            f"Total failures: {failure_count + 1}"
        )

    async def _fallback_to_whatsapp(
        self, session: QuizSession, patient_id: UUID, quiz_template_id: UUID
    ) -> Dict[str, Any]:
        """
        Fallback to WhatsApp conversational flow when link-based approach fails.

        Args:
            session: Quiz session
            patient_id: Patient ID
            quiz_template_id: Quiz template ID

        Returns:
            Dictionary with fallback result
        """
        logger.info(f"Initiating fallback to WhatsApp for session {session.id}")

        metadata = session.session_metadata or {}
        metadata["fallback_activated"] = True
        metadata["fallback_activated_at"] = now_sao_paulo().isoformat()
        metadata["fallback_reason"] = "max_failures_exceeded"
        metadata["delivery_method"] = DeliveryMethod.WHATSAPP.value
        metadata["link_status"] = QuizLinkStatus.REVOKED.value

        session.session_metadata = metadata
        self.db.commit()

        # Record fallback activation metrics
        await self.metrics_collector.record_fallback_activated(
            patient_id=str(patient_id),
            quiz_session_id=str(session.id),
            reason="max_failures_exceeded",
            fallback_type="whatsapp",
        )

        logger.info(f"Fallback to WhatsApp activated for session {session.id}")

        return {
            "action": "fallback_to_whatsapp",
            "session_id": str(session.id),
            "patient_id": str(patient_id),
            "quiz_template_id": str(quiz_template_id),
            "fallback_reason": "max_failures_exceeded",
        }

    def _record_channel_failure(self, channel: str) -> None:
        """
        Record delivery channel failure for circuit breaker pattern.

        Args:
            channel: Delivery channel name
        """
        now = now_sao_paulo()

        if channel not in self._channel_failures:
            self._channel_failures[channel] = []

        self._channel_failures[channel].append(now)

        # Clean up old failures (older than 1 hour)
        cutoff = now - timedelta(hours=1)
        self._channel_failures[channel] = [
            ts for ts in self._channel_failures[channel] if ts > cutoff
        ]

        # Update circuit breaker state
        failure_count = len(self._channel_failures[channel])

        if failure_count >= 5:  # 5 failures in 1 hour
            self._circuit_breaker_states[channel] = CircuitBreakerState.OPEN
            logger.warning(f"Circuit breaker OPEN for channel {channel}")
        elif failure_count >= 3:
            self._circuit_breaker_states[channel] = CircuitBreakerState.HALF_OPEN
            logger.warning(f"Circuit breaker HALF_OPEN for channel {channel}")
        else:
            self._circuit_breaker_states[channel] = CircuitBreakerState.CLOSED

    def get_channel_health(self, channel: str) -> Dict[str, Any]:
        """
        Get health status of a delivery channel.

        Args:
            channel: Delivery channel name

        Returns:
            Dictionary with channel health information
        """
        state = self._circuit_breaker_states.get(channel, CircuitBreakerState.CLOSED)
        failure_count = len(self._channel_failures.get(channel, []))

        return {
            "channel": channel,
            "state": state.value,
            "recent_failures": failure_count,
            "is_healthy": state == CircuitBreakerState.CLOSED,
            "last_failure": (
                self._channel_failures[channel][-1].isoformat()
                if channel in self._channel_failures and self._channel_failures[channel]
                else None
            ),
        }

    def should_use_alternative_channel(
        self, preferred_channel: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if alternative delivery channel should be used.

        Args:
            preferred_channel: Preferred delivery channel

        Returns:
            Tuple of (should_use_alternative, alternative_channel)
        """
        health = self.get_channel_health(preferred_channel)

        if health["state"] == CircuitBreakerState.OPEN.value:
            # Circuit breaker is open, use alternative
            alternatives = ["whatsapp", "email", "sms"]
            alternatives.remove(
                preferred_channel
            ) if preferred_channel in alternatives else None

            # Find healthy alternative
            for alt in alternatives:
                alt_health = self.get_channel_health(alt)
                if alt_health["is_healthy"]:
                    logger.info(
                        f"Using alternative channel {alt} instead of {preferred_channel} "
                        f"(circuit breaker: {health['state']})"
                    )
                    return True, alt

            # No healthy alternative, use WhatsApp as last resort
            return True, "whatsapp"

        return False, None

    def get_resilience_metrics(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> ResilienceMetrics:
        """
        Calculate resilience metrics for monitoring.

        Args:
            start_date: Start date for metrics calculation
            end_date: End date for metrics calculation

        Returns:
            ResilienceMetrics object with calculated metrics
        """
        logger.info("Calculating resilience metrics")

        # Build query
        query = self.db.query(QuizSession).filter(
            QuizSession.session_metadata.isnot(None)
        )

        if start_date:
            query = query.filter(QuizSession.started_at >= start_date)
        if end_date:
            query = query.filter(QuizSession.started_at <= end_date)

        sessions = query.all()

        metrics = ResilienceMetrics()
        metrics.total_links_created = len(sessions)

        expired_count = 0
        regenerated_count = 0
        fallback_count = 0
        reminder_success = 0
        reminder_failure = 0
        completion_times = []

        for session in sessions:
            metadata = session.session_metadata or {}

            # Check if expired
            expires_at_str = metadata.get("expires_at")
            if expires_at_str:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if now_sao_paulo() > expires_at and session.status != "completed":
                        expired_count += 1
                except (ValueError, TypeError) as e:
                    logger.debug(
                        f"Failed to parse expires_at from session metadata: {e}"
                    )

            # Count regenerations
            if metadata.get("regeneration_count", 0) > 0:
                regenerated_count += 1

            # Count fallbacks
            if metadata.get("fallback_activated"):
                fallback_count += 1

            # Count reminder outcomes
            failures = metadata.get("failures", [])
            for failure in failures:
                if failure.get("reason") == FailureReason.DELIVERY_FAILED.value:
                    reminder_failure += 1

            # Successful delivery (accessed and completed)
            if metadata.get("accessed_at") and session.status == "completed":
                reminder_success += 1

            # Completion times
            if session.status == "completed" and session.completed_at:
                duration = (
                    session.completed_at - session.started_at
                ).total_seconds() / 60
                completion_times.append(duration)

        metrics.expired_links_count = expired_count
        metrics.regenerated_links_count = regenerated_count
        metrics.fallback_activations = fallback_count
        metrics.reminder_success_count = reminder_success
        metrics.reminder_failure_count = reminder_failure

        # Calculate rates
        if metrics.total_links_created > 0:
            metrics.link_expiry_rate = expired_count / metrics.total_links_created
            metrics.fallback_activation_rate = (
                fallback_count / metrics.total_links_created
            )

        total_reminders = reminder_success + reminder_failure
        if total_reminders > 0:
            metrics.reminder_success_rate = reminder_success / total_reminders

        if completion_times:
            metrics.average_completion_time_minutes = sum(completion_times) / len(
                completion_times
            )

        # Channel health
        for channel in ["whatsapp", "email", "sms"]:
            metrics.channel_health[channel] = self.get_channel_health(channel)

        logger.info(f"Resilience metrics calculated: {metrics}")
        return metrics

    def create_dead_letter_record(
        self, session_id: UUID, reason: str, payload: Dict[str, Any]
    ) -> None:
        """
        Create a dead letter queue record for failed reminders.

        Args:
            session_id: Quiz session ID
            reason: Failure reason
            payload: Original task payload
        """
        logger.error(f"Creating dead letter record for session {session_id}: {reason}")

        session = self.session_repository.get(session_id)
        if not session:
            logger.error(f"Cannot create DLQ record - session {session_id} not found")
            return

        metadata = session.session_metadata or {}

        if "dead_letter_queue" not in metadata:
            metadata["dead_letter_queue"] = []

        dlq_record = {
            "timestamp": now_sao_paulo().isoformat(),
            "reason": reason,
            "payload": payload,
            "retry_count": payload.get("retry_count", 0),
        }

        metadata["dead_letter_queue"].append(dlq_record)
        session.session_metadata = metadata
        self.db.commit()

        logger.info(f"Dead letter record created for session {session_id}")
