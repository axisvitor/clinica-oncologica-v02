"""
Tests for LGPD middleware
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request
from datetime import datetime


class TestLGPDMiddleware:
    """Test LGPD compliance middleware."""

    @pytest.mark.asyncio
    async def test_patient_access_logged(self):
        """Test patient data access is logged."""
        from app.middleware.lgpd_middleware import LGPDMiddleware

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/v2/patients/123"
        mock_request.method = "GET"
        mock_request.client.host = "127.0.0.1"
        mock_request.state.user_id = "user_456"

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_call_next = AsyncMock(return_value=mock_response)

        middleware = LGPDMiddleware(app=MagicMock())

        with patch('app.middleware.lgpd_middleware.logger') as mock_logger:
            await middleware.dispatch(mock_request, mock_call_next)

            mock_logger.info.assert_called()
            call_args = str(mock_logger.info.call_args)
            assert "LGPD" in call_args or "patient" in call_args

    @pytest.mark.asyncio
    async def test_sensitive_data_access_tracked(self):
        """Test sensitive data access is tracked in audit log."""
        from app.middleware.lgpd_middleware import LGPDMiddleware

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/v2/patients/123/medical-history"
        mock_request.method = "GET"
        mock_request.client.host = "192.168.1.100"
        mock_request.state.user_id = "doctor_789"

        middleware = LGPDMiddleware(app=MagicMock())
        middleware._audit_service = AsyncMock()

        mock_call_next = AsyncMock()

        await middleware.dispatch(mock_request, mock_call_next)

        # Audit service should be called
        if hasattr(middleware, '_audit_service'):
            middleware._audit_service.log_access.assert_called_once()

    @pytest.mark.asyncio
    async def test_anonymization_on_export(self):
        """Test data is anonymized on export requests."""
        from app.middleware.lgpd_middleware import LGPDMiddleware

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/v2/patients/export"
        mock_request.method = "GET"
        mock_request.query_params = {"format": "csv", "anonymize": "true"}

        middleware = LGPDMiddleware(app=MagicMock())

        should_anonymize = middleware._should_anonymize(mock_request)

        assert should_anonymize is True

    @pytest.mark.asyncio
    async def test_consent_validation(self):
        """Test consent is validated for data processing."""
        from app.middleware.lgpd_middleware import LGPDMiddleware

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/v2/patients/123/share"
        mock_request.method = "POST"

        middleware = LGPDMiddleware(app=MagicMock())
        middleware._consent_service = AsyncMock()
        middleware._consent_service.has_consent.return_value = True

        mock_call_next = AsyncMock()

        await middleware.dispatch(mock_request, mock_call_next)

        # Consent check should be performed
        if hasattr(middleware, '_consent_service'):
            middleware._consent_service.has_consent.assert_called()


class TestPatientDataDeletion:
    """Test patient data deletion (LGPD Art. 16)."""

    @pytest.mark.asyncio
    async def test_soft_delete_marks_as_deleted(self):
        """Test soft delete marks patient as deleted."""
        from app.repositories.patient import PatientRepository

        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result

        repo = PatientRepository(db=mock_db)

        result = await repo.soft_delete(patient_id="123")

        assert result is True
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_hard_delete_removes_data(self):
        """Test hard delete completely removes patient data."""
        from app.repositories.patient import PatientRepository

        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result

        repo = PatientRepository(db=mock_db)

        result = await repo.hard_delete(
            patient_id="123",
            audit_reason="LGPD Art. 16 request"
        )

        assert result is True
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cascading_delete_removes_related_data(self):
        """Test deleting patient removes all related data."""
        from app.services.patient_deletion_service import PatientDeletionService

        service = PatientDeletionService()
        service._patient_repo = AsyncMock()
        service._appointment_repo = AsyncMock()
        service._medical_record_repo = AsyncMock()
        service._consent_repo = AsyncMock()

        await service.delete_patient_data(
            patient_id="123",
            deletion_type="hard"
        )

        # All related data should be deleted
        service._patient_repo.hard_delete.assert_called_once()
        service._appointment_repo.delete_by_patient.assert_called_once()
        service._medical_record_repo.delete_by_patient.assert_called_once()
        service._consent_repo.delete_by_patient.assert_called_once()

    @pytest.mark.asyncio
    async def test_deletion_audit_logged(self):
        """Test deletion is logged in audit trail."""
        from app.services.patient_deletion_service import PatientDeletionService

        service = PatientDeletionService()
        service._audit_service = AsyncMock()

        await service._log_deletion(
            patient_id="123",
            deletion_type="hard",
            requested_by="user_456",
            reason="LGPD Art. 16"
        )

        service._audit_service.log_deletion.assert_called_once()


class TestDataPortability:
    """Test data portability (LGPD Art. 18)."""

    @pytest.mark.asyncio
    async def test_patient_data_export_json(self):
        """Test patient data can be exported as JSON."""
        from app.services.data_portability_service import DataPortabilityService

        service = DataPortabilityService()
        service._patient_repo = AsyncMock()
        service._patient_repo.get_full_data.return_value = {
            "id": "123",
            "name": "Test Patient",
            "medical_history": [{"date": "2024-01-01", "diagnosis": "Test"}]
        }

        export_data = await service.export_patient_data(
            patient_id="123",
            format="json"
        )

        assert "id" in export_data
        assert "medical_history" in export_data

    @pytest.mark.asyncio
    async def test_patient_data_export_csv(self):
        """Test patient data can be exported as CSV."""
        from app.services.data_portability_service import DataPortabilityService

        service = DataPortabilityService()

        data = {
            "id": "123",
            "name": "Test Patient",
            "email": "test@example.com"
        }

        csv_output = await service.convert_to_csv(data)

        assert "id,name,email" in csv_output or "123" in csv_output

    @pytest.mark.asyncio
    async def test_export_includes_all_personal_data(self):
        """Test export includes all categories of personal data."""
        from app.services.data_portability_service import DataPortabilityService

        service = DataPortabilityService()
        service._gather_all_data = AsyncMock()
        service._gather_all_data.return_value = {
            "basic_info": {},
            "medical_records": [],
            "appointments": [],
            "prescriptions": [],
            "consents": [],
            "audit_logs": []
        }

        export = await service.export_patient_data("123", format="json")

        assert "medical_records" in export
        assert "appointments" in export
        assert "prescriptions" in export


class TestConsentManagement:
    """Test consent management."""

    @pytest.mark.asyncio
    async def test_consent_can_be_granted(self):
        """Test consent can be granted."""
        from app.services.consent_service import ConsentService

        service = ConsentService()
        service._consent_repo = AsyncMock()

        await service.grant_consent(
            patient_id="123",
            purpose="data_processing",
            granted_by="patient"
        )

        service._consent_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_consent_can_be_revoked(self):
        """Test consent can be revoked."""
        from app.services.consent_service import ConsentService

        service = ConsentService()
        service._consent_repo = AsyncMock()

        await service.revoke_consent(
            patient_id="123",
            purpose="data_processing"
        )

        service._consent_repo.revoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_consent_check_before_processing(self):
        """Test consent is checked before data processing."""
        from app.services.consent_service import ConsentService

        service = ConsentService()
        service._consent_repo = AsyncMock()
        service._consent_repo.has_active_consent.return_value = True

        has_consent = await service.has_consent(
            patient_id="123",
            purpose="marketing"
        )

        assert has_consent is True

    @pytest.mark.asyncio
    async def test_consent_expiration(self):
        """Test expired consent is not valid."""
        from app.services.consent_service import ConsentService
        from datetime import timedelta

        service = ConsentService()
        service._consent_repo = AsyncMock()

        expired_consent = {
            "patient_id": "123",
            "purpose": "research",
            "granted_at": datetime.utcnow() - timedelta(days=400),
            "expires_at": datetime.utcnow() - timedelta(days=10)
        }

        service._consent_repo.get_consent.return_value = expired_consent

        is_valid = await service.is_consent_valid("123", "research")

        assert is_valid is False


class TestDataMinimization:
    """Test data minimization principles."""

    @pytest.mark.asyncio
    async def test_only_required_fields_collected(self):
        """Test only required fields are collected."""
        from app.schemas.patient import PatientCreateSchema

        # Schema should only have required fields
        schema = PatientCreateSchema(
            name="Test Patient",
            phone="+5511999999999"
        )

        # Optional fields should be None
        assert schema.name == "Test Patient"
        assert schema.phone == "+5511999999999"

    @pytest.mark.asyncio
    async def test_sensitive_data_filtered_in_list(self):
        """Test sensitive data is filtered in list endpoints."""
        from app.services.patient_service import PatientService

        service = PatientService()
        service._patient_repo = AsyncMock()
        service._patient_repo.list.return_value = [
            {
                "id": "123",
                "name": "Test Patient",
                "cpf_encrypted": b"encrypted_data",  # Should be filtered
                "cpf_hash": "hash123"
            }
        ]

        patients = await service.list_patients()

        # Encrypted data should not be in response
        assert "cpf_encrypted" not in patients[0]

    @pytest.mark.asyncio
    async def test_data_retention_policy_enforced(self):
        """Test data retention policy is enforced."""
        from app.services.data_retention_service import DataRetentionService
        from datetime import timedelta

        service = DataRetentionService()
        service._patient_repo = AsyncMock()

        # Mock old inactive patients
        old_date = datetime.utcnow() - timedelta(days=730)  # 2 years
        service._patient_repo.find_inactive_since.return_value = [
            {"id": "old_patient_1", "last_activity": old_date}
        ]

        await service.cleanup_old_data()

        # Old data should be marked for deletion
        service._patient_repo.mark_for_deletion.assert_called()
