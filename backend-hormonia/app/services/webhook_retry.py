"""
Webhook Retry Service with Exponential Backoff

MEDIUM-009: Enhanced webhook processing with automatic retry logic,
exponential backoff, circuit breaker integration, and DLQ support.

Features:
- Automatic retry with exponential backoff (2s, 4s, 8s, 16s, 32s)
- Circuit breaker integration for fast-fail behavior
- Dead Letter Queue (DLQ) for failed webhooks after max retries
- Prometheus metrics for monitoring
- Configurable retry parameters

Retry Schedule:
    Attempt 1: Immediate
    Attempt 2: +2s  (total: 2s)
    Attempt 3: +4s  (total: 6s)
    Attempt 4: +8s  (total: 14s)
    Attempt 5: +16s (total: 30s)
    After 5 failures: Send to DLQ
"""

import logging
import asyncio
from typing import Any, Dict, Optional, Callable
from datetime import datetime, timezone

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log,
)
import aiohttp

from app.config.settings.webhooks import webhook_settings
from app.monitoring.metrics import (
    webhook_retry_attempts,
    webhook_retry_success,
    webhook_retry_failures,
    webhook_dlq_enqueued,
)
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class WebhookRetryService:
    """
    Webhook processing with exponential backoff retry.

    Integrates with:
    - Circuit breaker for fast-fail behavior
    - DLQ service for permanent failures
    - Prometheus metrics for monitoring

    Usage:
        service = WebhookRetryService(dlq_service=dlq)
        result = await service.process_webhook_with_retry(webhook_data)
    """

    def __init__(
        self,
        dlq_service: Optional[Any] = None,
        max_retries: int = None,
        min_wait: int = None,
        max_wait: int = None,
        multiplier: int = None,
    ):
        """
        Initialize webhook retry service.

        Args:
            dlq_service: Dead Letter Queue service for failed webhooks
            max_retries: Maximum retry attempts (default from config)
            min_wait: Minimum wait time in seconds (default from config)
            max_wait: Maximum wait time in seconds (default from config)
            multiplier: Exponential backoff multiplier (default from config)
        """
        self.dlq_service = dlq_service
        self.max_retries = max_retries or webhook_settings.WEBHOOK_MAX_RETRIES
        self.min_wait = min_wait or webhook_settings.WEBHOOK_RETRY_MIN_WAIT
        self.max_wait = max_wait or webhook_settings.WEBHOOK_RETRY_MAX_WAIT
        self.multiplier = multiplier or webhook_settings.WEBHOOK_RETRY_MULTIPLIER
        # Backward-compatible state used by legacy tests/observers.
        self._current_attempt = 0

        logger.info(
            f"WebhookRetryService initialized: "
            f"max_retries={self.max_retries}, "
            f"min_wait={self.min_wait}s, "
            f"max_wait={self.max_wait}s"
        )

    def _retry_wait_seconds(self, attempt_number: int) -> int:
        """
        Calculate exponential backoff delay after a failed attempt.

        attempt_number is 1-based:
            1 -> min_wait
            2 -> min_wait * 2
            3 -> min_wait * 4
        """
        base_wait = int(self.min_wait * self.multiplier)
        if base_wait <= 0:
            base_wait = int(self.min_wait) if self.min_wait else 1
        delay = base_wait * (2 ** max(0, attempt_number - 1))
        return min(delay, int(self.max_wait))

    async def process_webhook_with_retry(
        self, webhook_data: Dict[str, Any], processor_func: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Process webhook with automatic retry and exponential backoff.

        Retry schedule (with default settings):
        - Attempt 1: Immediate
        - Attempt 2: +2s  (total: 2s)
        - Attempt 3: +4s  (total: 6s)
        - Attempt 4: +8s  (total: 14s)
        - Attempt 5: +16s (total: 30s)

        After 5 failures: Send to DLQ

        Args:
            webhook_data: Webhook payload data
            processor_func: Optional custom processor function

        Returns:
            Processing result dictionary

        Raises:
            RetryError: If all retries are exhausted
        """
        webhook_id = webhook_data.get("id", "unknown")

        # Build a per-call retrying wrapper using instance config (no shared state)
        retrying = retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(
                multiplier=self._retry_wait_seconds(1),
                min=self._retry_wait_seconds(1),
                max=self.max_wait,
            ),
            retry=retry_if_exception_type(
                (TimeoutError, ConnectionError, aiohttp.ClientError, asyncio.TimeoutError)
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO),
            reraise=True,
        )

        async def _attempt(webhook_data: Dict[str, Any]) -> Dict[str, Any]:
            # Tenacity tracks attempt number internally via retry_state
            attempt_number = _attempt.retry.statistics.get("attempt_number", 1)
            self._current_attempt = attempt_number

            # Record retry attempt metric
            webhook_retry_attempts.labels(attempt_number=attempt_number).inc()

            try:
                if processor_func:
                    result = await processor_func(webhook_data)
                else:
                    result = await self._process_webhook_internal(webhook_data)

                webhook_retry_success.labels(attempt_number=attempt_number).inc()
                self._current_attempt = 0
                logger.info(
                    f"Webhook {webhook_id} processed successfully on attempt {attempt_number}",
                    extra={
                        "webhook_id": webhook_id,
                        "attempt": attempt_number,
                        "total_attempts": self.max_retries,
                    },
                )
                return result

            except Exception as e:
                webhook_retry_failures.labels(
                    attempt_number=attempt_number, error_type=type(e).__name__
                ).inc()

                logger.warning(
                    f"Webhook {webhook_id} processing failed on attempt {attempt_number}: {e}",
                    extra={
                        "webhook_id": webhook_id,
                        "attempt": attempt_number,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                raise

        _attempt = retrying(_attempt)

        try:
            return await _attempt(webhook_data)
        except Exception as e:
            # All retries exhausted -- send to DLQ
            logger.error(
                f"Webhook {webhook_id} failed after {self.max_retries} attempts",
                extra={"webhook_id": webhook_id, "final_error": str(e)},
            )
            await self._send_to_dlq(webhook_data, error=str(e))
            raise
        finally:
            # Avoid leaking attempt state across requests.
            self._current_attempt = 0

    async def _process_webhook_internal(
        self, webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Internal webhook processing logic (placeholder).

        Override this method or pass custom processor_func to process_webhook_with_retry.

        Args:
            webhook_data: Webhook payload

        Returns:
            Processing result
        """
        # Placeholder - actual processing logic should be injected
        # via processor_func parameter
        return {
            "status": "success",
            "webhook_id": webhook_data.get("id"),
            "processed_at": now_sao_paulo().isoformat(),
        }

    async def _send_to_dlq(self, webhook_data: Dict[str, Any], error: str) -> None:
        """
        Send failed webhook to Dead Letter Queue.

        Args:
            webhook_data: Webhook payload
            error: Error message
        """
        if not self.dlq_service:
            logger.warning(
                "No DLQ service configured, webhook will be lost",
                extra={"webhook_id": webhook_data.get("id")},
            )
            return

        dlq_payload = {
            "webhook_data": webhook_data,
            "error": error,
            "retry_count": self.max_retries,
            "failed_at": now_sao_paulo().isoformat(),
            "error_type": "max_retries_exhausted",
        }

        try:
            await self.dlq_service.enqueue(dlq_payload)

            # Record DLQ metric
            webhook_dlq_enqueued.labels(error_type="max_retries_exhausted").inc()

            logger.info(
                f"Webhook {webhook_data.get('id')} sent to DLQ after {self.max_retries} failed attempts"
            )

        except Exception as dlq_error:
            logger.error(
                f"Failed to send webhook to DLQ: {dlq_error}",
                extra={
                    "webhook_id": webhook_data.get("id"),
                    "dlq_error": str(dlq_error),
                },
            )

    def get_retry_statistics(self) -> Dict[str, Any]:
        """
        Get retry configuration and statistics.

        Returns:
            Dictionary with retry settings
        """
        return {
            "max_retries": self.max_retries,
            "min_wait_seconds": self.min_wait,
            "max_wait_seconds": self.max_wait,
            "multiplier": self.multiplier,
            "retry_schedule": [
                {
                    "attempt": i + 1,
                    "wait_time": self._retry_wait_seconds(i + 1),
                    "cumulative_wait": sum(
                        self._retry_wait_seconds(j + 1) for j in range(i)
                    ),
                }
                for i in range(self.max_retries)
            ],
        }


class CircuitBreakerAwareWebhookRetry(WebhookRetryService):
    """
    Webhook retry service with circuit breaker integration.

    Features:
    - Circuit breaker wraps retry logic
    - If circuit is OPEN, fail fast without retry
    - If circuit is CLOSED, retry with exponential backoff
    - If circuit is HALF_OPEN, allow single attempt
    """

    def __init__(self, circuit_breaker, *args, **kwargs):
        """
        Initialize with circuit breaker.

        Args:
            circuit_breaker: Circuit breaker instance (e.g., whatsapp_breaker)
            *args, **kwargs: Passed to parent WebhookRetryService
        """
        super().__init__(*args, **kwargs)
        self.circuit_breaker = circuit_breaker

    async def process_webhook_with_retry(
        self, webhook_data: Dict[str, Any], processor_func: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Process webhook with circuit breaker and retry.

        Circuit breaker provides fast-fail behavior when service is down.
        Retry logic handles transient failures when circuit is closed.

        Args:
            webhook_data: Webhook payload
            processor_func: Optional custom processor

        Returns:
            Processing result
        """
        # Check circuit breaker state
        if self.circuit_breaker.is_open():
            logger.warning(
                f"Circuit breaker OPEN, failing fast for webhook {webhook_data.get('id')}",
                extra={"webhook_id": webhook_data.get("id"), "circuit_state": "OPEN"},
            )

            # Send directly to DLQ (no retry when circuit is open)
            await self._send_to_dlq(
                webhook_data, error="Circuit breaker OPEN - service unavailable"
            )

            raise Exception("Circuit breaker OPEN - webhook processing unavailable")

        # Circuit is CLOSED or HALF_OPEN - attempt processing with retry
        try:
            # Wrap retry logic with circuit breaker
            async def circuit_breaker_processor(data):
                return await self.circuit_breaker.call(
                    super(
                        CircuitBreakerAwareWebhookRetry, self
                    ).process_webhook_with_retry,
                    data,
                    processor_func,
                )

            return await circuit_breaker_processor(webhook_data)

        except Exception as e:
            logger.error(
                f"Circuit breaker-aware webhook processing failed: {e}",
                extra={
                    "webhook_id": webhook_data.get("id"),
                    "circuit_state": self.circuit_breaker.state,
                },
            )
            raise


# Singleton instance (optional)
_webhook_retry_service: Optional[WebhookRetryService] = None


def get_webhook_retry_service(
    dlq_service: Optional[Any] = None, circuit_breaker: Optional[Any] = None
) -> WebhookRetryService:
    """
    Get webhook retry service instance.

    Args:
        dlq_service: Optional DLQ service
        circuit_breaker: Optional circuit breaker for integration

    Returns:
        WebhookRetryService instance
    """
    global _webhook_retry_service

    if _webhook_retry_service is None:
        if circuit_breaker:
            _webhook_retry_service = CircuitBreakerAwareWebhookRetry(
                circuit_breaker=circuit_breaker, dlq_service=dlq_service
            )
        else:
            _webhook_retry_service = WebhookRetryService(dlq_service=dlq_service)

    return _webhook_retry_service
