"""
Taskiq LGPD tasks — async-native replacements for Celery lgpd_tasks (M009-S04).

2 tasks migrated from Celery to Taskiq:
  1. persist_lgpd_audit_log          — on-demand, retry-enabled
  2. cleanup_expired_lgpd_audit_logs — cron 30 5 * * * (daily 02:30 BRT → 05:30 UTC)

Key translation patterns from Celery → Taskiq:
  - Pure helper functions imported from app.tasks.lgpd_tasks (no duplication)
  - `get_scoped_session()` preserved for sync ORM (LGPDAuditLog model)
  - `self` (bind=True) removed: SmartRetryMiddleware handles retries
  - Structured logging via log_task_start/success/error from taskiq_base

Schedule labels (1 of 2 tasks is periodic):
  - cleanup_expired_lgpd_audit_logs: cron 30 5 * * * (BRT 02:30 → UTC 05:30)
"""

import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from sqlalchemy import delete

from app.database import get_scoped_session
from app.models.lgpd_audit import LGPDAuditLog
from app.taskiq_broker import broker
from app.tasks.taskiq_base import log_task_error, log_task_start, log_task_success
from app.utils.timezone import now_sao_paulo

# Pure helpers imported from Celery module — zero logic duplication (D007).
from app.tasks.lgpd_tasks import (
    _is_patient_context,
    _normalize_action,
    _normalize_data_category,
    _normalize_fields_accessed,
    _normalize_legal_basis,
    _normalize_optional_text,
    _normalize_purpose,
    _normalize_resource_type,
    _resolve_patient_identifier,
    _resolve_patient_uuid,
    _safe_parse_uuid,
    _sanitize_additional_data,
    _SENSITIVE_DATA_CATEGORIES,
)

logger = logging.getLogger("app.tasks.lgpd_taskiq")


