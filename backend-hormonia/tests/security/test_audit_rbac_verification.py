import pytest

from app.core.permissions import Permission, PermissionChecker, ROLE_DEFINITIONS
from app.models.user import UserRole

@pytest.mark.security
class TestRBACAuditVerification:
    """
    Audit verification tests for RBAC permission enforcement.
    Ensures roles have the correct set of permissions according to the principle of least privilege.
    """

    def test_admin_permissions_completeness(self):
        """Verify that ADMIN role has all necessary administrative permissions."""
        admin_perms = ROLE_DEFINITIONS[UserRole.ADMIN].permissions
        
        # Check for missing critical admin permissions found during audit
        missing = []
        if Permission.PATIENT_SENSITIVE_DATA not in admin_perms:
            missing.append("PATIENT_SENSITIVE_DATA")
        if Permission.USER_DELETE not in admin_perms:
            missing.append("USER_DELETE")
        if Permission.PATIENT_DELETE not in admin_perms:
            missing.append("PATIENT_DELETE")
            
        assert not missing, f"ADMIN role is missing critical permissions: {missing}"

    def test_doctor_permissions_limitations(self):
        """Verify that DOCTOR role does NOT have administrative permissions."""
        doctor_perms = ROLE_DEFINITIONS[UserRole.DOCTOR].permissions
        
        admin_only_perms = {
            Permission.ADMIN_PANEL,
            Permission.ADMIN_SETTINGS,
            Permission.ADMIN_LOGS,
            Permission.USER_CREATE,
            Permission.USER_DELETE,
            Permission.USER_LIST,
            Permission.WEBHOOK_MANAGE,
            Permission.INTEGRATION_MANAGE,
        }
        
        forbidden = doctor_perms.intersection(admin_only_perms)
        assert not forbidden, f"DOCTOR role has unauthorized admin permissions: {forbidden}"

    def test_role_permissions_has_permission_utility(self):
        """Verify the utility function for permission checking works correctly."""
        # Admin should have PATIENT_READ
        assert PermissionChecker.has_permission(UserRole.ADMIN, Permission.PATIENT_READ)

        # Doctor should have PATIENT_READ
        assert PermissionChecker.has_permission(UserRole.DOCTOR, Permission.PATIENT_READ)

        # Doctor should NOT have ADMIN_PANEL
        assert not PermissionChecker.has_permission(UserRole.DOCTOR, Permission.ADMIN_PANEL)

    def test_patient_sensitive_data_access(self):
        """
        Verify who can access patient sensitive data.
        In clinical systems, both DOCTOR and ADMIN typically need this, 
        or it's restricted to DOCTOR.
        Audit check: Ensure ADMIN can access if required for support.
        """
        has_access = PermissionChecker.has_permission(
            UserRole.ADMIN, Permission.PATIENT_SENSITIVE_DATA
        )
        # If this fails, we documented a gap in ADMIN capabilities
        assert has_access, "ADMIN should have PATIENT_SENSITIVE_DATA permission for system support"
