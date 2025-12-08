"""
DLQ (Dead Letter Queue) Service - Modular Implementation.

This package provides a modular, well-structured implementation of the
Dead Letter Queue service with clear separation of concerns.

Architecture:
    - base.py: Type definitions, protocols, and configuration
    - message_processor.py: Message reprocessing logic
    - retry_handler.py: Retry scheduling and backoff
    - dead_letter_handler.py: Queue management
    - metrics.py: Prometheus metrics collection
    - service.py: Main orchestrator (DLQService)

Usage:
    from app.services.dlq_service import DLQService, ErrorCategory

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

Backward Compatibility:
    This module maintains full backward compatibility with the original
    DLQService. All existing imports and API calls continue to work.
"""

from .base import ErrorCategory, RetryConfig
from .service import DLQService

# Legacy imports for backward compatibility
__all__ = [
    "DLQService",
    "ErrorCategory",
    "RetryConfig",
]
