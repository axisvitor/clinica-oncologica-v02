"""
Test remaining role enum fixes for business dependencies and quiz alerts.
"""
import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from fastapi import HTTPException

from app.models.user import User, UserRole
from app.models.patient import Patient
from app.dependencies.business_dependencies import validate_patient_access, verify_patient_access


class TestBusinessDependenciesRoleFixes:
    """Test that business dependencies use correct UserRole enum values."""
    
    def test_validate_patient_access_admin_role(self):
        """Test that admin users can access patients without SUPER_ADMIN."""
        # Setup
        admin_user = Mock(spec=User)
        admin_user.role = UserRole.ADMIN
        admin_user.id = uuid4()
        
        patient = Mock(spec=Patient)
        patient.id = uuid4()
        patient.doctor_id = uuid4()
        
        patient_service = Mock()
        patient_service.get_patient.return_value = patient
        
        # Test - should not raise exception for ADMIN role
        result = validate_patient_access(patient.id, admin_user, patient_service)
        assert result == patient
    
    def test_validate_patient_access_doctor_role(self):
        """Test that doctors can access their assigned patients."""
        # Setup
        doctor_user = Mock(spec=User)
        doctor_user.role = UserRole.DOCTOR
        doctor_user.id = uuid4()
        
        patient = Mock(spec=Patient)
        patient.id = uuid4()
        patient.doctor_id = doctor_user.id  # Assigned to this doctor
        
        patient_service = Mock()
        patient_service.get_patient.return_value = patient
        
        # Test - should not raise exception for assigned patient
        result = validate_patient_access(patient.id, doctor_user, patient_service)
        assert result == patient
    
    def test_validate_patient_access_doctor_wrong_patient(self):
        """Test that doctors cannot access unassigned patients."""
        # Setup
        doctor_user = Mock(spec=User)
        doctor_user.role = UserRole.DOCTOR
        doctor_user.id = uuid4()
        
        patient = Mock(spec=Patient)
        patient.id = uuid4()
        patient.doctor_id = uuid4()  # Different doctor
        
        patient_service = Mock()
        patient_service.get_patient.return_value = patient
        
        # Test - should raise 403 for unassigned patient
        with pytest.raises(HTTPException) as exc_info:
            validate_patient_access(patient.id, doctor_user, patient_service)
        
        assert exc_info.value.status_code == 403
        assert "not assigned to current doctor" in exc_info.value.detail
    
    def test_verify_patient_access_admin_role(self):
        """Test that verify_patient_access works with ADMIN role only."""
        # Setup
        admin_user = Mock(spec=User)
        admin_user.role = UserRole.ADMIN
        admin_user.id = uuid4()
        
        patient = Mock(spec=Patient)
        patient.id = uuid4()
        
        patient_repo = Mock()
        patient_repo.get.return_value = patient
        
        # Test - should return patient for admin
        result = verify_patient_access(patient.id, admin_user, patient_repo)
        assert result == patient


class TestQuizAlertsRoleFixes:
    """Test that quiz alerts endpoints use UserRole enum instead of strings."""
    
    def test_role_enum_import(self):
        """Test that UserRole is properly imported in quiz_alerts module."""
        from app.api.v1.quiz_alerts import UserRole
        assert UserRole.ADMIN == "admin"
        assert UserRole.DOCTOR == "doctor"
    
    @patch('app.api.v1.quiz_alerts.get_current_user')
    @patch('app.api.v1.quiz_alerts.get_db')
    def test_authorization_uses_role_enum(self, mock_get_db, mock_get_current_user):
        """Test that authorization checks use UserRole enum, not string comparison."""
        from app.api.v1.quiz_alerts import get_patient_quiz_alerts
        
        # Setup admin user with proper enum role
        admin_user = Mock(spec=User)
        admin_user.role = UserRole.ADMIN
        
        mock_get_current_user.return_value = admin_user
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        # This should not raise an exception since we're using enum comparison
        # The function should proceed past authorization check
        patient_id = uuid4()
        
        # Mock the AlertRepository to avoid database calls
        with patch('app.api.v1.quiz_alerts.AlertRepository') as mock_alert_repo:
            mock_repo_instance = Mock()
            mock_alert_repo.return_value = mock_repo_instance
            mock_repo_instance.get_by_patient.return_value = []
            
            # This call should succeed with proper enum role checking
            try:
                result = get_patient_quiz_alerts(
                    patient_id=patient_id,
                    current_user=admin_user,
                    db=mock_db
                )
                # If we get here, authorization passed correctly
                assert result is not None
            except HTTPException as e:
                # Should not get 403 for valid admin role
                assert e.status_code != 403, f"Got 403 error: {e.detail}"


if __name__ == "__main__":
    pytest.main([__file__])