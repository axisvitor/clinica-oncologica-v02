"""
Retry management and backoff strategies for flow error recovery.
Handles scheduling retries, calculating backoff delays, and managing retry state.
"""

import logging
import json
from datetime import datetime, timedelta
from uuid import UUID
from dataclasses import dataclass, field
from typing import Optional, Any

from .classifier import ErrorHandlerConstants, RecoveryStrategy, ErrorCategory
from .redis_scan import scan_keys
from app.utils.timezone import now_sao_paulo, to_sao_paulo

logger = logging.getLogger(__name__)


@dataclass
class ErrorContext:
    """Context information for error handling."""

    patient_id: UUID
    flow_state_id: Optional[UUID] = None
    message_id: Optional[UUID] = None
    operation: str = ""
    timestamp: datetime = field(default_factory=now_sao_paulo)
    additional_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorRecord:
    """Record of an error occurrence."""

    id: str
    error_type: str
    category: ErrorCategory
    severity: Any  # ErrorSeverity from classifier
    message: str
    context: ErrorContext
    stack_trace: Optional[str] = None
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.RETRY_EXPONENTIAL
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=now_sao_paulo)


@dataclass
class RecoveryResult:
    """Result of error recovery attempt."""

    success: bool
    strategy_used: RecoveryStrategy
    attempts_made: int
    error_resolved: bool
    fallback_applied: bool = False
    next_retry_at: Optional[datetime] = None
    message: str = ""
    additional_data: dict[str, Any] = field(default_factory=dict)


