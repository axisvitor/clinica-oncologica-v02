"""
Unit tests for patient_metadata_schema module.

Tests clinical field validation for patient metadata JSONB.

Reference: V2 API Evolution - Clinical Fields
Related: app/utils/patient_metadata_schema.py
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.utils.patient_metadata_schema import (
    validate_clinical_metadata,
    validate_blood_type,
    validate_emergency_contact,
    get_clinical_fields,
    merge_clinical_metadata,
    extract_clinical_summary,
    ClinicalMetadataSchema,
    MedicalHistorySchema,
    EmergencyContactSchema,
    BloodTypeValidator,
)
from app.core.exceptions import ValidationError


# =========================================================================
# BLOOD TYPE VALIDATION TESTS
# =========================================================================


class TestBloodTypeValidation:
    """Test blood type validation."""

    def test_valid_blood_types(self):
        """Test all valid blood type formats."""
        valid_types = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
        for blood_type in valid_types:
            assert validate_blood_type(blood_type) is True

    def test_invalid_blood_types(self):
        """Test invalid blood type formats."""
        invalid_types = [
            "A",  # Missing +/-
            "a+",  # Lowercase
            "AB",  # Missing +/-
            "C+",  # Invalid letter
            "O++",  # Double +
            "AB+-",  # Mixed +/-
            "",  # Empty
            "AB +",  # Space
        ]
        for blood_type in invalid_types:
            assert validate_blood_type(blood_type) is False

    def test_blood_type_validator_pydantic(self):
        """Test BloodTypeValidator Pydantic model."""
        # Valid
        validator = BloodTypeValidator(blood_type="A+")
        assert validator.blood_type == "A+"

        # Invalid
        with pytest.raises(PydanticValidationError):
            BloodTypeValidator(blood_type="Invalid")


# =========================================================================
# EMERGENCY CONTACT VALIDATION TESTS
# =========================================================================


class TestEmergencyContactValidation:
    """Test emergency contact validation."""

    def test_valid_emergency_contact(self):
        """Test valid emergency contact."""
        contact = {
            "name": "Maria Silva",
            "phone": "+5511987654321",
            "relationship": "Spouse",
            "email": "maria@example.com"
        }
        assert validate_emergency_contact(contact) is True

    def test_emergency_contact_minimal(self):
        """Test emergency contact with only required fields."""
        contact = {
            "name": "João Santos",
            "phone": "+5511912345678"
        }
        assert validate_emergency_contact(contact) is True

    def test_invalid_phone_format(self):
        """Test invalid phone formats."""
        invalid_phones = [
            {"name": "Test", "phone": "11987654321"},  # Missing +
            {"name": "Test", "phone": "+"},  # Just +
            {"name": "Test", "phone": "+55abc"},  # Non-digits
            {"name": "Test", "phone": "555-1234"},  # US format without +
        ]
        for contact in invalid_phones:
            assert validate_emergency_contact(contact) is False

    def test_missing_required_fields(self):
        """Test emergency contact missing required fields."""
        # Missing name
        assert validate_emergency_contact({"phone": "+5511987654321"}) is False

        # Missing phone
        assert validate_emergency_contact({"name": "Test"}) is False

    def test_emergency_contact_schema(self):
        """Test EmergencyContactSchema Pydantic model."""
        # Valid
        schema = EmergencyContactSchema(
            name="Maria Silva",
            phone="+5511987654321",
            relationship="Spouse"
        )
        assert schema.name == "Maria Silva"
        assert schema.phone == "+5511987654321"

        # Invalid phone
        with pytest.raises(PydanticValidationError):
            EmergencyContactSchema(
                name="Test",
                phone="invalid"
            )


# =========================================================================
# MEDICAL HISTORY VALIDATION TESTS
# =========================================================================


class TestMedicalHistoryValidation:
    """Test medical history validation."""

    def test_valid_medical_history(self):
        """Test valid medical history."""
        history = {
            "allergies": ["Penicillin", "Peanuts"],
            "medications": ["Aspirin 100mg", "Lisinopril 10mg"],
            "conditions": ["Diabetes Type 2", "Hypertension"]
        }
        schema = MedicalHistorySchema(**history)
        assert len(schema.allergies) == 2
        assert len(schema.medications) == 2
        assert len(schema.conditions) == 2

    def test_duplicate_removal(self):
        """Test that duplicate items are removed from lists."""
        history = {
            "allergies": ["Penicillin", "Penicillin", "Peanuts"],
            "medications": ["Aspirin", "Aspirin"]
        }
        schema = MedicalHistorySchema(**history)
        assert len(schema.allergies) == 2
        assert len(schema.medications) == 1

    def test_empty_lists(self):
        """Test empty lists are valid."""
        history = {
            "allergies": [],
            "medications": [],
            "conditions": []
        }
        schema = MedicalHistorySchema(**history)
        assert schema.allergies == []
        assert schema.medications == []

    def test_none_values(self):
        """Test None values for optional fields."""
        history = MedicalHistorySchema()
        assert history.allergies is None
        assert history.medications is None
        assert history.conditions is None


# =========================================================================
# CLINICAL METADATA VALIDATION TESTS
# =========================================================================


class TestClinicalMetadataValidation:
    """Test complete clinical metadata validation."""

    def test_valid_complete_clinical_metadata(self):
        """Test validation of complete clinical metadata."""
        metadata = {
            "medical_history": {
                "allergies": ["Penicillin"],
                "medications": ["Aspirin 100mg"],
                "conditions": ["Diabetes Type 2"]
            },
            "blood_type": "A+",
            "emergency_contact": {
                "name": "Maria Silva",
                "phone": "+5511987654321",
                "relationship": "Spouse"
            }
        }
        result = validate_clinical_metadata(metadata)
        assert result == metadata

    def test_validation_with_extra_fields(self):
        """Test that extra fields are preserved (backward compatibility)."""
        metadata = {
            "medical_history": {
                "allergies": ["Penicillin"]
            },
            "preferences": {  # Not a clinical field
                "language": "pt-BR"
            }
        }
        result = validate_clinical_metadata(metadata)
        assert "preferences" in result
        assert "medical_history" in result

    def test_invalid_blood_type_strict(self):
        """Test validation fails with invalid blood type in strict mode."""
        metadata = {
            "blood_type": "Invalid"
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_clinical_metadata(metadata, strict=True)
        assert "Invalid clinical metadata" in str(exc_info.value)

    def test_invalid_blood_type_non_strict(self):
        """Test validation returns original data in non-strict mode."""
        metadata = {
            "blood_type": "Invalid"
        }
        result = validate_clinical_metadata(metadata, strict=False)
        # In non-strict mode, returns original data
        assert result == metadata

    def test_empty_metadata(self):
        """Test validation of empty metadata."""
        result = validate_clinical_metadata({})
        assert result == {}

    def test_none_metadata(self):
        """Test validation of None metadata."""
        result = validate_clinical_metadata(None)
        assert result == {}


# =========================================================================
# CLINICAL FIELDS EXTRACTION TESTS
# =========================================================================


class TestGetClinicalFields:
    """Test extraction of clinical fields from metadata."""

    def test_extract_all_clinical_fields(self):
        """Test extraction of all clinical fields."""
        metadata = {
            "medical_history": {
                "allergies": ["Penicillin"]
            },
            "blood_type": "A+",
            "emergency_contact": {
                "name": "Maria",
                "phone": "+5511987654321"
            },
            "preferences": {  # Not clinical
                "language": "pt-BR"
            }
        }
        clinical = get_clinical_fields(metadata)
        assert "medical_history" in clinical
        assert "blood_type" in clinical
        assert "emergency_contact" in clinical
        assert "preferences" not in clinical

    def test_extract_partial_clinical_fields(self):
        """Test extraction when only some clinical fields present."""
        metadata = {
            "blood_type": "O+",
            "preferences": {
                "language": "pt-BR"
            }
        }
        clinical = get_clinical_fields(metadata)
        assert clinical == {"blood_type": "O+"}

    def test_extract_no_clinical_fields(self):
        """Test extraction when no clinical fields present."""
        metadata = {
            "preferences": {
                "language": "pt-BR"
            }
        }
        clinical = get_clinical_fields(metadata)
        assert clinical == {}


# =========================================================================
# MERGE CLINICAL METADATA TESTS
# =========================================================================


class TestMergeClinicalMetadata:
    """Test merging of clinical metadata."""

    def test_merge_new_fields(self):
        """Test merging new clinical fields into existing metadata."""
        existing = {
            "preferences": {
                "language": "pt-BR"
            }
        }
        updates = {
            "blood_type": "A+",
            "medical_history": {
                "allergies": ["Penicillin"]
            }
        }
        result = merge_clinical_metadata(existing, updates)
        assert result["blood_type"] == "A+"
        assert result["medical_history"]["allergies"] == ["Penicillin"]
        assert result["preferences"]["language"] == "pt-BR"

    def test_merge_medical_history_deep(self):
        """Test deep merge of medical_history."""
        existing = {
            "medical_history": {
                "allergies": ["Penicillin"]
            }
        }
        updates = {
            "medical_history": {
                "medications": ["Aspirin"]
            }
        }
        result = merge_clinical_metadata(existing, updates)
        assert result["medical_history"]["allergies"] == ["Penicillin"]
        assert result["medical_history"]["medications"] == ["Aspirin"]

    def test_merge_overwrites_simple_values(self):
        """Test that simple values are overwritten."""
        existing = {
            "blood_type": "A+"
        }
        updates = {
            "blood_type": "B+"
        }
        result = merge_clinical_metadata(existing, updates)
        assert result["blood_type"] == "B+"

    def test_merge_with_none_existing(self):
        """Test merging when existing is None."""
        updates = {
            "blood_type": "A+"
        }
        result = merge_clinical_metadata(None, updates)
        assert result["blood_type"] == "A+"

    def test_merge_validation_enabled(self):
        """Test that validation runs when enabled."""
        existing = {}
        updates = {
            "blood_type": "Invalid"
        }
        with pytest.raises(ValidationError):
            merge_clinical_metadata(existing, updates, validate_result=True)

    def test_merge_validation_disabled(self):
        """Test that validation is skipped when disabled."""
        existing = {}
        updates = {
            "blood_type": "Invalid"
        }
        # Should not raise when validation disabled
        result = merge_clinical_metadata(existing, updates, validate_result=False)
        assert result["blood_type"] == "Invalid"


# =========================================================================
# CLINICAL SUMMARY EXTRACTION TESTS
# =========================================================================


class TestExtractClinicalSummary:
    """Test extraction of clinical summary for API responses."""

    def test_extract_complete_summary(self):
        """Test extraction of complete clinical summary."""
        metadata = {
            "medical_history": {
                "allergies": ["Penicillin"],
                "medications": ["Aspirin"],
                "conditions": ["Diabetes"]
            },
            "blood_type": "A+",
            "emergency_contact": {
                "name": "Maria Silva",
                "phone": "+5511987654321"
            }
        }
        summary = extract_clinical_summary(metadata)
        assert summary["allergies"] == ["Penicillin"]
        assert summary["current_medications"] == ["Aspirin"]
        assert summary["comorbidities"] == ["Diabetes"]
        assert summary["blood_type"] == "A+"
        assert summary["emergency_contact_name"] == "Maria Silva"
        assert summary["emergency_contact_phone"] == "+5511987654321"

    def test_extract_partial_summary(self):
        """Test extraction when only some fields present."""
        metadata = {
            "blood_type": "O+",
            "medical_history": {
                "allergies": ["Peanuts"]
            }
        }
        summary = extract_clinical_summary(metadata)
        assert summary["blood_type"] == "O+"
        assert summary["allergies"] == ["Peanuts"]
        assert "current_medications" not in summary
        assert "emergency_contact_name" not in summary

    def test_extract_empty_summary(self):
        """Test extraction from empty metadata."""
        summary = extract_clinical_summary({})
        assert summary == {}

    def test_extract_none_summary(self):
        """Test extraction from None metadata."""
        summary = extract_clinical_summary(None)
        assert summary == {}

    def test_summary_field_mapping(self):
        """Test that field names are correctly mapped for API."""
        metadata = {
            "medical_history": {
                "medications": ["Aspirin"],
                "conditions": ["Hypertension"]
            }
        }
        summary = extract_clinical_summary(metadata)
        # medications -> current_medications
        assert "current_medications" in summary
        assert "medications" not in summary
        # conditions -> comorbidities
        assert "comorbidities" in summary
        assert "conditions" not in summary


# =========================================================================
# INTEGRATION TESTS
# =========================================================================


class TestClinicalMetadataIntegration:
    """Integration tests for clinical metadata workflows."""

    def test_complete_patient_metadata_workflow(self):
        """Test complete workflow: validate -> extract -> merge."""
        # 1. Initial patient metadata
        initial = {
            "preferences": {
                "language": "pt-BR"
            },
            "medical_history": {
                "allergies": ["Penicillin"]
            }
        }

        # 2. Validate initial
        validated = validate_clinical_metadata(initial)
        assert validated == initial

        # 3. Extract clinical summary for API
        summary = extract_clinical_summary(validated)
        assert summary["allergies"] == ["Penicillin"]

        # 4. Merge new clinical data
        updates = {
            "blood_type": "A+",
            "emergency_contact": {
                "name": "Maria Silva",
                "phone": "+5511987654321"
            },
            "medical_history": {
                "medications": ["Aspirin"]
            }
        }
        merged = merge_clinical_metadata(validated, updates)

        # 5. Validate merged result
        final = validate_clinical_metadata(merged)
        assert final["blood_type"] == "A+"
        assert final["medical_history"]["allergies"] == ["Penicillin"]
        assert final["medical_history"]["medications"] == ["Aspirin"]
        assert final["emergency_contact"]["name"] == "Maria Silva"

        # 6. Extract final summary
        final_summary = extract_clinical_summary(final)
        assert final_summary["blood_type"] == "A+"
        assert final_summary["allergies"] == ["Penicillin"]
        assert final_summary["current_medications"] == ["Aspirin"]
        assert final_summary["emergency_contact_name"] == "Maria Silva"

    def test_api_response_structure(self):
        """Test that extracted summary matches expected API response structure."""
        metadata = {
            "medical_history": {
                "allergies": ["Penicillin", "Latex"],
                "medications": ["Metformin 500mg", "Lisinopril 10mg"],
                "conditions": ["Type 2 Diabetes", "Hypertension"]
            },
            "blood_type": "B+",
            "emergency_contact": {
                "name": "João Silva",
                "phone": "+5511987654321",
                "relationship": "Husband"
            }
        }

        summary = extract_clinical_summary(metadata)

        # Verify API-friendly field names
        expected_fields = {
            "allergies",
            "current_medications",
            "comorbidities",
            "blood_type",
            "emergency_contact_name",
            "emergency_contact_phone"
        }
        assert set(summary.keys()) == expected_fields

        # Verify data types
        assert isinstance(summary["allergies"], list)
        assert isinstance(summary["current_medications"], list)
        assert isinstance(summary["comorbidities"], list)
        assert isinstance(summary["blood_type"], str)
        assert isinstance(summary["emergency_contact_name"], str)
        assert isinstance(summary["emergency_contact_phone"], str)
