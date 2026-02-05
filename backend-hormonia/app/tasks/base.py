"""Base task classes and utilities for Celery tasks."""

import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator
from datetime import datetime, timezone
from celery import Task
from sqlalchemy.orm import Session

from app.database import get_db, get_scoped_session
from app.exceptions import ExternalServiceError


logger = logging.getLogger(__name__)


# Use get_scoped_session from app.database as the standard context manager
get_db_session = get_scoped_session


class BaseTask(Task):
    """Base task class with common retry logic, logging and error handling.

    Provides:
    - Automatic retry for common exceptions
    - Exponential backoff with jitter
    - Standardized logging
    - Database session management
    - Error handling patterns
    """

    # Default retry configuration
    autoretry_for = (
        ExternalServiceError,
        ConnectionError,
        TimeoutError,
        OSError,
    )
    retry_kwargs = {"max_retries": 3, "countdown": 60}
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes
    retry_jitter = True

    def get_task_logger(self) -> logging.Logger:
        """
        Get logger instance for this task.

        Returns:
            logging.Logger: Logger instance with task name
        """
        return logging.getLogger(f"tasks.{self.name}")

    def log_task_start(self, **kwargs) -> None:
        """
        Log task start with parameters.

        Args:
            **kwargs: Task parameters to log
        """
        task_logger = self.get_task_logger()
        task_logger.info(f"Starting task {self.name} with params: {kwargs}")

    def log_task_success(self, result: Any, **kwargs) -> None:
        """
        Log successful task completion.

        Args:
            result (Any): Task result
            **kwargs: Additional context to log
        """
        task_logger = self.get_task_logger()
        task_logger.info(f"Task {self.name} completed successfully")

    def log_task_error(self, exc: Exception, **kwargs) -> None:
        """
        Log task error with context.

        Args:
            exc (Exception): Exception that occurred
            **kwargs: Additional context to log
        """
        task_logger = self.get_task_logger()
        task_logger.error(
            f"Task {self.name} failed: {exc}",
            exc_info=True,
            extra={"task_params": kwargs},
        )

    def create_error_result(self, error: str, **context) -> Dict[str, Any]:
        """
        Create standardized error result.

        Args:
            error (str): Error message
            **context: Additional context

        Returns:
            Dict[str, Any]: Standardized error result dictionary containing:
                - success: False
                - error: Error message
                - task_name: Name of the task
                - failed_at: ISO timestamp of failure
        """
        return {
            "success": False,
            "error": error,
            "task_name": self.name,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            **context,
        }

    def create_success_result(self, **data) -> Dict[str, Any]:
        """
        Create standardized success result.

        Args:
            **data: Result data

        Returns:
            Dict[str, Any]: Standardized success result dictionary containing:
                - success: True
                - task_name: Name of the task
                - completed_at: ISO timestamp of completion
        """
        return {
            "success": True,
            "task_name": self.name,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            **data,
        }

    def handle_retry(self, exc: Exception, **context) -> None:
        """
        Handle task retry with exponential backoff.

        Args:
            exc (Exception): Exception that triggered retry
            **context: Additional context for logging

        Raises:
            Retry: If retry should be attempted
            Exception: If max retries exceeded
        """
        if self.request.retries < self.max_retries:
            countdown = min(60 * (2**self.request.retries), self.retry_backoff_max)

            task_logger = self.get_task_logger()
            task_logger.warning(
                f"Retrying task {self.name} in {countdown} seconds "
                f"(attempt {self.request.retries + 1}/{self.max_retries}): {exc}"
            )

            raise self.retry(countdown=countdown, exc=exc)
        else:
            self.log_task_error(exc, **context)
            raise exc


class DatabaseTask(BaseTask):
    """Base task class for database operations.

    Extends BaseTask with database-specific functionality:
    - Automatic database session management
    - Database error handling
    - Transaction management
    """

    def run_with_db(self, func, *args, **kwargs) -> Any:
        """
        Execute function with database session.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Any: Function result
        """
        with get_db_session() as db:
            return func(db, *args, **kwargs)


class MessageTask(BaseTask):
    """Base task class for message operations with retry logic.

    Specialized for message processing with appropriate retry settings.
    """

    # Message-specific retry configuration
    autoretry_for = (
        ExternalServiceError,
        ConnectionError,
        TimeoutError,
    )
    retry_kwargs = {"max_retries": 3, "countdown": 60}


class MonitoringTask(BaseTask):
    """Base task class for monitoring operations.

    Specialized for monitoring tasks with appropriate settings.
    """

    # Monitoring-specific configuration
    retry_kwargs = {"max_retries": 2, "countdown": 30}


class ReportTask(BaseTask):
    """Base task class for report generation.

    Specialized for report generation with longer timeouts.
    """

    # Report-specific configuration
    retry_kwargs = {"max_retries": 2, "countdown": 120}
    retry_backoff_max = 1200  # 20 minutes for reports
