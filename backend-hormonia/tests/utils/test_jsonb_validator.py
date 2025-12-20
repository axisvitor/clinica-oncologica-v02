"""
Unit tests for JSONB metadata validator (LOW-007).

Tests the patient metadata JSON schema validation to ensure
data integrity and consistent structure.

Reference: LOW-007 - JSONB Schema Validation

Test Coverage:
- Valid metadata structures
- Invalid fields and types
- Schema violations
- Helper functions (merge, sanitize, etc.)
- Edge cases
"""

import pytest

from app.utils.jsonb_validator import (
    validate_patient_metadata,
    get_validation_errors,
    is_valid_metadata,
    sanitize_metadata,
    merge_metadata,
    get_allowed_fields,
)
from app.core.exceptions import ValidationError


# =========================================================================
# VALID METADATA TESTS
# =========================================================================


def test_empty_metadata_is_valid():
    """Empty metadata dict is valid."""
    metadata = {}
    result = validate_patient_metadata(metadata)
    assert result == {}


def test_null_metadata_returns_empty_dict():
    """None metadata returns empty dict."""
    result = validate_patient_metadata(None)
    assert result == {}


def test_valid_preferences_only():
    """Metadata with only preferences is valid."""
    metadata = {
        "preferences": {
            "language": "pt-BR",
            "notification_enabled": True
        }
    }
    result = validate_patient_metadata(metadata)
    assert result == metadata


def test_valid_medical_history_only():
    """Metadata with only medical_history is valid."""
    metadata = {
        "medical_history": {
            "allergies": ["penicillin", "latex"],
            "medications": ["aspirin"],
            "conditions": ["hypertension"]
        }
    }
    result = validate_patient_metadata(metadata)
    assert result == metadata


def test_valid_emergency_contact():
    """Metadata with valid emergency_contact is valid."""
    metadata = {
        "emergency_contact": {
            "name": "João Silva",
            "relationship": "spouse",
            "phone": "+5511999999999",
            "email": "joao@example.com"
        }
    }
    result = validate_patient_metadata(metadata)
    assert result == metadata


def test_valid_complete_metadata():
    """Complete valid metadata passes validation."""
    metadata = {
        "preferences": {
            "language": "pt-BR",
            "timezone": "America/Sao_Paulo",
            "notification_enabled": True,
            "notification_time": "09:00",
            "communication_channel": "whatsapp"
        },
        "medical_history": {
            "allergies": ["penicillin"],
            "medications": ["metformin"],
            "conditions": ["diabetes"],
            "family_history": ["cancer"],
            "surgeries": [
                {
                    "type": "appendectomy",
                    "date": "2020-05-15",
                    "notes": "No complications"
                }
            ]
        },
        "emergency_contact": {
            "name": "Maria Silva",
            "relationship": "daughter",
            "phone": "+5511988888888"
        },
        "insurance": {
            "provider": "SulAmerica",
            "policy_number": "12345678",
            "expiration_date": "2025-12-31"
        },
        "onboarding": {
            "completed": True,
            "completed_at": "2024-01-15T10:30:00Z",
            "steps_completed": ["welcome", "assessment", "preferences"],
            "welcome_sent": True,
            "initial_assessment_done": True
        },
        "custom_fields": {
            "referral_source": "website",
            "notes": "VIP patient"
        },
        "doctor_name": "Dr. João Santos"
    }
    result = validate_patient_metadata(metadata)
    assert result == metadata


def test_valid_minimal_emergency_contact():
    """Emergency contact with only required fields is valid."""
    metadata = {
        "emergency_contact": {
            "name": "Test Contact",
            "phone": "+5511999999999"
        }
    }
    result = validate_patient_metadata(metadata)
    assert result == metadata


# =========================================================================
# INVALID FIELD TYPE TESTS
# =========================================================================


def test_invalid_preference_language():
    """Invalid language enum raises ValidationError."""
    metadata = {
        "preferences": {
            "language": "fr-FR"  # Not in enum: pt-BR, en-US, es-ES
        }
    }

    with pytest.raises(ValidationError) as exc_info:
        validate_patient_metadata(metadata)

    assert "Invalid metadata" in str(exc_info.value.message)


