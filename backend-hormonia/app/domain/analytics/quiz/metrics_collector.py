"""
Quiz-specific metrics collection and instrumentation.

Provides:
- Quiz completion rate by template
- Send latency (message enqueue → delivery)
- Response latency (question sent → answer received)
- Template-specific analytics
"""

import logging
import time
from datetime import datetime, UTC
from typing import Dict
from uuid import UUID

from app.core.redis_unified import get_async_redis

logger = logging.getLogger(__name__)


class QuizMetricsCollector:
    """
    Collects and aggregates quiz-specific metrics.

    Metrics tracked:
    - quiz_completion_total{template_id}: Total completions per template
    - quiz_send_latency_seconds{template_id, percentile}: Send latency distribution
    - quiz_response_latency_seconds{template_id, question_id}: Time from question → answer
    - quiz_abandonment_rate{template_id}: Sessions started but not completed
    - quiz_clarification_rate{template_id}: Invalid responses requiring clarification
    """

    METRICS_KEY_PREFIX = "quiz_metrics"
    COMPLETION_KEY = "completions"
    SEND_LATENCY_KEY = "send_latency"
    RESPONSE_LATENCY_KEY = "response_latency"
    ABANDONMENT_KEY = "abandonment"
    CLARIFICATION_KEY = "clarifications"

    def __init__(self):
        """Initialize quiz metrics collector."""
        self._redis_client = None

    async def _get_redis(self):
        """Lazy-load Redis client."""
        if not self._redis_client:
            self._redis_client = await get_async_redis()
        return self._redis_client

    async def record_quiz_completion(self, template_id: UUID, session_id: UUID) -> None:
        """
        Record successful quiz completion.

        Args:
            template_id: Quiz template ID
            session_id: Quiz session ID
        """
        try:
            redis = await self._get_redis()
            key = f"{self.METRICS_KEY_PREFIX}:{self.COMPLETION_KEY}:{template_id}"

            # Increment counter
            await redis.incr(key)

            # Set TTL (30 days)
            await redis.expire(key, 30 * 24 * 3600)

            # Track daily completion (for trend analysis)
            today = datetime.now(UTC).strftime("%Y%m%d")
            daily_key = f"{key}:daily:{today}"
            await redis.incr(daily_key)
            await redis.expire(daily_key, 30 * 24 * 3600)

            logger.info(
                f"Quiz completion recorded: template={template_id}, session={session_id}"
            )

        except Exception as e:
            logger.error(f"Failed to record quiz completion: {e}", exc_info=True)

    async def record_send_latency(
        self, template_id: UUID, latency_seconds: float, message_type: str = "question"
    ) -> None:
        """
        Record message send latency.

        Args:
            template_id: Quiz template ID
            latency_seconds: Time from enqueue to delivery confirmation
            message_type: Type of message (question, intro, completion, etc.)
        """
        try:
            redis = await self._get_redis()
            key = f"{self.METRICS_KEY_PREFIX}:{self.SEND_LATENCY_KEY}:{template_id}:{message_type}"

            # Store latency value in sorted set (for percentile calculation)
            timestamp = time.time()
            await redis.zadd(key, {f"{timestamp}:{latency_seconds}": latency_seconds})

            # Keep only last 1000 samples
            await redis.zremrangebyrank(key, 0, -1001)

            # Set TTL (7 days)
            await redis.expire(key, 7 * 24 * 3600)

            logger.debug(
                f"Send latency recorded: template={template_id}, "
                f"type={message_type}, latency={latency_seconds:.3f}s"
            )

        except Exception as e:
            logger.error(f"Failed to record send latency: {e}", exc_info=True)

    async def record_response_latency(
        self,
        template_id: UUID,
        question_id: str,
        session_id: UUID,
        latency_seconds: float,
    ) -> None:
        """
        Record response latency (time from question sent to answer received).

        Args:
            template_id: Quiz template ID
            question_id: Question ID
            session_id: Session ID
            latency_seconds: Time from question sent to response received
        """
        try:
            redis = await self._get_redis()
            key = f"{self.METRICS_KEY_PREFIX}:{self.RESPONSE_LATENCY_KEY}:{template_id}:{question_id}"

            # Store in sorted set
            timestamp = time.time()
            await redis.zadd(key, {f"{session_id}:{timestamp}": latency_seconds})

            # Keep only last 500 samples per question
            await redis.zremrangebyrank(key, 0, -501)

            # Set TTL (7 days)
            await redis.expire(key, 7 * 24 * 3600)

            logger.debug(
                f"Response latency recorded: template={template_id}, "
                f"question={question_id}, latency={latency_seconds:.3f}s"
            )

        except Exception as e:
            logger.error(f"Failed to record response latency: {e}", exc_info=True)

    async def record_quiz_abandonment(
        self, template_id: UUID, session_id: UUID
    ) -> None:
        """
        Record quiz abandonment (session started but not completed).

        Args:
            template_id: Quiz template ID
            session_id: Session ID
        """
        try:
            redis = await self._get_redis()
            key = f"{self.METRICS_KEY_PREFIX}:{self.ABANDONMENT_KEY}:{template_id}"

            await redis.incr(key)
            await redis.expire(key, 30 * 24 * 3600)

            logger.info(
                f"Quiz abandonment recorded: template={template_id}, session={session_id}"
            )

        except Exception as e:
            logger.error(f"Failed to record quiz abandonment: {e}", exc_info=True)

    async def record_clarification_request(
        self, template_id: UUID, question_id: str, session_id: UUID
    ) -> None:
        """
        Record clarification request (invalid response requiring re-prompt).

        Args:
            template_id: Quiz template ID
            question_id: Question ID
            session_id: Session ID
        """
        try:
            redis = await self._get_redis()
            key = f"{self.METRICS_KEY_PREFIX}:{self.CLARIFICATION_KEY}:{template_id}:{question_id}"

            await redis.incr(key)
            await redis.expire(key, 7 * 24 * 3600)

            logger.debug(
                f"Clarification recorded: template={template_id}, "
                f"question={question_id}, session={session_id}"
            )

        except Exception as e:
            logger.error(f"Failed to record clarification: {e}", exc_info=True)

    async def get_completion_count(self, template_id: UUID) -> int:
        """Get total completion count for a template."""
        try:
            redis = await self._get_redis()
            key = f"{self.METRICS_KEY_PREFIX}:{self.COMPLETION_KEY}:{template_id}"
            count = await redis.get(key)
            return int(count) if count else 0

        except Exception as e:
            logger.error(f"Failed to get completion count: {e}", exc_info=True)
            return 0

    async def get_send_latency_percentiles(
        self, template_id: UUID, message_type: str = "question"
    ) -> Dict[str, float]:
        """
        Calculate send latency percentiles (p50, p95, p99).

        Args:
            template_id: Quiz template ID
            message_type: Message type filter

        Returns:
            Dict with p50, p95, p99 latencies in seconds
        """
        try:
            redis = await self._get_redis()
            key = f"{self.METRICS_KEY_PREFIX}:{self.SEND_LATENCY_KEY}:{template_id}:{message_type}"

            # Get all latency values
            values = await redis.zrange(key, 0, -1, withscores=True)

            if not values:
                return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "samples": 0}

            latencies = sorted([score for _, score in values])
            n = len(latencies)

            def percentile(p: float) -> float:
                k = (n - 1) * p
                f = int(k)
                c = int(k) + 1
                if c >= n:
                    return latencies[-1]
                d0 = latencies[f] * (c - k)
                d1 = latencies[c] * (k - f)
                return d0 + d1

            return {
                "p50": percentile(0.50),
                "p95": percentile(0.95),
                "p99": percentile(0.99),
                "samples": n,
            }

        except Exception as e:
            logger.error(f"Failed to calculate latency percentiles: {e}", exc_info=True)
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "samples": 0}

    async def get_response_latency_percentiles(
        self, template_id: UUID, question_id: str
    ) -> Dict[str, float]:
        """
        Calculate response latency percentiles for a specific question.

        Args:
            template_id: Quiz template ID
            question_id: Question ID

        Returns:
            Dict with p50, p95, p99 response latencies
        """
        try:
            redis = await self._get_redis()
            key = f"{self.METRICS_KEY_PREFIX}:{self.RESPONSE_LATENCY_KEY}:{template_id}:{question_id}"

            values = await redis.zrange(key, 0, -1, withscores=True)

            if not values:
                return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "samples": 0}

            latencies = sorted([score for _, score in values])
            n = len(latencies)

            def percentile(p: float) -> float:
                k = (n - 1) * p
                f = int(k)
                c = int(k) + 1
                if c >= n:
                    return latencies[-1]
                d0 = latencies[f] * (c - k)
                d1 = latencies[c] * (k - f)
                return d0 + d1

            return {
                "p50": percentile(0.50),
                "p95": percentile(0.95),
                "p99": percentile(0.99),
                "samples": n,
            }

        except Exception as e:
            logger.error(f"Failed to calculate response latency: {e}", exc_info=True)
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "samples": 0}

    async def get_abandonment_rate(self, template_id: UUID) -> float:
        """
        Calculate abandonment rate (abandonments / completions).

        Args:
            template_id: Quiz template ID

        Returns:
            Abandonment rate (0.0 to 1.0)
        """
        try:
            redis = await self._get_redis()

            completion_key = (
                f"{self.METRICS_KEY_PREFIX}:{self.COMPLETION_KEY}:{template_id}"
            )
            abandonment_key = (
                f"{self.METRICS_KEY_PREFIX}:{self.ABANDONMENT_KEY}:{template_id}"
            )

            completions = await redis.get(completion_key)
            abandonments = await redis.get(abandonment_key)

            completions = int(completions) if completions else 0
            abandonments = int(abandonments) if abandonments else 0

            total = completions + abandonments
            if total == 0:
                return 0.0

            return abandonments / total

        except Exception as e:
            logger.error(f"Failed to calculate abandonment rate: {e}", exc_info=True)
            return 0.0

    async def get_clarification_rate(
        self, template_id: UUID, question_id: str
    ) -> float:
        """
        Calculate clarification rate for a specific question.

        Args:
            template_id: Quiz template ID
            question_id: Question ID

        Returns:
            Clarification rate (0.0 to 1.0)
        """
        try:
            redis = await self._get_redis()

            clarification_key = f"{self.METRICS_KEY_PREFIX}:{self.CLARIFICATION_KEY}:{template_id}:{question_id}"
            clarifications = await redis.get(clarification_key)

            # For rate calculation, would need total responses per question
            # (not implemented here, would require additional tracking)

            return int(clarifications) if clarifications else 0

        except Exception as e:
            logger.error(f"Failed to calculate clarification rate: {e}", exc_info=True)
            return 0.0


# Singleton instance
_quiz_metrics_collector = None


async def get_quiz_metrics_collector() -> QuizMetricsCollector:
    """Get or create singleton quiz metrics collector instance."""
    global _quiz_metrics_collector
    if _quiz_metrics_collector is None:
        _quiz_metrics_collector = QuizMetricsCollector()
    return _quiz_metrics_collector
