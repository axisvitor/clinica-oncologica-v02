"""LGPD Audit Tasks - Async persistence for LGPD compliance audit logs.

QW-005: Implements LGPD (Brazilian Data Protection Law) compliance
by persisting audit logs asynchronously to avoid middleware latency.

This module provides:
- Async task for persisting LGPD audit records to database
- Background processing for high-volume audit logging
- Proper error handling and retry logic
"""

import hashlib
import logging
import re
from datetime import timedelta
from typing import Any, Dict, Optional, Sequence
from uuid import UUID

from app.task_queue import task_queue as celery_app

from app.tasks.base import DatabaseTask, get_db_session
from app.models.lgpd_audit import LGPDAuditLog, LGPDActionType, LGPDDataCategory
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

_SENSITIVE_DATA_CATEGORIES = {
    LGPDDataCategory.HEALTH.value,
    LGPDDataCategory.GENETIC.value,
    LGPDDataCategory.BIOMETRIC.value,
}
_SENSITIVE_CONTEXT_KEYS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "jwt",
    "private_key",
)
_PATIENT_RESOURCE_MARKERS = {"patient", "patients"}
_PATIENT_NON_ID_SEGMENTS = {
    "search",
    "list",
    "export",
    "new",
    "bulk",
    "summary",
    "history",
    "consents",
}


def _normalize_optional_text(value: Any, max_length: int) -> Optional[str]:
    """Normalize optional text values and enforce max length."""
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized[:max_length]


def _safe_parse_uuid(value: Optional[str], field_name: str, task_logger: logging.Logger) -> Optional[UUID]:
    """Parse UUID safely to avoid dropping logs due to malformed identifiers."""
    normalized_value = _normalize_optional_text(value, 255)
    if not normalized_value:
        return None
    try:
        return UUID(normalized_value)
    except (TypeError, ValueError):
        task_logger.warning("Invalid %s provided for LGPD audit log; skipping UUID field", field_name)
        return None


def _sanitize_context_value(value: Any, key: Optional[str] = None) -> Any:
    """Recursively sanitize potentially sensitive values from additional context."""
    normalized_key = (key or "").lower()
    if any(token in normalized_key for token in _SENSITIVE_CONTEXT_KEYS):
        return "***"

    if isinstance(value, dict):
        return {k: _sanitize_context_value(v, k) for k, v in value.items()}

    if isinstance(value, list):
        return [_sanitize_context_value(item) for item in value]

    if isinstance(value, str) and value.lower().startswith("bearer "):
        return "Bearer ***"

    return value


