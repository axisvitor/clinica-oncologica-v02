"""
Unit tests for Firebase Authentication Service

Tests token validation, error handling, and edge cases for Firebase auth integration.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from firebase_admin import auth as firebase_auth
from firebase_admin import exceptions

# Import the service - adjust path based on actual structure
try:
    from app.services.firebase_auth_service import FirebaseAuthService, get_firebase_auth_service
except ImportError:
    # Fallback for different project structures
    from services.firebase_auth_service import FirebaseAuthService, get_firebase_auth_service


@pytest.fixture
def firebase_service():
    """Fixture for Firebase auth service with mock credentials"""
    return get_firebase_auth_service(
        project_id="test-project",
        private_key="-----BEGIN PRIVATE KEY-----\\nMOCK_KEY\\n-----END PRIVATE KEY-----",
        client_email="test@test.iam.gserviceaccount.com"
    )


class TestFirebaseAuthService:
    """Test suite for Firebase authentication service"""

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_valid_token(self, mock_verify, firebase_service):
        """Test valid token verification returns user data"""
        # Arrange
        mock_verify.return_value = {
            'uid': 'test-uid-123',
            'email': 'test@example.com',
            'email_verified': True,
            'name': 'Test User'
        }

        # Act
        result = await firebase_service.verify_token('valid-token')

        # Assert
        assert result['uid'] == 'test-uid-123'
        assert result['email'] == 'test@example.com'
        assert result['email_verified'] is True
        mock_verify.assert_called_once_with('valid-token', check_revoked=True)

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_expired_token(self, mock_verify, firebase_service):
        """Test expired token raises appropriate error"""
        # Arrange
        mock_verify.side_effect = ExpiredIdTokenError('Token expired')

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await firebase_service.verify_token('expired-token')

        assert 'expired' in str(exc_info.value).lower()

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_invalid_token(self, mock_verify, firebase_service):
        """Test invalid token raises appropriate error"""
        # Arrange
        mock_verify.side_effect = InvalidIdTokenError('Invalid token')

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await firebase_service.verify_token('invalid-token')

        assert 'invalid' in str(exc_info.value).lower()

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_revoked_token(self, mock_verify, firebase_service):
        """Test revoked token is rejected"""
        # Arrange
        mock_verify.side_effect = firebase_auth.RevokedIdTokenError('Token revoked')

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await firebase_service.verify_token('revoked-token')

        assert 'revoked' in str(exc_info.value).lower()

    async def test_empty_token_rejected(self, firebase_service):
        """Test empty token is rejected without Firebase call"""
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await firebase_service.verify_token('')

        assert exc_info.value is not None

    async def test_none_token_rejected(self, firebase_service):
        """Test None token is rejected without Firebase call"""
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await firebase_service.verify_token(None)

        assert exc_info.value is not None

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_unverified_email(self, mock_verify, firebase_service):
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
    async def test_verify_token_with_claims(self, mock_verify, firebase_service):
        """Test token verification with custom claims"""
        # Arrange
        mock_verify.return_value = {
            'uid': 'admin-uid-789',
            'email': 'admin@example.com',
            'email_verified': True,
            'admin': True,
            'role': 'super_admin'
        }

        # Act
        result = await firebase_service.verify_token('admin-token')

        # Assert
        assert result['admin'] is True
        assert result['role'] == 'super_admin'

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_token_network_error(self, mock_verify, firebase_service):
        """Test handling of network errors during verification"""
        # Arrange
        mock_verify.side_effect = Exception('Network error: Connection timeout')

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await firebase_service.verify_token('token-with-network-issue')

        assert 'network' in str(exc_info.value).lower() or 'connection' in str(exc_info.value).lower()

    @patch('firebase_admin.auth.verify_id_token')
    async def test_verify_malformed_token(self, mock_verify, firebase_service):
        """Test handling of malformed token format"""
        # Arrange
        mock_verify.side_effect = ValueError('Malformed token')

        # Act & Assert
        with pytest.raises(Exception):
            await firebase_service.verify_token('malformed.token.format')


@pytest.mark.integration
class TestFirebaseAuthServiceIntegration:
    """Integration tests for Firebase auth service (requires Firebase connection)"""

    @pytest.mark.skip(reason="Requires Firebase credentials and network connection")
    async def test_real_firebase_connection(self):
        """Test actual Firebase connection (skip in CI/CD)"""
        # This test should be run manually with real credentials
        # when testing actual Firebase integration
        pass
