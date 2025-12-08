"""
JSONB Schema Validation for Patient Metadata.

This module provides JSON Schema validation for the patient.metadata JSONB field,
ensuring data integrity and consistent structure across the application.

Reference: LOW-007 - JSONB Schema Validation
Migration: 014_validate_patient_metadata.py

Usage:
    from app.utils.jsonb_validator import validate_patient_metadata

    metadata = {...}
    validated = validate_patient_metadata(metadata)
"""

from typing import Dict, Any, List, Optional
from jsonschema import validate, ValidationError as JsonSchemaValidationError, Draft7Validator
from app.core.exceptions import ValidationError


# =========================================================================
# PATIENT METADATA JSON SCHEMA
# =========================================================================

PATIENT_METADATA_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Patient Metadata Schema",
    "description": "Schema for validating patient metadata JSONB field",
    "type": "object",
    "properties": {
        "preferences": {
            "type": "object",
            "description": "Patient preferences and settings",
            "properties": {
                "language": {
                    "type": "string",
                    "enum": ["pt-BR", "en-US", "es-ES"],
                    "description": "Preferred language for communications"
                },
                "timezone": {
                    "type": "string",
                    "description": "Patient timezone (e.g., 'America/Sao_Paulo')",
                    "pattern": "^[A-Za-z]+/[A-Za-z_]+$"
                },
                "notification_enabled": {
                    "type": "boolean",
                    "description": "Whether notifications are enabled"
                },
                "notification_time": {
                    "type": "string",
                    "description": "Preferred notification time (HH:MM format)",
                    "pattern": "^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
                },
                "communication_channel": {
                    "type": "string",
                    "enum": ["whatsapp", "email", "sms", "phone"],
                    "description": "Preferred communication channel"
                }
            },
            "additionalProperties": False
        },
        "medical_history": {
            "type": "object",
            "description": "Medical history information",
            "properties": {
                "allergies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of known allergies",
                    "uniqueItems": True
                },
                "medications": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Current medications",
                    "uniqueItems": True
                },
                "conditions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Pre-existing medical conditions (comorbidities)",
                    "uniqueItems": True
                },
                "family_history": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Family medical history",
                    "uniqueItems": True
                },
                "surgeries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "date": {"type": "string", "format": "date"},
                            "notes": {"type": "string"}
                        },
                        "required": ["type", "date"]
                    },
                    "description": "Past surgical procedures"
                }
            },
            "additionalProperties": False
        },
        "blood_type": {
            "type": "string",
            "pattern": "^(A|B|AB|O)[+-]$",
            "description": "Blood type in standard format (A+, B-, AB+, O-, etc.)"
        },
        "emergency_contact": {
            "type": "object",
            "description": "Emergency contact information",
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "relationship": {"type": "string"},
                "phone": {
                    "type": "string",
                    "pattern": "^\\+[1-9]\\d{1,14}$"  # E.164 format
                },
                "email": {
                    "type": "string",
                    "format": "email"
                }
            },
            "required": ["name", "phone"],
            "additionalProperties": False
        },
        "insurance": {
            "type": "object",
            "description": "Insurance information",
            "properties": {
                "provider": {"type": "string"},
                "policy_number": {"type": "string"},
                "group_number": {"type": "string"},
                "expiration_date": {
                    "type": "string",
                    "format": "date"
                }
            },
            "additionalProperties": False
        },
        "onboarding": {
            "type": "object",
            "description": "Onboarding process metadata",
            "properties": {
                "completed": {"type": "boolean"},
                "completed_at": {
                    "type": "string",
                    "format": "date-time"
                },
                "steps_completed": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "welcome_sent": {"type": "boolean"},
                "initial_assessment_done": {"type": "boolean"}
            },
            "additionalProperties": False
        },
        "custom_fields": {
            "type": "object",
            "description": "Custom fields for clinic-specific data",
            "additionalProperties": True  # Allow any custom fields
        },
        "doctor_name": {
            "type": "string",
            "description": "Cached doctor name for performance"
        },
        "system": {
            "type": "object",
            "description": "System-managed metadata",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["whatsapp", "web", "api", "import"],
                    "description": "How the patient was created"
                },
                "version": {
                    "type": "string",
                    "description": "Schema version for migrations"
                },
                "last_sync": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Last sync timestamp"
                }
            },
            "additionalProperties": False
        }
    },
    "additionalProperties": False  # Strict: no unknown top-level keys
}


# =========================================================================
# VALIDATION FUNCTIONS
# =========================================================================


def validate_patient_metadata(
    metadata: Dict[str, Any],
    strict: bool = True
) -> Dict[str, Any]:
    """
    Validate patient metadata against JSON schema.

    Args:
        metadata: The metadata dictionary to validate
        strict: If True, raise ValidationError on failure. If False, return errors dict.

    Returns:
        The validated metadata (same as input if valid)

    Raises:
        ValidationError: If metadata doesn't match schema (when strict=True)

    Examples:
        >>> metadata = {"preferences": {"language": "pt-BR"}}
        >>> validated = validate_patient_metadata(metadata)

        >>> bad_metadata = {"unknown_field": "value"}
        >>> validate_patient_metadata(bad_metadata)  # Raises ValidationError
    """
    if metadata is None:
        return {}

    try:
        # Validate against schema
        validate(instance=metadata, schema=PATIENT_METADATA_SCHEMA)
        return metadata
    except JsonSchemaValidationError as e:
        error_message = f"Invalid metadata: {e.message}"
        error_details = {
            "field": ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "root",
            "error": e.message,
            "schema_path": ".".join(str(p) for p in e.absolute_schema_path) if e.absolute_schema_path else None,
            "failed_value": e.instance
        }

        if strict:
            raise ValidationError(error_message, error_details)
        else:
            return error_details


