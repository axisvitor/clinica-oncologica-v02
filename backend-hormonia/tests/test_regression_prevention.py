"""
Comprehensive Regression Tests for Critical Bug Fixes
Tests to prevent regression of dependency injection, role enum, schema, and date parameter issues.
"""

import pytest
import ast
import re
from pathlib import Path
from typing import List, Dict, Set, Any
from unittest.mock import Mock, patch
from datetime import datetime, date

from app.dependencies.service_dependencies import _ThreadSafeProviderDependency
from app.models.user import UserRole
from app.core.date_utils import coerce_to_date


class TestDependencyInjectionRegression:
    """Test dependency injection patterns to prevent generator object issues."""
    
    def test_provider_dependency_returns_provider_not_generator(self):
        """Test that DI returns actual provider instances, not generator objects."""
        # Create the dependency instance
        provider_dep = _ThreadSafeProviderDependency()
        
        # Get the provider
        provider_gen = provider_dep()
        provider = next(provider_gen)
        
        # Verify it's not a generator
        assert not hasattr(provider, '__next__'), "Provider should not be a generator object"
        
        # Verify it has expected service attributes
        assert hasattr(provider, 'monthly_quiz_service'), "Provider should have monthly_quiz_service"
        assert hasattr(provider, 'quiz_service'), "Provider should have quiz_service"
        
        # Verify services are callable/accessible
        assert provider.monthly_quiz_service is not None
        assert provider.quiz_service is not None
    
    def test_dependency_injection_code_patterns(self):
        """Test that DI code follows correct patterns."""
        backend_root = Path(__file__).parent.parent
        di_file = backend_root / "app/dependencies/service_dependencies.py"
        
        assert di_file.exists(), "service_dependencies.py should exist"
        
        with open(di_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should not have return statement for generator functions
        assert "return get_thread_safe_service_provider()" not in content, \
            "Should use 'yield from' not 'return' for generator functions"
        
        # Should have yield from pattern
        assert "yield from" in content, "Should use 'yield from' pattern in DI"
    
    def test_fastapi_depends_usage(self):
        """Test that FastAPI Depends() usage is correct."""
        backend_root = Path(__file__).parent.parent
        api_files = list((backend_root / "app/api").rglob("*.py"))
        
        for file_path in api_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # If file uses Depends, check patterns
            if "Depends(" in content:
                # Should not have obvious generator return patterns in dependencies
                assert "return (" not in content or "yield" in content, \
                    f"File {file_path} may have incorrect dependency patterns"


class TestRoleEnumRegression:
    """Test role enum usage to prevent non-existent role references."""
    
    def test_user_role_enum_exists_and_has_values(self):
        """Test that UserRole enum exists and has expected values."""
        # Verify enum exists
        assert hasattr(UserRole, 'ADMIN'), "UserRole should have ADMIN role"
        assert hasattr(UserRole, 'DOCTOR'), "UserRole should have DOCTOR role"
        
        # Verify enum values are strings
        assert isinstance(UserRole.ADMIN.value, str), "Role values should be strings"
        assert isinstance(UserRole.DOCTOR.value, str), "Role values should be strings"
    
    def test_no_references_to_nonexistent_roles(self):
        """Test that code doesn't reference non-existent roles."""
        backend_root = Path(__file__).parent.parent
        
        # Get valid roles
        valid_roles = {role.name for role in UserRole}
        
        # Common non-existent roles that might be referenced
        invalid_roles = {'SUPER_ADMIN', 'NURSE', 'PATIENT', 'MANAGER'}
        
        python_files = list((backend_root / "app").rglob("*.py"))
        
        for file_path in python_files:
            if "test" in str(file_path):
                continue
                
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for UserRole.INVALID_ROLE patterns
            role_pattern = r'UserRole\.([A-Z_]+)'
            matches = re.findall(role_pattern, content)
            
            for role in matches:
                assert role in valid_roles, \
                    f"File {file_path} references non-existent role UserRole.{role}"
    
    def test_role_comparisons_use_enums_not_strings(self):
        """Test that role comparisons use enum values, not string literals."""
        backend_root = Path(__file__).parent.parent
        python_files = list((backend_root / "app/api").rglob("*.py"))
        
        for file_path in python_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for string role comparisons that should use enums
            string_patterns = [
                r'\.role\s*==\s*["\']admin["\']',
                r'\.role\s*==\s*["\']doctor["\']',
                r'["\']admin["\']\s*==\s*.*\.role',
                r'["\']doctor["\']\s*==\s*.*\.role'
            ]
            
            for pattern in string_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                assert not matches, \
                    f"File {file_path} uses string role comparison instead of enum: {matches}"
    
    def test_analytics_endpoints_use_valid_roles(self):
        """Test that analytics endpoints only reference valid roles."""
        backend_root = Path(__file__).parent.parent
        analytics_file = backend_root / "app/api/v1/analytics.py"
        
        if analytics_file.exists():
            with open(analytics_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Should not reference SUPER_ADMIN
            assert "UserRole.SUPER_ADMIN" not in content, \
                "Analytics should not reference non-existent SUPER_ADMIN role"
            
            # Should use valid roles
            if "UserRole." in content:
                valid_roles = {role.name for role in UserRole}
                role_matches = re.findall(r'UserRole\.([A-Z_]+)', content)
                
                for role in role_matches:
                    assert role in valid_roles, \
                        f"Analytics references invalid role: UserRole.{role}"


class TestDatabaseModelRegression:
    """Test database model compatibility to prevent schema drift issues."""
    
    def test_alert_model_column_mappings(self):
        """Test that Alert model uses correct column mappings."""
        from app.models.alert import Alert
        
        # Test that model has proper column mappings
        assert hasattr(Alert, 'alert_type'), "Alert should have alert_type attribute"
        assert hasattr(Alert, 'description'), "Alert should have description attribute"
        
        # Test column name mappings (if using SQLAlchemy column mapping)
        # This would need to be adapted based on actual implementation
        table = Alert.__table__
        column_names = [col.name for col in table.columns]
        
        # Should map to actual database columns
        assert 'type' in column_names or 'alert_type' in column_names, \
            "Alert table should have type or alert_type column"
        assert 'message' in column_names or 'description' in column_names, \
            "Alert table should have message or description column"
    
    def test_alert_model_status_property(self):
        """Test that Alert model handles status property correctly."""
        from app.models.alert import Alert
        
        # Create test alert
        alert = Alert()
        
        # Test status property mapping
        if hasattr(alert, 'status'):
            # Test status setter/getter
            alert.status = "acknowledged"
            assert alert.acknowledged == True, "Status 'acknowledged' should set acknowledged=True"
            
            alert.status = "pending"
            assert alert.acknowledged == False, "Status 'pending' should set acknowledged=False"
    
    def test_models_dont_reference_nonexistent_columns(self):
        """Test that models don't reference columns that don't exist in schema."""
        backend_root = Path(__file__).parent.parent
        
        # Load schema information if available
        schema_file = backend_root / "sql/SCHEMA_MASTER_COMPLETO.sql"
        if not schema_file.exists():
            pytest.skip("Schema file not found - skipping schema validation")
        
        # This is a simplified test - in practice, you'd parse the schema
        # and validate against actual model definitions
        model_files = list((backend_root / "app/models").glob("*.py"))
        
        for model_file in model_files:
            if model_file.name == "__init__.py":
                continue
                
            with open(model_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Basic check for common problematic patterns
            # This should be expanded based on actual schema issues found
            if "alert" in model_file.name.lower():
                # Alert model specific checks
                assert 'Column("alert_type"' not in content or 'Column("type"' in content, \
                    "Alert model should use correct column names"


class TestDateParameterRegression:
    """Test date parameter handling to prevent validation errors."""
    
    def test_coerce_to_date_function_exists(self):
        """Test that coerce_to_date utility function exists and works."""
        # Test with various input formats
        test_cases = [
            ("2025-10-05T15:01:57.695Z", date(2025, 10, 5)),
            ("2025-10-05", date(2025, 10, 5)),
            (datetime(2025, 10, 5, 15, 1, 57), date(2025, 10, 5)),
            (date(2025, 10, 5), date(2025, 10, 5)),
            (None, None),
        ]
        
        for input_val, expected in test_cases:
            result = coerce_to_date(input_val)
            assert result == expected, f"coerce_to_date({input_val}) should return {expected}"
    
    def test_coerce_to_date_error_handling(self):
        """Test that coerce_to_date handles invalid inputs properly."""
        invalid_inputs = [
            "invalid-date",
            "2025-13-45",  # Invalid date
            123,  # Invalid type
            [],   # Invalid type
        ]
        
        for invalid_input in invalid_inputs:
            with pytest.raises(ValueError):
                coerce_to_date(invalid_input)
    
    def test_analytics_endpoints_accept_datetime_strings(self):
        """Test that analytics endpoints can handle datetime string parameters."""
        # This would require setting up test client and testing actual endpoints
        # For now, we'll test the pattern exists in the code
        
        backend_root = Path(__file__).parent.parent
        analytics_file = backend_root / "app/api/v1/analytics.py"
        
        if analytics_file.exists():
            with open(analytics_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Should use coerce_to_date for date parameters
            if "start_date" in content or "end_date" in content:
                assert "coerce_to_date" in content, \
                    "Analytics endpoints with date parameters should use coerce_to_date"
    
    def test_api_endpoints_have_proper_date_error_handling(self):
        """Test that API endpoints handle date parameter errors properly."""
        backend_root = Path(__file__).parent.parent
        api_files = list((backend_root / "app/api").rglob("*.py"))
        
        for file_path in api_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # If using coerce_to_date, should have error handling
            if "coerce_to_date" in content:
                assert "HTTPException" in content or "ValueError" in content, \
                    f"File {file_path} uses coerce_to_date but lacks error handling"


class TestCodePatternRegression:
    """Test general code patterns to prevent regression of critical issues."""
    
    def test_no_generator_return_patterns_in_dependencies(self):
        """Test that dependency files don't have problematic generator return patterns."""
        backend_root = Path(__file__).parent.parent
        dep_files = list((backend_root / "app/dependencies").glob("*.py"))
        
        for file_path in dep_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "__call__":
                    # Check for return statements in __call__ methods
                    for stmt in node.body:
                        if isinstance(stmt, ast.Return) and stmt.value:
                            # If returning a function call, it might be problematic
                            if isinstance(stmt.value, ast.Call):
                                # Should use yield from instead
                                has_yield_from = any(
                                    isinstance(s, ast.Expr) and isinstance(s.value, ast.YieldFrom)
                                    for s in node.body
                                )
                                
                                if not has_yield_from:
                                    pytest.fail(
                                        f"File {file_path}:{node.lineno} - "
                                        f"__call__ method returns function call without yield from"
                                    )
    
    def test_consistent_import_patterns(self):
        """Test that imports follow consistent patterns."""
        backend_root = Path(__file__).parent.parent
        
        # Check that date utils are imported correctly where used
        api_files = list((backend_root / "app/api").rglob("*.py"))
        
        for file_path in api_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # If using coerce_to_date, should have proper import
            if "coerce_to_date(" in content:
                assert "from app.core.date_utils import" in content, \
                    f"File {file_path} uses coerce_to_date but missing import"
    
    def test_error_handling_patterns(self):
        """Test that error handling follows consistent patterns."""
        backend_root = Path(__file__).parent.parent
        api_files = list((backend_root / "app/api").rglob("*.py"))
        
        for file_path in api_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # If file has date coercion, should have HTTPException
            if "coerce_to_date" in content:
                assert "HTTPException" in content, \
                    f"File {file_path} uses date coercion but no HTTPException for errors"


# Integration test to verify all fixes work together
class TestIntegratedRegression:
    """Integration tests to verify all critical fixes work together."""
    
    @pytest.mark.integration
    def test_dependency_injection_with_role_checks(self):
        """Test that DI works correctly with role-based endpoints."""
        # This would require a more complex setup with actual FastAPI testing
        # For now, we verify the patterns exist
        
        provider_dep = _ThreadSafeProviderDependency()
        provider = next(provider_dep())
        
        # Verify provider works
        assert provider is not None
        assert not hasattr(provider, '__next__')
        
        # Verify role enum works
        admin_role = UserRole.ADMIN
        assert admin_role.value == "admin"
    
    @pytest.mark.integration
    def test_date_parameters_with_error_handling(self):
        """Test that date parameter handling works with proper error handling."""
        # Test valid date conversion
        result = coerce_to_date("2025-10-05T15:01:57.695Z")
        assert result == date(2025, 10, 5)
        
        # Test error handling
        with pytest.raises(ValueError):
            coerce_to_date("invalid-date")
    
    @pytest.mark.integration  
    def test_all_critical_patterns_together(self):
        """Test that all critical patterns work together without conflicts."""
        # This is a meta-test that verifies the system can import and use
        # all the fixed components together
        
        # Test DI
        provider_dep = _ThreadSafeProviderDependency()
        provider = next(provider_dep())
        assert provider is not None
        
        # Test roles
        role = UserRole.ADMIN
        assert role.value == "admin"
        
        # Test date utils
        test_date = coerce_to_date("2025-10-05")
        assert test_date == date(2025, 10, 5)
        
        # If we get here, all components work together
        assert True, "All critical components work together"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])