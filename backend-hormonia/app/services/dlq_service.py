"""
DLQ Service - Backward Compatibility Wrapper.

This module provides backward compatibility by re-exporting the refactored
DLQService from the dlq package.

MIGRATION COMPLETE:
    The original 999-line DLQService has been refactored into modular components:
    - app/services/dlq/base.py (157 lines) - Types and protocols
    - app/services/dlq/message_processor.py (359 lines) - Message reprocessing
    - app/services/dlq/retry_handler.py (238 lines) - Retry logic
    - app/services/dlq/dead_letter_handler.py (318 lines) - Queue management
    - app/services/dlq/metrics.py (206 lines) - Metrics collection
    - app/services/dlq/service.py (346 lines) - Main orchestrator

BACKWARD COMPATIBILITY:
    All existing imports continue to work:
        from app.services.dlq_service import DLQService, ErrorCategory

    All public API methods remain unchanged.
    No changes required to existing code.

USAGE:
    # Existing code continues to work
    dlq_service = DLQService(db)

    # Add message
    failed_msg = dlq_service.add_to_dlq(
        message_id=msg_id,
        patient_id=patient_id,
        error_message="Error text",
        error_type="ErrorType",
        payload=payload_dict,
        failure_reason=FailureReason.WHATSAPP_ERROR
    )

    # Retry message
    success, error = dlq_service.retry_message(dlq_id)

    # List messages
    messages = dlq_service.list_messages(page=1, size=20)

    # Get statistics
    stats = dlq_service.get_stats()

    # Process scheduled retries (worker/cron)
    processed = dlq_service.process_scheduled_retries()

NEW MODULAR ARCHITECTURE:
    For new code, you can import specific components:

    from app.services.dlq.service import DLQService
    from app.services.dlq.base import ErrorCategory, RetryConfig
    from app.services.dlq.message_processor import DLQMessageProcessor
    from app.services.dlq.retry_handler import DLQRetryHandler
    from app.services.dlq.metrics import DLQMetricsCollector
"""

# Re-export from new modular structure
from app.services.dlq import DLQService, ErrorCategory

# Legacy backup available at: dlq_service_legacy.py.bak

__all__ = [
    "DLQService",
    "ErrorCategory",
]
