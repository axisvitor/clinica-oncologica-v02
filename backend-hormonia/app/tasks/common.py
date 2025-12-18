"""Common imports and utilities for task modules.

This module centralizes frequently used imports across all task modules
to reduce code duplication and improve maintainability.
"""

# Standard library imports
import asyncio
import logging
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Generator
from uuid import UUID
from contextlib import contextmanager

# Third-party imports
from celery import Task, current_app as celery_app
from celery.exceptions import Retry
from sqlalchemy.orm import Session

# Application imports
from app.config import settings
from app.database import get_db, SessionLocal
from app.exceptions import ExternalServiceError

# Models - commonly used across tasks
from app.models.patient import Patient
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.message import Message, MessageStatus
from app.models.quiz import QuizSession, QuizResponse
from app.models.flow import PatientFlowState, FlowTemplate
from app.models.flow_analytics import FlowAnalytics, FlowMessage

# Services - frequently imported
from app.domain.messaging.delivery import MessageSender
from app.services.quiz import QuizSessionService
from app.services.reporting import ReportService
from app.services.conversation_memory import get_conversation_memory

# Repositories - commonly used
from app.repositories.patient import PatientRepository
from app.repositories.message import MessageRepository
from app.repositories.alert import AlertRepository
from app.repositories.quiz import (
    QuizTemplateRepository,
    QuizResponseRepository,
    QuizSessionRepository,
)
from app.repositories.flow import FlowStateRepository
from app.repositories.flow_template import FlowTemplateRepository

# Task base classes
from .base import BaseTask, DatabaseTask, MessageTask, MonitoringTask, ReportTask
from .config import task_configs

# Common logger setup
logger = logging.getLogger(__name__)


# Common utility functions
@contextmanager
def get_task_db() -> Generator[Session, None, None]:
    """Get database session for tasks with proper cleanup.

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_task_logger(task_name: str) -> logging.Logger:
    """Get logger instance for a specific task.

    Args:
        task_name: Name of the task

    Returns:
        Logger instance
    """
    return logging.getLogger(f"tasks.{task_name}")


def create_task_result(success: bool, **data) -> Dict[str, Any]:
    """Create standardized task result.

    Args:
        success: Whether task was successful
        **data: Additional result data

    Returns:
        Standardized result dictionary
    """
    result = {"success": success, "timestamp": datetime.utcnow().isoformat(), **data}

    if not success and "error" not in result:
        result["error"] = "Unknown error occurred"

    return result


def handle_task_error(exc: Exception, task_name: str, **context) -> Dict[str, Any]:
    """Handle task error with standardized logging and result.

    Args:
        exc: Exception that occurred
        task_name: Name of the task
        **context: Additional context for logging

    Returns:
        Error result dictionary
    """
    task_logger = get_task_logger(task_name)
    task_logger.error(
        f"Task {task_name} failed: {exc}",
        exc_info=True,
        extra={"task_context": context},
    )

    return create_task_result(
        success=False, error=str(exc), task_name=task_name, context=context
    )


# Common task decorators and mixins
class TaskResultMixin:
    """Mixin for standardized task results."""

    def success_result(self, **data) -> Dict[str, Any]:
        """Create success result."""
        return create_task_result(True, **data)

    def error_result(self, error: str, **data) -> Dict[str, Any]:
        """Create error result."""
        return create_task_result(False, error=error, **data)


class DatabaseTaskMixin:
    """Mixin for database operations in tasks."""

    def with_db(self, func, *args, **kwargs) -> Any:
        """Execute function with database session."""
        with get_task_db() as db:
            return func(db, *args, **kwargs)


# Export commonly used items
__all__ = [
    # Standard library
    "asyncio",
    "logging",
    "datetime",
    "timedelta",
    "date",
    "Path",
    "Any",
    "Dict",
    "List",
    "Optional",
    "Generator",
    "UUID",
    "contextmanager",
    # Celery
    "Task",
    "celery_app",
    "Retry",
    "Session",
    # Application
    "settings",
    "get_db",
    "SessionLocal",
    "ExternalServiceError",
    # Models
    "Patient",
    "Alert",
    "AlertSeverity",
    "AlertStatus",
    "Message",
    "MessageStatus",
    "QuizSession",
    "QuizResponse",
    "PatientFlowState",
    "FlowTemplate",
    "FlowAnalytics",
    "FlowMessage",
    # Services
    "MessageSender",
    "QuizSessionService",
    "ReportService",
    "get_conversation_memory",
    # Repositories
    "PatientRepository",
    "MessageRepository",
    "AlertRepository",
    "QuizTemplateRepository",
    "QuizResponseRepository",
    "QuizSessionRepository",
    "FlowTemplateRepository",
    "FlowStateRepository",
    # Task classes
    "BaseTask",
    "DatabaseTask",
    "MessageTask",
    "MonitoringTask",
    "ReportTask",
    "task_configs",
    # Utilities
    "logger",
    "get_task_db",
    "get_task_logger",
    "create_task_result",
    "handle_task_error",
    "TaskResultMixin",
    "DatabaseTaskMixin",
]
