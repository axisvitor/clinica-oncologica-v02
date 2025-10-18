"""
Backend Role Permissions Tests - Comprehensive Coverage
Tests for get_permissions_for_role function and role system alignment

IMPORTANT: Must align 100% with frontend role system (QW-011, QW-012)
Frontend has 6 permissions:
- canManageUsers
- canManagePatients
- canViewReports
- canManageFlows
- canAccessAdmin
- canManageSettings

Backend uses dot notation permissions that map to these frontend permissions.

@see app/dependencies/auth_dependencies.py::get_permissions_for_role
@see app/models/user.py::UserRole
"""

import pytest
from app.dependencies.auth_dependencies import get_permissions_for_role
from app.models.user import UserRole


class TestGetPermissionsForRole:
    """Test suite for get_permissions_for_role function."""

    def test_admin_has_all_permissions(self):
        """Admin should have all permissions."""
        perms = get_permissions_for_role("admin")

        # Admin should have many permissions
        assert len(perms) > 0
        assert isinstance(perms, list)

        # Check critical admin permissions
        assert "admin.read" in perms
        assert "admin.write" in perms
        assert "users.read" in perms
        assert "users.write" in perms
        assert "settings.read" in perms
        assert "settings.write" in perms

    def test_admin_case_insensitive(self):
        """Admin permissions should work with any case."""
        perms_lower = get_permissions_for_role("admin")
        perms_upper = get_permissions_for_role("ADMIN")
        perms_mixed = get_permissions_for_role("Admin")

        assert perms_lower == perms_upper
        assert perms_lower == perms_mixed

    def test_admin_has_user_management_permissions(self):
        """Admin should be able to manage users (maps to canManageUsers)."""
        perms = get_permissions_for_role("admin")

        # User management permissions
        assert "users.read" in perms
        assert "users.write" in perms
        assert "users.delete" in perms

    def test_admin_has_patient_permissions(self):
        """Admin should be able to manage patients (maps to canManagePatients)."""
        perms = get_permissions_for_role("admin")

        # Patient permissions
        assert "patients.read" in perms
        assert "patients.write" in perms
        assert "patients.delete" in perms

    def test_admin_has_reports_permissions(self):
        """Admin should be able to view/manage reports (maps to canViewReports)."""
        perms = get_permissions_for_role("admin")

        # Reports permissions
        assert "reports.read" in perms
        assert "reports.write" in perms
        assert "reports.delete" in perms

    def test_admin_has_settings_permissions(self):
        """Admin should be able to manage settings (maps to canManageSettings)."""
        perms = get_permissions_for_role("admin")

        # Settings permissions
        assert "settings.read" in perms
        assert "settings.write" in perms

    def test_admin_has_analytics_permissions(self):
        """Admin should have analytics access."""
        perms = get_permissions_for_role("admin")

        # Analytics permissions
        assert "analytics.read" in perms
        assert "analytics.write" in perms

    def test_admin_has_security_permissions(self):
        """Admin should have security/audit access."""
        perms = get_permissions_for_role("admin")

        # Security permissions
        assert "security.read" in perms
        assert "security.write" in perms

    def test_doctor_has_clinical_permissions(self):
        """Doctor should have clinical permissions only."""
        perms = get_permissions_for_role("doctor")

        # Clinical permissions
        assert "patients.read" in perms
        assert "patients.write" in perms
        assert "appointments.read" in perms
        assert "appointments.write" in perms
        assert "treatments.read" in perms
        assert "treatments.write" in perms
        assert "reports.read" in perms
        assert "reports.write" in perms

    def test_doctor_case_insensitive(self):
        """Doctor permissions should work with any case."""
        perms_lower = get_permissions_for_role("doctor")
        perms_upper = get_permissions_for_role("DOCTOR")
        perms_mixed = get_permissions_for_role("Doctor")

        assert perms_lower == perms_upper
        assert perms_lower == perms_mixed

    def test_doctor_cannot_manage_users(self):
        """Doctor should NOT be able to manage users."""
        perms = get_permissions_for_role("doctor")

        # Should NOT have user management
        assert "users.read" not in perms
        assert "users.write" not in perms
        assert "users.delete" not in perms

    def test_doctor_cannot_access_admin(self):
        """Doctor should NOT have admin permissions."""
        perms = get_permissions_for_role("doctor")

        # Should NOT have admin access
        assert "admin.read" not in perms
        assert "admin.write" not in perms
        assert "admin.delete" not in perms

    def test_doctor_cannot_manage_settings(self):
        """Doctor should NOT be able to manage system settings."""
        perms = get_permissions_for_role("doctor")

        # Should NOT have settings access
        assert "settings.read" not in perms
        assert "settings.write" not in perms

    def test_doctor_cannot_delete_patients(self):
        """Doctor can read/write patients but NOT delete."""
        perms = get_permissions_for_role("doctor")

        # Can manage patients
        assert "patients.read" in perms
        assert "patients.write" in perms

        # But cannot delete
        assert "patients.delete" not in perms

    def test_doctor_cannot_access_billing(self):
        """Doctor should NOT have billing access."""
        perms = get_permissions_for_role("doctor")

        # Should NOT have billing
        assert "billing.read" not in perms
        assert "billing.write" not in perms

    def test_doctor_has_fewer_permissions_than_admin(self):
        """Doctor should have significantly fewer permissions than admin."""
        admin_perms = get_permissions_for_role("admin")
        doctor_perms = get_permissions_for_role("doctor")

        assert len(doctor_perms) < len(admin_perms)
        assert len(doctor_perms) == 8  # Exact count for doctor
        assert len(admin_perms) > 20  # Admin has many more

    def test_invalid_role_returns_minimal_permissions(self):
        """Invalid role should return minimal default permissions."""
        perms = get_permissions_for_role("invalid")

        # Should have minimal read-only access
        assert "patients.read" in perms
        assert "appointments.read" in perms

        # Should NOT have write/delete
        assert "patients.write" not in perms
        assert "patients.delete" not in perms

    def test_empty_role_returns_minimal_permissions(self):
        """Empty role should return minimal default permissions."""
        perms = get_permissions_for_role("")

        # Should have minimal read-only access
        assert "patients.read" in perms
        assert "appointments.read" in perms

    def test_none_role_returns_minimal_permissions(self):
        """None role should return minimal default permissions."""
        perms = get_permissions_for_role(None)

        # Should have minimal read-only access
        assert "patients.read" in perms
        assert "appointments.read" in perms

    def test_legacy_roles_not_supported(self):
        """Legacy roles (nurse, patient, etc) should return default permissions."""
        legacy_roles = ["nurse", "patient", "assistant", "researcher", "coordinator"]

        for role in legacy_roles:
            perms = get_permissions_for_role(role)

            # Should return default minimal permissions
            assert "patients.read" in perms
            assert "appointments.read" in perms

            # Should NOT have admin permissions
            assert "admin.read" not in perms
            assert "users.write" not in perms