class RetryManager:
    """Manages retry scheduling and backoff calculations for error recovery."""

    def __init__(self, redis_client, retry_delays: Optional[dict] = None):
        """
        Initialize retry manager.

        Args:
            redis_client: Redis client for scheduling
            retry_delays: Custom retry delay configuration
        """
        self.redis = redis_client
        self.retry_delays = retry_delays or {
            RecoveryStrategy.RETRY_EXPONENTIAL: ErrorHandlerConstants.DEFAULT_EXPONENTIAL_DELAYS,
            RecoveryStrategy.RETRY_LINEAR: [ErrorHandlerConstants.DEFAULT_LINEAR_DELAY]
            * 5,
        }

    async def _scan_keys(self, pattern: str, count: int = 200) -> list[Any]:
        """List keys using SCAN to avoid blocking Redis with KEYS."""
        return await scan_keys(self.redis, pattern=pattern, count=count)

    def _calculate_ttl_seconds(self, target_at: datetime) -> int:
        """Calculate a positive Redis TTL for scheduled operations."""
        target_at_aware = to_sao_paulo(target_at)
        ttl_seconds = (
            int((target_at_aware - now_sao_paulo()).total_seconds())
            + ErrorHandlerConstants.REDIS_RETRY_BUFFER
        )
        return max(1, ttl_seconds)

    def calculate_exponential_backoff(self, attempt: int) -> int:
        """
        Calculate exponential backoff delay.

        Args:
            attempt: Current retry attempt number

        Returns:
            Delay in seconds
        """
        delays = self.retry_delays[RecoveryStrategy.RETRY_EXPONENTIAL]
        delay_index = min(attempt, len(delays) - 1)
        return delays[delay_index]

    def calculate_linear_backoff(self, attempt: int) -> int:
        """
        Calculate linear backoff delay.

        Args:
            attempt: Current retry attempt number

        Returns:
            Delay in seconds
        """
        return ErrorHandlerConstants.DEFAULT_LINEAR_DELAY

    def calculate_next_retry_time(
        self, strategy: RecoveryStrategy, attempt: int
    ) -> datetime:
        """
        Calculate next retry time based on strategy and attempt.

        Args:
            strategy: Recovery strategy to use
            attempt: Current retry attempt number

        Returns:
            Next retry datetime
        """
        if strategy == RecoveryStrategy.RETRY_EXPONENTIAL:
            delay_seconds = self.calculate_exponential_backoff(attempt)
        elif strategy == RecoveryStrategy.RETRY_LINEAR:
            delay_seconds = self.calculate_linear_backoff(attempt)
        else:
            delay_seconds = ErrorHandlerConstants.DEFAULT_LINEAR_DELAY

        return now_sao_paulo() + timedelta(seconds=delay_seconds)

    async def schedule_retry(
        self, error_record: ErrorRecord, retry_at: datetime
    ) -> bool:
        """
        Schedule retry operation in Redis.

        Args:
            error_record: Error record to retry
            retry_at: When to retry

        Returns:
            Success status
        """
        try:
            retry_at_aware = to_sao_paulo(retry_at)
            retry_data = {
                "error_id": error_record.id,
                "patient_id": str(error_record.context.patient_id),
                "operation": error_record.context.operation,
                "retry_at": retry_at_aware.isoformat(),
                "attempt": error_record.recovery_attempts,
            }

            ttl_seconds = self._calculate_ttl_seconds(retry_at_aware)

            # Store in Redis
            await self.redis.setex(
                f"flow_retry:{error_record.id}", ttl_seconds, json.dumps(retry_data)
            )

            logger.info(
                f"Scheduled retry for error {error_record.id} at {retry_at_aware}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to schedule retry: {e}")
            return False

    async def schedule_flow_resume(self, patient_id: UUID, resume_at: datetime) -> bool:
        """
        Schedule flow resume operation.

        Args:
            patient_id: Patient ID for flow resume
            resume_at: When to resume

        Returns:
            Success status
        """
        try:
            resume_at_aware = to_sao_paulo(resume_at)
            resume_data = {
                "patient_id": str(patient_id),
                "resume_at": resume_at_aware.isoformat(),
                "reason": "error_recovery",
            }

            ttl_seconds = self._calculate_ttl_seconds(resume_at_aware)

            # Store in Redis
            await self.redis.setex(
                f"flow_resume:{patient_id}", ttl_seconds, json.dumps(resume_data)
            )

            logger.info(
                f"Scheduled flow resume for patient {patient_id} at {resume_at_aware}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to schedule flow resume: {e}")
            return False

    async def get_scheduled_retries(self) -> list[dict]:
        """
        Get all scheduled retries.

        Returns:
            List of scheduled retry data
        """
        try:
            retry_keys = await self._scan_keys("flow_retry:*")
            retries = []

            for key in retry_keys:
                retry_data = await self.redis.get(key)
                if retry_data:
                    retries.append(json.loads(retry_data))

            return retries

        except Exception as e:
            logger.error(f"Failed to get scheduled retries: {e}")
            return []

    async def cancel_retry(self, error_id: str) -> bool:
        """
        Cancel scheduled retry.

        Args:
            error_id: Error ID to cancel

        Returns:
            Success status
        """
        try:
            await self.redis.delete(f"flow_retry:{error_id}")
            logger.info(f"Cancelled retry for error {error_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel retry: {e}")
            return False

    def should_retry(self, error_record: ErrorRecord) -> bool:
        """
        Determine if error should be retried.

        Args:
            error_record: Error record to check

        Returns:
            True if should retry
        """
        return error_record.recovery_attempts < error_record.max_recovery_attempts

    def get_retry_delay(self, strategy: RecoveryStrategy, attempt: int) -> int:
        """
        Get retry delay for strategy and attempt.

        Args:
            strategy: Recovery strategy
            attempt: Attempt number

        Returns:
            Delay in seconds
        """
        if strategy == RecoveryStrategy.RETRY_EXPONENTIAL:
            return self.calculate_exponential_backoff(attempt)
        elif strategy == RecoveryStrategy.RETRY_LINEAR:
            return self.calculate_linear_backoff(attempt)
        else:
            return ErrorHandlerConstants.DEFAULT_LINEAR_DELAY