def _sanitize_additional_data(additional_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return sanitized additional_data and guarantee a dictionary payload."""
    if not isinstance(additional_data, dict):
        return {}
    sanitized = _sanitize_context_value(additional_data)
    return sanitized if isinstance(sanitized, dict) else {}


def _extract_resource_from_path(path: Optional[str]) -> Optional[str]:
    """Extract a stable resource segment from URL path-like strings."""
    normalized_path = _normalize_optional_text(path, 2048)
    if not normalized_path:
        return None

    segments = [segment.strip() for segment in normalized_path.split("/") if segment.strip()]
    for segment in segments:
        lower_segment = segment.lower()
        if lower_segment in {"api", "v1", "v2", "v3"}:
            continue
        return segment
    return None


def _extract_patient_identifier_from_path(path: Optional[str]) -> Optional[str]:
    """Extract patient identifier candidate from patient route paths."""
    normalized_path = _normalize_optional_text(path, 2048)
    if not normalized_path:
        return None

    segments = [segment.strip() for segment in normalized_path.split("/") if segment.strip()]
    for index, segment in enumerate(segments):
        if segment.lower() not in _PATIENT_RESOURCE_MARKERS:
            continue
        if index + 1 >= len(segments):
            return None

        candidate = segments[index + 1].split("?")[0].strip()
        if not candidate:
            return None
        if candidate.lower() in _PATIENT_NON_ID_SEGMENTS:
            return None
        return candidate
    return None


def _is_patient_context(
    resource_type: str,
    patient_id: Optional[str],
    additional_data: Dict[str, Any],
) -> bool:
    """Identify patient-related operations even when resource_type is inconsistent."""
    if _normalize_optional_text(patient_id, 255):
        return True

    normalized_resource = _normalize_optional_text(resource_type, 255)
    if normalized_resource and "patient" in normalized_resource.lower():
        return True

    path = _normalize_optional_text(additional_data.get("path"), 2048)
    if path and "/patient" in path.lower():
        return True

    for key in ("patient_id", "patient_uuid", "patient_identifier"):
        if _normalize_optional_text(additional_data.get(key), 255):
            return True

    return False


def _normalize_resource_type(
    resource_type: str,
    additional_data: Dict[str, Any],
    patient_context: bool,
) -> str:
    """Normalize resource type to a stable token for downstream audit analysis."""
    if patient_context:
        return "patient"

    candidate = _normalize_optional_text(resource_type, 255)
    if not candidate:
        candidate = _normalize_optional_text(additional_data.get("resource_type"), 255)
    if not candidate:
        candidate = _extract_resource_from_path(additional_data.get("path"))

    if not candidate:
        return "unknown_resource"

    normalized = candidate.lower()
    if normalized.startswith("/"):
        from_path = _extract_resource_from_path(normalized)
        normalized = from_path.lower() if from_path else normalized

    normalized = re.sub(r"[^a-z0-9_/.-]", "_", normalized).replace("-", "_").strip("_/.")
    if not normalized:
        return "unknown_resource"
    if normalized in _PATIENT_RESOURCE_MARKERS or "patient" in normalized:
        return "patient"
    if "/" in normalized:
        normalized = normalized.split("/", 1)[0]

    return normalized[:100] or "unknown_resource"


def _normalize_action(action: str) -> str:
    """Normalize action with a safe fallback."""
    normalized = _normalize_optional_text(action, 50)
    if not normalized:
        return LGPDActionType.VIEW.value

    mapped_http_actions = {
        "get": LGPDActionType.VIEW.value,
        "post": LGPDActionType.CREATE.value,
        "put": LGPDActionType.UPDATE.value,
        "patch": LGPDActionType.UPDATE.value,
        "delete": LGPDActionType.DELETE.value,
    }
    return mapped_http_actions.get(normalized.lower(), normalized.lower())


def _normalize_data_category(data_category: str, patient_context: bool) -> str:
    """Normalize data category with patient-aware fallback."""
    normalized = _normalize_optional_text(data_category, 50)
    if normalized:
        return normalized.lower()
    if patient_context:
        return LGPDDataCategory.HEALTH.value
    return LGPDDataCategory.PERSONAL_BASIC.value


def _normalize_fields_accessed(
    fields_accessed: Optional[list],
    additional_data: Dict[str, Any],
    resource_type: str,
    patient_context: bool,
) -> list:
    """Ensure fields_accessed is always a normalized non-empty list."""
    source_fields: Any = fields_accessed
    if source_fields is None:
        source_fields = additional_data.get("fields_accessed")

    if isinstance(source_fields, str):
        source_fields = [source_fields]
    elif not isinstance(source_fields, Sequence):
        source_fields = []

    normalized_fields = []
    seen_fields = set()
    for field in source_fields:
        if not isinstance(field, (str, int, float)):
            continue
        normalized_field = _normalize_optional_text(str(field).lower(), 100)
        if not normalized_field or normalized_field in seen_fields:
            continue
        seen_fields.add(normalized_field)
        normalized_fields.append(normalized_field)

    if normalized_fields:
        return normalized_fields
    if patient_context:
        return ["patient_record"]
    if resource_type == "unknown_resource":
        return ["resource_record"]
    return [f"{resource_type}_record"]


def _default_purpose(action: str, patient_context: bool) -> str:
    """Infer purpose for missing values while keeping semantics explicit."""
    if action.startswith("consent_"):
        return "consent_management"
    if action in {"view", "search", "download", "export"}:
        return "patient_care_access" if patient_context else "service_data_access"
    if action in {"create", "update", "delete", "backup", "restore", "anonymize"}:
        return "patient_record_management" if patient_context else "service_operation"
    if action == "access_denied":
        return "security_monitoring"
    return "patient_data_processing" if patient_context else "system_operation"


def _normalize_purpose(
    purpose: Optional[str],
    additional_data: Dict[str, Any],
    action: str,
    patient_context: bool,
) -> str:
    """Resolve purpose from explicit input, context, or deterministic fallback."""
    explicit_purpose = _normalize_optional_text(purpose, 255)
    if explicit_purpose:
        return explicit_purpose

    context_purpose = _normalize_optional_text(additional_data.get("purpose"), 255)
    if context_purpose:
        return context_purpose

    return _default_purpose(action, patient_context)


def _normalize_legal_basis(
    legal_basis: Optional[str],
    additional_data: Dict[str, Any],
    action: str,
    data_category: str,
    patient_context: bool,
) -> str:
    """Resolve legal basis from explicit input, context, or deterministic fallback."""
    explicit_legal_basis = _normalize_optional_text(legal_basis, 100)
    if explicit_legal_basis:
        return explicit_legal_basis

    context_legal_basis = _normalize_optional_text(additional_data.get("legal_basis"), 100)
    if context_legal_basis:
        return context_legal_basis

    if action.startswith("consent_"):
        return "consent"
    if patient_context or data_category in _SENSITIVE_DATA_CATEGORIES:
        return "health_protection"
    return "legitimate_interest"


def _resolve_patient_uuid(
    patient_id: Optional[str],
    resource_id: Optional[str],
    additional_data: Dict[str, Any],
    patient_context: bool,
    task_logger: logging.Logger,
) -> Optional[UUID]:
    """Resolve patient UUID from direct input and context fallbacks."""
    direct_uuid = _safe_parse_uuid(patient_id, "patient_id", task_logger)
    if direct_uuid:
        return direct_uuid

    for key in ("patient_id", "patient_uuid", "patientId"):
        context_uuid = _safe_parse_uuid(additional_data.get(key), key, task_logger)
        if context_uuid:
            return context_uuid

    path_candidate = _extract_patient_identifier_from_path(additional_data.get("path"))
    path_uuid = _safe_parse_uuid(path_candidate, "path_patient_id", task_logger)
    if path_uuid:
        return path_uuid

    if patient_context:
        resource_uuid = _safe_parse_uuid(resource_id, "resource_id", task_logger)
        if resource_uuid:
            return resource_uuid

    return None


def _resolve_patient_identifier(
    patient_identifier: Optional[str],
    patient_id: Optional[str],
    patient_uuid: Optional[UUID],
    resource_id: Optional[str],
    request_id: Optional[str],
    additional_data: Dict[str, Any],
    patient_context: bool,
) -> Optional[str]:
    """Resolve anonymized patient identifier for patient-context audit logs."""
    explicit_identifier = _normalize_optional_text(patient_identifier, 255)
    if explicit_identifier:
        return explicit_identifier
    if not patient_context:
        return None

    fallback_candidates = [
        str(patient_uuid) if patient_uuid else None,
        _normalize_optional_text(patient_id, 255),
        _normalize_optional_text(additional_data.get("patient_identifier"), 255),
        _normalize_optional_text(additional_data.get("patient_id"), 255),
        _extract_patient_identifier_from_path(additional_data.get("path")),
        _normalize_optional_text(resource_id, 255),
        _normalize_optional_text(request_id, 255),
    ]

    for candidate in fallback_candidates:
        if candidate:
            digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:32]
            return f"pid:{digest}"

    return "pid:unknown"


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="lgpd.persist_audit_log",
    queue="celery",
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
    purpose: Optional[str] = None,
    legal_basis: Optional[str] = None,
    patient_identifier: Optional[str] = None,
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
        purpose: Purpose of processing/access
        legal_basis: Legal basis for processing
        patient_identifier: Anonymized patient identifier for non-null patient-context logs

    Returns:
        Dict containing success status and audit log ID
    """
    task_logger = logging.getLogger(f"tasks.{self.name}")
    task_logger.debug(f"Persisting LGPD audit log: action={action}, resource={resource_type}")

    try:
        sanitized_additional_data = _sanitize_additional_data(additional_data)
        patient_context = _is_patient_context(resource_type, patient_id, sanitized_additional_data)
        normalized_action = _normalize_action(action)
        normalized_resource_type = _normalize_resource_type(
            resource_type=resource_type,
            additional_data=sanitized_additional_data,
            patient_context=patient_context,
        )
        patient_context = patient_context or normalized_resource_type == "patient"

        normalized_data_category = _normalize_data_category(data_category, patient_context)
        resolved_user_id = _safe_parse_uuid(user_id, "user_id", task_logger)
        resolved_patient_id = _resolve_patient_uuid(
            patient_id=patient_id,
            resource_id=resource_id,
            additional_data=sanitized_additional_data,
            patient_context=patient_context,
            task_logger=task_logger,
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
        if normalized_input_resource and normalized_input_resource.lower() != normalized_resource_type:
            sanitized_additional_data.setdefault("resource_type_original", normalized_input_resource)

        with get_db_session() as db:
            # Calculate retention period (5 years for health data per LGPD)
            retention_years = (
                5
                if normalized_data_category in _SENSITIVE_DATA_CATEGORIES or patient_context
                else 2
            )
            retention_until = now_sao_paulo() + timedelta(days=365 * retention_years)

            # Create audit log record
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

            task_logger.info(
                f"LGPD audit log persisted: id={audit_log.id}, action={normalized_action}"
            )

            return {
                "success": True,
                "audit_log_id": str(audit_log.id),
                "action": normalized_action,
                "resource_type": normalized_resource_type,
            }

    except Exception as exc:
        task_logger.error(
            f"Failed to persist LGPD audit log: {exc}",
            exc_info=True,
            extra={
                "action": _normalize_action(action),
                "resource_type": _normalize_resource_type(
                    resource_type=resource_type,
                    additional_data=_sanitize_additional_data(additional_data),
                    patient_context=bool(_normalize_optional_text(patient_id, 255)),
                ),
                "user_id": user_id,
            },
        )
        raise


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="lgpd.cleanup_expired_audit_logs",
    queue="celery",
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
            now = now_sao_paulo()
            
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
