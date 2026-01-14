"""LGPD Audit Tasks - Async persistence for LGPD compliance audit logs.

QW-005: Implements LGPD (Brazilian Data Protection Law) compliance
by persisting audit logs asynchronously to avoid middleware latency.

This module provides:
- Async task for persisting LGPD audit records to database
- Background processing for high-volume audit logging
- Proper error handling and retry logic
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from app.task_queue import task_queue as celery_app

from app.tasks.base import DatabaseTask, get_db_session
from app.models.lgpd_audit import LGPDAuditLog, LGPDActionType, LGPDDataCategory

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="lgpd.persist_audit_log",
    queue="default",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def persist_lgpd_audit_log(
    self,
    action: str,
    resource_type: str,
    data_category: str = "personal_basic",
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    user_role: Optional[str] = None,
    patient_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    fields_accessed: Optional[list] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None,
    request_id: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    additional_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Persist LGPD audit log record to database asynchronously.

    This task is called by the LGPD middleware to avoid adding latency
    to HTTP requests while ensuring compliance with LGPD audit requirements.

    Args:
        action: LGPD action type (view, create, update, delete, etc.)
        resource_type: Type of resource accessed (e.g., "patients", "messages")
        data_category: LGPD data category (personal_basic, health, etc.)
        user_id: ID of the user performing the action
        user_email: Email of the user (denormalized for audit trail)
        user_role: Role of the user
        patient_id: ID of the patient whose data was accessed
        resource_id: ID of the specific resource
        fields_accessed: List of field names accessed
        ip_address: Client IP address
        user_agent: Client user agent
        session_id: Session ID for correlation
        request_id: Request ID for correlation
        success: Whether the access was successful
        error_message: Error message if access failed
        additional_data: Additional context data

    Returns:
        Dict containing success status and audit log ID
    """
    task_logger = logging.getLogger(f"tasks.{self.name}")
    task_logger.debug(f"Persisting LGPD audit log: action={action}, resource={resource_type}")

    try:
        with get_db_session() as db:
            # Calculate retention period (5 years for health data per LGPD)
            retention_years = 5 if data_category in ("health", "genetic", "biometric") else 2
            retention_until = datetime.now(timezone.utc) + timedelta(days=365 * retention_years)

            # Create audit log record
            audit_log = LGPDAuditLog(
                action=action,
                resource_type=resource_type,
                data_category=data_category,
                user_id=UUID(user_id) if user_id else None,
                user_email=user_email,
                user_role=user_role,
                patient_id=UUID(patient_id) if patient_id else None,
                resource_id=resource_id,
                fields_accessed=fields_accessed,
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else None,
                session_id=session_id,
                request_id=request_id,
                success=success,
                error_message=error_message,
                additional_data=additional_data,
                retention_until=retention_until,
                can_be_deleted=False,
            )

            db.add(audit_log)
            db.commit()
            db.refresh(audit_log)

            task_logger.info(
                f"LGPD audit log persisted: id={audit_log.id}, action={action}"
            )

            return {
                "success": True,
                "audit_log_id": str(audit_log.id),
                "action": action,
                "resource_type": resource_type,
            }

    except Exception as exc:
        task_logger.error(
            f"Failed to persist LGPD audit log: {exc}",
            exc_info=True,
            extra={
                "action": action,
                "resource_type": resource_type,
                "user_id": user_id,
            },
        )
        raise


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="lgpd.cleanup_expired_audit_logs",
    queue="default",
    max_retries=2,
)
def cleanup_expired_lgpd_audit_logs(self, batch_size: int = 1000) -> Dict[str, Any]:
    """
    Clean up LGPD audit logs that have passed their retention period.

    This task should be scheduled periodically (e.g., weekly) to maintain
    compliance with LGPD data retention requirements.

    Args:
        batch_size: Number of records to process per batch

    Returns:
        Dict containing cleanup statistics
    """
    task_logger = logging.getLogger(f"tasks.{self.name}")
    task_logger.info("Starting LGPD audit log cleanup")

    try:
        with get_db_session() as db:
            from sqlalchemy import delete

            # Find and delete expired records that are marked as deletable
            now = datetime.now(timezone.utc)
            
            result = db.execute(
                delete(LGPDAuditLog)
                .where(LGPDAuditLog.retention_until < now)
                .where(LGPDAuditLog.can_be_deleted == True)
                .execution_options(synchronize_session=False)
            )
            
            deleted_count = result.rowcount
            db.commit()

            task_logger.info(f"LGPD audit log cleanup completed: deleted {deleted_count} records")

            return {
                "success": True,
                "deleted_count": deleted_count,
                "batch_size": batch_size,
            }

    except Exception as exc:
        task_logger.error(f"LGPD audit log cleanup failed: {exc}", exc_info=True)
        raise


__all__ = ["persist_lgpd_audit_log", "cleanup_expired_lgpd_audit_logs"]
