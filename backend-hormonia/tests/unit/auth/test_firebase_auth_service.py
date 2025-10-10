"""Unit tests for Firebase Authentication Service

Tests Firebase JWT token validation, user management, and custom claims.
Comprehensive coverage including error scenarios and edge cases.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, Any, Optional
import firebase_admin
from firebase_admin import auth, credentials
from fastapi import HTTPException, status

from app.services.firebase_auth_service import (
    FirebaseAuthService,
    get_firebase_auth_service,
    _firebase_service_instance
)


class TestFirebaseAuthServiceInitialization:
    """Test Firebase Auth Service initialization and configuration."""

    def setup_method(self):
        """Reset Firebase state before each test."""
        # Reset class variables to ensure clean state
        FirebaseAuthService._initialized = False
        FirebaseAuthService._app = None

        # Reset singleton instance
        global _firebase_service_instance
        _firebase_service_instance = None

    @patch('app.services.firebase_auth_service.firebase_admin')
    @patch('app.services.firebase_auth_service.credentials')
    def test_successful_initialization(self, mock_credentials, mock_firebase_admin):
        """Test successful Firebase Admin SDK initialization."""
        # Arrange
        mock_firebase_admin._apps = []
        mock_firebase_admin.initialize_app.return_value = Mock()
        mock_cred = Mock()
        mock_credentials.Certificate.return_value = mock_cred

        project_id = "test-project"
        private_key = "-----BEGIN PRIVATE KEY-----\\ntest_key\\n-----END PRIVATE KEY-----"
        client_email = "test@test-project.iam.gserviceaccount.com"

        # Act
        service = FirebaseAuthService(project_id, private_key, client_email)

        # Assert
        assert service.project_id == project_id
        assert service.private_key == private_key
        assert service.client_email == client_email
        assert FirebaseAuthService._initialized is True

        # Verify credentials were created with proper format
        expected_cred_dict = {
            "type": "service_account",
            "project_id": project_id,
            "private_key": "-----BEGIN PRIVATE KEY-----\ntest_key\n-----END PRIVATE KEY-----",
            "client_email": client_email,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        mock_credentials.Certificate.assert_called_once_with(expected_cred_dict)
        mock_firebase_admin.initialize_app.assert_called_once_with(mock_cred)

    @patch('app.services.firebase_auth_service.firebase_admin')
    @patch('app.services.firebase_auth_service.credentials')
    def test_existing_app_initialization(self, mock_credentials, mock_firebase_admin):
        """Test initialization when Firebase app already exists."""
        # Arrange
        mock_existing_app = Mock()
        mock_firebase_admin._apps = [mock_existing_app]
        mock_firebase_admin.get_app.return_value = mock_existing_app

        # Act
        service = FirebaseAuthService("test-project", "test-key", "test@example.com")

        # Assert
        assert FirebaseAuthService._initialized is True
        mock_firebase_admin.get_app.assert_called_once()
        mock_firebase_admin.initialize_app.assert_not_called()

    @patch('app.services.firebase_auth_service.firebase_admin')
    @patch('app.services.firebase_auth_service.credentials')
    def test_initialization_failure(self, mock_credentials, mock_firebase_admin):
        """Test Firebase initialization failure handling."""
        # Arrange
        mock_firebase_admin._apps = []
        mock_credentials.Certificate.side_effect = Exception("Invalid credentials")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Firebase initialization failed"):
            FirebaseAuthService("test-project", "invalid-key", "test@example.com")

    def test_singleton_instance_creation(self):
        """Test singleton pattern for Firebase Auth Service."""
        with patch('app.services.firebase_auth_service.FirebaseAuthService') as mock_service:
            mock_instance = Mock()
            mock_service.return_value = mock_instance

            # First call creates instance
            service1 = get_firebase_auth_service("project", "key", "email")

            # Second call returns same instance
            service2 = get_firebase_auth_service("project", "key", "email")

            assert service1 == service2
            mock_service.assert_called_once_with(
                project_id="project",
                private_key="key",
                client_email="email"
            )


class TestTokenVerification:
    """Test Firebase JWT token verification functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.service = Mock(spec=FirebaseAuthService)
        self.service.verify_token = FirebaseAuthService.verify_token.__get__(self.service)

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_valid_token_verification(self, mock_auth):
        """Test successful token verification with user data extraction."""
        # Arrange
        token = "valid.jwt.token"
        decoded_token = {
            "uid": "user123",
            "email": "test@example.com",
            "email_verified": True,
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
            "auth_time": 1234567890,
            "exp": 1234567890 + 3600,
            "iss": "firebase",
            "aud": "test-project",
            "role": "admin",  # Custom claim
            "permissions": ["read", "write"],  # Custom claim
            "iat": 1234567890,
            "sub": "user123"
        }
        mock_auth.verify_id_token.return_value = decoded_token

        # Act
        result = await self.service.verify_token(token)

        # Assert
        mock_auth.verify_id_token.assert_called_once_with(token, check_revoked=True)

        expected_result = {
            "uid": "user123",
            "email": "test@example.com",
            "email_verified": True,
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
            "custom_claims": {
                "role": "admin",
                "permissions": ["read", "write"]
            },
            "auth_time": 1234567890,
            "exp": 1234567890 + 3600,
        }
        assert result == expected_result

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_token_verification_with_minimal_claims(self, mock_auth):
        """Test token verification with minimal required claims."""
        # Arrange
        token = "minimal.jwt.token"
        decoded_token = {
            "uid": "user456",
            "iss": "firebase",
            "aud": "test-project",
            "iat": 1234567890,
            "exp": 1234567890 + 3600,
            "sub": "user456"
        }
        mock_auth.verify_id_token.return_value = decoded_token

        # Act
        result = await self.service.verify_token(token)

        # Assert
        expected_result = {
            "uid": "user456",
            "email": None,
            "email_verified": False,
            "name": None,
            "picture": None,
            "custom_claims": {},
            "auth_time": None,
            "exp": 1234567890 + 3600,
        }
        assert result == expected_result

    @pytest.mark.asyncio
    async def test_empty_token_validation(self):
        """Test validation of empty or None token."""
        # Test None token
        with pytest.raises(HTTPException) as exc_info:
            await self.service.verify_token(None)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Invalid token format"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

        # Test empty string token
        with pytest.raises(HTTPException) as exc_info:
            await self.service.verify_token("")

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Invalid token format"

    @pytest.mark.asyncio
    async def test_non_string_token_validation(self):
        """Test validation of non-string token."""
        with pytest.raises(HTTPException) as exc_info:
            await self.service.verify_token(123)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Invalid token format"

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_expired_token_error(self, mock_auth):
        """Test handling of expired token error."""
        # Arrange
        token = "expired.jwt.token"
        mock_auth.verify_id_token.side_effect = auth.ExpiredIdTokenError("Token expired")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await self.service.verify_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Token has expired"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_revoked_token_error(self, mock_auth):
        """Test handling of revoked token error."""
        # Arrange
        token = "revoked.jwt.token"
        mock_auth.verify_id_token.side_effect = auth.RevokedIdTokenError("Token revoked")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await self.service.verify_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Token has been revoked"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_invalid_token_error(self, mock_auth):
        """Test handling of invalid token error."""
        # Arrange
        token = "invalid.jwt.token"
        mock_auth.verify_id_token.side_effect = auth.InvalidIdTokenError("Invalid token")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await self.service.verify_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Invalid authentication token"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_user_disabled_error(self, mock_auth):
        """Test handling of disabled user error."""
        # Arrange
        token = "disabled_user.jwt.token"
        mock_auth.verify_id_token.side_effect = auth.UserDisabledError("User disabled")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await self.service.verify_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "User account has been disabled"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_unexpected_error_during_verification(self, mock_auth):
        """Test handling of unexpected errors during token verification."""
        # Arrange
        token = "valid.jwt.token"
        mock_auth.verify_id_token.side_effect = Exception("Unexpected error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await self.service.verify_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Could not validate credentials"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


class TestUserRetrieval:
    """Test Firebase user data retrieval functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.service = Mock(spec=FirebaseAuthService)
        self.service.get_user = FirebaseAuthService.get_user.__get__(self.service)

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_successful_user_retrieval(self, mock_auth):
        """Test successful user data retrieval from Firebase."""
        # Arrange
        uid = "user123"
        mock_user_record = Mock()
        mock_user_record.uid = uid
        mock_user_record.email = "test@example.com"
        mock_user_record.email_verified = True
        mock_user_record.display_name = "Test User"
        mock_user_record.photo_url = "https://example.com/photo.jpg"
        mock_user_record.disabled = False
        mock_user_record.custom_claims = {"role": "admin", "permissions": ["read", "write"]}

        # Mock provider data
        mock_provider = Mock()
        mock_provider.provider_id = "google.com"
        mock_provider.uid = "google_uid_123"
        mock_provider.email = "test@example.com"
        mock_user_record.provider_data = [mock_provider]

        # Mock metadata
        mock_metadata = Mock()
        mock_metadata.creation_timestamp = 1234567890
        mock_metadata.last_sign_in_timestamp = 1234567900
        mock_user_record.user_metadata = mock_metadata

        mock_auth.get_user.return_value = mock_user_record

        # Act
        result = await self.service.get_user(uid)

        # Assert
        mock_auth.get_user.assert_called_once_with(uid)

        expected_result = {
            "uid": uid,
            "email": "test@example.com",
            "email_verified": True,
            "display_name": "Test User",
            "photo_url": "https://example.com/photo.jpg",
            "disabled": False,
            "custom_claims": {"role": "admin", "permissions": ["read", "write"]},
            "provider_data": [
                {
                    "provider_id": "google.com",
                    "uid": "google_uid_123",
                    "email": "test@example.com",
                }
            ],
            "created_at": 1234567890,
            "last_sign_in": 1234567900,
        }
        assert result == expected_result

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_user_retrieval_with_no_custom_claims(self, mock_auth):
        """Test user retrieval when user has no custom claims."""
        # Arrange
        uid = "user456"
        mock_user_record = Mock()
        mock_user_record.uid = uid
        mock_user_record.email = "simple@example.com"
        mock_user_record.email_verified = False
        mock_user_record.display_name = None
        mock_user_record.photo_url = None
        mock_user_record.disabled = False
        mock_user_record.custom_claims = None  # No custom claims
        mock_user_record.provider_data = []

        mock_metadata = Mock()
        mock_metadata.creation_timestamp = 1234567890
        mock_metadata.last_sign_in_timestamp = None
        mock_user_record.user_metadata = mock_metadata

        mock_auth.get_user.return_value = mock_user_record

        # Act
        result = await self.service.get_user(uid)

        # Assert
        expected_result = {
            "uid": uid,
            "email": "simple@example.com",
            "email_verified": False,
            "display_name": None,
            "photo_url": None,
            "disabled": False,
            "custom_claims": {},  # Should default to empty dict
            "provider_data": [],
            "created_at": 1234567890,
            "last_sign_in": None,
        }
        assert result == expected_result

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_user_not_found(self, mock_auth):
        """Test handling when user is not found."""
        # Arrange
        uid = "nonexistent_user"
        mock_auth.get_user.side_effect = auth.UserNotFoundError("User not found")

        # Act
        result = await self.service.get_user(uid)

        # Assert
        assert result is None
        mock_auth.get_user.assert_called_once_with(uid)

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_user_retrieval_error(self, mock_auth):
        """Test handling of unexpected errors during user retrieval."""
        # Arrange
        uid = "user123"
        mock_auth.get_user.side_effect = Exception("Firebase service error")

        # Act
        result = await self.service.get_user(uid)

        # Assert
        assert result is None
        mock_auth.get_user.assert_called_once_with(uid)


class TestCustomClaimsManagement:
    """Test Firebase custom claims management functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.service = Mock(spec=FirebaseAuthService)
        self.service.set_custom_claims = FirebaseAuthService.set_custom_claims.__get__(self.service)

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_successful_custom_claims_setting(self, mock_auth):
        """Test successful setting of custom claims for a user."""
        # Arrange
        uid = "user123"
        claims = {"role": "admin", "permissions": ["read", "write", "delete"]}
        mock_auth.set_custom_user_claims.return_value = None

        # Act
        result = await self.service.set_custom_claims(uid, claims)

        # Assert
        assert result is True
        mock_auth.set_custom_user_claims.assert_called_once_with(uid, claims)

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_custom_claims_setting_with_empty_claims(self, mock_auth):
        """Test setting empty custom claims (clearing claims)."""
        # Arrange
        uid = "user456"
        claims = {}
        mock_auth.set_custom_user_claims.return_value = None

        # Act
        result = await self.service.set_custom_claims(uid, claims)

        # Assert
        assert result is True
        mock_auth.set_custom_user_claims.assert_called_once_with(uid, claims)

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_custom_claims_setting_error(self, mock_auth):
        """Test handling of errors during custom claims setting."""
        # Arrange
        uid = "user123"
        claims = {"role": "admin"}
        mock_auth.set_custom_user_claims.side_effect = Exception("Firebase error")

        # Act
        result = await self.service.set_custom_claims(uid, claims)

        # Assert
        assert result is False
        mock_auth.set_custom_user_claims.assert_called_once_with(uid, claims)

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_custom_claims_with_complex_data(self, mock_auth):
        """Test setting complex custom claims data."""
        # Arrange
        uid = "user789"
        claims = {
            "role": "manager",
            "permissions": ["read", "write"],
            "department": "engineering",
            "level": 5,
            "features": {
                "beta_access": True,
                "advanced_features": ["feature1", "feature2"]
            }
        }
        mock_auth.set_custom_user_claims.return_value = None

        # Act
        result = await self.service.set_custom_claims(uid, claims)

        # Assert
        assert result is True
        mock_auth.set_custom_user_claims.assert_called_once_with(uid, claims)


class TestTokenRevocation:
    """Test Firebase token revocation functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.service = Mock(spec=FirebaseAuthService)
        self.service.revoke_refresh_tokens = FirebaseAuthService.revoke_refresh_tokens.__get__(self.service)

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_successful_token_revocation(self, mock_auth):
        """Test successful revocation of refresh tokens."""
        # Arrange
        uid = "user123"
        mock_auth.revoke_refresh_tokens.return_value = None

        # Act
        result = await self.service.revoke_refresh_tokens(uid)

        # Assert
        assert result is True
        mock_auth.revoke_refresh_tokens.assert_called_once_with(uid)

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_token_revocation_error(self, mock_auth):
        """Test handling of errors during token revocation."""
        # Arrange
        uid = "user456"
        mock_auth.revoke_refresh_tokens.side_effect = Exception("Firebase error")

        # Act
        result = await self.service.revoke_refresh_tokens(uid)

        # Assert
        assert result is False
        mock_auth.revoke_refresh_tokens.assert_called_once_with(uid)

    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_token_revocation_for_nonexistent_user(self, mock_auth):
        """Test token revocation for a non-existent user."""
        # Arrange
        uid = "nonexistent_user"
        mock_auth.revoke_refresh_tokens.side_effect = auth.UserNotFoundError("User not found")

        # Act
        result = await self.service.revoke_refresh_tokens(uid)

        # Assert
        assert result is False
        mock_auth.revoke_refresh_tokens.assert_called_once_with(uid)


class TestIntegrationScenarios:
    """Test integration scenarios and edge cases."""

    def setup_method(self):
        """Setup test fixtures."""
        FirebaseAuthService._initialized = False
        FirebaseAuthService._app = None

        global _firebase_service_instance
        _firebase_service_instance = None

    @patch('app.services.firebase_auth_service.firebase_admin')
    @patch('app.services.firebase_auth_service.credentials')
    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_full_workflow_token_verification_and_user_retrieval(
        self, mock_auth, mock_credentials, mock_firebase_admin
    ):
        """Test complete workflow: initialize service, verify token, get user data."""
        # Arrange - Initialize service
        mock_firebase_admin._apps = []
        mock_firebase_admin.initialize_app.return_value = Mock()
        mock_cred = Mock()
        mock_credentials.Certificate.return_value = mock_cred

        service = FirebaseAuthService(
            "test-project",
            "test-key",
            "test@example.com"
        )

        # Arrange - Token verification
        token = "valid.jwt.token"
        decoded_token = {
            "uid": "user123",
            "email": "test@example.com",
            "email_verified": True,
            "name": "Test User",
            "role": "admin",
            "iss": "firebase",
            "aud": "test-project",
            "iat": 1234567890,
            "exp": 1234567890 + 3600,
            "sub": "user123"
        }
        mock_auth.verify_id_token.return_value = decoded_token

        # Arrange - User retrieval
        mock_user_record = Mock()
        mock_user_record.uid = "user123"
        mock_user_record.email = "test@example.com"
        mock_user_record.email_verified = True
        mock_user_record.display_name = "Test User"
        mock_user_record.custom_claims = {"role": "admin"}
        mock_user_record.provider_data = []
        mock_metadata = Mock()
        mock_metadata.creation_timestamp = 1234567890
        mock_metadata.last_sign_in_timestamp = 1234567900
        mock_user_record.user_metadata = mock_metadata
        mock_auth.get_user.return_value = mock_user_record

        # Act - Verify token
        token_result = await service.verify_token(token)

        # Act - Get user data
        user_result = await service.get_user(token_result["uid"])

        # Assert
        assert token_result["uid"] == "user123"
        assert token_result["email"] == "test@example.com"
        assert token_result["custom_claims"]["role"] == "admin"

        assert user_result["uid"] == "user123"
        assert user_result["email"] == "test@example.com"
        assert user_result["custom_claims"]["role"] == "admin"

    @patch('app.services.firebase_auth_service.firebase_admin')
    @patch('app.services.firebase_auth_service.credentials')
    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_security_workflow_revoke_tokens_and_verify_failure(
        self, mock_auth, mock_credentials, mock_firebase_admin
    ):
        """Test security workflow: revoke tokens and ensure verification fails."""
        # Arrange - Initialize service
        mock_firebase_admin._apps = []
        mock_firebase_admin.initialize_app.return_value = Mock()
        mock_cred = Mock()
        mock_credentials.Certificate.return_value = mock_cred

        service = FirebaseAuthService(
            "test-project",
            "test-key",
            "test@example.com"
        )

        uid = "user123"
        token = "revoked.jwt.token"

        # Act - Revoke tokens
        mock_auth.revoke_refresh_tokens.return_value = None
        revoke_result = await service.revoke_refresh_tokens(uid)

        # Act - Try to verify revoked token
        mock_auth.verify_id_token.side_effect = auth.RevokedIdTokenError("Token revoked")

        # Assert
        assert revoke_result is True

        with pytest.raises(HTTPException) as exc_info:
            await service.verify_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Token has been revoked"

    @patch('app.services.firebase_auth_service.firebase_admin')
    @patch('app.services.firebase_auth_service.credentials')
    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_admin_workflow_set_claims_and_verify_updated_token(
        self, mock_auth, mock_credentials, mock_firebase_admin
    ):
        """Test admin workflow: set custom claims and verify updated token."""
        # Arrange - Initialize service
        mock_firebase_admin._apps = []
        mock_firebase_admin.initialize_app.return_value = Mock()
        mock_cred = Mock()
        mock_credentials.Certificate.return_value = mock_cred

        service = FirebaseAuthService(
            "test-project",
            "test-key",
            "test@example.com"
        )

        uid = "user123"
        new_claims = {"role": "super_admin", "permissions": ["all"]}

        # Act - Set custom claims
        mock_auth.set_custom_user_claims.return_value = None
        claims_result = await service.set_custom_claims(uid, new_claims)

        # Act - Verify token with new claims
        token = "updated.jwt.token"
        decoded_token = {
            "uid": uid,
            "email": "admin@example.com",
            "role": "super_admin",
            "permissions": ["all"],
            "iss": "firebase",
            "aud": "test-project",
            "iat": 1234567890,
            "exp": 1234567890 + 3600,
            "sub": uid
        }
        mock_auth.verify_id_token.return_value = decoded_token

        token_result = await service.verify_token(token)

        # Assert
        assert claims_result is True
        assert token_result["uid"] == uid
        assert token_result["custom_claims"]["role"] == "super_admin"
        assert token_result["custom_claims"]["permissions"] == ["all"]

    def test_multiple_service_instances_singleton_behavior(self):
        """Test that multiple service instance requests return the same singleton."""
        with patch('app.services.firebase_auth_service.FirebaseAuthService') as mock_service:
            mock_instance = Mock()
            mock_service.return_value = mock_instance

            # Create multiple instances with same parameters
            service1 = get_firebase_auth_service("project", "key", "email")
            service2 = get_firebase_auth_service("project", "key", "email")
            service3 = get_firebase_auth_service("different", "params", "here")

            # Should all return the same singleton instance
            assert service1 == service2 == service3

            # Service should only be instantiated once
            mock_service.assert_called_once()


class TestLoggingAndErrorMessages:
    """Test logging behavior and error message consistency."""

    def setup_method(self):
        """Setup test fixtures."""
        self.service = Mock(spec=FirebaseAuthService)
        self.service.verify_token = FirebaseAuthService.verify_token.__get__(self.service)
        self.service.get_user = FirebaseAuthService.get_user.__get__(self.service)
        self.service.set_custom_claims = FirebaseAuthService.set_custom_claims.__get__(self.service)
        self.service.revoke_refresh_tokens = FirebaseAuthService.revoke_refresh_tokens.__get__(self.service)

    @patch('app.services.firebase_auth_service.logger')
    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_logging_during_successful_operations(self, mock_auth, mock_logger):
        """Test that successful operations generate appropriate log messages."""
        # Test successful token verification
        token = "valid.jwt.token"
        decoded_token = {
            "uid": "user123",
            "email": "test@example.com",
            "iss": "firebase",
            "aud": "test-project",
            "iat": 1234567890,
            "exp": 1234567890 + 3600,
            "sub": "user123"
        }
        mock_auth.verify_id_token.return_value = decoded_token

        await self.service.verify_token(token)

        mock_logger.debug.assert_called_with(
            "Successfully verified token for user: test@example.com with custom claims: []"
        )

    @patch('app.services.firebase_auth_service.logger')
    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_logging_during_error_conditions(self, mock_auth, mock_logger):
        """Test that error conditions generate appropriate log messages."""
        # Test invalid token logging
        token = "invalid.jwt.token"
        mock_auth.verify_id_token.side_effect = auth.InvalidIdTokenError("Invalid")

        with pytest.raises(HTTPException):
            await self.service.verify_token(token)

        mock_logger.warning.assert_called_with("Invalid token: Invalid")

    @patch('app.services.firebase_auth_service.logger')
    @patch('app.services.firebase_auth_service.auth')
    @pytest.mark.asyncio
    async def test_logging_user_operations(self, mock_auth, mock_logger):
        """Test logging for user management operations."""
        # Test successful custom claims setting
        uid = "user123"
        claims = {"role": "admin"}
        mock_auth.set_custom_user_claims.return_value = None

        await self.service.set_custom_claims(uid, claims)

        mock_logger.info.assert_called_with(
            f"Set custom claims for user {uid}: {claims}"
        )

        # Test successful token revocation
        mock_auth.revoke_refresh_tokens.return_value = None

        await self.service.revoke_refresh_tokens(uid)

        mock_logger.info.assert_called_with(f"Revoked refresh tokens for user: {uid}")