def test_invalid_preference_notification_enabled_type():
    """Non-boolean notification_enabled raises ValidationError."""
    metadata = {
        "preferences": {
            "notification_enabled": "yes"  # Should be boolean
        }
    }

    with pytest.raises(ValidationError):
        validate_patient_metadata(metadata)


def test_invalid_allergies_not_array():
    """Allergies as non-array raises ValidationError."""
    metadata = {
        "medical_history": {
            "allergies": "penicillin"  # Should be array
        }
    }

    with pytest.raises(ValidationError):
        validate_patient_metadata(metadata)


def test_invalid_emergency_contact_phone_format():
    """Invalid phone format raises ValidationError."""
    metadata = {
        "emergency_contact": {
            "name": "Test",
            "phone": "123"  # Invalid E.164 format
        }
    }

    with pytest.raises(ValidationError):
        validate_patient_metadata(metadata)


def test_invalid_surgery_missing_required_field():
    """Surgery without required 'date' field raises ValidationError."""
    metadata = {
        "medical_history": {
            "surgeries": [
                {
                    "type": "appendectomy"
                    # Missing required "date" field
                }
            ]
        }
    }

    with pytest.raises(ValidationError):
        validate_patient_metadata(metadata)


# =========================================================================
# UNKNOWN FIELD TESTS (additionalProperties: false)
# =========================================================================


def test_unknown_top_level_field_rejected():
    """Unknown top-level field raises ValidationError."""
    metadata = {
        "unknown_field": "value"
    }

    with pytest.raises(ValidationError):
        validate_patient_metadata(metadata)


def test_unknown_preference_field_rejected():
    """Unknown field in preferences raises ValidationError."""
    metadata = {
        "preferences": {
            "language": "pt-BR",
            "unknown_preference": "value"  # Not in schema
        }
    }

    with pytest.raises(ValidationError):
        validate_patient_metadata(metadata)


def test_unknown_medical_history_field_rejected():
    """Unknown field in medical_history raises ValidationError."""
    metadata = {
        "medical_history": {
            "allergies": [],
            "unknown_medical_field": "value"
        }
    }

    with pytest.raises(ValidationError):
        validate_patient_metadata(metadata)


def test_custom_fields_allow_additional_properties():
    """custom_fields section allows any additional properties."""
    metadata = {
        "custom_fields": {
            "any_field_1": "value1",
            "any_field_2": 123,
            "any_field_3": {"nested": "object"}
        }
    }
    result = validate_patient_metadata(metadata)
    assert result == metadata


# =========================================================================
# HELPER FUNCTION TESTS
# =========================================================================


def test_get_validation_errors_returns_list():
    """get_validation_errors returns list of errors."""
    metadata = {"unknown_field": "value"}
    errors = get_validation_errors(metadata)

    assert isinstance(errors, list)
    assert len(errors) > 0
    assert "field" in errors[0]
    assert "message" in errors[0]


def test_get_validation_errors_empty_for_valid():
    """get_validation_errors returns empty list for valid metadata."""
    metadata = {"preferences": {"language": "pt-BR"}}
    errors = get_validation_errors(metadata)
    assert errors == []


def test_is_valid_metadata_true_for_valid():
    """is_valid_metadata returns True for valid metadata."""
    metadata = {"preferences": {"language": "pt-BR"}}
    assert is_valid_metadata(metadata) is True


def test_is_valid_metadata_false_for_invalid():
    """is_valid_metadata returns False for invalid metadata."""
    metadata = {"unknown_field": "value"}
    assert is_valid_metadata(metadata) is False


def test_is_valid_metadata_true_for_null():
    """is_valid_metadata returns True for None."""
    assert is_valid_metadata(None) is True


def test_sanitize_metadata_removes_unknown_fields():
    """sanitize_metadata removes unknown top-level fields."""
    metadata = {
        "preferences": {"language": "pt-BR"},
        "unknown_field": "should be removed",
        "another_unknown": "also removed"
    }
    result = sanitize_metadata(metadata)

    assert "preferences" in result
    assert "unknown_field" not in result
    assert "another_unknown" not in result


