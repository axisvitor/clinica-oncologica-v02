"""LGPD helpers extracted from app.tasks.lgpd_tasks."""

import hashlib
import logging
import re
from typing import Any, Dict, Optional, Sequence
from uuid import UUID

from app.models.lgpd_audit import LGPDActionType, LGPDDataCategory

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