def get_validation_errors(metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get all validation errors without raising exception.

    Args:
        metadata: The metadata to validate

    Returns:
        List of error dictionaries, or empty list if valid

    Examples:
        >>> errors = get_validation_errors({"unknown": "value"})
        >>> if errors:
        ...     print(f"Found {len(errors)} errors")
    """
    if metadata is None:
        return []

    validator = Draft7Validator(PATIENT_METADATA_SCHEMA)
    errors = []

    for error in validator.iter_errors(metadata):
        errors.append({
            "field": ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "root",
            "message": error.message,
            "schema_path": ".".join(str(p) for p in error.absolute_schema_path),
            "failed_value": error.instance
        })

    return errors


def is_valid_metadata(metadata: Dict[str, Any]) -> bool:
    """
    Check if metadata is valid without raising exception.

    Args:
        metadata: The metadata to validate

    Returns:
        True if valid, False otherwise

    Examples:
        >>> if is_valid_metadata(patient.patient_data):
        ...     print("Valid metadata")
    """
    if metadata is None:
        return True

    try:
        validate(instance=metadata, schema=PATIENT_METADATA_SCHEMA)
        return True
    except JsonSchemaValidationError:
        return False


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove invalid fields from metadata to make it valid.

    This is useful for migration scenarios where you want to clean up
    existing data instead of failing validation.

    Args:
        metadata: The metadata to sanitize

    Returns:
        Sanitized metadata (only valid fields retained)

    Examples:
        >>> dirty_metadata = {"preferences": {"language": "pt-BR"}, "unknown": "bad"}
        >>> clean = sanitize_metadata(dirty_metadata)
        >>> print(clean)  # {"preferences": {"language": "pt-BR"}}
    """
    if metadata is None:
        return {}

    sanitized = {}

    # Only keep known top-level keys
    known_keys = set(PATIENT_METADATA_SCHEMA["properties"].keys())

    for key, value in metadata.items():
        if key in known_keys:
            # TODO: Deep validation/sanitization for nested objects
            # For now, just keep the value as-is if top-level key is valid
            sanitized[key] = value

    return sanitized


def merge_metadata(
    existing: Optional[Dict[str, Any]],
    updates: Dict[str, Any],
    validate_result: bool = True
) -> Dict[str, Any]:
    """
    Safely merge metadata updates into existing metadata.

    Args:
        existing: Current metadata (or None)
        updates: New metadata to merge
        validate_result: If True, validate merged result

    Returns:
        Merged metadata

    Raises:
        ValidationError: If merged result is invalid (when validate_result=True)

    Examples:
        >>> existing = {"preferences": {"language": "pt-BR"}}
        >>> updates = {"preferences": {"timezone": "America/Sao_Paulo"}}
        >>> merged = merge_metadata(existing, updates)
        >>> print(merged)  # {"preferences": {"language": "pt-BR", "timezone": "..."}}
    """
    if existing is None:
        existing = {}

    # Deep merge
    result = existing.copy()

    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Deep merge for nested dicts
            result[key] = {**result[key], **value}
        else:
            # Replace for non-dict values
            result[key] = value

    if validate_result:
        return validate_patient_metadata(result)

    return result


# =========================================================================
# SCHEMA INFORMATION
# =========================================================================


def get_schema_version() -> str:
    """Get the current schema version."""
    return "1.1.0"  # Clinical fields added: blood_type, enhanced emergency_contact


def get_allowed_fields() -> List[str]:
    """Get list of allowed top-level fields in metadata."""
    return list(PATIENT_METADATA_SCHEMA["properties"].keys())


def get_schema_docs() -> str:
    """Get human-readable schema documentation."""
    return """
Patient Metadata Schema v1.1.0 (Clinical Fields Added)

Allowed top-level fields:
- preferences: Patient preferences (language, timezone, notifications)
- medical_history: Medical history (allergies, medications, conditions/comorbidities)
- blood_type: Blood type in standard format (A+, B-, AB+, O-, etc.) - NEW
- emergency_contact: Emergency contact information (name, phone, relationship, email)
- insurance: Insurance policy information
- onboarding: Onboarding process metadata
- custom_fields: Clinic-specific custom fields
- doctor_name: Cached doctor name (performance)
- system: System-managed metadata

Clinical Fields (V2 API Evolution):
- medical_history.allergies: Known allergies
- medical_history.medications: Current medications
- medical_history.conditions: Pre-existing conditions (comorbidities)
- blood_type: Blood type (NEW)
- emergency_contact.name: Emergency contact name (REQUIRED with phone)
- emergency_contact.phone: Emergency contact phone in E.164 format (REQUIRED with name)

For full schema details, see:
- docs/schemas/PATIENT_METADATA_SCHEMA.md
- app/utils/patient_metadata_schema.py (clinical validation)
"""


__all__ = [
    "PATIENT_METADATA_SCHEMA",
    "validate_patient_metadata",
    "get_validation_errors",
    "is_valid_metadata",
    "sanitize_metadata",
    "merge_metadata",
    "get_schema_version",
    "get_allowed_fields",
    "get_schema_docs",
]
