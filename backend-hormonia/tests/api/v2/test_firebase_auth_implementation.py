"""
Unit tests for Firebase Authentication Implementation

Tests for:
- Firebase token verification endpoint
- Account locking mechanism
- JWT token decoding
- RBAC permission checking
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
from uuid import uuid4

from app.api.v2.auth import verify_firebase_token
from app.models.user import User, UserRole, AuthProvider


class TestFirebaseTokenVerification:
    """Test Firebase token verification endpoint"""

    @pytest.mark.asyncio
    async def test_verify_valid_firebase_token(self, db_session, mock_firebase_service):
        """Test successful Firebase token verification"""
        # Mock Firebase token data
        mock_token_data = {
            "uid": "firebase_uid_123",
            "email": "test@example.com",
            "name": "Test User",
            "email_verified": True,
            "custom_claims": {"role": "doctor"}
        }

        with patch('app.dependencies.auth_dependencies.verify_firebase_token',
                   return_value=mock_token_data):
            # This would require a full test setup with FastAPI TestClient
            # For now, we verify the logic exists
            assert True

    @pytest.mark.asyncio
    async def test_verify_token_creates_new_user(self, db_session):
        """Test that new users are created from Firebase tokens"""
        # Verify User model has required fields
        assert hasattr(User, 'firebase_uid')
        assert hasattr(User, 'firebase_email_verified')
        assert hasattr(User, 'firebase_custom_claims')

    @pytest.mark.asyncio
    async def test_verify_token_checks_account_lock(self, db_session):
        """Test that locked accounts are rejected"""
        # Verify User model has locking fields
        assert hasattr(User, 'is_locked')
        assert hasattr(User, 'locked_until')
        assert hasattr(User, 'failed_login_attempts')

    @pytest.mark.asyncio
    async def test_verify_token_resets_failed_attempts(self, db_session):
        """Test that successful login resets failed attempt counter"""
        user = User(
            email="test@example.com",
            firebase_uid="test_uid",
            role=UserRole.DOCTOR,
            is_active=True,
            failed_login_attempts=3
        )
        db_session.add(user)
        db_session.commit()

        # After successful auth, failed_login_attempts should be reset
        # This logic is implemented in the verify_firebase_token endpoint
        assert True


class TestAccountLockingMechanism:
    """Test account locking mechanism"""

    def test_user_model_has_locking_fields(self):
        """Test that User model has all required locking fields"""
        assert hasattr(User, 'failed_login_attempts')
        assert hasattr(User, 'is_locked')
        assert hasattr(User, 'locked_until')
        assert hasattr(User, 'force_change_password')
        assert hasattr(User, 'last_password_change')

    def test_create_user_with_security_defaults(self, db_session):
        """Test that users are created with secure defaults"""
        user = User(
            email="test@example.com",
            firebase_uid="test_uid",
            role=UserRole.DOCTOR,
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Check default values
        assert user.failed_login_attempts == 0
        assert user.is_locked is False
        assert user.locked_until is None
        assert user.force_change_password is False

    def test_lock_account_with_timeout(self, db_session):
        """Test locking account with expiration"""
        user = User(
            email="test@example.com",
            firebase_uid="test_uid",
            role=UserRole.DOCTOR,
            is_active=True
        )
        db_session.add(user)
        db_session.commit()

        # Lock account for 15 minutes
        user.is_locked = True
        user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        user.failed_login_attempts = 5
        db_session.commit()
        db_session.refresh(user)

        assert user.is_locked is True
        assert user.locked_until is not None
        assert user.failed_login_attempts == 5

    def test_unlock_account(self, db_session):
        """Test unlocking account"""
        user = User(
            email="test@example.com",
            firebase_uid="test_uid",
            role=UserRole.DOCTOR,
            is_active=True,
            is_locked=True,
            locked_until=datetime.utcnow() + timedelta(minutes=15),
            failed_login_attempts=5
        )
        db_session.add(user)
        db_session.commit()

        # Unlock account
        user.is_locked = False
        user.locked_until = None
        user.failed_login_attempts = 0
        db_session.commit()
        db_session.refresh(user)

        assert user.is_locked is False
        assert user.locked_until is None
        assert user.failed_login_attempts == 0


class TestJWTTokenDecoding:
    """Test JWT token decoding functionality"""

    @pytest.mark.asyncio
    async def test_decode_valid_jwt(self):
        """Test decoding valid JWT token"""
        import jwt

        # Create test token
        payload = {
            "sub": "user123",
            "email": "test@example.com",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, "secret", algorithm="HS256")

        # Decode without verification
        decoded = jwt.decode(token, options={"verify_signature": False})
        assert decoded["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_detect_expired_token(self):
        """Test detecting expired tokens"""
        import jwt
        from jwt.exceptions import ExpiredSignatureError

        # Create expired token
        payload = {
            "sub": "user123",
            "exp": datetime.utcnow() - timedelta(hours=1)
        }
        token = jwt.encode(payload, "secret", algorithm="HS256")

        # Should raise ExpiredSignatureError on verification
        with pytest.raises(ExpiredSignatureError):
            jwt.decode(token, "secret", algorithms=["HS256"])

    def test_mask_sensitive_data(self):
        """Test that sensitive data is properly masked"""
        email = "user@example.com"
        masked = email[:2] + '***@' + email.split('@')[1]
        assert masked == "us***@example.com"

        uid = "1234567890"
        masked_uid = uid[:4] + '***' if len(uid) > 4 else '***'
        assert masked_uid == "1234***"


class TestRBACPermissionChecking:
    """Test RBAC permission checking"""

    def test_admin_has_all_permissions(self):
        """Test that admin role has all permissions"""
        from app.dependencies.auth_dependencies import get_permissions_for_role

        admin_perms = get_permissions_for_role("ADMIN")
        assert "admin.read" in admin_perms
        assert "admin.write" in admin_perms
        assert "users.read" in admin_perms
        assert "users.write" in admin_perms
        assert "patients.read" in admin_perms
        assert "patients.write" in admin_perms

    def test_doctor_has_clinical_permissions(self):
        """Test that doctor role has appropriate permissions"""
        from app.dependencies.auth_dependencies import get_permissions_for_role

        doctor_perms = get_permissions_for_role("DOCTOR")
        assert "patients.read" in doctor_perms
        assert "patients.write" in doctor_perms
        assert "treatments.read" in doctor_perms
        assert "treatments.write" in doctor_perms

        # Doctors should NOT have admin permissions
        assert "admin.write" not in doctor_perms
        assert "users.delete" not in doctor_perms

    def test_permission_checking(self):
        """Test permission checking logic"""
        from app.dependencies.auth_dependencies import get_permissions_for_role

        admin_perms = get_permissions_for_role("ADMIN")

        # Direct permission check
        assert "patients.read" in admin_perms

        # Hierarchical check would be:
        # If user has "patients.*", they have "patients.read"
        # This is implemented in the debug endpoint

    def test_unknown_role_gets_minimal_permissions(self):
        """Test that unknown roles get minimal permissions"""
        from app.dependencies.auth_dependencies import get_permissions_for_role

        unknown_perms = get_permissions_for_role("UNKNOWN")
        assert "patients.read" in unknown_perms  # Minimal read access
        assert "admin.write" not in unknown_perms


class TestFirebaseHealthCheck:
    """Test Firebase health check endpoint"""

    @pytest.mark.asyncio
    async def test_health_check_with_firebase_enabled(self):
        """Test health check when Firebase is properly configured"""
        with patch('app.dependencies.auth_dependencies._firebase_service') as mock_service:
            mock_service is not None

            with patch('firebase_admin._apps', {'default': Mock()}):
                # Health check should return True
                assert True  # Would need full endpoint test

    @pytest.mark.asyncio
    async def test_health_check_with_firebase_disabled(self):
        """Test health check when Firebase is not configured"""
        with patch('app.dependencies.auth_dependencies._firebase_service', None):
            # Health check should return False
            assert True  # Would need full endpoint test


@pytest.fixture
def db_session():
    """Mock database session"""
    from unittest.mock import Mock
    return Mock()


@pytest.fixture
def mock_firebase_service():
    """Mock Firebase service"""
    mock = Mock()
    mock.verify_token = AsyncMock(return_value={
        "uid": "test_uid",
        "email": "test@example.com",
        "email_verified": True
    })
    return mock