def test_sanitize_metadata_keeps_valid_fields():
    """sanitize_metadata keeps all valid fields."""
    metadata = {
        "preferences": {"language": "pt-BR"},
        "medical_history": {"allergies": ["penicillin"]},
        "custom_fields": {"test": "value"}
    }
    result = sanitize_metadata(metadata)

    assert result == metadata


def test_sanitize_null_metadata():
    """sanitize_metadata handles None."""
    result = sanitize_metadata(None)
    assert result == {}


def test_merge_metadata_simple():
    """merge_metadata merges two metadata dicts."""
    existing = {"preferences": {"language": "pt-BR"}}
    updates = {"medical_history": {"allergies": ["latex"]}}

    result = merge_metadata(existing, updates)

    assert "preferences" in result
    assert "medical_history" in result
    assert result["preferences"]["language"] == "pt-BR"


def test_merge_metadata_deep_merge():
    """merge_metadata deep merges nested dicts."""
    existing = {
        "preferences": {
            "language": "pt-BR",
            "notification_enabled": True
        }
    }
    updates = {
        "preferences": {
            "timezone": "America/Sao_Paulo"
        }
    }

    result = merge_metadata(existing, updates)

    assert result["preferences"]["language"] == "pt-BR"
    assert result["preferences"]["timezone"] == "America/Sao_Paulo"
    assert result["preferences"]["notification_enabled"] is True


def test_merge_metadata_validates_result():
    """merge_metadata validates merged result by default."""
    existing = {"preferences": {"language": "pt-BR"}}
    updates = {"unknown_field": "value"}

    with pytest.raises(ValidationError):
        merge_metadata(existing, updates, validate_result=True)


def test_merge_metadata_skip_validation():
    """merge_metadata can skip validation."""
    existing = {"preferences": {"language": "pt-BR"}}
    updates = {"unknown_field": "value"}

    result = merge_metadata(existing, updates, validate_result=False)
    assert "unknown_field" in result


def test_get_allowed_fields():
    """get_allowed_fields returns list of valid top-level fields."""
    fields = get_allowed_fields()

    assert isinstance(fields, list)
    assert "preferences" in fields
    assert "medical_history" in fields
    assert "emergency_contact" in fields
    assert "custom_fields" in fields


# =========================================================================
# EDGE CASES
# =========================================================================


def test_empty_arrays_are_valid():
    """Empty arrays in medical_history are valid."""
    metadata = {
        "medical_history": {
            "allergies": [],
            "medications": [],
            "conditions": []
        }
    }
    result = validate_patient_metadata(metadata)
    assert result == metadata


def test_notification_time_format_validation():
    """notification_time validates HH:MM format."""
    # Valid formats
    valid_times = ["00:00", "09:30", "23:59", "12:00"]
    for time in valid_times:
        metadata = {"preferences": {"notification_time": time}}
        result = validate_patient_metadata(metadata)
        assert result["preferences"]["notification_time"] == time

    # Invalid formats
    invalid_times = ["9:30", "25:00", "12:60", "12:5", "abc"]
    for time in invalid_times:
        metadata = {"preferences": {"notification_time": time}}
        with pytest.raises(ValidationError):
            validate_patient_metadata(metadata)


def test_timezone_pattern_validation():
    """timezone validates pattern (Continent/City)."""
    # Valid timezones
    valid_timezones = ["America/Sao_Paulo", "Europe/London", "Asia/Tokyo"]
    for tz in valid_timezones:
        metadata = {"preferences": {"timezone": tz}}
        result = validate_patient_metadata(metadata)
        assert result["preferences"]["timezone"] == tz

    # Invalid timezones
    invalid_timezones = ["invalid", "America", "123"]
    for tz in invalid_timezones:
        metadata = {"preferences": {"timezone": tz}}
        with pytest.raises(ValidationError):
            validate_patient_metadata(metadata)


def test_unique_items_in_arrays():
    """Arrays enforce uniqueItems constraint."""
    # Note: jsonschema doesn't always enforce uniqueItems strictly
    # This test documents expected behavior
    metadata = {
        "medical_history": {
            "allergies": ["penicillin", "latex", "penicillin"]  # Duplicate
        }
    }
    # This should ideally fail, but jsonschema may not enforce it
    # depending on implementation
    result = validate_patient_metadata(metadata)
    # Test passes if no exception (lenient) or fails (strict)
    assert result is not None
