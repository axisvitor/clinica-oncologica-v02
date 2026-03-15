"""Self-contained helpers for historical Alembic revisions.

Keep this module free of application runtime imports so graph inspection commands
(`history`, `heads`, `current`) can load revisions without bootstrapping
settings, integrations, or service code.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

SAO_PAULO_TZ_NAME = "America/Sao_Paulo"
SAO_PAULO_TZ = ZoneInfo(SAO_PAULO_TZ_NAME)

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
                    "description": "Preferred language for communications",
                },
                "timezone": {
                    "type": "string",
                    "description": "Patient timezone (e.g., 'America/Sao_Paulo')",
                    "pattern": "^[A-Za-z]+/[A-Za-z_]+$",
                },
                "notification_enabled": {
                    "type": "boolean",
                    "description": "Whether notifications are enabled",
                },
                "notification_time": {
                    "type": "string",
                    "description": "Preferred notification time (HH:MM format)",
                    "pattern": "^([01][0-9]|2[0-3]):[0-5][0-9]$",
                },
                "communication_channel": {
                    "type": "string",
                    "enum": ["whatsapp", "email", "sms", "phone"],
                    "description": "Preferred communication channel",
                },
            },
            "additionalProperties": False,
        },
        "medical_history": {
            "type": "object",
            "description": "Medical history information",
            "properties": {
                "allergies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of known allergies",
                    "uniqueItems": True,
                },
                "medications": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Current medications",
                    "uniqueItems": True,
                },
                "conditions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Pre-existing medical conditions (comorbidities)",
                    "uniqueItems": True,
                },
                "family_history": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Family medical history",
                    "uniqueItems": True,
                },
                "surgeries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "date": {"type": "string", "format": "date"},
                            "notes": {"type": "string"},
                        },
                        "required": ["type", "date"],
                    },
                    "description": "Past surgical procedures",
                },
            },
            "additionalProperties": False,
        },
        "blood_type": {
            "type": "string",
            "pattern": "^(A|B|AB|O)[+-]$",
            "description": "Blood type in standard format (A+, B-, AB+, O-, etc.)",
        },
        "emergency_contact": {
            "type": "object",
            "description": "Emergency contact information",
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "relationship": {"type": "string"},
                "phone": {
                    "type": "string",
                    "pattern": "^\\+[1-9]\\d{1,14}$",
                },
                "email": {"type": "string", "format": "email"},
            },
            "required": ["name", "phone"],
            "additionalProperties": False,
        },
        "insurance": {
            "type": "object",
            "description": "Insurance information",
            "properties": {
                "provider": {"type": "string"},
                "policy_number": {"type": "string"},
                "group_number": {"type": "string"},
                "expiration_date": {"type": "string", "format": "date"},
            },
            "additionalProperties": False,
        },
        "onboarding": {
            "type": "object",
            "description": "Onboarding process metadata",
            "properties": {
                "completed": {"type": "boolean"},
                "completed_at": {"type": "string", "format": "date-time"},
                "steps_completed": {"type": "array", "items": {"type": "string"}},
                "welcome_sent": {"type": "boolean"},
                "initial_assessment_done": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        "custom_fields": {
            "type": "object",
            "description": "Custom fields for clinic-specific data",
            "additionalProperties": True,
        },
        "doctor_name": {
            "type": "string",
            "description": "Cached doctor name for performance",
        },
        "quarantine": {
            "type": "boolean",
            "description": "Indicates the patient is quarantined due to a system issue",
        },
        "quarantine_reason": {
            "type": "string",
            "description": "Reason for patient quarantine",
        },
        "quarantine_at": {
            "type": "string",
            "format": "date-time",
            "description": "Timestamp when quarantine was applied",
        },
        "saga_id": {
            "type": "string",
            "pattern": "^[0-9a-fA-F-]{36}$",
            "description": "Saga identifier associated with quarantine",
        },
        "system": {
            "type": "object",
            "description": "System-managed metadata",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["whatsapp", "web", "api", "import"],
                    "description": "How the patient was created",
                },
                "version": {
                    "type": "string",
                    "description": "Schema version for migrations",
                },
                "last_sync": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Last sync timestamp",
                },
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}


def now_sao_paulo_naive() -> datetime:
    """Match the legacy helper semantics used by historical migrations."""
    return datetime.now(SAO_PAULO_TZ).replace(tzinfo=None)



def _load_jsonschema() -> tuple[Any, Any, Any]:
    from jsonschema import Draft7Validator, ValidationError as JsonSchemaValidationError, validate

    return Draft7Validator, JsonSchemaValidationError, validate



def get_validation_errors(metadata: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return legacy-shaped jsonschema errors for patient metadata."""
    if metadata is None:
        return []

    draft7_validator, _, _ = _load_jsonschema()
    validator = draft7_validator(PATIENT_METADATA_SCHEMA)
    errors: list[dict[str, Any]] = []

    for error in validator.iter_errors(metadata):
        errors.append(
            {
                "field": ".".join(str(part) for part in error.absolute_path)
                if error.absolute_path
                else "root",
                "message": error.message,
                "schema_path": ".".join(str(part) for part in error.absolute_schema_path),
                "failed_value": error.instance,
            }
        )

    return errors



def is_valid_metadata(metadata: dict[str, Any] | None) -> bool:
    """Preserve the historical boolean validation contract for migration 016."""
    if metadata is None:
        return True

    _, json_schema_validation_error, validate = _load_jsonschema()

    try:
        validate(instance=metadata, schema=PATIENT_METADATA_SCHEMA)
        return True
    except json_schema_validation_error:
        return False



def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Match the legacy top-level key sanitization helper."""
    if metadata is None:
        return {}

    known_keys = set(PATIENT_METADATA_SCHEMA["properties"].keys())
    return {key: value for key, value in metadata.items() if key in known_keys}


__all__ = [
    "PATIENT_METADATA_SCHEMA",
    "get_validation_errors",
    "is_valid_metadata",
    "now_sao_paulo_naive",
    "sanitize_metadata",
]