# ===========================================================================
# 1. persist_lgpd_audit_log — on-demand (no schedule label)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=30,
)
async def persist_lgpd_audit_log(
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
    purpose: Optional[str] = None,
    legal_basis: Optional[str] = None,
    patient_identifier: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist LGPD audit log record to database asynchronously.

    Called by the LGPD middleware to avoid adding latency to HTTP requests
    while ensuring compliance with LGPD audit requirements.

    All normalization/sanitization logic is imported from the Celery module's
    pure helper functions — no duplication.

    Args:
        action: LGPD action type (view, create, update, delete, etc.)
        resource_type: Type of resource accessed
        data_category: LGPD data category
        user_id: ID of the user performing the action
        user_email: Email of the user
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
        purpose: Purpose of processing/access
        legal_basis: Legal basis for processing
        patient_identifier: Anonymized patient identifier

    Returns:
        Dict containing success status and audit log ID.
    """
    start_time = log_task_start(
        "persist_lgpd_audit_log", action=action, resource_type=resource_type
    )

    try:
        sanitized_additional_data = _sanitize_additional_data(additional_data)
        patient_context = _is_patient_context(
            resource_type, patient_id, sanitized_additional_data
        )
        normalized_action = _normalize_action(action)
        normalized_resource_type = _normalize_resource_type(
            resource_type=resource_type,
            additional_data=sanitized_additional_data,
            patient_context=patient_context,
        )
        patient_context = patient_context or normalized_resource_type == "patient"

        normalized_data_category = _normalize_data_category(data_category, patient_context)
        resolved_user_id = _safe_parse_uuid(user_id, "user_id", logger)
        resolved_patient_id = _resolve_patient_uuid(
            patient_id=patient_id,
            resource_id=resource_id,
            additional_data=sanitized_additional_data,
            patient_context=patient_context,
            task_logger=logger,
        )
        resolved_resource_id = _normalize_optional_text(resource_id, 255)
        if not resolved_resource_id and patient_context and resolved_patient_id:
            resolved_resource_id = str(resolved_patient_id)

        normalized_fields_accessed = _normalize_fields_accessed(
            fields_accessed=fields_accessed,
            additional_data=sanitized_additional_data,
            resource_type=normalized_resource_type,
            patient_context=patient_context,
        )
        normalized_purpose = _normalize_purpose(
            purpose=purpose,
            additional_data=sanitized_additional_data,
            action=normalized_action,
            patient_context=patient_context,
        )
        normalized_legal_basis = _normalize_legal_basis(
            legal_basis=legal_basis,
            additional_data=sanitized_additional_data,
            action=normalized_action,
            data_category=normalized_data_category,
            patient_context=patient_context,
        )
        resolved_patient_identifier = _resolve_patient_identifier(
            patient_identifier=patient_identifier,
            patient_id=patient_id,
            patient_uuid=resolved_patient_id,
            resource_id=resolved_resource_id,
            request_id=request_id,
            additional_data=sanitized_additional_data,
            patient_context=patient_context,
        )

        if patient_context:
            sanitized_additional_data.setdefault("patient_context", True)
        normalized_input_resource = _normalize_optional_text(resource_type, 100)
        if (
            normalized_input_resource
            and normalized_input_resource.lower() != normalized_resource_type
        ):
            sanitized_additional_data.setdefault(
                "resource_type_original", normalized_input_resource
            )

        with get_scoped_session() as db:
            retention_years = (
                5
                if normalized_data_category in _SENSITIVE_DATA_CATEGORIES or patient_context
                else 2
            )
            retention_until = now_sao_paulo() + timedelta(days=365 * retention_years)

            audit_log = LGPDAuditLog(
                action=normalized_action,
                resource_type=normalized_resource_type,
                data_category=normalized_data_category,
                user_id=resolved_user_id,
                user_email=user_email,
                user_role=user_role,
                patient_id=resolved_patient_id,
                patient_identifier=resolved_patient_identifier,
                resource_id=resolved_resource_id,
                fields_accessed=normalized_fields_accessed,
                purpose=normalized_purpose,
                legal_basis=normalized_legal_basis,
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else None,
                session_id=session_id,
                request_id=request_id,
                success=success,
                error_message=error_message,
                additional_data=sanitized_additional_data or None,
                retention_until=retention_until,
                can_be_deleted=False,
            )

            db.add(audit_log)
            db.commit()
            db.refresh(audit_log)

            result = {
                "success": True,
                "audit_log_id": str(audit_log.id),
                "action": normalized_action,
                "resource_type": normalized_resource_type,
            }

            log_task_success(
                "persist_lgpd_audit_log",
                start_time,
                audit_log_id=result["audit_log_id"],
                action=normalized_action,
            )
            return result

    except Exception as exc:
        log_task_error(
            "persist_lgpd_audit_log",
            exc,
            start_time,
            action=action,
            resource_type=resource_type,
        )
        raise


# ===========================================================================
# 2. cleanup_expired_lgpd_audit_logs — periodic (cron daily 05:30 UTC = 02:30 BRT)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=2,
    delay=60,
    schedule=[{"cron": "30 5 * * *", "kwargs": {"batch_size": 1000}}],
)
async def cleanup_expired_lgpd_audit_logs(batch_size: int = 1000) -> Dict[str, Any]:
    """Clean up LGPD audit logs that have passed their retention period.

    Deletes expired records marked as deletable to maintain compliance
    with LGPD data retention requirements.

    Args:
        batch_size: Number of records to process per batch.

    Returns:
        Dict containing cleanup statistics.
    """
    start_time = log_task_start("cleanup_expired_lgpd_audit_logs", batch_size=batch_size)

    try:
        with get_scoped_session() as db:
            now = now_sao_paulo()

            result = db.execute(
                delete(LGPDAuditLog)
                .where(LGPDAuditLog.retention_until < now)
                .where(LGPDAuditLog.can_be_deleted == True)  # noqa: E712
                .execution_options(synchronize_session=False)
            )

            deleted_count = result.rowcount
            db.commit()

            cleanup_result = {
                "success": True,
                "deleted_count": deleted_count,
                "batch_size": batch_size,
            }

            log_task_success(
                "cleanup_expired_lgpd_audit_logs",
                start_time,
                deleted_count=deleted_count,
            )
            return cleanup_result

    except Exception as exc:
        log_task_error("cleanup_expired_lgpd_audit_logs", exc, start_time)
        raise


__all__ = ["persist_lgpd_audit_log", "cleanup_expired_lgpd_audit_logs"]
