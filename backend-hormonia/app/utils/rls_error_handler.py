"""
Utility module for handling RLS (Row Level Security) errors across the application.

This module provides centralized error handling for RLS-related exceptions,
ensuring consistent error responses and proper logging.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
import traceback

from app.core.database import RLSError, RLSAccessDeniedError, RLSContextError

logger = logging.getLogger(__name__)


class RLSErrorHandler:
    """
    Centralized error handler for RLS-related exceptions.

    Provides methods to handle different types of RLS errors and convert
    them to appropriate HTTP responses with proper logging.
    """

    @staticmethod
    def handle_rls_access_denied(
        error: RLSAccessDeniedError,
        user_context: Optional[Dict[str, Any]] = None,
        operation: str = "database operation",
    ) -> HTTPException:
        """
        Handle RLS access denied errors.

        Args:
            error: The RLS access denied error
            user_context: User context if available
            operation: Description of the operation that failed

        Returns:
            HTTPException with appropriate status and message
        """
        user_id = user_context.get("user_id") if user_context else "unknown"
        user_role = user_context.get("role") if user_context else "unknown"

        logger.warning(
            f"RLS access denied for user {user_id} (role: {user_role}) "
            f"during {operation}: {str(error)}"
        )

        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "access_denied",
                "error_type": "rls_access_denied",
                "message": "You don't have permission to access this resource",
                "operation": operation,
                "user_id": user_id,
                "timestamp": str(logger.handlers[0].formatter.formatTime())
                if logger.handlers
                else None,
            },
        )

    @staticmethod
    def handle_rls_context_error(
        error: RLSContextError,
        user_context: Optional[Dict[str, Any]] = None,
        operation: str = "database operation",
    ) -> HTTPException:
        """
        Handle RLS context errors.

        Args:
            error: The RLS context error
            user_context: User context if available
            operation: Description of the operation that failed

        Returns:
            HTTPException with appropriate status and message
        """
        user_id = user_context.get("user_id") if user_context else "unknown"

        logger.error(
            f"RLS context error for user {user_id} during {operation}: {str(error)}"
        )

        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_context",
                "error_type": "rls_context_error",
                "message": "Authentication context is required for this operation",
                "operation": operation,
                "user_id": user_id,
                "timestamp": str(logger.handlers[0].formatter.formatTime())
                if logger.handlers
                else None,
            },
        )

    @staticmethod
    def handle_general_rls_error(
        error: RLSError,
        user_context: Optional[Dict[str, Any]] = None,
        operation: str = "database operation",
    ) -> HTTPException:
        """
        Handle general RLS errors.

        Args:
            error: The RLS error
            user_context: User context if available
            operation: Description of the operation that failed

        Returns:
            HTTPException with appropriate status and message
        """
        user_id = user_context.get("user_id") if user_context else "unknown"

        logger.error(
            f"RLS error for user {user_id} during {operation}: {str(error)}\n"
            f"Traceback: {traceback.format_exc()}"
        )

        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "rls_operation_failed",
                "error_type": "rls_error",
                "message": "Row Level Security operation encountered an error",
                "operation": operation,
                "user_id": user_id,
                "timestamp": str(logger.handlers[0].formatter.formatTime())
                if logger.handlers
                else None,
            },
        )

    @staticmethod
    def handle_database_error(
        error: Exception,
        user_context: Optional[Dict[str, Any]] = None,
        operation: str = "database operation",
    ) -> HTTPException:
        """
        Handle general database errors that might be RLS-related.

        Args:
            error: The database error
            user_context: User context if available
            operation: Description of the operation that failed

        Returns:
            HTTPException with appropriate status and message
        """
        user_id = user_context.get("user_id") if user_context else "unknown"

        # Check if it's a specific RLS-related error
        error_message = str(error).lower()

        if "permission denied" in error_message or "access denied" in error_message:
            logger.warning(
                f"Database permission denied for user {user_id} during {operation}: {str(error)}"
            )
            return HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "permission_denied",
                    "error_type": "database_permission_error",
                    "message": "Access denied by database security policies",
                    "operation": operation,
                    "user_id": user_id,
                },
            )

        if "row level security" in error_message or "rls" in error_message:
            logger.error(
                f"RLS policy violation for user {user_id} during {operation}: {str(error)}"
            )
            return HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "rls_policy_violation",
                    "error_type": "rls_policy_error",
                    "message": "Operation blocked by Row Level Security policy",
                    "operation": operation,
                    "user_id": user_id,
                },
            )

        # General database error
        logger.error(
            f"Database error for user {user_id} during {operation}: {str(error)}\n"
            f"Traceback: {traceback.format_exc()}"
        )

        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "database_error",
                "error_type": "database_operation_error",
                "message": "Database operation failed",
                "operation": operation,
                "user_id": user_id,
            },
        )

    @classmethod
    def handle_any_rls_error(
        cls,
        error: Exception,
        user_context: Optional[Dict[str, Any]] = None,
        operation: str = "database operation",
    ) -> HTTPException:
        """
        Handle any RLS-related error with appropriate routing.

        Args:
            error: The error to handle
            user_context: User context if available
            operation: Description of the operation that failed

        Returns:
            HTTPException with appropriate status and message
        """
        if isinstance(error, RLSAccessDeniedError):
            return cls.handle_rls_access_denied(error, user_context, operation)
        elif isinstance(error, RLSContextError):
            return cls.handle_rls_context_error(error, user_context, operation)
        elif isinstance(error, RLSError):
            return cls.handle_general_rls_error(error, user_context, operation)
        elif isinstance(error, SQLAlchemyError):
            return cls.handle_database_error(error, user_context, operation)
        else:
            # Fallback for unknown errors
            return cls.handle_database_error(error, user_context, operation)


class RLSAuditLogger:
    """
    Audit logger for RLS operations.

    Provides methods to log RLS-related operations for compliance
    and security monitoring.
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.audit")

    def log_access_attempt(
        self,
        user_context: Dict[str, Any],
        resource_type: str,
        resource_id: str,
        operation: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Log an access attempt for audit purposes.

        Args:
            user_context: User context information
            resource_type: Type of resource being accessed
            resource_id: ID of the resource
            operation: Operation being performed
            success: Whether the operation was successful
            details: Additional details about the operation
        """
        log_entry = {
            "event_type": "rls_access_attempt",
            "user_id": user_context.get("user_id"),
            "user_role": user_context.get("role"),
            "user_email": user_context.get("email"),
            "resource_type": resource_type,
            "resource_id": resource_id,
            "operation": operation,
            "success": success,
            "timestamp": str(logger.handlers[0].formatter.formatTime())
            if logger.handlers
            else None,
            "details": details or {},
        }

        if success:
            self.logger.info(f"RLS Access Success: {log_entry}")
        else:
            self.logger.warning(f"RLS Access Denied: {log_entry}")

    def log_rls_policy_evaluation(
        self,
        user_context: Dict[str, Any],
        policy_name: str,
        result: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Log RLS policy evaluation for monitoring.

        Args:
            user_context: User context information
            policy_name: Name of the RLS policy
            result: Result of policy evaluation (allow/deny)
            details: Additional details about the evaluation
        """
        log_entry = {
            "event_type": "rls_policy_evaluation",
            "user_id": user_context.get("user_id"),
            "user_role": user_context.get("role"),
            "policy_name": policy_name,
            "result": result,
            "timestamp": str(logger.handlers[0].formatter.formatTime())
            if logger.handlers
            else None,
            "details": details or {},
        }

        self.logger.info(f"RLS Policy Evaluation: {log_entry}")


# Global instances
rls_error_handler = RLSErrorHandler()
rls_audit_logger = RLSAuditLogger()


# Convenience functions for common operations
def handle_rls_error(
    error: Exception,
    user_context: Optional[Dict[str, Any]] = None,
    operation: str = "database operation",
) -> HTTPException:
    """
    Convenience function to handle any RLS error.

    Args:
        error: The error to handle
        user_context: User context if available
        operation: Description of the operation that failed

    Returns:
        HTTPException with appropriate status and message
    """
    return rls_error_handler.handle_any_rls_error(error, user_context, operation)


def log_rls_access(
    user_context: Dict[str, Any],
    resource_type: str,
    resource_id: str,
    operation: str,
    success: bool,
    details: Optional[Dict[str, Any]] = None,
):
    """
    Convenience function to log RLS access attempts.

    Args:
        user_context: User context information
        resource_type: Type of resource being accessed
        resource_id: ID of the resource
        operation: Operation being performed
        success: Whether the operation was successful
        details: Additional details about the operation
    """
    rls_audit_logger.log_access_attempt(
        user_context, resource_type, resource_id, operation, success, details
    )


def log_rls_policy(
    user_context: Dict[str, Any],
    policy_name: str,
    result: str,
    details: Optional[Dict[str, Any]] = None,
):
    """
    Convenience function to log RLS policy evaluations.

    Args:
        user_context: User context information
        policy_name: Name of the RLS policy
        result: Result of policy evaluation
        details: Additional details about the evaluation
    """
    rls_audit_logger.log_rls_policy_evaluation(
        user_context, policy_name, result, details
    )
