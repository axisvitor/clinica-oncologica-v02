"""
Audit Logging Utility
Provides structured audit logging for compliance, security, and debugging.
Tracks all CRUD operations on templates and other sensitive resources.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
from enum import Enum

logger = logging.getLogger("audit")


class AuditAction(str, Enum):
    """Enumeration of auditable actions."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    READ = "read"  # For sensitive data access
    PUBLISH = "publish"
    ARCHIVE = "archive"
    DUPLICATE = "duplicate"
    ROLLBACK = "rollback"
    SEARCH = "search"
    VALIDATE = "validate"


class AuditLogger:
    """
    Structured audit logging for compliance and debugging.

    Logs all operations on sensitive resources with full context including:
    - Action performed (create, update, delete, etc.)
    - Resource affected (type and ID)
    - User who performed the action
    - Timestamp and additional context
    - IP address for security tracking
    """

    @staticmethod
    def log(
        action: AuditAction,
        resource_type: str,
        resource_id: str,
        user_id: str,
        user_role: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Log an audit event with full context.

        Args:
            action: The action performed (CREATE, UPDATE, DELETE, etc.)
            resource_type: Type of resource (flow_template, quiz_template, etc.)
            resource_id: Unique identifier of the resource
            user_id: ID of the user performing the action
            user_role: Role of the user (admin, editor, viewer, etc.)
            details: Additional context as key-value pairs
            ip_address: Client IP address for security tracking
            success: Whether the operation succeeded
            error_message: Error message if operation failed

        Example:
            >>> AuditLogger.log(
            ...     action=AuditAction.CREATE,
            ...     resource_type="flow_template",
            ...     resource_id="123e4567-e89b-12d3-a456-426614174000",
            ...     user_id="user-uuid",
            ...     user_role="admin",
            ...     details={"template_name": "Onboarding Flow", "version": 1},
            ...     ip_address="192.168.1.1",
            ...     success=True
            ... )
        """
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action.value,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "user_id": user_id,
            "user_role": user_role,
            "details": details or {},
            "ip_address": ip_address,
            "success": success,
            "error_message": error_message,
        }

        # Log as structured JSON for easy parsing and analysis
        log_level = logging.INFO if success else logging.WARNING
        logger.log(
            log_level,
            f"AUDIT: {action.value} {resource_type}:{resource_id} by user:{user_id} {'SUCCESS' if success else 'FAILED'}",
            extra={"audit_data": audit_entry},
        )

    @staticmethod
    def log_batch(
        action: AuditAction,
        resource_type: str,
        resource_ids: List[str],
        user_id: str,
        user_role: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        success: bool = True,
    ) -> None:
        """
        Log a batch operation affecting multiple resources.

        Args:
            action: The action performed
            resource_type: Type of resources affected
            resource_ids: List of resource IDs affected
            user_id: ID of the user performing the action
            user_role: Role of the user
            details: Additional context
            ip_address: Client IP address
            success: Whether the operation succeeded

        Example:
            >>> AuditLogger.log_batch(
            ...     action=AuditAction.ARCHIVE,
            ...     resource_type="flow_template",
            ...     resource_ids=["id1", "id2", "id3"],
            ...     user_id="user-uuid",
            ...     user_role="admin",
            ...     details={"reason": "End of quarter cleanup"},
            ...     ip_address="192.168.1.1"
            ... )
        """
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action.value,
            "resource_type": resource_type,
            "resource_ids": resource_ids,
            "resource_count": len(resource_ids),
            "user_id": user_id,
            "user_role": user_role,
            "details": details or {},
            "ip_address": ip_address,
            "success": success,
        }

        logger.info(
            f"AUDIT: BATCH {action.value} {len(resource_ids)} {resource_type}(s) by user:{user_id}",
            extra={"audit_data": audit_entry},
        )

    @staticmethod
    def log_access(
        resource_type: str,
        resource_id: str,
        user_id: str,
        user_role: Optional[str] = None,
        access_type: str = "view",
        ip_address: Optional[str] = None,
    ) -> None:
        """
        Log access to sensitive resources (read operations).

        Args:
            resource_type: Type of resource accessed
            resource_id: ID of the resource
            user_id: ID of the user accessing
            user_role: Role of the user
            access_type: Type of access (view, download, export, etc.)
            ip_address: Client IP address

        Example:
            >>> AuditLogger.log_access(
            ...     resource_type="patient_data",
            ...     resource_id="patient-123",
            ...     user_id="user-uuid",
            ...     user_role="doctor",
            ...     access_type="view",
            ...     ip_address="192.168.1.1"
            ... )
        """
        AuditLogger.log(
            action=AuditAction.READ,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            user_role=user_role,
            details={"access_type": access_type},
            ip_address=ip_address,
            success=True,
        )

    @staticmethod
    def log_security_event(
        event_type: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        severity: str = "medium",
    ) -> None:
        """
        Log security-related events.

        Args:
            event_type: Type of security event (failed_login, permission_denied, etc.)
            user_id: ID of the user involved (if applicable)
            details: Additional context
            ip_address: Client IP address
            severity: Severity level (low, medium, high, critical)

        Example:
            >>> AuditLogger.log_security_event(
            ...     event_type="permission_denied",
            ...     user_id="user-uuid",
            ...     details={"attempted_action": "delete", "resource": "template-123"},
            ...     ip_address="192.168.1.1",
            ...     severity="high"
            ... )
        """
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "details": details or {},
            "ip_address": ip_address,
            "severity": severity,
        }

        log_level = logging.WARNING if severity in ["high", "critical"] else logging.INFO
        logger.log(
            log_level,
            f"SECURITY: {event_type} severity:{severity} user:{user_id or 'anonymous'}",
            extra={"security_event": audit_entry},
        )
