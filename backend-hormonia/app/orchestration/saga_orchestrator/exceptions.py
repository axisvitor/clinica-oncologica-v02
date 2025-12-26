"""
Saga Orchestrator Exceptions.

This module defines custom exceptions for saga orchestration errors,
providing clear error types for different failure scenarios.
"""

from typing import Optional
from uuid import UUID


class SagaError(Exception):
    """Base exception for saga-related errors."""

    def __init__(
        self,
        message: str,
        saga_id: Optional[UUID] = None,
        original_error: Optional[Exception] = None,
    ):
        self.message = message
        self.saga_id = saga_id
        self.original_error = original_error
        super().__init__(self.message)


class SagaCompensationError(SagaError):
    """
    Exception raised when saga compensation fails.

    This error indicates that the system failed to properly rollback
    a saga transaction, which may require manual intervention.
    """

    pass


class SagaStepError(SagaError):
    """
    Exception raised when a saga step fails.

    Includes information about which step failed and the original error.
    """

    def __init__(
        self,
        message: str,
        step_number: int,
        step_name: str,
        saga_id: Optional[UUID] = None,
        original_error: Optional[Exception] = None,
    ):
        self.step_number = step_number
        self.step_name = step_name
        super().__init__(message, saga_id, original_error)


class SagaLockError(SagaError):
    """
    Exception raised when a saga lock cannot be acquired.

    This typically indicates a concurrent operation on the same saga.
    """

    pass


class SagaNotFoundError(SagaError):
    """Exception raised when a saga record cannot be found."""

    pass


class SagaAlreadyCompletedError(SagaError):
    """Exception raised when attempting to modify a completed saga."""

    pass
