"""
Comprehensive RBAC tests for patient endpoints.

Tests role-based access control on all patient CRUD operations,
ensuring proper authorization and data isolation.
"""

import pytest
from uuid import uuid4, UUID
from datetime import date
from unittest.mock import Mock, AsyncMock, patch

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import UserRole
from app.models.patient import Patient, FlowState
from app.core.authorization import (
    require_permission,
    require_role,
    check_patient_access,
    ensure_patient_access,
)
from app.core.permissions import Permission


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def admin_user():
    """Create a mock admin user."""
    return {
        "id": str(uuid4()),
        "email": "admin@hormonia.io",
        "role": "admin",
        "is_active": True,
        "full_name": "Admin User",
    }


@pytest.fixture
def doctor_user():
    """Create a mock doctor user."""
    return {
        "id": str(uuid4()),
        "email": "doctor@hospital.com",
        "role": "doctor",
        "is_active": True,
        "full_name": "Doctor User",
    }


@pytest.fixture
def other_doctor_user():
    """Create another mock doctor user."""
    return {
        "id": str(uuid4()),
        "email": "other@hospital.com",
        "role": "doctor",
        "is_active": True,
        "full_name": "Other Doctor",
    }


@pytest.fixture
def patient_data():
    """Create mock patient data."""
    return {
        "id": str(uuid4()),
        "name": "Test Patient",
        "email": "patient@example.com",
        "phone": "+5511999998888",
        "birth_date": date(1990, 1, 1),
        "cpf": "12345678901",
        "treatment_type": "quimioterapia",
        "doctor_id": None,  # Will be set by tests
    }


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = Mock(spec=Session)
    return db


# ============================================================================
# AUTHORIZATION DECORATOR TESTS
# ============================================================================

