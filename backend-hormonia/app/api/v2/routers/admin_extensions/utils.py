"""
Admin Extensions Utilities
Serialization helpers for DLQ items and audit logs.
"""

from typing import Optional, List

from app.models.failed_message import FailedMessage
from app.models.audit_log import AuditLog
from app.api.v2.dependencies import apply_field_selection


HISTORICAL_AUDIT_METADATA_KEYS = {"firebase_uid"}


def serialize_dlq_item(item: FailedMessage, fields: Optional[List[str]] = None) -> dict:
    """
    Serialize DLQ item to dict with optional field selection.

    Args:
        item: FailedMessage instance
        fields: Optional list of fields to include

    Returns:
        Serialized DLQ item dictionary
    """
    data = {
        "id": item.id,
        "patient_id": item.patient_id,
        "phone_number": item.phone_number,
        "message_type": item.message_type,
        "message_content": item.message_content,
        "error_message": item.error_message,
        "error_code": item.error_code,
        "retry_count": item.retry_count,
        "max_retries": item.max_retries,
        "next_retry_at": item.next_retry_at,
        "last_retry_at": item.last_retry_at,
        "status": item.status.value if hasattr(item.status, "value") else item.status,
        "resolved_at": item.resolved_at,
        "dlq_metadata": item.dlq_metadata or {},
        "reviewed_by": item.reviewed_by,
        "original_message_id": item.original_message_id,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }

    if fields:
        selected = apply_field_selection(data, fields)
        # Keep required response-model fields even when field selection is requested.
        required_fields = {
            "id",
            "patient_id",
            "phone_number",
            "message_type",
            "error_message",
            "retry_count",
            "max_retries",
            "status",
            "created_at",
            "updated_at",
        }
        for key in required_fields:
            selected.setdefault(key, data.get(key))
        data = selected

    return data


def serialize_audit_log(
    log: AuditLog, fields: Optional[List[str]] = None, redact_sensitive: bool = True
) -> dict:
    """
    Serialize audit log to dict with optional field selection and redaction.

    Args:
        log: AuditLog instance
        fields: Optional list of fields to include
        redact_sensitive: Whether to redact sensitive data (default: True)

    Returns:
        Serialized audit log dictionary
    """
    event_data = {
        key: value
        for key, value in (log.event_metadata or {}).items()
        if key not in HISTORICAL_AUDIT_METADATA_KEYS
    }

    # Redact sensitive data if requested
    if redact_sensitive:
        sensitive_keys = ["password", "token", "api_key", "secret", "credential"]
        event_data = {
            k: "[REDACTED]" if any(sk in k.lower() for sk in sensitive_keys) else v
            for k, v in event_data.items()
        }

    data = {
        "id": log.id,
        "event_type": log.event_type.value
        if hasattr(log.event_type, "value")
        else str(log.event_type),
        "event_status": log.event_status,
        "user_id": log.user_id,
        "user_email": log.user_email,
        "ip_address": str(log.ip_address) if log.ip_address else None,
        "user_agent": log.user_agent,
        "resource": log.resource,
        "action": log.action,
        "event_metadata": event_data,
        "message": log.message,
        "error_details": log.error_details,
        "created_at": log.created_at,
        "updated_at": log.updated_at,
    }

    if fields:
        data = apply_field_selection(data, fields)

    return data