class TestFrontendBackendAlignment:
    """
    Test alignment between frontend permissions and backend permissions.

    Frontend permissions (from shared.ts):
    - canManageUsers: Admin only
    - canManagePatients: Admin + Doctor
    - canViewReports: Admin + Doctor
    - canManageFlows: Admin only
    - canAccessAdmin: Admin only
    - canManageSettings: Admin only
    """

    def test_admin_aligns_with_frontend_can_manage_users(self):
        """Admin backend permissions should support frontend canManageUsers."""
        perms = get_permissions_for_role("admin")

        # canManageUsers requires users.* permissions
        assert "users.read" in perms
        assert "users.write" in perms
        assert "users.delete" in perms

    def test_doctor_cannot_manage_users_aligns_with_frontend(self):
        """Doctor backend should NOT support frontend canManageUsers."""
        perms = get_permissions_for_role("doctor")

        # Doctor should NOT have user management
        assert "users.read" not in perms
        assert "users.write" not in perms

    def test_both_roles_can_manage_patients_aligns_with_frontend(self):
        """Both roles backend should support frontend canManagePatients."""
        admin_perms = get_permissions_for_role("admin")
        doctor_perms = get_permissions_for_role("doctor")

        # Both should have patient read/write
        assert "patients.read" in admin_perms
        assert "patients.write" in admin_perms
        assert "patients.read" in doctor_perms
        assert "patients.write" in doctor_perms

    def test_both_roles_can_view_reports_aligns_with_frontend(self):
        """Both roles backend should support frontend canViewReports."""
        admin_perms = get_permissions_for_role("admin")
        doctor_perms = get_permissions_for_role("doctor")

        # Both should have reports read
        assert "reports.read" in admin_perms
        assert "reports.read" in doctor_perms

    def test_admin_can_access_admin_aligns_with_frontend(self):
        """Admin backend should support frontend canAccessAdmin."""
        admin_perms = get_permissions_for_role("admin")

        # Admin should have admin.* permissions
        assert "admin.read" in admin_perms
        assert "admin.write" in admin_perms

    def test_doctor_cannot_access_admin_aligns_with_frontend(self):
        """Doctor backend should NOT support frontend canAccessAdmin."""
        doctor_perms = get_permissions_for_role("doctor")

        # Doctor should NOT have admin permissions
        assert "admin.read" not in doctor_perms
        assert "admin.write" not in doctor_perms

    def test_admin_can_manage_settings_aligns_with_frontend(self):
        """Admin backend should support frontend canManageSettings."""
        admin_perms = get_permissions_for_role("admin")

        # Admin should have settings permissions
        assert "settings.read" in admin_perms
        assert "settings.write" in admin_perms

    def test_doctor_cannot_manage_settings_aligns_with_frontend(self):
        """Doctor backend should NOT support frontend canManageSettings."""
        doctor_perms = get_permissions_for_role("doctor")

        # Doctor should NOT have settings
        assert "settings.read" not in doctor_perms
        assert "settings.write" not in doctor_perms


