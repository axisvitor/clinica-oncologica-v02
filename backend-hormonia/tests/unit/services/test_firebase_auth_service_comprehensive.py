"""
Comprehensive unit tests for Firebase Authentication Service

Tests all public methods, error handling, edge cases, and security scenarios
with focus on achieving 90%+ code coverage.
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock, call
from firebase_admin import auth as firebase_auth
from firebase_admin import exceptions
from fastapi import HTTPException, status
from typing import Dict, Any

# Import the service - adjust path based on actual structure
try:
    from app.services.firebase_auth_service import FirebaseAuthService, get_firebase_auth_service
except ImportError:
    # Fallback for different project structures
    from services.firebase_auth_service import FirebaseAuthService, get_firebase_auth_service


@pytest.fixture
def mock_firebase_app():
    """Mock Firebase app for testing."""
    with patch('firebase_admin.initialize_app') as mock_init, \
         patch('firebase_admin.get_app') as mock_get, \
         patch('firebase_admin._apps', {}):
        mock_app = Mock()
        mock_init.return_value = mock_app
        mock_get.return_value = mock_app
        yield mock_app


@pytest.fixture
def firebase_service(mock_firebase_app):
    """Fixture for Firebase auth service with mock credentials"""
    with patch('firebase_admin.credentials.Certificate') as mock_cert:
        mock_cert.return_value = Mock()
        service = FirebaseAuthService(
            project_id="test-project",
            private_key="-----BEGIN PRIVATE KEY-----\nMOCK_KEY\n-----END PRIVATE KEY-----",
            client_email="test@test.iam.gserviceaccount.com"
        )
        return service


@pytest.fixture
def mock_credentials():
    """Mock Firebase credentials for testing."""
    return {
        "project_id": "test-project",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMOCK_KEY\n-----END PRIVATE KEY-----",
        "client_email": "test@test.iam.gserviceaccount.com"
    }


@pytest.fixture
def sample_token_data():
    """Sample Firebase token data for testing."""
    return {
        'uid': 'test-uid-123',
        'email': 'test@example.com',
        'email_verified': True,
        'name': 'Test User',
        'picture': 'https://example.com/photo.jpg',
        'auth_time': 1234567890,
        'exp': 1234571490,
        'iss': 'firebase-issuer',
        'aud': 'test-project'
    }


class TestFirebaseAuthServiceInitialization:
    """Test Firebase service initialization and setup."""

    def test_service_initialization(self, mock_credentials):
        """Test Firebase service initialization."""
        with patch('firebase_admin.initialize_app') as mock_init, \
             patch('firebase_admin.credentials.Certificate') as mock_cert, \
             patch('firebase_admin._apps', {}):

            mock_cert.return_value = Mock()
            mock_init.return_value = Mock()

            service = FirebaseAuthService(**mock_credentials)

            assert service.project_id == "test-project"
            assert service.private_key == mock_credentials["private_key"]
            assert service.client_email == mock_credentials["client_email"]

            # Verify Firebase was initialized
            mock_cert.assert_called_once()
            mock_init.assert_called_once()

    def test_service_initialization_existing_app(self, mock_credentials):
        """Test Firebase service initialization with existing app."""
        with patch('firebase_admin.initialize_app') as mock_init, \
             patch('firebase_admin.get_app') as mock_get, \
             patch('firebase_admin._apps', {'default': Mock()}), \
             patch('firebase_admin.credentials.Certificate') as mock_cert:

            mock_cert.return_value = Mock()
            mock_get.return_value = Mock()

            service = FirebaseAuthService(**mock_credentials)

            # Should use existing app, not create new one
            mock_init.assert_not_called()
            mock_get.assert_called_once()

    def test_initialization_failure(self, mock_credentials):
        """Test Firebase initialization failure handling."""
        with patch('firebase_admin.credentials.Certificate') as mock_cert, \
             patch('firebase_admin._apps', {}), \
             patch('firebase_admin.initialize_app') as mock_init:

            mock_cert.side_effect = Exception("Invalid credentials")

            with pytest.raises(RuntimeError, match="Firebase initialization failed"):
                FirebaseAuthService(**mock_credentials)

    def test_private_key_formatting(self, mock_credentials):
        """Test private key formatting with escaped newlines."""
        mock_credentials["private_key"] = "-----BEGIN PRIVATE KEY-----\\nMOCK_KEY\\n-----END PRIVATE KEY-----"

        with patch('firebase_admin.initialize_app') as mock_init, \
             patch('firebase_admin.credentials.Certificate') as mock_cert, \
             patch('firebase_admin._apps', {}):

            mock_cert.return_value = Mock()
            mock_init.return_value = Mock()

            service = FirebaseAuthService(**mock_credentials)

            # Verify the certificate was called with formatted key
            call_args = mock_cert.call_args[0][0]
            assert "\n" in call_args["private_key"]
            assert "\\n" not in call_args["private_key"]

    def test_credentials_dict_structure(self, mock_credentials):
        """Test that credentials dictionary has correct structure."""
        with patch('firebase_admin.initialize_app') as mock_init, \
             patch('firebase_admin.credentials.Certificate') as mock_cert, \
             patch('firebase_admin._apps', {}):

            mock_cert.return_value = Mock()
            mock_init.return_value = Mock()

            service = FirebaseAuthService(**mock_credentials)

            # Verify the certificate was called with complete credentials
            call_args = mock_cert.call_args[0][0]
            assert call_args["type"] == "service_account"
            assert call_args["project_id"] == "test-project"
            assert call_args["client_email"] == "test@test.iam.gserviceaccount.com"
            assert call_args["token_uri"] == "https://oauth2.googleapis.com/token"


class TestFirebaseAuthServiceTokenVerification:
    """Test token verification functionality."""

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_valid_token(self, mock_verify, firebase_service, sample_token_data):
        """Test valid token verification returns user data"""
        # Arrange
        mock_verify.return_value = sample_token_data

        # Act
        result = await firebase_service.verify_token('valid-token')

        # Assert
        assert result['uid'] == 'test-uid-123'
        assert result['email'] == 'test@example.com'
        assert result['email_verified'] is True
        assert result['name'] == 'Test User'
        assert result['picture'] == 'https://example.com/photo.jpg'
        assert result['auth_time'] == 1234567890
        assert result['exp'] == 1234571490
        assert result['custom_claims'] == {}  # No custom claims in this token
        mock_verify.assert_called_once_with('valid-token', check_revoked=True)

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_token_with_custom_claims(self, mock_verify, firebase_service):
        """Test token verification with custom claims"""
        # Arrange
        mock_verify.return_value = {
            'uid': 'admin-uid-789',
            'email': 'admin@example.com',
            'email_verified': True,
            'name': 'Admin User',
            'admin': True,
            'role': 'super_admin',
            'permissions': ['read', 'write', 'admin'],
            # Reserved claims (should be filtered out of custom_claims)
            'iss': 'firebase-issuer',
            'aud': 'test-project',
            'auth_time': 1234567890,
            'exp': 1234571490,
            'firebase': {'identities': {}},
            'sub': 'admin-uid-789',
            'iat': 1234567890
        }

        # Act
        result = await firebase_service.verify_token('admin-token')

        # Assert
        assert result['uid'] == 'admin-uid-789'
        assert result['email'] == 'admin@example.com'
        assert result['custom_claims']['admin'] is True
        assert result['custom_claims']['role'] == 'super_admin'
        assert result['custom_claims']['permissions'] == ['read', 'write', 'admin']

        # Reserved claims should not be in custom_claims
        assert 'iss' not in result['custom_claims']
        assert 'aud' not in result['custom_claims']
        assert 'firebase' not in result['custom_claims']
        assert 'sub' not in result['custom_claims']

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_expired_token(self, mock_verify, firebase_service):
        """Test expired token raises appropriate HTTPException"""
        # Arrange
        mock_verify.side_effect = firebase_auth.ExpiredIdTokenError('Token expired')

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await firebase_service.verify_token('expired-token')

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'expired' in exc_info.value.detail.lower()

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_invalid_token(self, mock_verify, firebase_service):
        """Test invalid token raises appropriate HTTPException"""
        # Arrange
        mock_verify.side_effect = firebase_auth.InvalidIdTokenError('Invalid token')

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await firebase_service.verify_token('invalid-token')

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'invalid' in exc_info.value.detail.lower()

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_revoked_token(self, mock_verify, firebase_service):
        """Test revoked token raises appropriate HTTPException"""
        # Arrange
        mock_verify.side_effect = firebase_auth.RevokedIdTokenError('Token revoked')

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await firebase_service.verify_token('revoked-token')

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'revoked' in exc_info.value.detail.lower()

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_disabled_user(self, mock_verify, firebase_service):
        """Test disabled user token raises appropriate HTTPException"""
        # Arrange
        mock_verify.side_effect = firebase_auth.UserDisabledError('User disabled')

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await firebase_service.verify_token('disabled-user-token')

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'disabled' in exc_info.value.detail.lower()

    async def test_empty_token_rejected(self, firebase_service):
        """Test empty token is rejected without Firebase call"""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await firebase_service.verify_token('')

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'invalid token format' in exc_info.value.detail.lower()

    async def test_none_token_rejected(self, firebase_service):
        """Test None token is rejected without Firebase call"""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await firebase_service.verify_token(None)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'invalid token format' in exc_info.value.detail.lower()

    async def test_non_string_token_rejected(self, firebase_service):
        """Test non-string token is rejected"""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await firebase_service.verify_token(123)  # Integer instead of string

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'invalid token format' in exc_info.value.detail.lower()

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_malformed_token(self, mock_verify, firebase_service):
        """Test handling of malformed token format"""
        # Arrange
        mock_verify.side_effect = ValueError('Malformed token')

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await firebase_service.verify_token('malformed.token.format')

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'could not validate credentials' in exc_info.value.detail.lower()

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_generic_exception(self, mock_verify, firebase_service):
        """Test handling of generic exceptions during verification"""
        # Arrange
        mock_verify.side_effect = Exception('Unexpected error')

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await firebase_service.verify_token('token-with-error')

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'could not validate credentials' in exc_info.value.detail.lower()

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_token_unverified_email(self, mock_verify, firebase_service):
        """Test token with unverified email is handled correctly"""
        # Arrange
        mock_verify.return_value = {
            'uid': 'test-uid-456',
            'email': 'unverified@example.com',
            'email_verified': False
        }

        # Act
        result = await firebase_service.verify_token('unverified-email-token')

        # Assert
        assert result['email_verified'] is False
        # Service should still return user data; verification check is handled at route level
        assert result['uid'] == 'test-uid-456'

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_token_network_error(self, mock_verify, firebase_service):
        """Test handling of network errors during verification"""
        # Arrange
        mock_verify.side_effect = Exception('Network error: Connection timeout')

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await firebase_service.verify_token('token-with-network-issue')

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


class TestFirebaseAuthServiceUserOperations:
    """Test user-related operations in Firebase Auth Service"""

    @patch('firebase_admin.auth.get_user')
    async def test_get_user_success(self, mock_get_user, firebase_service):
        """Test successful user retrieval"""
        # Arrange
        mock_user_record = Mock()
        mock_user_record.uid = "test-uid-123"
        mock_user_record.email = "test@example.com"
        mock_user_record.email_verified = True
        mock_user_record.display_name = "Test User"
        mock_user_record.photo_url = "https://example.com/photo.jpg"
        mock_user_record.disabled = False
        mock_user_record.custom_claims = {"role": "doctor"}
        mock_user_record.provider_data = [
            Mock(provider_id="password", uid="test@example.com", email="test@example.com")
        ]
        mock_user_record.user_metadata = Mock(
            creation_timestamp=1234567890,
            last_sign_in_timestamp=1234567900
        )
        mock_get_user.return_value = mock_user_record

        # Act
        result = await firebase_service.get_user("test-uid-123")

        # Assert
        assert result is not None
        assert result["uid"] == "test-uid-123"
        assert result["email"] == "test@example.com"
        assert result["email_verified"] is True
        assert result["display_name"] == "Test User"
        assert result["custom_claims"] == {"role": "doctor"}
        assert len(result["provider_data"]) == 1
        assert result["created_at"] == 1234567890
        assert result["last_sign_in"] == 1234567900
        mock_get_user.assert_called_once_with("test-uid-123")

    @patch('firebase_admin.auth.get_user')
    async def test_get_user_with_null_values(self, mock_get_user, firebase_service):
        """Test user retrieval with null/empty values"""
        # Arrange
        mock_user_record = Mock()
        mock_user_record.uid = "test-uid-456"
        mock_user_record.email = "test2@example.com"
        mock_user_record.email_verified = False
        mock_user_record.display_name = None
        mock_user_record.photo_url = None
        mock_user_record.disabled = False
        mock_user_record.custom_claims = None
        mock_user_record.provider_data = []
        mock_user_record.user_metadata = Mock(
            creation_timestamp=None,
            last_sign_in_timestamp=None
        )
        mock_get_user.return_value = mock_user_record

        # Act
        result = await firebase_service.get_user("test-uid-456")

        # Assert
        assert result is not None
        assert result["uid"] == "test-uid-456"
        assert result["display_name"] is None
        assert result["photo_url"] is None
        assert result["custom_claims"] == {}
        assert result["provider_data"] == []
        assert result["created_at"] is None
        assert result["last_sign_in"] is None

    @patch('firebase_admin.auth.get_user')
    async def test_get_user_not_found(self, mock_get_user, firebase_service):
        """Test user not found scenario"""
        # Arrange
        mock_get_user.side_effect = firebase_auth.UserNotFoundError("User not found")

        # Act
        result = await firebase_service.get_user("nonexistent-uid")

        # Assert
        assert result is None
        mock_get_user.assert_called_once_with("nonexistent-uid")

    @patch('firebase_admin.auth.get_user')
    async def test_get_user_error(self, mock_get_user, firebase_service):
        """Test error during user retrieval"""
        # Arrange
        mock_get_user.side_effect = Exception("Firebase error")

        # Act
        result = await firebase_service.get_user("error-uid")

        # Assert
        assert result is None
        mock_get_user.assert_called_once_with("error-uid")

    @patch('firebase_admin.auth.set_custom_user_claims')
    async def test_set_custom_claims_success(self, mock_set_claims, firebase_service):
        """Test successful custom claims setting"""
        # Arrange
        mock_set_claims.return_value = None
        claims = {"role": "admin", "permissions": ["read", "write"]}

        # Act
        result = await firebase_service.set_custom_claims("test-uid", claims)

        # Assert
        assert result is True
        mock_set_claims.assert_called_once_with("test-uid", claims)

    @patch('firebase_admin.auth.set_custom_user_claims')
    async def test_set_custom_claims_empty_claims(self, mock_set_claims, firebase_service):
        """Test setting empty custom claims"""
        # Arrange
        mock_set_claims.return_value = None
        claims = {}

        # Act
        result = await firebase_service.set_custom_claims("test-uid", claims)

        # Assert
        assert result is True
        mock_set_claims.assert_called_once_with("test-uid", {})

    @patch('firebase_admin.auth.set_custom_user_claims')
    async def test_set_custom_claims_error(self, mock_set_claims, firebase_service):
        """Test error during custom claims setting"""
        # Arrange
        mock_set_claims.side_effect = Exception("Firebase error")
        claims = {"role": "admin"}

        # Act
        result = await firebase_service.set_custom_claims("test-uid", claims)

        # Assert
        assert result is False
        mock_set_claims.assert_called_once_with("test-uid", claims)

    @patch('firebase_admin.auth.revoke_refresh_tokens')
    async def test_revoke_refresh_tokens_success(self, mock_revoke, firebase_service):
        """Test successful token revocation"""
        # Arrange
        mock_revoke.return_value = None

        # Act
        result = await firebase_service.revoke_refresh_tokens("test-uid")

        # Assert
        assert result is True
        mock_revoke.assert_called_once_with("test-uid")

    @patch('firebase_admin.auth.revoke_refresh_tokens')
    async def test_revoke_refresh_tokens_error(self, mock_revoke, firebase_service):
        """Test error during token revocation"""
        # Arrange
        mock_revoke.side_effect = Exception("Firebase error")

        # Act
        result = await firebase_service.revoke_refresh_tokens("test-uid")

        # Assert
        assert result is False
        mock_revoke.assert_called_once_with("test-uid")


class TestFirebaseAuthServiceSingleton:
    """Test Firebase Auth Service singleton functionality"""

    def test_get_firebase_auth_service_singleton(self, mock_credentials):
        """Test singleton pattern for Firebase auth service"""
        with patch('firebase_admin.initialize_app') as mock_init, \
             patch('firebase_admin.credentials.Certificate') as mock_cert, \
             patch('firebase_admin._apps', {}):

            mock_cert.return_value = Mock()
            mock_init.return_value = Mock()

            # Reset singleton
            import app.services.firebase_auth_service as fas
            fas._firebase_service_instance = None

            # First call should create instance
            service1 = get_firebase_auth_service(**mock_credentials)

            # Second call should return same instance
            service2 = get_firebase_auth_service(**mock_credentials)

            assert service1 is service2
            assert mock_init.call_count == 1  # Only called once

    def test_get_firebase_auth_service_different_credentials(self, mock_credentials):
        """Test singleton with different credentials still returns same instance"""
        with patch('firebase_admin.initialize_app') as mock_init, \
             patch('firebase_admin.credentials.Certificate') as mock_cert, \
             patch('firebase_admin._apps', {}):

            mock_cert.return_value = Mock()
            mock_init.return_value = Mock()

            # Reset singleton
            import app.services.firebase_auth_service as fas
            fas._firebase_service_instance = None

            # First call
            service1 = get_firebase_auth_service(**mock_credentials)

            # Second call with different credentials
            different_creds = mock_credentials.copy()
            different_creds["project_id"] = "different-project"
            service2 = get_firebase_auth_service(**different_creds)

            # Should still return same instance (singleton pattern)
            assert service1 is service2


class TestFirebaseAuthServiceEdgeCases:
    """Test edge cases and security scenarios"""

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_token_very_large_claims(self, mock_verify, firebase_service):
        """Test token with very large custom claims"""
        # Arrange
        large_claims_data = {
            'uid': 'test-uid-123',
            'email': 'test@example.com',
            'email_verified': True,
            'large_claim': 'x' * 10000,  # Very large claim
            'nested_claim': {
                'level1': {
                    'level2': {
                        'data': list(range(1000))
                    }
                }
            }
        }
        mock_verify.return_value = large_claims_data

        # Act
        result = await firebase_service.verify_token('large-claims-token')

        # Assert
        assert result['uid'] == 'test-uid-123'
        assert 'large_claim' in result['custom_claims']
        assert 'nested_claim' in result['custom_claims']

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_token_special_characters(self, mock_verify, firebase_service):
        """Test token with special characters in claims"""
        # Arrange
        mock_verify.return_value = {
            'uid': 'test-uid-123',
            'email': 'test@example.com',
            'email_verified': True,
            'special_chars': '!@#$%^&*()_+-={}[]|;:,.<>?',
            'unicode_chars': 'héllo wörld 🔥',
            'html_chars': '<script>alert("test")</script>'
        }

        # Act
        result = await firebase_service.verify_token('special-chars-token')

        # Assert
        assert result['uid'] == 'test-uid-123'
        assert result['custom_claims']['special_chars'] == '!@#$%^&*()_+-={}[]|;:,.<>?'
        assert result['custom_claims']['unicode_chars'] == 'héllo wörld 🔥'
        assert result['custom_claims']['html_chars'] == '<script>alert("test")</script>'

    async def test_verify_token_whitespace_only(self, firebase_service):
        """Test token with only whitespace characters"""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await firebase_service.verify_token('   ')

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_verify_token_very_long_token(self, firebase_service):
        """Test very long token string"""
        long_token = 'a' * 10000  # Very long token

        with patch('firebase_admin.auth.verify_id_token') as mock_verify:
            mock_verify.side_effect = firebase_auth.InvalidIdTokenError('Invalid token')

            with pytest.raises(HTTPException):
                await firebase_service.verify_token(long_token)

            # Verify Firebase was called with the long token
            mock_verify.assert_called_once_with(long_token, check_revoked=True)


class TestFirebaseAuthServiceLogging:
    """Test logging behavior in Firebase Auth Service"""

    @patch('firebase_admin.auth.verify_id_token')
    async def test_successful_verification_logging(self, mock_verify, firebase_service):
        """Test that successful verification logs appropriately"""
        # Arrange
        mock_verify.return_value = {
            'uid': 'test-uid-123',
            'email': 'test@example.com',
            'email_verified': True,
            'role': 'doctor'
        }

        with patch('app.services.firebase_auth_service.logger') as mock_logger:
            # Act
            await firebase_service.verify_token('valid-token')

            # Assert
            mock_logger.debug.assert_called()
            debug_call = mock_logger.debug.call_args[0][0]
            assert 'successfully verified token' in debug_call.lower()

    @patch('firebase_admin.auth.verify_id_token')
    async def test_invalid_token_logging(self, mock_verify, firebase_service):
        """Test that invalid token attempts are logged"""
        # Arrange
        mock_verify.side_effect = firebase_auth.InvalidIdTokenError('Invalid token')

        with patch('app.services.firebase_auth_service.logger') as mock_logger:
            # Act & Assert
            with pytest.raises(HTTPException):
                await firebase_service.verify_token('invalid-token')

            # Verify warning was logged
            mock_logger.warning.assert_called()

    async def test_empty_token_logging(self, firebase_service):
        """Test that empty token attempts are logged"""
        with patch('app.services.firebase_auth_service.logger') as mock_logger:
            # Act & Assert
            with pytest.raises(HTTPException):
                await firebase_service.verify_token('')

            # Verify warning was logged
            mock_logger.warning.assert_called()

    def test_initialization_logging(self, mock_credentials):
        """Test that initialization success is logged"""
        with patch('firebase_admin.initialize_app') as mock_init, \
             patch('firebase_admin.credentials.Certificate') as mock_cert, \
             patch('firebase_admin._apps', {}), \
             patch('app.services.firebase_auth_service.logger') as mock_logger:

            mock_cert.return_value = Mock()
            mock_init.return_value = Mock()

            # Act
            service = FirebaseAuthService(**mock_credentials)

            # Assert
            mock_logger.info.assert_called()

    def test_initialization_error_logging(self, mock_credentials):
        """Test that initialization errors are logged"""
        with patch('firebase_admin.credentials.Certificate') as mock_cert, \
             patch('firebase_admin._apps', {}), \
             patch('app.services.firebase_auth_service.logger') as mock_logger:

            mock_cert.side_effect = Exception("Invalid credentials")

            # Act & Assert
            with pytest.raises(RuntimeError):
                FirebaseAuthService(**mock_credentials)

            # Verify error was logged
            mock_logger.error.assert_called()


@pytest.mark.integration
class TestFirebaseAuthServiceIntegration:
    """Integration tests for Firebase auth service (requires Firebase connection)"""

    @pytest.mark.skip(reason="Requires Firebase credentials and network connection")
    async def test_real_firebase_connection(self):
        """Test actual Firebase connection (skip in CI/CD)"""
        # This test should be run manually with real credentials
        # when testing actual Firebase integration
        pass

    @pytest.mark.skip(reason="Requires Firebase credentials and network connection")
    async def test_real_token_verification(self):
        """Test actual token verification with Firebase"""
        # This test should use real Firebase tokens
        pass