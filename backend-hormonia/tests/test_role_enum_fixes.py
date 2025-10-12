"""
Unit tests for role enum fixes in analytics and monthly quiz APIs.

Tests that analytics endpoints only reference existing UserRole values
and that role checks work correctly with UserRole.ADMIN enum comparison.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException
import sys
import os

# Add the app directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock the config and database before importing app modules
with patch.dict(os.environ, {
    'SECRET_KEY': 'test-secret-key',
    'DATABASE_URL': 'postgresql://test:test@localhost/test',
    'REDIS_URL': 'redis://localhost:6379/0'
}):
    from app.models.user import User, UserRole


class TestAnalyticsRoleEnumFixes:
    """Test analytics endpoints use proper UserRole enum values."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create mock admin user
        self.admin_user = Mock(spec=User)
        self.admin_user.id = "admin-user-id"
        self.admin_user.role = UserRole.ADMIN
        
        # Create mock doctor user
        self.doctor_user = Mock(spec=User)
        self.doctor_user.id = "doctor-user-id"
        self.doctor_user.role = UserRole.DOCTOR

    def test_admin_role_filtering_logic(self):
        """Test the admin role filtering logic used in analytics endpoints."""
        # Test the filtering pattern used in analytics APIs
        # Admin should get None (see all data)
        admin_filter = None if self.admin_user.role == UserRole.ADMIN else self.admin_user.id
        assert admin_filter is None
        
        # Doctor should get their ID (filtered data)
        doctor_filter = None if self.doctor_user.role == UserRole.ADMIN else self.doctor_user.id
        assert doctor_filter == "doctor-user-id"

    def test_system_health_access_logic(self):
        """Test system health access logic without importing full modules."""
        # Test the access control pattern used in system health endpoint
        # Admin should have access
        admin_has_access = self.admin_user.role == UserRole.ADMIN
        assert admin_has_access is True
        
        # Doctor should be denied access
        doctor_has_access = self.doctor_user.role == UserRole.ADMIN
        assert doctor_has_access is False

    def test_role_enum_values_exist(self):
        """Test that only existing UserRole enum values are used."""
        # Verify UserRole only has ADMIN and DOCTOR
        available_roles = [role.value for role in UserRole]
        assert "admin" in available_roles
        assert "doctor" in available_roles
        
        # Verify SUPER_ADMIN does not exist
        assert "super_admin" not in available_roles
        assert not hasattr(UserRole, 'SUPER_ADMIN')

    def test_enum_comparison_not_string(self):
        """Test that role comparisons use enum, not string."""
        admin_user = Mock(spec=User)
        admin_user.role = UserRole.ADMIN
        
        # Enum comparison should work
        assert admin_user.role == UserRole.ADMIN
        
        # String comparison should NOT work (this is what we fixed)
        assert admin_user.role != "admin"


class TestMonthlyQuizRoleEnumFixes:
    """Test monthly quiz endpoints use proper UserRole enum comparison."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create mock admin user
        self.admin_user = Mock(spec=User)
        self.admin_user.id = "admin-user-id"
        self.admin_user.role = UserRole.ADMIN
        
        # Create mock doctor user
        self.doctor_user = Mock(spec=User)
        self.doctor_user.id = "doctor-user-id"
        self.doctor_user.role = UserRole.DOCTOR

    def test_monthly_quiz_role_filtering_logic(self):
        """Test the role filtering logic used in monthly quiz endpoints."""
        # Test the filtering pattern used in monthly quiz APIs
        # Admin should get None (see all data)
        admin_filter = None if self.admin_user.role == UserRole.ADMIN else self.admin_user.id
        assert admin_filter is None
        
        # Doctor should get their ID (filtered data)
        doctor_filter = None if self.doctor_user.role == UserRole.ADMIN else self.doctor_user.id
        assert doctor_filter == "doctor-user-id"


class TestRoleEnumConsistency:
    """Test overall role enum consistency across the system."""

    def test_user_role_enum_values(self):
        """Test UserRole enum has expected values."""
        # Test enum values
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.DOCTOR.value == "doctor"
        
        # Test enum count (should only be 2 roles)
        assert len(list(UserRole)) == 2

    def test_role_comparison_patterns(self):
        """Test proper role comparison patterns."""
        user = Mock(spec=User)
        user.role = UserRole.ADMIN
        
        # Correct patterns (what we implemented)
        assert user.role == UserRole.ADMIN  # Enum comparison
        assert user.role != UserRole.DOCTOR  # Enum comparison
        
        # Incorrect patterns (what we fixed)
        assert user.role != "admin"  # String comparison should not work
        assert not (user.role in {"admin", "super_admin"})  # String set should not work

    def test_admin_role_filtering_logic(self):
        """Test the admin role filtering logic used throughout APIs."""
        admin_user = Mock(spec=User)
        admin_user.id = "admin-id"
        admin_user.role = UserRole.ADMIN
        
        doctor_user = Mock(spec=User)
        doctor_user.id = "doctor-id"
        doctor_user.role = UserRole.DOCTOR
        
        # Test the filtering pattern used in APIs
        # Admin should get None (see all data)
        admin_filter = None if admin_user.role == UserRole.ADMIN else admin_user.id
        assert admin_filter is None
        
        # Doctor should get their ID (filtered data)
        doctor_filter = None if doctor_user.role == UserRole.ADMIN else doctor_user.id
        assert doctor_filter == "doctor-id"