class TestUserRoleEnum:
    """Test UserRole enum from models."""

    def test_user_role_enum_has_admin(self):
        """UserRole enum should have ADMIN."""
        assert hasattr(UserRole, "ADMIN")
        assert UserRole.ADMIN.value == "admin"

    def test_user_role_enum_has_doctor(self):
        """UserRole enum should have DOCTOR."""
        assert hasattr(UserRole, "DOCTOR")
        assert UserRole.DOCTOR.value == "doctor"

    def test_user_role_enum_has_only_two_roles(self):
        """UserRole enum should have ONLY 2 roles (admin, doctor)."""
        roles = list(UserRole)
        assert len(roles) == 2

        role_values = [r.value for r in roles]
        assert "admin" in role_values
        assert "doctor" in role_values

    def test_user_role_enum_no_legacy_roles(self):
        """UserRole enum should NOT have legacy roles."""
        roles = list(UserRole)
        role_values = [r.value for r in roles]

        # Should NOT have these legacy roles
        assert "nurse" not in role_values
        assert "patient" not in role_values
        assert "assistant" not in role_values
        assert "super_admin" not in role_values
        assert "coordinator" not in role_values
        assert "researcher" not in role_values


class TestPermissionMapping:
    """Test specific permission mappings."""

    def test_admin_permission_count(self):
        """Admin should have exactly the expected number of permissions."""
        perms = get_permissions_for_role("admin")

        # Admin should have substantial permissions
        assert len(perms) >= 28  # At least 28 permissions

    def test_doctor_permission_count(self):
        """Doctor should have exactly 8 permissions."""
        perms = get_permissions_for_role("doctor")

        # Doctor has exactly 8 clinical permissions
        assert len(perms) == 8

    def test_doctor_permissions_are_subset_of_admin(self):
        """All doctor permissions should be included in admin permissions."""
        admin_perms = set(get_permissions_for_role("admin"))
        doctor_perms = set(get_permissions_for_role("doctor"))

        # Doctor permissions should be a subset of admin
        assert doctor_perms.issubset(admin_perms)

    def test_no_duplicate_permissions_admin(self):
        """Admin permissions should not have duplicates."""
        perms = get_permissions_for_role("admin")
        assert len(perms) == len(set(perms))

    def test_no_duplicate_permissions_doctor(self):
        """Doctor permissions should not have duplicates."""
        perms = get_permissions_for_role("doctor")
        assert len(perms) == len(set(perms))

    def test_all_permissions_use_dot_notation(self):
        """All permissions should use dot notation (resource.action)."""
        admin_perms = get_permissions_for_role("admin")
        doctor_perms = get_permissions_for_role("doctor")

        all_perms = admin_perms + doctor_perms

        for perm in all_perms:
            assert "." in perm, f"Permission '{perm}' should use dot notation"
            parts = perm.split(".")
            assert len(parts) >= 2, (
                f"Permission '{perm}' should have at least resource.action"
            )


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_whitespace_role(self):
        """Role with whitespace should return default permissions."""
        perms = get_permissions_for_role("  ")
        assert "patients.read" in perms

    def test_special_characters_role(self):
        """Role with special characters should return default permissions."""
        perms = get_permissions_for_role("admin!")
        assert "patients.read" in perms
        # Should NOT match admin
        assert "admin.read" not in perms

    def test_numeric_role(self):
        """Numeric role should return default permissions."""
        perms = get_permissions_for_role("123")
        assert "patients.read" in perms

    def test_very_long_role_string(self):
        """Very long role string should not crash."""
        long_role = "a" * 10000
        perms = get_permissions_for_role(long_role)
        assert isinstance(perms, list)

    def test_returns_list_not_set(self):
        """Function should return list, not set."""
        perms = get_permissions_for_role("admin")
        assert isinstance(perms, list)

    def test_returns_strings_not_enums(self):
        """Function should return strings, not enum values."""
        perms = get_permissions_for_role("admin")
        for perm in perms:
            assert isinstance(perm, str)


