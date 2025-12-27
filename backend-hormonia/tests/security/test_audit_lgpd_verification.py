import pytest
from sqlalchemy.orm import Session
from fastapi import Request
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

    def test_lgpd_middleware_logging(self, db_session: Session):
        """
        Verify that LGPDMiddleware logs patient data access with correct user_id.
        """
        from fastapi.testclient import TestClient
        from app.main import app
        from unittest.mock import patch, MagicMock
        
        client = TestClient(app)
        
        with patch("app.middleware.lgpd_middleware.logger") as mock_logger:
            # Use a mock token that will be accepted or mock the dependency
            from app.dependencies.auth_dependencies import get_current_user_from_session
            
            async def mock_get_user(request: Request):
                print(f"DEBUG: mock_get_user called for {request.url.path}")
                request.state.user_id = "test-user-id"
                request.state.user_role = "admin"
                return {"id": "test-user-id", "role": "admin"}
            
            print(f"DEBUG: Setting override for {get_current_user_from_session}")
            app.dependency_overrides[get_current_user_from_session] = mock_get_user
            
            response = client.get("/api/v2/patients/")
            print(f"DEBUG: Response status: {response.status_code}")
            
            # Clean up overrides
            app.dependency_overrides = {}
            
            # Check response to ensure it didn't fail with 401/403
            assert response.status_code != 401, "Auth failed"
            assert response.status_code != 403, "Permission denied"
            
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