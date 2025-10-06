"""
Shared fixtures for Firebase authentication integration tests.

Provides mock Firebase tokens, user data, and database fixtures
for comprehensive auth testing.
"""
import pytest
from typing import Dict, Any
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock
from sqlalchemy.orm import Session

from app.models.user import User, UserRole, AuthProvider
from app.services.firebase_auth_service import FirebaseAuthService
from app.services.firebase_user_sync_service import FirebaseUserSyncService


@pytest.fixture
def firebase_token_data_admin() -> Dict[str, Any]:
    """
    Mock Firebase token data for admin user with custom claims.

    Returns:
        Dictionary containing all Firebase token claims for an admin
    """
    return {
        "uid": "firebase_admin_test_001",
        "email": "admin@clinica.test.com",
        "email_verified": True,
        "name": "Admin Test User",
        "picture": "https://example.com/admin.jpg",
        "custom_claims": {
            "role": "admin",
            "department": "IT",
            "permissions": ["read", "write", "delete"]
        },
        "auth_time": int(datetime.utcnow().timestamp()),
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    }


@pytest.fixture
def firebase_token_data_doctor() -> Dict[str, Any]:
    """
    Mock Firebase token data for doctor user with custom claims.

    Returns:
        Dictionary containing all Firebase token claims for a doctor
    """
    return {
        "uid": "firebase_doctor_test_001",
        "email": "doctor@clinica.test.com",
        "email_verified": True,
        "name": "Dr. Test Doctor",
        "picture": "https://example.com/doctor.jpg",
        "custom_claims": {
            "role": "doctor",
            "specialty": "Oncology",
            "license": "CRM-12345"
        },
        "auth_time": int(datetime.utcnow().timestamp()),
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    }


@pytest.fixture
def firebase_token_data_top_level_claims() -> Dict[str, Any]:
    """
    Mock Firebase token data with claims at top level (legacy format).

    Tests backward compatibility with older token formats where
    role is at top-level instead of in custom_claims.

    Returns:
        Dictionary with top-level role claim
    """
    return {
        "uid": "firebase_legacy_test_001",
        "email": "legacy@clinica.test.com",
        "email_verified": True,
        "name": "Legacy User",
        "role": "medico",  # Top-level role (Portuguese)
        "custom_claims": {},  # Empty custom claims
        "auth_time": int(datetime.utcnow().timestamp()),
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    }


@pytest.fixture
def firebase_token_data_list_roles() -> Dict[str, Any]:
    """
    Mock Firebase token data with roles as a list (edge case).

    Tests handling of roles provided as array instead of single value.

    Returns:
        Dictionary with role as list
    """
    return {
        "uid": "firebase_list_roles_test_001",
        "email": "multirole@clinica.test.com",
        "email_verified": True,
        "name": "Multi-Role User",
        "custom_claims": {
            "role": ["doctor", "admin"],  # List of roles
            "primary_role": "doctor"
        },
        "auth_time": int(datetime.utcnow().timestamp()),
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    }


@pytest.fixture
def firebase_token_data_no_claims() -> Dict[str, Any]:
    """
    Mock Firebase token data without any role claims.

    Tests default role assignment when no claims are present.

    Returns:
        Dictionary without any role information
    """
    return {
        "uid": "firebase_no_claims_test_001",
        "email": "noclaims@clinica.test.com",
        "email_verified": False,
        "name": "No Claims User",
        "auth_time": int(datetime.utcnow().timestamp()),
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    }


@pytest.fixture
def mock_firebase_service():
    """
    Mock FirebaseAuthService for testing without actual Firebase connection.

    Returns:
        Mocked FirebaseAuthService instance
    """
    service = AsyncMock(spec=FirebaseAuthService)
    service.verify_token = AsyncMock()
    service.get_user = AsyncMock()
    service.set_custom_claims = AsyncMock(return_value=True)
    return service


@pytest.fixture
def firebase_sync_service(db_session, mock_firebase_service):
    """
    Create FirebaseUserSyncService with mocked Firebase service.

    Args:
        db_session: Test database session
        mock_firebase_service: Mocked Firebase service

    Returns:
        FirebaseUserSyncService instance for testing
    """
    return FirebaseUserSyncService(db_session, mock_firebase_service)


@pytest.fixture
def create_test_user(db_session):
    """
    Factory fixture to create test users in the database.

    Usage:
        user = create_test_user(
            email="test@example.com",
            firebase_uid="test_uid",
            role=UserRole.DOCTOR
        )

    Returns:
        Function that creates and returns a User instance
    """
    def _create_user(
        email: str = "test@clinica.test.com",
        firebase_uid: str = None,
        role: UserRole = UserRole.DOCTOR,
        is_active: bool = True,
        firebase_custom_claims: Dict[str, Any] = None
    ) -> User:
        user = User(
            email=email,
            full_name="Test User",
            role=role,
            is_active=is_active,
            auth_provider=AuthProvider.FIREBASE if firebase_uid else AuthProvider.LOCAL,
            firebase_uid=firebase_uid,
            firebase_email_verified=True,
            firebase_custom_claims=firebase_custom_claims or {},
            firebase_last_sign_in=datetime.utcnow(),
            last_firebase_sync=datetime.utcnow()
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create_user


@pytest.fixture
def mock_audit_log_table(db_session):
    """
    Setup mock audit log table for testing sync logging.

    Ensures audit_log_entries table exists for sync operation logging.
    """
    from sqlalchemy import text

    try:
        # Create temporary audit table for testing
        db_session.execute(text("""
            CREATE TEMP TABLE IF NOT EXISTS audit_log_entries (
                id SERIAL PRIMARY KEY,
                event_type VARCHAR(100),
                event_data JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        db_session.commit()
    except Exception:
        # Table might already exist
        pass

    yield

    # Cleanup
    try:
        db_session.execute(text("DROP TABLE IF EXISTS temp.audit_log_entries"))
        db_session.commit()
    except Exception:
        pass


@pytest.fixture
def performance_timer():
    """
    Context manager for measuring test execution time.

    Usage:
        with performance_timer() as timer:
            # Execute code
            pass
        assert timer.elapsed_ms < 500, "Operation took too long"

    Returns:
        Timer context manager
    """
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.elapsed_ms = None

        def __enter__(self):
            self.start_time = datetime.utcnow()
            return self

        def __exit__(self, *args):
            self.end_time = datetime.utcnow()
            delta = self.end_time - self.start_time
            self.elapsed_ms = delta.total_seconds() * 1000

    return Timer


@pytest.fixture
def mock_http_client():
    """
    Mock HTTP client for testing /auth/me endpoint.

    Returns:
        Mocked AsyncClient for API testing
    """
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    return client
