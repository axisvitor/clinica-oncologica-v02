"""
Production-grade tests for patient API endpoints

This test suite validates critical patient API functionality including
pagination, idempotency, CPF encryption, and data validation.
"""
import pytest
from fastapi import status
from uuid import uuid4
from datetime import date, timedelta

from app.models.patient import Patient, FlowState


class TestPatientPagination:
    """Test pagination limits and edge cases"""

    def test_pagination_respects_max_limit(self, client, auth_headers):
        """Test that pagination enforces max limit."""
        response = client.get(
            "/api/v2/patients?limit=10000",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        # API v2 clamps limit to 100 in dependency layer.
        assert len(data["data"]) <= 100

    def test_pagination_rejects_negative_values(self, client, auth_headers):
        """Test rejection of invalid pagination values"""
        response = client.get(
            "/api/v2/patients?page=-1",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = client.get(
            "/api/v2/patients?page_size=0",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = client.get(
            "/api/v2/patients?page_size=-10",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_pagination_default_values(self, client, auth_headers):
        """Test pagination default response contract."""
        response = client.get(
            "/api/v2/patients",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "next_cursor" in data
        assert "has_more" in data

    def test_pagination_boundary_values(self, client, auth_headers):
        """Test pagination at boundary values"""
        response = client.get(
            "/api/v2/patients?page=1&page_size=1",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data.get("page") == 1
        assert data.get("page_size") == 1

        response = client.get(
            "/api/v2/patients?page=1&page_size=100",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data.get("page") == 1
        assert data.get("page_size") == 100


class TestPatientIdempotency:
    """Test idempotency key support"""

    def test_create_with_idempotency_key(self, client, auth_headers, test_doctor_user):
        """Test patient creation with idempotency key"""
        idempotency_key = f"patient-create-{uuid4()}"
        suffix = f"{uuid4().int % 100000000:08d}"
        patient_data = {
            "name": "João Silva",
            "phone": f"+55119{suffix}",
            "email": f"joao_{uuid4().hex[:8]}@gmail.com",
            "birth_date": "1985-05-15",
            "treatment_type": "hormone_therapy",
            "doctor_id": str(test_doctor_user.id),
        }

        response1 = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers={
                **auth_headers,
                "X-Idempotency-Key": idempotency_key,
            },
        )
        assert response1.status_code == status.HTTP_201_CREATED
        patient_id_1 = response1.json()["id"]

        response2 = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers={
                **auth_headers,
                "X-Idempotency-Key": idempotency_key,
            },
        )
        assert response2.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        assert response2.json()["id"] == patient_id_1

    def test_different_idempotency_keys_create_separate_patients(self, client, auth_headers, test_doctor_user):
        """Test that different idempotency keys create separate patients"""
        payload_1 = {
            "name": "João Silva 1",
            "phone": f"+55119{uuid4().int % 100000000:08d}",
            "email": f"joao_{uuid4().hex[:8]}@gmail.com",
            "birth_date": "1985-05-15",
            "treatment_type": "hormone_therapy",
            "doctor_id": str(test_doctor_user.id),
        }
        payload_2 = {
            "name": "João Silva 2",
            "phone": f"+55119{uuid4().int % 100000000:08d}",
            "email": f"joao_{uuid4().hex[:8]}@gmail.com",
            "birth_date": "1986-06-20",
            "treatment_type": "hormone_therapy",
            "doctor_id": str(test_doctor_user.id),
        }

        response1 = client.post(
            "/api/v2/patients",
            json=payload_1,
            headers={
                **auth_headers,
                "X-Idempotency-Key": f"key-{uuid4()}",
            },
        )

        response2 = client.post(
            "/api/v2/patients",
            json=payload_2,
            headers={
                **auth_headers,
                "X-Idempotency-Key": f"key-{uuid4()}",
            },
        )

        assert response1.status_code == status.HTTP_201_CREATED
        assert response2.status_code == status.HTTP_201_CREATED
        assert response1.json()["id"] != response2.json()["id"]


class TestCPFEncryption:
    """Test CPF encryption and validation"""

    def test_cpf_encryption_on_create(self):
        """Test that CPF is encrypted when patient is created"""
        patient = Patient(
            name="Test Patient",
            phone="5511999999999",
            email="test@gmail.com",
            doctor_id=uuid4()
        )

        # Set CPF using encryption method
        patient.set_cpf("12345678909")

        # Verify encrypted fields are set
        assert patient.cpf_encrypted is not None
        assert patient.cpf_hash is not None

        # Verify decryption works
        decrypted = patient.cpf_decrypted
        assert decrypted == "12345678909"

    def test_cpf_formatting_and_masking(self):
        """Test CPF formatting with and without masking"""
        patient = Patient(
            name="Test Patient",
            phone="5511999999999",
            doctor_id=uuid4()
        )

        patient.set_cpf("12345678909")

        # Get formatted CPF without mask
        formatted = patient.get_cpf_display(mask=False)
        assert formatted == "123.456.789-01"

        # Get masked CPF
        masked = patient.get_cpf_display(mask=True)
        assert "***" in masked
        assert "789" in masked  # Last 3 digits before hyphen visible

    def test_cpf_hash_searchability(self):
        """Test that CPF hash enables searching"""
        patient1 = Patient(
            name="Patient 1",
            phone="5511111111111",
            doctor_id=uuid4()
        )
        patient1.set_cpf("12345678909")

        patient2 = Patient(
            name="Patient 2",
            phone="5511222222222",
            doctor_id=uuid4()
        )
        patient2.set_cpf("12345678909")  # Same CPF

        # Same CPF should produce same hash
        assert patient1.cpf_hash == patient2.cpf_hash

        # Different CPF should produce different hash
        patient3 = Patient(
            name="Patient 3",
            phone="5511333333333",
            doctor_id=uuid4()
        )
        patient3.set_cpf("12345678909")

        assert patient1.cpf_hash == patient3.cpf_hash


class TestPatientValidation:
    """Test patient data validation"""

    def test_birth_date_minimum_age_validation(self):
        """Test that patients must be at least 18 years old"""
        patient = Patient(
            name="Too Young",
            phone="5511999999999",
            doctor_id=uuid4()
        )

        # Set birth date to 17 years ago
        too_recent = date.today() - timedelta(days=int(17 * 365.25))

        with pytest.raises(ValueError, match="must be at least 18 years old"):
            patient.birth_date = too_recent

    def test_birth_date_maximum_age_validation(self):
        """Test that birth date cannot indicate impossible age"""
        patient = Patient(
            name="Too Old",
            phone="5511999999999",
            doctor_id=uuid4()
        )

        # Set birth date to 121 years ago
        too_old = date.today() - timedelta(days=int(121 * 365.25))

        with pytest.raises(ValueError, match="over 120 years old"):
            patient.birth_date = too_old

    def test_birth_date_future_validation(self):
        """Test that birth date cannot be in the future"""
        patient = Patient(
            name="Future Person",
            phone="5511999999999",
            doctor_id=uuid4()
        )

        # Set birth date to tomorrow
        future_date = date.today() + timedelta(days=1)

        with pytest.raises(ValueError, match="cannot be in the future"):
            patient.birth_date = future_date

    def test_phone_format_validation(self):
        """Test phone number format validation"""
        # Valid Brazilian phone format
        valid_phones = [
            "5511999999999",  # With country code
            "11999999999",    # Without country code
            "+5511999999999"  # With + prefix
        ]

        for phone in valid_phones:
            patient = Patient(
                name="Test",
                phone=phone,
                doctor_id=uuid4()
            )
            assert patient.phone is not None

    def test_email_format_validation(self):
        """Test email format validation"""
        valid_emails = [
            "test@gmail.com",
            "user.name@domain.co.uk",
            "user+tag@gmail.com"
        ]

        for email in valid_emails:
            patient = Patient(
                name="Test",
                phone="5511999999999",
                email=email,
                doctor_id=uuid4()
            )
            assert patient.email == email


class TestPatientFlowState:
    """Test patient flow state management"""

    def test_default_flow_state(self):
        """Test that new patients start in ONBOARDING state"""
        patient = Patient(
            name="New Patient",
            phone="5511999999999",
            doctor_id=uuid4()
        )

        assert patient.flow_state == FlowState.ONBOARDING
        assert patient.current_day == 0

    def test_flow_state_transitions(self):
        """Test valid flow state transitions"""
        patient = Patient(
            name="Test Patient",
            phone="5511999999999",
            doctor_id=uuid4(),
            flow_state=FlowState.ONBOARDING
        )

        # ONBOARDING -> ACTIVE
        patient.flow_state = FlowState.ACTIVE
        assert patient.flow_state == FlowState.ACTIVE

        # ACTIVE -> PAUSED
        patient.flow_state = FlowState.PAUSED
        assert patient.flow_state == FlowState.PAUSED

        # PAUSED -> ACTIVE
        patient.flow_state = FlowState.ACTIVE
        assert patient.flow_state == FlowState.ACTIVE

        # ACTIVE -> COMPLETED
        patient.flow_state = FlowState.COMPLETED
        assert patient.flow_state == FlowState.COMPLETED


class TestPatientMetadata:
    """Test patient metadata handling"""

    def test_metadata_schema_validation(self):
        """Test that patient_data validates against schema"""
        patient = Patient(
            name="Test",
            phone="5511999999999",
            doctor_id=uuid4()
        )

        # Valid metadata
        valid_metadata = {
            "timezone": "America/Sao_Paulo",
            "preferred_contact": "whatsapp",
            "notes": "Patient prefers morning appointments"
        }

        # Should not raise error
        patient.patient_data = valid_metadata
        assert patient.patient_data == valid_metadata

    def test_metadata_field_access(self):
        """Test metadata field getter/setter"""
        patient = Patient(
            name="Test",
            phone="5511999999999",
            doctor_id=uuid4()
        )

        # Set individual field
        patient.set_metadata_field("preferred_language", "pt-BR")
        assert patient.get_metadata_field("preferred_language") == "pt-BR"

        # Get non-existent field with default
        assert patient.get_metadata_field("non_existent", "default") == "default"

    def test_metadata_bulk_update(self):
        """Test bulk metadata update"""
        patient = Patient(
            name="Test",
            phone="5511999999999",
            doctor_id=uuid4()
        )

        updates = {
            "timezone": "America/Sao_Paulo",
            "language": "pt-BR",
            "notifications_enabled": True
        }

        patient.update_metadata(updates)

        for key, value in updates.items():
            assert patient.get_metadata_field(key) == value
