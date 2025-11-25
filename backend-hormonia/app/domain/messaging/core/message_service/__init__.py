"""
Message Service Package - Consolidated Message Management Core (QW-022).

This package consolidates core message functionality previously spread across
multiple files:
- Message CRUD operations (from message.py)
- Message factory and templates (from message_factory.py)
- Message scheduling (from message_scheduler.py)

Package Structure:
    - config.py: Configuration, enums, and constants
    - exceptions.py: Custom exception classes
    - service.py: Core CRUD operations (MessageService)
    - factory.py: Template-based message creation (MessageFactory)
    - scheduler.py: Time-based message scheduling (MessageScheduler)
    - templates.py: Message template strings

Legacy Files Consolidated:
    - app/services/message.py (MessageService)
    - app/services/message_factory.py (MessageFactory)
    - app/services/message_scheduler.py (MessageScheduler)

Consolidation: 3 files (1,021 lines) → 7 modular files (~300 lines each)
"""

from typing import Optional
from sqlalchemy.orm import Session

# Configuration and enums
from .config import (
    MessageTemplate,
    SchedulingWindow,
    MessageSchedulerConfig,
)

# Exceptions
from .exceptions import (
    MessageSchedulingError,
    TimezoneError,
    TaskSchedulingError,
)

# Core services
from .service import MessageService
from .factory import MessageFactory
from .scheduler import MessageScheduler

# Templates
from .templates import MessageTemplates


# ============================================================================
# Public API - Factory Functions
# ============================================================================


def get_message_service(db: Session) -> MessageService:
    """
    Get MessageService instance.

    Args:
        db: Database session

    Returns:
        MessageService instance
    """
    return MessageService(db)


def get_message_factory(db: Session) -> MessageFactory:
    """
    Get MessageFactory instance.

    Args:
        db: Database session

    Returns:
        MessageFactory instance
    """
    return MessageFactory(db)


def get_message_scheduler(
    db: Session, config: Optional[MessageSchedulerConfig] = None
) -> MessageScheduler:
    """
    Get MessageScheduler instance.

    Args:
        db: Database session
        config: Optional configuration

    Returns:
        MessageScheduler instance
    """
    return MessageScheduler(db, config)


# ============================================================================
# Public API - Exports
# ============================================================================

__all__ = [
    # Configuration and enums
    "MessageTemplate",
    "SchedulingWindow",
    "MessageSchedulerConfig",
    # Exceptions
    "MessageSchedulingError",
    "TimezoneError",
    "TaskSchedulingError",
    # Core services
    "MessageService",
    "MessageFactory",
    "MessageScheduler",
    # Templates
    "MessageTemplates",
    # Factory functions
    "get_message_service",
    "get_message_factory",
    "get_message_scheduler",
]