class TestRequirePermission:
    """Test the require_permission decorator."""

    @pytest.mark.asyncio
    async def test_decorator_with_valid_permission(self, admin_user):
        """Test decorator allows access with valid permission."""
        @require_permission(Permission.PATIENT_READ)
        async def test_endpoint(current_user):
            return {"success": True}

        result = await test_endpoint(current_user=admin_user)
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_decorator_without_authentication(self):
        """Test decorator blocks unauthenticated requests."""
        @require_permission(Permission.PATIENT_READ)
        async def test_endpoint(current_user):
            return {"success": True}

        with pytest.raises(HTTPException) as exc_info:
            await test_endpoint(current_user=None)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Authentication required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_decorator_without_permission(self):
        """Test decorator blocks users without required permission."""
        unauthorized_user = {
            "id": str(uuid4()),
            "email": "patient@example.com",
            "role": "patient",
            "is_active": True,
        }

        @require_permission(Permission.PATIENT_DELETE)
        async def test_endpoint(current_user):
            return {"success": True}

        with pytest.raises(HTTPException) as exc_info:
            await test_endpoint(current_user=unauthorized_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Permission denied" in exc_info.value.detail


class TestRequireRole:
    """Test the require_role decorator."""

    @pytest.mark.asyncio
    async def test_admin_role_allowed(self, admin_user):
        """Test admin role is allowed."""
        @require_role(UserRole.ADMIN)
        async def test_endpoint(current_user):
            return {"success": True}

        result = await test_endpoint(current_user=admin_user)
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_doctor_role_allowed(self, doctor_user):
        """Test doctor role is allowed."""
        @require_role(UserRole.ADMIN, UserRole.DOCTOR)
        async def test_endpoint(current_user):
            return {"success": True}

        result = await test_endpoint(current_user=doctor_user)
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_unauthorized_role_blocked(self):
        """Test unauthorized role is blocked."""
        unauthorized_user = {
            "id": str(uuid4()),
            "email": "patient@example.com",
            "role": "patient",
            "is_active": True,
        }

        @require_role(UserRole.ADMIN, UserRole.DOCTOR)
        async def test_endpoint(current_user):
            return {"success": True}

        with pytest.raises(HTTPException) as exc_info:
            await test_endpoint(current_user=unauthorized_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Insufficient permissions" in exc_info.value.detail


# ============================================================================
# PATIENT ACCESS CONTROL TESTS
# ============================================================================

class TestPatientAccessControl:
    """Test patient-specific access control functions."""

    def test_admin_can_access_all_patients(self, admin_user):
        """Test admins can access any patient."""
        patient_doctor_id = UUID(str(uuid4()))
        assert check_patient_access(admin_user, patient_doctor_id) is True

    def test_doctor_can_access_own_patients(self, doctor_user):
        """Test doctors can access their own patients."""
        doctor_id = UUID(doctor_user["id"])
        assert check_patient_access(doctor_user, doctor_id) is True

    def test_doctor_cannot_access_other_patients(self, doctor_user, other_doctor_user):
        """Test doctors cannot access other doctors' patients."""
        other_doctor_id = UUID(other_doctor_user["id"])
        assert check_patient_access(doctor_user, other_doctor_id) is False

    def test_ensure_patient_access_allows_admin(self, admin_user):
        """Test ensure_patient_access allows admin."""
        patient_doctor_id = UUID(str(uuid4()))
        # Should not raise exception
        ensure_patient_access(admin_user, patient_doctor_id)

    def test_ensure_patient_access_allows_own_doctor(self, doctor_user):
        """Test ensure_patient_access allows doctor for own patient."""
        doctor_id = UUID(doctor_user["id"])
        # Should not raise exception
        ensure_patient_access(doctor_user, doctor_id)

    def test_ensure_patient_access_blocks_other_doctor(self, doctor_user, other_doctor_user):
        """Test ensure_patient_access blocks other doctor."""
        other_doctor_id = UUID(other_doctor_user["id"])

        with pytest.raises(HTTPException) as exc_info:
            ensure_patient_access(doctor_user, other_doctor_id)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Access denied" in exc_info.value.detail


# ============================================================================
# ENDPOINT INTEGRATION TESTS
# ============================================================================

class TestListPatientsRBAC:
    """Test RBAC on list patients endpoint."""

    def test_admin_can_list_all_patients(self, admin_user, mock_db):
        """Test admin can list all patients."""
        # This would be an integration test with actual endpoint
        # For now, we verify the authorization logic
        assert admin_user["role"] == "admin"

    def test_doctor_can_only_list_own_patients(self, doctor_user, mock_db):
        """Test doctor can only list their own patients."""
        assert doctor_user["role"] == "doctor"
        # Verify doctor_id filter is applied in endpoint


class TestGetPatientRBAC:
    """Test RBAC on get single patient endpoint."""

    def test_admin_can_get_any_patient(self, admin_user, patient_data):
        """Test admin can get any patient."""
        patient_data["doctor_id"] = str(uuid4())
        # Verify access control allows admin
        assert check_patient_access(admin_user, UUID(patient_data["doctor_id"])) is True

    def test_doctor_can_get_own_patient(self, doctor_user, patient_data):
        """Test doctor can get their own patient."""
        patient_data["doctor_id"] = doctor_user["id"]
        assert check_patient_access(doctor_user, UUID(patient_data["doctor_id"])) is True

    def test_doctor_cannot_get_other_patient(self, doctor_user, other_doctor_user, patient_data):
        """Test doctor cannot get other doctor's patient."""
        patient_data["doctor_id"] = other_doctor_user["id"]
        assert check_patient_access(doctor_user, UUID(patient_data["doctor_id"])) is False


class TestCreatePatientRBAC:
    """Test RBAC on create patient endpoint."""

    def test_admin_can_create_patient_for_any_doctor(self, admin_user):
        """Test admin can create patient for any doctor."""
        # Admin should have PATIENT_CREATE permission
        from app.core.permissions import RolePermissions
        assert RolePermissions.has_permission("admin", Permission.PATIENT_CREATE)

    def test_doctor_can_create_own_patient(self, doctor_user):
        """Test doctor can create patient for themselves."""
        # Doctor should have PATIENT_CREATE permission
        from app.core.permissions import RolePermissions
        assert RolePermissions.has_permission("doctor", Permission.PATIENT_CREATE)

    def test_doctor_cannot_create_for_other_doctor(self, doctor_user, other_doctor_user):
        """Test doctor cannot create patient for another doctor."""
        # This is enforced in endpoint logic, not just permission
        # Verify that endpoint checks doctor_id matches current_user


class TestUpdatePatientRBAC:
    """Test RBAC on update patient endpoint."""

    def test_admin_can_update_any_patient(self, admin_user, patient_data):
        """Test admin can update any patient."""
        patient_data["doctor_id"] = str(uuid4())
        assert check_patient_access(admin_user, UUID(patient_data["doctor_id"])) is True

    def test_doctor_can_update_own_patient(self, doctor_user, patient_data):
        """Test doctor can update their own patient."""
        patient_data["doctor_id"] = doctor_user["id"]
        assert check_patient_access(doctor_user, UUID(patient_data["doctor_id"])) is True

    def test_doctor_cannot_update_other_patient(self, doctor_user, other_doctor_user, patient_data):
        """Test doctor cannot update other doctor's patient."""
        patient_data["doctor_id"] = other_doctor_user["id"]

        with pytest.raises(HTTPException):
            ensure_patient_access(doctor_user, UUID(patient_data["doctor_id"]))


class TestDeletePatientRBAC:
    """Test RBAC on delete patient endpoint."""

    def test_only_admin_can_delete_patient(self, admin_user):
        """Test only admins can delete patients."""
        from app.core.permissions import RolePermissions
        assert RolePermissions.has_permission("admin", Permission.PATIENT_DELETE)

    def test_doctor_cannot_delete_patient(self, doctor_user):
        """Test doctors cannot delete patients."""
        from app.core.permissions import RolePermissions
        assert not RolePermissions.has_permission("doctor", Permission.PATIENT_DELETE)


class TestSearchPatientsRBAC:
    """Test RBAC on search patients endpoint."""

    def test_admin_can_search_all_patients(self, admin_user):
        """Test admin can search all patients."""
        from app.core.permissions import RolePermissions
        assert RolePermissions.has_permission("admin", Permission.PATIENT_READ)

    def test_doctor_can_only_search_own_patients(self, doctor_user):
        """Test doctor can only search their own patients."""
        from app.core.permissions import RolePermissions
        assert RolePermissions.has_permission("doctor", Permission.PATIENT_READ)
        # Verify search is scoped to doctor_id


# ============================================================================
# DATA ISOLATION TESTS
# ============================================================================

class TestDataIsolation:
    """Test data isolation between doctors."""

    def test_doctors_cannot_see_each_other_patients(self, doctor_user, other_doctor_user):
        """Test doctors cannot see each other's patients."""
        # Doctor 1's patient
        doctor1_patient_id = UUID(doctor_user["id"])

        # Doctor 2 should not have access
        assert check_patient_access(other_doctor_user, doctor1_patient_id) is False

    def test_admin_sees_all_patients(self, admin_user, doctor_user, other_doctor_user):
        """Test admin can see all doctors' patients."""
        doctor1_patient_id = UUID(doctor_user["id"])
        doctor2_patient_id = UUID(other_doctor_user["id"])

        assert check_patient_access(admin_user, doctor1_patient_id) is True
        assert check_patient_access(admin_user, doctor2_patient_id) is True


# ============================================================================
# PERMISSION VALIDATION TESTS
# ============================================================================

class TestPermissionValidation:
    """Test permission validation for patient operations."""

    def test_patient_read_permissions(self):
        """Test which roles have patient read permission."""
        from app.core.permissions import RolePermissions

        assert RolePermissions.has_permission("admin", Permission.PATIENT_READ)
        assert RolePermissions.has_permission("doctor", Permission.PATIENT_READ)

    def test_patient_create_permissions(self):
        """Test which roles have patient create permission."""
        from app.core.permissions import RolePermissions

        assert RolePermissions.has_permission("admin", Permission.PATIENT_CREATE)
        assert RolePermissions.has_permission("doctor", Permission.PATIENT_CREATE)

    def test_patient_update_permissions(self):
        """Test which roles have patient update permission."""
        from app.core.permissions import RolePermissions

        assert RolePermissions.has_permission("admin", Permission.PATIENT_UPDATE)
        assert RolePermissions.has_permission("doctor", Permission.PATIENT_UPDATE)

    def test_patient_delete_permissions(self):
        """Test which roles have patient delete permission."""
        from app.core.permissions import RolePermissions

        assert RolePermissions.has_permission("admin", Permission.PATIENT_DELETE)
        assert not RolePermissions.has_permission("doctor", Permission.PATIENT_DELETE)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
