"""
Role Enum Regression Tests
Comprehensive tests to prevent regression of role enum usage issues.
"""

import pytest
import ast
import re
from pathlib import Path
from typing import Set, List
from enum import Enum

from app.models.user import UserRole


class TestRoleEnumRegression:
    """Comprehensive tests for role enum usage patterns."""
    
    def test_user_role_enum_definition(self):
        """Test that UserRole enum is properly defined."""
        # Verify it's an Enum
        assert issubclass(UserRole, Enum), "UserRole should be an Enum"
        
        # Verify it has expected roles
        assert hasattr(UserRole, 'ADMIN'), "UserRole should have ADMIN role"
        assert hasattr(UserRole, 'DOCTOR'), "UserRole should have DOCTOR role"
        
        # Verify enum values are strings
        assert isinstance(UserRole.ADMIN.value, str), "ADMIN role value should be string"
        assert isinstance(UserRole.DOCTOR.value, str), "DOCTOR role value should be string"
        
        # Verify specific values
        assert UserRole.ADMIN.value == "admin", "ADMIN role should have value 'admin'"
        assert UserRole.DOCTOR.value == "doctor", "DOCTOR role should have value 'doctor'"
    
    def test_user_role_enum_completeness(self):
        """Test that UserRole enum contains all expected roles and no invalid ones."""
        # Get all defined roles
        defined_roles = {role.name for role in UserRole}
        
        # Expected roles (based on current system)
        expected_roles = {'ADMIN', 'DOCTOR'}
        
        # Should have at least the expected roles
        assert expected_roles.issubset(defined_roles), \
            f"Missing expected roles: {expected_roles - defined_roles}"
        
        # Should not have problematic roles that were causing issues
        problematic_roles = {'SUPER_ADMIN', 'SUPERADMIN'}
        assert not problematic_roles.intersection(defined_roles), \
            f"Found problematic roles: {problematic_roles.intersection(defined_roles)}"
    
    def test_role_enum_string_representations(self):
        """Test string representations of role enums."""
        # Test string conversion
        assert str(UserRole.ADMIN) == "UserRole.ADMIN"
        assert str(UserRole.DOCTOR) == "UserRole.DOCTOR"
        
        # Test value access
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.DOCTOR.value == "doctor"
        
        # Test name access
        assert UserRole.ADMIN.name == "ADMIN"
        assert UserRole.DOCTOR.name == "DOCTOR"
    
    def test_role_enum_comparison_patterns(self):
        """Test that role enum comparisons work correctly."""
        admin_role = UserRole.ADMIN
        doctor_role = UserRole.DOCTOR
        
        # Enum to enum comparison
        assert admin_role == UserRole.ADMIN
        assert admin_role != UserRole.DOCTOR
        assert doctor_role == UserRole.DOCTOR
        assert doctor_role != UserRole.ADMIN
        
        # Enum to string comparison (should NOT be equal)
        assert admin_role != "admin"
        assert admin_role != "ADMIN"
        assert doctor_role != "doctor"
        assert doctor_role != "DOCTOR"
        
        # Value comparison
        assert admin_role.value == "admin"
        assert doctor_role.value == "doctor"


