import os
import pytest
from sqlalchemy.orm import Session
from app.models.patient import Patient
from app.models.user import User
import uuid

os.environ.setdefault(
    "HASH_SALT", "test-hash-salt-1234567890abcdef1234567890abcdef"
)

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

    def test_patient_encryption_on_create(self, db_session: Session):
        """Verify encryption fields are set when creating a patient with plaintext."""
        doctor = User(
            id=uuid.uuid4(),
            email=f"doctor_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Test Doctor",
            is_active=True,
        )
        db_session.add(doctor)
        db_session.commit()

        patient = Patient(
            name="Test Patient",
            doctor_id=doctor.id,
        )
        patient.email = "patient@example.com"
        patient.phone = "+5511999999999"
        patient.cpf = "11144477735"

        db_session.add(patient)
        db_session.commit()

        assert patient.email_encrypted is not None
        assert patient.email_hash is not None
        assert patient.phone_encrypted is not None
        assert patient.phone_hash is not None
        assert patient.cpf_encrypted is not None
        assert patient.cpf_hash is not None
        assert patient.email_decrypted == "patient@example.com"
        assert patient.phone_decrypted == "+5511999999999"
        assert patient.cpf_decrypted == "11144477735"

    def test_patient_encryption_on_update(self, db_session: Session):
        """Verify encryption fields update when PII is changed."""
        doctor = User(
            id=uuid.uuid4(),
            email=f"doctor_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Test Doctor",
            is_active=True,
        )
        db_session.add(doctor)
        db_session.commit()

        patient = Patient(
            name="Test Patient",
            doctor_id=doctor.id,
        )
        patient.email = "patient@example.com"
        patient.phone = "+5511999999999"
        patient.cpf = "11144477735"

        db_session.add(patient)
        db_session.commit()

        old_email_hash = patient.email_hash
        old_phone_hash = patient.phone_hash
        old_cpf_hash = patient.cpf_hash

        patient.email = "updated@example.com"
        patient.phone = "+5511888888888"
        patient.cpf = "52998224725"

        db_session.add(patient)
        db_session.commit()

        assert patient.email_hash != old_email_hash
        assert patient.phone_hash != old_phone_hash
        assert patient.cpf_hash != old_cpf_hash
        assert patient.email_decrypted == "updated@example.com"
        assert patient.phone_decrypted == "+5511888888888"
        assert patient.cpf_decrypted == "52998224725"

    def test_pii_masking_utility(self):
        """
        Verify that PII masking utility works correctly for all fields.
        """
        from app.utils.pii_redaction import mask_cpf, mask_phone, mask_email
        
        # Test CPF masking
        assert mask_cpf("12345678901") == "123.***.***-01"
        
        # Test Phone masking
        assert mask_phone("5511999998888") == "+55***8888"
        
        # Test Email masking
        assert mask_email("patient@example.com") == "pa***@example.com"

    @pytest.mark.asyncio
    async def test_lgpd_middleware_logging(self):
        """
        Verify that LGPDMiddleware logs patient data access with correct user_id.
        """
        from unittest.mock import patch
        from app.middleware.lgpd_middleware import LGPDMiddleware
        
        with patch("app.middleware.lgpd_middleware.logger") as mock_logger:
            async def app_stub(scope, receive, send):
                scope.setdefault("state", {})
                scope["state"]["user_id"] = "test-user-id"
                scope["state"]["user_role"] = "admin"
                await send(
                    {"type": "http.response.start", "status": 200, "headers": []}
                )
                await send({"type": "http.response.body", "body": b"OK"})

            middleware = LGPDMiddleware(app_stub)
            scope = {
                "type": "http",
                "method": "GET",
                "path": "/api/v2/patients/",
                "headers": [],
                "client": ("127.0.0.1", 1234),
                "state": {},
            }

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message):
                return None

            await middleware(scope, receive, send)
            
            # Check if logger was called with LGPD info
            found_log = False
            for call in mock_logger.info.call_args_list:
                args, kwargs = call
                if "LGPD: Patient data access" in args[0]:
                    found_log = True
                    extra = kwargs.get("extra", {})
                    # If this fails, it means request.state was not accessible after call_next
                    assert extra.get("user_id") == "test-user-id", f"user_id was {extra.get('user_id')}"
                    assert extra.get("path") == "/api/v2/patients/"
                    assert "status_code" in extra
            
            assert found_log, "LGPD access log not found"
