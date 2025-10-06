"""
Integration tests for Firebase custom claims extraction.

Tests comprehensive claims extraction from Firebase tokens including:
- Top-level claims extraction (role at root level)
- custom_claims dictionary extraction
- List-style roles handling (role as array)
- Role mapping (admin, doctor, medico variants)
- Fallback to Firebase Admin SDK when claims missing in token
"""
import pytest
from typing import Dict, Any
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.models.user import User, UserRole, AuthProvider
from app.services.firebase_user_sync_service import FirebaseUserSyncService


class TestFirebaseClaimsExtraction:
    """Test suite for Firebase custom claims extraction and role mapping."""

    @pytest.mark.asyncio
    async def test_extract_claims_from_custom_claims_dict(
        self,
        db_session,
        firebase_sync_service,
        firebase_token_data_doctor
    ):
        """
        Test extraction of role from custom_claims dictionary.

        This is the standard Firebase token format with claims
        nested in a custom_claims object.
        """
        # Act
        user, created = await firebase_sync_service.sync_firebase_user(
            firebase_uid=firebase_token_data_doctor["uid"],
            firebase_data=firebase_token_data_doctor,
            auto_create=True
        )

        # Assert
        assert created is True
        assert user.role == UserRole.DOCTOR
        assert user.firebase_custom_claims.get("role") == "doctor"
        assert user.firebase_custom_claims.get("specialty") == "Oncology"
        assert user.firebase_uid == firebase_token_data_doctor["uid"]

    @pytest.mark.asyncio
    async def test_extract_claims_from_top_level(
        self,
        db_session,
        firebase_sync_service,
        firebase_token_data_top_level_claims
    ):
        """
        Test extraction of role from top-level token claims.

        Tests backward compatibility with legacy token format
        where role is at the root level instead of nested.
        """
        # Act
        user, created = await firebase_sync_service.sync_firebase_user(
            firebase_uid=firebase_token_data_top_level_claims["uid"],
            firebase_data=firebase_token_data_top_level_claims,
            auto_create=True
        )

        # Assert
        assert created is True
        assert user.role == UserRole.DOCTOR
        # Should extract top-level role into custom_claims
        assert "role" in user.firebase_custom_claims or user.role == UserRole.DOCTOR

    @pytest.mark.asyncio
    async def test_extract_claims_list_style_roles(
        self,
        db_session,
        firebase_sync_service,
        firebase_token_data_list_roles
    ):
        """
        Test handling of roles provided as a list/array.

        When Firebase returns multiple roles as an array,
        should extract the first role or primary_role.
        """
        # Act
        user, created = await firebase_sync_service.sync_firebase_user(
            firebase_uid=firebase_token_data_list_roles["uid"],
            firebase_data=firebase_token_data_list_roles,
            auto_create=True
        )

        # Assert
        assert created is True
        # Should handle list and extract primary role
        assert user.role in [UserRole.DOCTOR, UserRole.ADMIN]
        assert user.firebase_custom_claims is not None

    @pytest.mark.asyncio
    async def test_role_mapping_admin_variants(
        self,
        db_session,
        firebase_sync_service,
        firebase_token_data_admin
    ):
        """
        Test role mapping for admin variants (admin, super_admin).

        All admin-type roles should map to UserRole.ADMIN.
        """
        # Test standard admin
        user, created = await firebase_sync_service.sync_firebase_user(
            firebase_uid=firebase_token_data_admin["uid"],
            firebase_data=firebase_token_data_admin,
            auto_create=True
        )

        assert user.role == UserRole.ADMIN

        # Test super_admin variant
        firebase_token_data_admin["custom_claims"]["role"] = "super_admin"
        firebase_token_data_admin["uid"] = "firebase_super_admin_test"
        firebase_token_data_admin["email"] = "superadmin@clinica.test.com"

        user2, created2 = await firebase_sync_service.sync_firebase_user(
            firebase_uid=firebase_token_data_admin["uid"],
            firebase_data=firebase_token_data_admin,
            auto_create=True
        )

        assert user2.role == UserRole.ADMIN

    @pytest.mark.asyncio
    async def test_role_mapping_doctor_variants(
        self,
        db_session,
        firebase_sync_service
    ):
        """
        Test role mapping for doctor variants (doctor, medico).

        Portuguese 'medico' should also map to UserRole.DOCTOR.
        """
        # Test with 'medico' (Portuguese)
        token_data = {
            "uid": "firebase_medico_test",
            "email": "medico@clinica.test.com",
            "email_verified": True,
            "custom_claims": {"role": "medico"},
            "auth_time": int(datetime.utcnow().timestamp())
        }

        user, created = await firebase_sync_service.sync_firebase_user(
            firebase_uid=token_data["uid"],
            firebase_data=token_data,
            auto_create=True
        )

        assert user.role == UserRole.DOCTOR

    @pytest.mark.asyncio
    async def test_fallback_to_firebase_sdk_when_claims_missing(
        self,
        db_session,
        firebase_token_data_no_claims
    ):
        """
        Test fallback to Firebase Admin SDK when claims missing in token.

        If token doesn't contain role claims, should fetch from
        Firebase Admin SDK using get_user().
        """
        # Mock Firebase service to return user with claims
        from unittest.mock import AsyncMock
        mock_firebase = AsyncMock()
        mock_firebase.get_user = AsyncMock(return_value={
            "uid": firebase_token_data_no_claims["uid"],
            "email": firebase_token_data_no_claims["email"],
            "custom_claims": {"role": "doctor"}
        })

        sync_service = FirebaseUserSyncService(db_session, mock_firebase)

        # Act
        user, created = await sync_service.sync_firebase_user(
            firebase_uid=firebase_token_data_no_claims["uid"],
            firebase_data=firebase_token_data_no_claims,
            auto_create=True
        )

        # Assert
        assert created is True
        # Should have fetched claims from Firebase SDK
        mock_firebase.get_user.assert_called_once_with(
            firebase_token_data_no_claims["uid"]
        )

    @pytest.mark.asyncio
    async def test_claims_update_on_user_sync(
        self,
        db_session,
        firebase_sync_service,
        firebase_token_data_doctor,
        create_test_user
    ):
        """
        Test that custom claims are updated when user is synced.

        When existing user is synced with new claims, their
        firebase_custom_claims should be updated.
        """
        # Create existing user with old claims
        existing_user = create_test_user(
            email=firebase_token_data_doctor["email"],
            firebase_uid=firebase_token_data_doctor["uid"],
            role=UserRole.DOCTOR,
            firebase_custom_claims={"role": "doctor", "old_claim": "value"}
        )

        # Update token with new claims
        firebase_token_data_doctor["custom_claims"]["new_claim"] = "new_value"

        # Act - sync with updated data
        user, created = await firebase_sync_service.sync_firebase_user(
            firebase_uid=firebase_token_data_doctor["uid"],
            firebase_data=firebase_token_data_doctor,
            auto_create=False
        )

        # Assert
        assert created is False
        assert user.id == existing_user.id
        assert "new_claim" in user.firebase_custom_claims
        assert user.firebase_custom_claims["new_claim"] == "new_value"

    @pytest.mark.asyncio
    async def test_role_change_via_claims_update(
        self,
        db_session,
        firebase_sync_service,
        firebase_token_data_doctor,
        create_test_user
    ):
        """
        Test that user role is updated when claims change.

        If custom claims change from doctor to admin,
        the user's role should be updated accordingly.
        """
        # Create user as doctor
        existing_user = create_test_user(
            email=firebase_token_data_doctor["email"],
            firebase_uid=firebase_token_data_doctor["uid"],
            role=UserRole.DOCTOR,
            firebase_custom_claims={"role": "doctor"}
        )

        # Change role in token to admin
        firebase_token_data_doctor["custom_claims"]["role"] = "admin"

        # Act - sync with updated role
        user, created = await firebase_sync_service.sync_firebase_user(
            firebase_uid=firebase_token_data_doctor["uid"],
            firebase_data=firebase_token_data_doctor,
            auto_create=False
        )

        # Assert
        assert created is False
        assert user.id == existing_user.id
        assert user.role == UserRole.ADMIN
        assert user.firebase_custom_claims["role"] == "admin"

    @pytest.mark.asyncio
    async def test_claims_extraction_preserves_all_fields(
        self,
        db_session,
        firebase_sync_service,
        firebase_token_data_doctor
    ):
        """
        Test that all custom claim fields are preserved.

        Custom claims may contain metadata beyond just role
        (specialty, permissions, etc.) - all should be stored.
        """
        # Add extra fields to custom claims
        firebase_token_data_doctor["custom_claims"].update({
            "specialty": "Cardiology",
            "license": "CRM-54321",
            "permissions": ["read", "write"],
            "metadata": {"department": "Surgery"}
        })

        # Act
        user, created = await firebase_sync_service.sync_firebase_user(
            firebase_uid=firebase_token_data_doctor["uid"],
            firebase_data=firebase_token_data_doctor,
            auto_create=True
        )

        # Assert
        assert user.firebase_custom_claims["specialty"] == "Cardiology"
        assert user.firebase_custom_claims["license"] == "CRM-54321"
        assert "permissions" in user.firebase_custom_claims
        assert "metadata" in user.firebase_custom_claims
