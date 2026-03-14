"""
User to cache dict conversion tests.

Tests for the user_to_cache_dict() helper function that converts
User models to cacheable dictionaries.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from app.dependencies.auth_dependencies import user_to_cache_dict
from app.models.user import User, UserRole


from app.utils.timezone import SAO_PAULO_TZ
class TestUserToCacheDict:
    """Test suite for user_to_cache_dict() helper function."""

    def test_converts_all_required_fields(self):
        """Test that all required fields are included in output dict."""
        # Arrange
        user_id = uuid4()
        user = User(
            id=user_id,
            firebase_uid="test_firebase_uid_123",
            email="doctor@example.com",
            full_name="Dr. Test User",
            role=UserRole.DOCTOR,
            is_active=True,
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=SAO_PAULO_TZ),
            updated_at=datetime(2024, 1, 15, 14, 30, 0, tzinfo=SAO_PAULO_TZ),
            firebase_last_sign_in=datetime(2024, 1, 20, 10, 0, 0, tzinfo=SAO_PAULO_TZ),
        )

        # Act
        result = user_to_cache_dict(user)

        # Assert
        assert result["id"] == str(user_id)
        assert "firebase_uid" not in result
        assert result["email"] == "doctor@example.com"
        assert result["full_name"] == "Dr. Test User"
        assert result["role"] == "doctor"
        assert result["is_active"] is True
        assert result["created_at"] == "2024-01-01T12:00:00-03:00"
        assert result["updated_at"] == "2024-01-15T14:30:00-03:00"
        assert result["last_login"] == "2024-01-20T10:00:00-03:00"

    def test_handles_none_timestamps(self):
        """Test that None timestamps are preserved as None."""
        # Arrange
        user = User(
            id=uuid4(),
            firebase_uid="test_uid",
            email="test@example.com",
            full_name="Test User",
            role=UserRole.DOCTOR,
            is_active=True,
            created_at=None,
            updated_at=None,
            firebase_last_sign_in=None,
        )

        # Act
        result = user_to_cache_dict(user)

        # Assert
        assert result["created_at"] is None
        assert result["updated_at"] is None
        assert result["last_login"] is None

    def test_converts_admin_role_enum_to_string(self):
        """Test that admin role enum is converted to string value."""
        # Arrange
        user = User(
            id=uuid4(),
            firebase_uid="admin_uid",
            email="admin@example.com",
            full_name="Admin User",
            role=UserRole.ADMIN,
            is_active=True,
        )

        # Act
        result = user_to_cache_dict(user)

        # Assert
        assert result["role"] == "admin"
        assert isinstance(result["role"], str)

    def test_converts_doctor_role_enum_to_string(self):
        """Test that doctor role enum is converted to string value."""
        # Arrange
        user = User(
            id=uuid4(),
            firebase_uid="doctor_uid",
            email="doctor@example.com",
            full_name="Doctor User",
            role=UserRole.DOCTOR,
            is_active=True,
        )

        # Act
        result = user_to_cache_dict(user)

        # Assert
        assert result["role"] == "doctor"
        assert isinstance(result["role"], str)

    def test_handles_inactive_user(self):
        """Test that inactive user status is correctly preserved."""
        # Arrange
        user = User(
            id=uuid4(),
            firebase_uid="inactive_uid",
            email="inactive@example.com",
            full_name="Inactive User",
            role=UserRole.DOCTOR,
            is_active=False,
        )

        # Act
        result = user_to_cache_dict(user)

        # Assert
        assert result["is_active"] is False

    def test_converts_uuid_to_string(self):
        """Test that UUID id is converted to string."""
        # Arrange
        user_id = uuid4()
        user = User(
            id=user_id,
            firebase_uid="test_uid",
            email="test@example.com",
            full_name="Test User",
            role=UserRole.DOCTOR,
            is_active=True,
        )

        # Act
        result = user_to_cache_dict(user)

        # Assert
        assert result["id"] == str(user_id)
        assert isinstance(result["id"], str)

    def test_output_is_json_serializable(self):
        """Test that output dict can be JSON serialized."""
        # Arrange
        import json
        user = User(
            id=uuid4(),
            firebase_uid="test_uid",
            email="test@example.com",
            full_name="Test User",
            role=UserRole.DOCTOR,
            is_active=True,
            created_at=datetime(2024, 1, 1, tzinfo=SAO_PAULO_TZ),
        )

        # Act
        result = user_to_cache_dict(user)

        # Assert - should not raise exception
        json_str = json.dumps(result)
        assert isinstance(json_str, str)
        assert len(json_str) > 0

    def test_handles_role_without_value_attribute(self):
        """Test fallback when role doesn't have .value attribute."""
        # Arrange
        user = User(
            id=uuid4(),
            firebase_uid="test_uid",
            email="test@example.com",
            full_name="Test User",
            role=UserRole.DOCTOR,
            is_active=True,
        )
        # Simulate role without .value by mocking
        user.role = "doctor"  # String instead of enum

        # Act
        result = user_to_cache_dict(user)

        # Assert
        assert result["role"] == "doctor"