class TestCodebaseRoleUsageRegression:
    """Test role usage patterns throughout the codebase."""
    
    def test_no_nonexistent_role_references(self):
        """Test that no code references non-existent roles."""
        backend_root = Path(__file__).parent.parent
        
        # Get valid roles
        valid_roles = {role.name for role in UserRole}
        
        # Known problematic roles that should not exist
        invalid_roles = {
            'SUPER_ADMIN', 'SUPERADMIN', 'NURSE', 'PATIENT', 
            'MANAGER', 'SUPERVISOR', 'ROOT', 'SYSTEM'
        }
        
        python_files = list((backend_root / "app").rglob("*.py"))
        
        for file_path in python_files:
            if "test" in str(file_path) or "__pycache__" in str(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find UserRole.SOMETHING patterns
                role_pattern = r'UserRole\.([A-Z_]+)'
                matches = re.findall(role_pattern, content)
                
                for role in matches:
                    assert role in valid_roles, \
                        f"File {file_path.relative_to(backend_root)} references non-existent role UserRole.{role}"
                    
                    assert role not in invalid_roles, \
                        f"File {file_path.relative_to(backend_root)} references invalid role UserRole.{role}"
            
            except Exception as e:
                pytest.fail(f"Error checking file {file_path}: {e}")
    
    def test_no_string_role_comparisons(self):
        """Test that code doesn't use string comparisons for roles."""
        backend_root = Path(__file__).parent.parent
        python_files = list((backend_root / "app").rglob("*.py"))
        
        # Patterns that indicate string role comparisons
        problematic_patterns = [
            r'\.role\s*==\s*["\']admin["\']',
            r'\.role\s*==\s*["\']doctor["\']',
            r'["\']admin["\']\s*==\s*.*\.role',
            r'["\']doctor["\']\s*==\s*.*\.role',
            r'\.role\s*!=\s*["\']admin["\']',
            r'\.role\s*!=\s*["\']doctor["\']',
            r'["\']admin["\']\s*!=\s*.*\.role',
            r'["\']doctor["\']\s*!=\s*.*\.role'
        ]
        
        for file_path in python_files:
            if "test" in str(file_path) or "__pycache__" in str(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                for pattern in problematic_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    assert not matches, \
                        f"File {file_path.relative_to(backend_root)} uses string role comparison: {matches[0] if matches else pattern}"
            
            except Exception as e:
                pytest.fail(f"Error checking file {file_path}: {e}")
    
    def test_analytics_api_role_usage(self):
        """Test that analytics API uses correct role patterns."""
        backend_root = Path(__file__).parent.parent
        analytics_file = backend_root / "app/api/v1/analytics.py"
        
        if not analytics_file.exists():
            pytest.skip("Analytics API file not found")
        
        with open(analytics_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should not reference SUPER_ADMIN
        assert "UserRole.SUPER_ADMIN" not in content, \
            "Analytics API should not reference non-existent SUPER_ADMIN role"
        
        # If it uses role sets, they should only contain valid roles
        valid_roles = {role.name for role in UserRole}
        
        # Find role set patterns like {UserRole.ADMIN, UserRole.SOMETHING}
        set_pattern = r'\{[^}]*UserRole\.[A-Z_]+[^}]*\}'
        set_matches = re.findall(set_pattern, content)
        
        for set_match in set_matches:
            roles_in_set = re.findall(r'UserRole\.([A-Z_]+)', set_match)
            for role in roles_in_set:
                assert role in valid_roles, \
                    f"Analytics API set contains invalid role: UserRole.{role}"
    
    def test_monthly_quiz_api_role_usage(self):
        """Test that monthly quiz API uses correct role patterns."""
        backend_root = Path(__file__).parent.parent
        monthly_quiz_file = backend_root / "app/api/v1/monthly_quiz.py"
        
        if not monthly_quiz_file.exists():
            pytest.skip("Monthly quiz API file not found")
        
        with open(monthly_quiz_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should use enum comparison, not string comparison
        string_patterns = [
            r'current_user\.role\s*==\s*["\']admin["\']',
            r'user\.role\s*==\s*["\']admin["\']'
        ]
        
        for pattern in string_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            assert not matches, \
                f"Monthly quiz API uses string role comparison instead of enum: {matches}"
        
        # Should use UserRole.ADMIN for admin checks
        if "admin" in content.lower():
            # If checking for admin role, should use enum
            admin_checks = re.findall(r'\.role\s*==\s*UserRole\.ADMIN', content)
            string_admin_checks = re.findall(r'\.role\s*==\s*["\']admin["\']', content)
            
            if string_admin_checks:
                assert len(admin_checks) > 0, \
                    "Monthly quiz API should use UserRole.ADMIN instead of string 'admin'"
    
    def test_permission_decorators_use_valid_roles(self):
        """Test that permission decorators only reference valid roles."""
        backend_root = Path(__file__).parent.parent
        python_files = list((backend_root / "app").rglob("*.py"))
        
        valid_roles = {role.name for role in UserRole}
        
        for file_path in python_files:
            if "test" in str(file_path) or "__pycache__" in str(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Check decorators
                        for decorator in node.decorator_list:
                            if isinstance(decorator, ast.Call):
                                # Look for role-related decorators
                                decorator_name = ""
                                if isinstance(decorator.func, ast.Name):
                                    decorator_name = decorator.func.id
                                elif isinstance(decorator.func, ast.Attribute):
                                    decorator_name = decorator.func.attr
                                
                                if any(word in decorator_name.lower() 
                                       for word in ['require', 'permission', 'role', 'auth']):
                                    
                                    # Check arguments for UserRole references
                                    for arg in decorator.args:
                                        if (isinstance(arg, ast.Attribute) and
                                            isinstance(arg.value, ast.Name) and
                                            arg.value.id == "UserRole"):
                                            
                                            assert arg.attr in valid_roles, \
                                                f"File {file_path.relative_to(backend_root)}:{node.lineno} - " \
                                                f"Decorator uses invalid role UserRole.{arg.attr}"
            
            except SyntaxError:
                # Skip files that can't be parsed
                continue
            except Exception as e:
                pytest.fail(f"Error checking decorators in {file_path}: {e}")


class TestRoleEnumIntegration:
    """Integration tests for role enum usage."""
    
    def test_role_enum_with_user_model(self):
        """Test that role enum integrates correctly with user model."""
        # This test would verify that the User model correctly uses the UserRole enum
        # Implementation depends on actual User model structure
        
        try:
            from app.models.user import User
            
            # If User model exists, test role field
            if hasattr(User, '__table__'):
                # Check if role column exists
                columns = [col.name for col in User.__table__.columns]
                if 'role' in columns:
                    # Test that role field can accept UserRole values
                    user = User()
                    user.role = UserRole.ADMIN
                    assert user.role == UserRole.ADMIN
                    
                    user.role = UserRole.DOCTOR
                    assert user.role == UserRole.DOCTOR
        
        except ImportError:
            pytest.skip("User model not available for testing")
    
    def test_role_enum_serialization(self):
        """Test that role enums can be properly serialized."""
        import json
        
        # Test JSON serialization of role values
        admin_role_value = UserRole.ADMIN.value
        doctor_role_value = UserRole.DOCTOR.value
        
        # Should be JSON serializable
        json_data = json.dumps({
            "admin_role": admin_role_value,
            "doctor_role": doctor_role_value
        })
        
        parsed_data = json.loads(json_data)
        assert parsed_data["admin_role"] == "admin"
        assert parsed_data["doctor_role"] == "doctor"
    
    def test_role_enum_in_sets_and_lists(self):
        """Test that role enums work correctly in collections."""
        # Test in sets
        admin_roles = {UserRole.ADMIN}
        all_roles = {UserRole.ADMIN, UserRole.DOCTOR}
        
        assert UserRole.ADMIN in admin_roles
        assert UserRole.DOCTOR not in admin_roles
        assert UserRole.ADMIN in all_roles
        assert UserRole.DOCTOR in all_roles
        
        # Test in lists
        role_list = [UserRole.ADMIN, UserRole.DOCTOR]
        assert UserRole.ADMIN in role_list
        assert UserRole.DOCTOR in role_list
        
        # Test set operations
        intersection = admin_roles.intersection(all_roles)
        assert intersection == {UserRole.ADMIN}
    
    def test_role_enum_case_sensitivity(self):
        """Test that role enum handling is case-sensitive as expected."""
        # Enum names should be case-sensitive
        assert hasattr(UserRole, 'ADMIN')
        assert not hasattr(UserRole, 'admin')
        assert not hasattr(UserRole, 'Admin')
        
        # Values should match expected case
        assert UserRole.ADMIN.value == "admin"  # lowercase value
        assert UserRole.DOCTOR.value == "doctor"  # lowercase value
    
    def test_role_enum_iteration(self):
        """Test that role enum can be iterated over."""
        roles = list(UserRole)
        
        # Should have at least ADMIN and DOCTOR
        role_names = {role.name for role in roles}
        assert 'ADMIN' in role_names
        assert 'DOCTOR' in role_names
        
        # Should be able to iterate
        for role in UserRole:
            assert isinstance(role, UserRole)
            assert isinstance(role.name, str)
            assert isinstance(role.value, str)


class TestRoleEnumErrorPrevention:
    """Tests to prevent common role enum errors."""
    
    def test_prevent_typos_in_role_names(self):
        """Test that common typos in role names are not present."""
        # Common typos that might be introduced
        typos = [
            'ADMIM', 'ADMON', 'AMIN',  # ADMIN typos
            'DOCTER', 'DOCTR', 'DOCTRO',  # DOCTOR typos
            'SUPERADMIN', 'SUPER_ADMIN'  # Non-existent roles
        ]
        
        for typo in typos:
            assert not hasattr(UserRole, typo), \
                f"UserRole should not have typo attribute: {typo}"
    
    def test_prevent_duplicate_role_values(self):
        """Test that role values are unique."""
        role_values = [role.value for role in UserRole]
        unique_values = set(role_values)
        
        assert len(role_values) == len(unique_values), \
            f"Duplicate role values found: {role_values}"
    
    def test_prevent_empty_or_invalid_role_values(self):
        """Test that all role values are valid strings."""
        for role in UserRole:
            assert isinstance(role.value, str), \
                f"Role {role.name} has non-string value: {role.value}"
            assert len(role.value) > 0, \
                f"Role {role.name} has empty value"
            assert role.value.strip() == role.value, \
                f"Role {role.name} has whitespace in value: '{role.value}'"
    
    def test_role_enum_backwards_compatibility(self):
        """Test that role enum maintains backwards compatibility."""
        # These roles should always exist for backwards compatibility
        required_roles = ['ADMIN', 'DOCTOR']
        
        for role_name in required_roles:
            assert hasattr(UserRole, role_name), \
                f"Required role {role_name} is missing - breaks backwards compatibility"
        
        # These values should remain stable
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.DOCTOR.value == "doctor"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])