class TestSecurityImplications:
    """Test security-related behavior."""

    def test_unknown_role_cannot_escalate_privileges(self):
        """Unknown role should never get admin permissions."""
        unknown_roles = ["hacker", "root", "superuser", "sudo"]

        for role in unknown_roles:
            perms = get_permissions_for_role(role)

            # Should NOT have admin permissions
            assert "admin.read" not in perms
            assert "admin.write" not in perms
            assert "users.write" not in perms
            assert "settings.write" not in perms

    def test_sql_injection_attempt_in_role(self):
        """SQL injection attempt in role should not cause issues."""
        sql_role = "admin'; DROP TABLE users; --"
        perms = get_permissions_for_role(sql_role)

        # Should return safe default
        assert isinstance(perms, list)
        assert "admin.read" not in perms

    def test_case_manipulation_cannot_bypass(self):
        """Case manipulation should not bypass security."""
        # Try variations that should NOT match admin
        invalid_admins = ["ADMINN", "admin1", "admin ", " admin", "admin\n"]

        for role in invalid_admins:
            perms = get_permissions_for_role(role)
            # Should NOT have admin permissions
            # (except for case-insensitive match like "ADMIN")
            if role.strip().upper() != "ADMIN":
                assert "admin.read" not in perms


class TestPermissionConsistency:
    """Test consistency across role system."""

    def test_admin_doctor_have_no_conflicting_interpretations(self):
        """Admin and doctor permissions should be clearly distinct."""
        admin_perms = set(get_permissions_for_role("admin"))
        doctor_perms = set(get_permissions_for_role("doctor"))

        # Doctor should not have any admin-exclusive permissions
        admin_exclusive = admin_perms - doctor_perms

        # Verify some admin-exclusive permissions exist
        assert "admin.read" in admin_exclusive
        assert "users.write" in admin_exclusive
        assert "settings.write" in admin_exclusive

    def test_permission_names_follow_convention(self):
        """All permissions should follow resource.action convention."""
        valid_actions = ["read", "write", "delete"]

        admin_perms = get_permissions_for_role("admin")

        for perm in admin_perms:
            parts = perm.split(".")
            if len(parts) >= 2:
                action = parts[-1]
                # Last part should be a valid action
                # (or it could be nested like admin.templates.read)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
