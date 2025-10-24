"""
Messaging Services Module - Consolidated Message Management (QW-022).

This module consolidates message-related services into a unified interface:
- Message CRUD operations
- Message factory and templates
- Message scheduling
- WhatsApp integration
- Idempotency handling

Consolidation:
    8 files → 2 files (75% reduction)

Legacy Files (Consolidated):
    - app/services/message.py
    - app/services/message_factory.py
    - app/services/message_scheduler.py
    - app/services/message_sender.py (deprecated)
    - app/services/idempotent_message_sender.py
    - app/services/monthly_quiz_message_integration.py
    - app/integrations/whatsapp/services/message_service.py
    - app/services/unified_whatsapp_service.py

New Structure:
    - messaging/message_service.py (Core: CRUD, factory, scheduling)
    - messaging/whatsapp_service.py (WhatsApp: sending, idempotency, queue)

Public API:
    Core Services:
        - MessageService: Message CRUD operations
        - MessageFactory: Template-based message creation
        - MessageScheduler: Time-based message scheduling

    WhatsApp Services:
        - WhatsAppService: WhatsApp message sending
        - IdempotentMessageSender: Idempotent message delivery

    Enums:
        - MessageTemplate: Pre-defined message templates
        - SchedulingWindow: Time window enums
        - MessagingMode: Queue/Direct/Legacy modes

    Factory Functions:
        - get_message_service(): Get MessageService instance
        - get_whatsapp_service(): Get WhatsAppService instance

Example Usage:
    >>> from app.services.messaging import MessageService, MessageFactory
    >>> from sqlalchemy.orm import Session
    >>>
    >>> # Message CRUD
    >>> service = MessageService(db)
    >>> message = service.create_message(message_data)
    >>>
    >>> # Template-based creation
    >>> factory = MessageFactory(db)
    >>> quiz_msg = factory.create_quiz_question_message(
    ...     patient_id=patient_id,
    ...     question=question,
    ...     options=options
    ... )
    >>>
    >>> # WhatsApp sending
    >>> from app.services.messaging import WhatsAppService
    >>> whatsapp = WhatsAppService(db)
    >>> await whatsapp.send_message(message)

Migration Notes:
    Legacy imports will continue to work via adapters:

    Old:
        from app.services.message import MessageService
        from app.services.message_factory import MessageFactory

    New (Recommended):
        from app.services.messaging import MessageService, MessageFactory

    Deprecated:
        from app.services.message_sender import MessageSender
        # Use WhatsAppService instead

Version: 1.0.0 (QW-022)
Status: Production Ready
"""

from typing import TYPE_CHECKING

# Import core message services
from .message_service import (
    MessageService,
    MessageFactory,
    MessageScheduler,
    MessageTemplate,
    SchedulingWindow,
    MessageSchedulerConfig,
    MessageSchedulingError,
    TimezoneError,
    TaskSchedulingError,
)

# Import WhatsApp services
from .whatsapp_service import (
    WhatsAppService,
    IdempotentMessageSender,
    MessagingMode,
    WhatsAppQueueService,
    WhatsAppServiceError,
    MessageDeliveryError,
    IdempotencyError,
)


# Factory functions
def get_message_service(db):
    """
    Get MessageService instance.

    Args:
        db: Database session

    Returns:
        MessageService instance

    Example:
        >>> service = get_message_service(db)
        >>> message = service.create_message(data)
    """
    return MessageService(db)


def get_message_factory(db):
    """
    Get MessageFactory instance.

    Args:
        db: Database session

    Returns:
        MessageFactory instance

    Example:
        >>> factory = get_message_factory(db)
        >>> msg = factory.create_quiz_question_message(...)
    """
    return MessageFactory(db)


def get_message_scheduler(db, config=None):
    """
    Get MessageScheduler instance.

    Args:
        db: Database session
        config: Optional MessageSchedulerConfig

    Returns:
        MessageScheduler instance

    Example:
        >>> scheduler = get_message_scheduler(db)
        >>> scheduler.schedule_message(patient_id, content, datetime)
    """
    return MessageScheduler(db, config)


def get_whatsapp_service(db, messaging_mode=MessagingMode.QUEUE):
    """
    Get WhatsAppService instance.

    Args:
        db: Database session
        messaging_mode: Messaging mode (default: QUEUE)

    Returns:
        WhatsAppService instance

    Example:
        >>> whatsapp = get_whatsapp_service(db)
        >>> await whatsapp.send_message(message)
    """
    return WhatsAppService(db, messaging_mode)


def get_idempotent_sender(db):
    """
    Get IdempotentMessageSender instance.

    Args:
        db: Database session

    Returns:
        IdempotentMessageSender instance

    Example:
        >>> sender = get_idempotent_sender(db)
        >>> result = await sender.send_message(message, idempotency_key)
    """
    return IdempotentMessageSender(db)


# Public API exports
__all__ = [
    # Core Services
    "MessageService",
    "MessageFactory",
    "MessageScheduler",
    # WhatsApp Services
    "WhatsAppService",
    "IdempotentMessageSender",
    "WhatsAppQueueService",
    # Enums
    "MessageTemplate",
    "SchedulingWindow",
    "MessagingMode",
    # Config
    "MessageSchedulerConfig",
    # Exceptions
    "MessageSchedulingError",
    "TimezoneError",
    "TaskSchedulingError",
    "WhatsAppServiceError",
    "MessageDeliveryError",
    "IdempotencyError",
    # Factory Functions
    "get_message_service",
    "get_message_factory",
    "get_message_scheduler",
    "get_whatsapp_service",
    "get_idempotent_sender",
]

__version__ = "1.0.0"
__consolidation__ = "QW-022"
__status__ = "Production Ready"
__files_consolidated__ = 8
__files_target__ = 2
__reduction__ = "75%"
