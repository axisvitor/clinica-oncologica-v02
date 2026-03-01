"""
DLQ (Dead Letter Queue) Service - Canonical Implementation.

This package provides the canonical, modular DLQ implementation with clear
separation of concerns. It is the single source of truth for retry
configuration and error categorization used across all DLQ specializations.

Architecture:
    - base.py: Type definitions, protocols, and configuration (RetryConfig, ErrorCategory)
    - message_processor.py: Message reprocessing logic
    - retry_handler.py: Retry scheduling and backoff
    - dead_letter_handler.py: Queue management
    - metrics.py: Prometheus metrics collection
    - atomic_retry.py: Distributed atomic retry counter (QW-004)
    - service.py: Main orchestrator (DLQService)

Specializations (import shared config from this package):
    - ``app.services.webhook_dlq.WebhookDLQ`` -- Redis-backed DLQ for
      transient webhook events. Imports RetryConfig from ``base.py``.
    - ``app.integrations.whatsapp.queue.dlq.DLQHandler`` -- WhatsApp-specific
      DLQ with patient validation, admin review, and scheduling.
      Imports ErrorCategory from ``base.py``.
    - ``app.resilience.retry.dead_letter.DeadLetterQueue`` -- Generic in-memory
      DLQ for the resilience/retry framework. Separate infrastructure concern.

Usage:
    from app.services.dlq import DLQService, ErrorCategory

    # Initialize service
    dlq_service = DLQService(db)

    # Add message to DLQ
    failed_msg = dlq_service.add_to_dlq(
        message_id=msg_id,
        patient_id=patient_id,
        error_message="Connection timeout",
        error_type="TimeoutError",
        payload=payload_dict,
        failure_reason=FailureReason.WHATSAPP_ERROR
    )

    # Retry message
    success, error = dlq_service.retry_message(failed_msg.id)

    # Get statistics
    stats = dlq_service.get_stats()

"""

from .base import ErrorCategory, RetryConfig
from .service import DLQService

__all__ = [
    "DLQService",
    "ErrorCategory",
    "RetryConfig",
]
