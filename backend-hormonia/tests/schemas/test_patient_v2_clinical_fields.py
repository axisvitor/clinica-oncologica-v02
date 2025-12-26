"""
Test clinical fields in patient v2 schemas
Validates new clinical fields: allergies, medications, blood_type, emergency_contact, patient_data
"""

import pytest
from datetime import date
from uuid import uuid4
from pydantic import ValidationError

from app.schemas.v2.patient import PatientV2Base, PatientV2Create, PatientV2Update, PatientV2Response


class TestPatientV2ClinicalFields:
    """Test suite for new clinical fields in patient v2 schemas"""

    def test_patient_v2_base_with_clinical_fields(self):
        """Test PatientV2Base accepts all clinical fields"""
        data = {
            "name": "João Silva",
            "email": "joao@example.com",
            "phone": "+5511987654321",
            "birth_date": date(1980, 5, 15),
            "cpf": "11144477735",  # Valid CPF for testing
            "treatment_type": "Reposição Hormonal",
            "treatment_start_date": date(2025, 1, 10),
            "doctor_notes": "Paciente respondeu bem ao tratamento",
            "diagnosis": "Hipotireoidismo",
            "treatment_phase": "maintenance",
            "timezone": "America/Sao_Paulo",
            "allergies": "Penicilina, Dipirona",
            "medications": "Levotiroxina 100mcg",
            "blood_type": "A+",
            "emergency_contact": "Maria Silva - (11) 99999-9999",
            "patient_data": {"insurance": "Unimed", "preferred_contact": "whatsapp"}
        }

        patient = PatientV2Base(**data)
        assert patient.allergies == "Penicilina, Dipirona"
        assert patient.medications == "Levotiroxina 100mcg"
        assert patient.blood_type == "A+"
        assert patient.emergency_contact == "Maria Silva - (11) 99999-9999"
        assert patient.patient_data == {"insurance": "Unimed", "preferred_contact": "whatsapp"}

    def test_blood_type_validation_valid_types(self):
        """Test blood type accepts valid patterns"""
        valid_types = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

        for blood_type in valid_types:
            data = {
                "name": "Test Patient",
                "blood_type": blood_type
            }
            patient = PatientV2Base(**data)
            assert patient.blood_type == blood_type

    def test_blood_type_validation_lowercase_normalization(self):
        """Test blood type normalizes lowercase to uppercase"""
        data = {
            "name": "Test Patient",
            "blood_type": "a+"
        }
        patient = PatientV2Base(**data)
        assert patient.blood_type == "A+"

    def test_blood_type_validation_invalid_type(self):
        """Test blood type rejects invalid patterns"""
        invalid_types = ["C+", "X-", "AA+", "123", "A++"]

        for blood_type in invalid_types:
            with pytest.raises(ValidationError) as exc_info:
                PatientV2Base(name="Test Patient", blood_type=blood_type)
            assert "blood_type" in str(exc_info.value)

    def test_patient_v2_create_with_clinical_fields(self):
        """Test PatientV2Create includes clinical fields"""
        data = {
            "name": "João Silva",
            "phone": "+5511987654321",
            "doctor_id": uuid4(),
            "email": "joao@example.com",
            "allergies": "Penicilina",
            "medications": "Levotiroxina 100mcg",
            "blood_type": "O+",
            "emergency_contact": "Maria Silva - (11) 99999-9999",
            "patient_data": {"insurance": "Unimed"}
        }

        patient = PatientV2Create(**data)
        assert patient.allergies == "Penicilina"
        assert patient.medications == "Levotiroxina 100mcg"
        assert patient.blood_type == "O+"
        assert patient.emergency_contact == "Maria Silva - (11) 99999-9999"
        assert patient.patient_data == {"insurance": "Unimed"}

    def test_patient_v2_update_with_clinical_fields(self):
        """Test PatientV2Update can update clinical fields"""
        data = {
            "allergies": "Penicilina, Dipirona",
            "medications": "Levotiroxina 125mcg",
            "blood_type": "AB+",
            "emergency_contact": "Pedro Silva - (11) 88888-8888",
            "patient_data": {"insurance": "Bradesco", "preferred_contact": "phone"}
        }

        patient_update = PatientV2Update(**data)
        assert patient_update.allergies == "Penicilina, Dipirona"
        assert patient_update.medications == "Levotiroxina 125mcg"
        assert patient_update.blood_type == "AB+"
        assert patient_update.emergency_contact == "Pedro Silva - (11) 88888-8888"
        assert patient_update.patient_data == {"insurance": "Bradesco", "preferred_contact": "phone"}

    def test_clinical_fields_optional(self):
        """Test all clinical fields are optional"""
        # Minimal valid data
        data = {
            "name": "Test Patient",
            "phone": "+5511987654321",
            "doctor_id": uuid4()
        }

        patient = PatientV2Create(**data)
        assert patient.allergies is None
        assert patient.medications is None
        assert patient.blood_type is None
        assert patient.emergency_contact is None
        assert patient.patient_data is None

    def test_empty_string_allergies(self):
        """Test empty string allergies is accepted"""
        data = {
            "name": "Test Patient",
            "allergies": ""
        }
        patient = PatientV2Base(**data)
        assert patient.allergies == ""

    def test_patient_data_jsonb_accepts_complex_structure(self):
        """Test patient_data accepts complex nested JSON structures"""
        data = {
            "name": "Test Patient",
            "patient_data": {
                "insurance": "Unimed",
                "preferences": {
                    "language": "pt-BR",
                    "notifications": {
                        "email": True,
                        "sms": False,
                        "whatsapp": True
                    }
                },
                "medical_history": [
                    {"condition": "diabetes", "year": 2010},
                    {"condition": "hypertension", "year": 2015}
                ]
            }
        }

        patient = PatientV2Base(**data)
        assert patient.patient_data["insurance"] == "Unimed"
        assert patient.patient_data["preferences"]["language"] == "pt-BR"
        assert patient.patient_data["preferences"]["notifications"]["whatsapp"] is True
        assert len(patient.patient_data["medical_history"]) == 2

    def test_emergency_contact_max_length(self):
        """Test emergency_contact respects max_length of 200"""
        data = {
            "name": "Test Patient",
            "emergency_contact": "A" * 201  # Exceeds limit
        }

        with pytest.raises(ValidationError) as exc_info:
            PatientV2Base(**data)
        assert "emergency_contact" in str(exc_info.value)

    def test_patient_v2_response_includes_clinical_fields(self):
        """Test PatientV2Response schema includes all clinical fields"""
        # This test verifies the schema structure
        from app.models.patient import FlowState

        data = {
            "id": uuid4(),
            "doctor_id": uuid4(),
            "created_at": "2025-01-01T10:00:00Z",
            "updated_at": "2025-01-15T14:30:00Z",
            "current_day": 12,
            "flow_state": FlowState.ACTIVE,
            "name": "João Silva",
            "email": "joao@example.com",
            "phone": "+5511987654321",
            "allergies": "Penicilina",
            "medications": "Levotiroxina 100mcg",
            "blood_type": "A+",
            "emergency_contact": "Maria Silva - (11) 99999-9999",
            "patient_data": {"insurance": "Unimed"}
        }

        # Should not raise validation error
        patient = PatientV2Response(**data)
        assert patient.allergies == "Penicilina"
        assert patient.medications == "Levotiroxina 100mcg"
        assert patient.blood_type == "A+"
        assert patient.emergency_contact == "Maria Silva - (11) 99999-9999"
        assert patient.patient_data == {"insurance": "Unimed"}
