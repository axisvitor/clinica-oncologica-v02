import pytest
from sqlalchemy.orm import Session
from app.models.patient import Patient
from app.models.user import User
import uuid

@pytest.mark.security
@pytest.mark.lgpd
class TestLGPDAuditVerification:
    """
    Audit verification tests for LGPD compliance.
    These tests verify that all PII fields have proper encryption and validation hooks.
    """

    def test_email_encryption_validation_hook(self, db_session: Session):
        """
        Verify that email encryption is validated before save.
        Should fail if email_encrypted is set without email_hash.
        """
        # Create a test doctor
        doctor = User(
            id=uuid.uuid4(),
            email=f"doctor_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Test Doctor",
            is_active=True
        )
        db_session.add(doctor)
        db_session.commit()

        # Attempt to create patient with incomplete email encryption
        # This SHOULD trigger a ValueError if the hook is implemented
        patient = Patient(
            name="Test Patient",
            doctor_id=doctor.id,
            email_encrypted=b"some-encrypted-data",
            # email_hash=None  # Intentionally missing
        )
        
        db_session.add(patient)
        
        with pytest.raises(ValueError, match="email encryption incomplete"):
            db_session.commit()

    def test_phone_encryption_validation_hook(self, db_session: Session):
        """
        Verify that phone encryption is validated before save.
        Should fail if phone_encrypted is set without phone_hash.
        """
        # Create a test doctor
        doctor = User(
            id=uuid.uuid4(),
            email=f"doctor_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Test Doctor",
            is_active=True
        )
        db_session.add(doctor)
        db_session.commit()

        # Attempt to create patient with incomplete phone encryption
        patient = Patient(
            name="Test Patient",
            doctor_id=doctor.id,
            phone_encrypted=b"some-encrypted-data",
            # phone_hash=None  # Intentionally missing
        )
        
        db_session.add(patient)
        
        with pytest.raises(ValueError, match="phone encryption incomplete"):
            db_session.commit()

    def test_pii_masking_utility(self):
        """
        Verify that PII masking utility works correctly for all fields.
        """
        from app.utils.pii_masking import mask_cpf, mask_phone, mask_email
        
        # Test CPF masking
        assert mask_cpf("12345678901") == "123.***.***-01"
        
        # Test Phone masking
        assert mask_phone("5511999998888") == "+55***8888"
        
        # Test Email masking
        assert mask_email("patient@example.com") == "pa***@example.com"
