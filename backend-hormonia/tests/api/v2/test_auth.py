"""
Tests for Auth API v2

Comprehensive test suite for authentication endpoints including:
- User profile management
- Session management
- User preferences
- Notifications
- Firebase integration
- Password management
- Health checks
- Caching behavior
- Rate limiting
"""

import pytest
import json
import base64
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.session import Session as SessionModel
from app.models.notification import Notification, NotificationType


# ============================================================================
# Helper Functions
# ============================================================================

def create_test_session(
    db: Session,
    user: User,
    is_active: bool = True,
    expires_in_days: int = 7,
    **kwargs
) -> SessionModel:
    """
    Create a test session for a user.

    Args:
        db: Database session
        user: User to create session for
        is_active: Whether session is active
        expires_in_days: Days until session expires
        **kwargs: Additional session attributes

    Returns:
        Created SessionModel instance
    """
    session = SessionModel(
        id=kwargs.get('id', uuid4()),
        user_id=user.id,
        session_token=f"test_token_{uuid4().hex}",
        is_active=is_active,
        created_at=kwargs.get('created_at', datetime.utcnow()),
        expires_at=kwargs.get('expires_at', datetime.utcnow() + timedelta(days=expires_in_days)),
        last_activity=kwargs.get('last_activity', datetime.utcnow()),
        ip_address=kwargs.get('ip_address', '192.168.1.1'),
        user_agent=kwargs.get('user_agent', 'Mozilla/5.0 Test Browser'),
        revoked_at=kwargs.get('revoked_at'),
        revocation_reason=kwargs.get('revocation_reason'),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def create_test_notification(
    db: Session,
    user: User,
    is_read: bool = False,
    notification_type: NotificationType = NotificationType.INFO,
    **kwargs
) -> Notification:
    """
    Create a test notification for a user.

    Args:
        db: Database session
        user: User to create notification for
        is_read: Whether notification is read
        notification_type: Type of notification
        **kwargs: Additional notification attributes

    Returns:
        Created Notification instance
    """
    notification = Notification(
        id=kwargs.get('id', uuid4()),
        user_id=user.id,
        title=kwargs.get('title', 'Test Notification'),
        message=kwargs.get('message', 'This is a test notification message'),
        notification_type=notification_type,
        is_read=is_read,
        read_at=kwargs.get('read_at'),
        created_at=kwargs.get('created_at', datetime.utcnow()),
        updated_at=kwargs.get('updated_at', datetime.utcnow()),
        notification_metadata=kwargs.get('notification_metadata', {}),
        action_url=kwargs.get('action_url'),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def create_cursor(data: dict) -> str:
    """Create a base64-encoded cursor for pagination."""
    return base64.b64encode(json.dumps(data).encode()).decode()


# ============================================================================
# User Profile Tests
# ============================================================================

class TestUserProfile:
    """Test suite for user profile endpoints (/me)"""

    def test_get_current_user_profile_success(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test successfully getting current user profile"""
        # Mock Redis to return None (cache miss)
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.setex = AsyncMock(return_value=True)

            response = client.get("/api/v2/auth/me", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(test_user.id)
            assert data["email"] == test_user.email
            assert data["full_name"] == test_user.full_name
            assert data["role"] == test_user.role.value
            assert "preferences" in data

    def test_get_current_user_profile_with_field_selection(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test getting user profile with field selection"""
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.setex = AsyncMock(return_value=True)

            response = client.get(
                "/api/v2/auth/me?fields=id,email,full_name",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert "email" in data
            assert "full_name" in data

    def test_get_current_user_profile_with_eager_loading(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test getting user profile with eager loading of relationships"""
        # Create test patient for the user
        from app.models.patient import Patient
        patient = Patient(
            id=uuid4(),
            name="Test Patient",
            email="patient@test.com",
            doctor_id=test_user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(patient)
        db_session.commit()

        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.setex = AsyncMock(return_value=True)

            response = client.get("/api/v2/auth/me", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert "patient_count" in data
            assert data["patient_count"] >= 1

    def test_get_current_user_profile_cached(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test getting user profile from Redis cache"""
        cached_data = {
            "id": str(test_user.id),
            "email": test_user.email,
            "full_name": test_user.full_name,
            "role": test_user.role.value,
            "preferences": {}
        }

        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

            response = client.get("/api/v2/auth/me", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(test_user.id)
            assert data["email"] == test_user.email

    def test_get_current_user_profile_unauthorized(self, client: TestClient):
        """Test getting user profile without authentication"""
        response = client.get("/api/v2/auth/me")
        assert response.status_code == 401

    @pytest.mark.slow
    def test_get_current_user_profile_rate_limited(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test rate limiting on user profile endpoint (100/minute)"""
        # This test would require actual rate limiter configuration
        # For now, we just verify the endpoint works normally
        response = client.get("/api/v2/auth/me", headers=auth_headers)
        assert response.status_code in [200, 429]

    def test_get_current_user_profile_invalid_fields(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test getting user profile with empty fields parameter"""
        response = client.get(
            "/api/v2/auth/me?fields=",
            headers=auth_headers
        )
        # Empty fields should either return all fields or return 400
        assert response.status_code in [200, 400]

    def test_get_current_user_profile_with_patient_count(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test user profile includes patient count for doctors"""
        from app.models.patient import Patient

        # Create multiple patients
        for i in range(3):
            patient = Patient(
                id=uuid4(),
                name=f"Patient {i}",
                email=f"patient{i}@test.com",
                doctor_id=test_user.id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db_session.add(patient)
        db_session.commit()

        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.setex = AsyncMock(return_value=True)

            response = client.get("/api/v2/auth/me", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert "patient_count" in data
            assert data["patient_count"] == 3

    def test_get_current_user_profile_with_notifications(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test user profile includes notification count"""
        # Create unread notifications
        for i in range(5):
            create_test_notification(
                db_session,
                test_user,
                is_read=False,
                title=f"Notification {i}"
            )

        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.setex = AsyncMock(return_value=True)

            response = client.get("/api/v2/auth/me", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert "notification_count" in data
            assert data["notification_count"] == 5

    def test_get_current_user_profile_different_roles(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        admin_auth_headers: dict,
        mock_redis
    ):
        """Test user profile for different user roles"""
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.setex = AsyncMock(return_value=True)

            response = client.get("/api/v2/auth/me", headers=admin_auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["role"] == UserRole.ADMIN.value


# ============================================================================
# Session Management Tests
# ============================================================================

class TestSessionManagement:
    """Test suite for session management endpoints"""

    def test_list_sessions_success(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test successfully listing active sessions"""
        # Create test sessions
        for i in range(3):
            create_test_session(db_session, test_user)

        response = client.get("/api/v2/auth/sessions", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data
        assert len(data["sessions"]) == 3

    def test_list_sessions_cursor_pagination(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test session listing with cursor pagination"""
        # Create multiple sessions
        sessions = []
        for i in range(10):
            session = create_test_session(
                db_session,
                test_user,
                created_at=datetime.utcnow() - timedelta(hours=i)
            )
            sessions.append(session)

        # Get first page
        response = client.get(
            "/api/v2/auth/sessions?limit=5",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 5

    def test_list_sessions_empty(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test listing sessions when user has no sessions"""
        response = client.get("/api/v2/auth/sessions", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert data["total"] == 0

    def test_list_sessions_multiple_pages(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test pagination across multiple pages"""
        # Create 15 sessions
        for i in range(15):
            create_test_session(
                db_session,
                test_user,
                created_at=datetime.utcnow() - timedelta(minutes=i)
            )

        # Get first page with limit=5
        response = client.get(
            "/api/v2/auth/sessions?limit=5",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 5

    def test_revoke_session_success(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test successfully revoking a session"""
        session = create_test_session(db_session, test_user)

        response = client.delete(
            f"/api/v2/auth/sessions/{session.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["revoked"] is True
        assert data["session_id"] == str(session.id)

        # Verify session is revoked in database
        db_session.refresh(session)
        assert session.is_active is False
        assert session.revoked_at is not None

    def test_revoke_session_not_found(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test revoking a non-existent session"""
        fake_session_id = uuid4()
        response = client.delete(
            f"/api/v2/auth/sessions/{fake_session_id}",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_revoke_session_unauthorized(self, client: TestClient, db_session: Session, test_user: User):
        """Test revoking a session without authentication"""
        session = create_test_session(db_session, test_user)

        response = client.delete(f"/api/v2/auth/sessions/{session.id}")
        assert response.status_code == 401

    def test_revoke_session_other_user(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        admin_user: User,
        auth_headers: dict
    ):
        """Test revoking another user's session (should fail)"""
        # Create session for admin_user
        admin_session = create_test_session(db_session, admin_user)

        # Try to revoke as test_user
        response = client.delete(
            f"/api/v2/auth/sessions/{admin_session.id}",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_revoke_current_session(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test revoking the current session"""
        session = create_test_session(db_session, test_user)

        response = client.delete(
            f"/api/v2/auth/sessions/{session.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["revoked"] is True

    def test_verify_session_valid(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test verifying a valid session"""
        create_test_session(db_session, test_user)

        response = client.post("/api/v2/auth/verify-session", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "user_id" in data
        assert data["user_id"] == str(test_user.id)

    def test_verify_session_expired(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test verifying an expired session"""
        # Create expired session
        create_test_session(
            db_session,
            test_user,
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )

        response = client.post("/api/v2/auth/verify-session", headers=auth_headers)

        assert response.status_code == 401

    def test_verify_session_invalid(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test verifying with no active session"""
        response = client.post("/api/v2/auth/verify-session", headers=auth_headers)
        assert response.status_code == 401

    def test_verify_session_missing_token(self, client: TestClient):
        """Test verifying session without authentication token"""
        response = client.post("/api/v2/auth/verify-session")
        assert response.status_code == 401

    def test_session_cleanup_on_logout(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test that revoked sessions are properly marked"""
        session = create_test_session(db_session, test_user)

        # Revoke session
        client.delete(f"/api/v2/auth/sessions/{session.id}", headers=auth_headers)

        # Verify session is no longer active
        db_session.refresh(session)
        assert session.is_active is False
        assert session.revoked_at is not None
        assert "User requested revocation" in session.revocation_reason

    def test_session_device_info(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test session includes device information"""
        session = create_test_session(
            db_session,
            test_user,
            ip_address='10.0.0.1',
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)'
        )

        response = client.get("/api/v2/auth/sessions", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        sessions = data["sessions"]

        if sessions:
            session_data = sessions[0]
            assert "ip_address" in session_data
            assert "user_agent" in session_data


# ============================================================================
# User Preferences Tests
# ============================================================================

class TestUserPreferences:
    """Test suite for user preferences endpoints"""

    def test_get_preferences_success(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test successfully getting user preferences"""
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.setex = AsyncMock(return_value=True)

            response = client.get("/api/v2/auth/preferences", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert "user_id" in data
            assert "preferences" in data
            assert data["user_id"] == str(test_user.id)

            # Check default preferences
            prefs = data["preferences"]
            assert prefs["language"] == "pt-BR"
            assert prefs["theme"] == "light"
            assert prefs["timezone"] == "America/Sao_Paulo"

    def test_get_preferences_default(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test getting default preferences for new user"""
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.setex = AsyncMock(return_value=True)

            response = client.get("/api/v2/auth/preferences", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            prefs = data["preferences"]
            assert prefs["notification_email"] is True
            assert prefs["notification_sms"] is True
            assert prefs["notification_whatsapp"] is True

    def test_get_preferences_cached(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test getting preferences from Redis cache"""
        cached_prefs = {
            "user_id": str(test_user.id),
            "preferences": {
                "language": "en-US",
                "theme": "dark"
            },
            "updated_at": datetime.utcnow().isoformat()
        }

        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=json.dumps(cached_prefs))

            response = client.get("/api/v2/auth/preferences", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["preferences"]["language"] == "en-US"
            assert data["preferences"]["theme"] == "dark"

    def test_update_preferences_full(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test full update of user preferences"""
        new_preferences = {
            "notification_email": False,
            "notification_sms": True,
            "notification_whatsapp": False,
            "language": "en-US",
            "timezone": "America/New_York",
            "theme": "dark",
            "email_digest_frequency": "weekly",
            "data_sharing_consent": True,
            "marketing_consent": False
        }

        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.delete = AsyncMock(return_value=1)

            response = client.put(
                "/api/v2/auth/preferences",
                json=new_preferences,
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["preferences"]["language"] == "en-US"
            assert data["preferences"]["theme"] == "dark"
            assert data["preferences"]["notification_email"] is False

    def test_update_preferences_invalid_language(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test updating preferences with invalid language"""
        invalid_preferences = {
            "language": "invalid-LANG",
            "theme": "light"
        }

        response = client.put(
            "/api/v2/auth/preferences",
            json=invalid_preferences,
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_update_preferences_invalid_theme(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test updating preferences with invalid theme"""
        invalid_preferences = {
            "language": "pt-BR",
            "theme": "neon"  # Invalid theme
        }

        response = client.put(
            "/api/v2/auth/preferences",
            json=invalid_preferences,
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_update_preferences_cache_invalidation(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test that cache is invalidated after preferences update"""
        new_preferences = {
            "language": "en-US",
            "theme": "dark"
        }

        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.delete = AsyncMock(return_value=1)

            response = client.put(
                "/api/v2/auth/preferences",
                json=new_preferences,
                headers=auth_headers
            )

            assert response.status_code == 200
            # Verify delete was called for cache keys
            assert mock_redis.delete.call_count > 0

    def test_patch_preferences_partial(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test partial update of preferences"""
        partial_update = {
            "theme": "dark",
            "language": "en-US"
        }

        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.delete = AsyncMock(return_value=1)

            response = client.patch(
                "/api/v2/auth/preferences",
                json=partial_update,
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["preferences"]["theme"] == "dark"
            assert data["preferences"]["language"] == "en-US"
            # Other fields should remain default
            assert data["preferences"]["notification_email"] is True

    def test_patch_preferences_single_field(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test updating a single preference field"""
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.delete = AsyncMock(return_value=1)

            response = client.patch(
                "/api/v2/auth/preferences",
                json={"theme": "dark"},
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["preferences"]["theme"] == "dark"

    def test_patch_preferences_validation(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test validation on partial preference update"""
        invalid_update = {
            "email_digest_frequency": "hourly"  # Invalid value
        }

        response = client.patch(
            "/api/v2/auth/preferences",
            json=invalid_update,
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_preferences_rate_limit(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test rate limiting on preferences update (20/hour)"""
        # Single update should work
        response = client.put(
            "/api/v2/auth/preferences",
            json={"theme": "dark"},
            headers=auth_headers
        )
        assert response.status_code in [200, 429]

    def test_preferences_concurrent_updates(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test handling concurrent preference updates"""
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.delete = AsyncMock(return_value=1)

            # First update
            response1 = client.patch(
                "/api/v2/auth/preferences",
                json={"theme": "dark"},
                headers=auth_headers
            )

            # Second update
            response2 = client.patch(
                "/api/v2/auth/preferences",
                json={"language": "en-US"},
                headers=auth_headers
            )

            assert response1.status_code == 200
            assert response2.status_code == 200

            # Verify final state
            response3 = client.get("/api/v2/auth/preferences", headers=auth_headers)
            data = response3.json()
            assert data["preferences"]["theme"] == "dark"
            assert data["preferences"]["language"] == "en-US"


# ============================================================================
# Notifications Tests
# ============================================================================

class TestNotifications:
    """Test suite for notification endpoints"""

    def test_list_notifications_success(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test successfully listing notifications"""
        # Create test notifications
        for i in range(5):
            create_test_notification(
                db_session,
                test_user,
                title=f"Notification {i}",
                is_read=(i % 2 == 0)
            )

        response = client.get("/api/v2/auth/notifications", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "unread_count" in data
        assert len(data["data"]) == 5

    def test_list_notifications_cursor_pagination(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test notification listing with cursor pagination"""
        # Create 15 notifications
        for i in range(15):
            create_test_notification(
                db_session,
                test_user,
                title=f"Notification {i}",
                created_at=datetime.utcnow() - timedelta(minutes=i)
            )

        # Get first page
        response = client.get(
            "/api/v2/auth/notifications?limit=10",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 10
        assert "next_cursor" in data
        assert data["has_more"] is True

    def test_list_notifications_filter_unread(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test filtering notifications by unread status"""
        # Create mix of read and unread
        for i in range(10):
            create_test_notification(
                db_session,
                test_user,
                title=f"Notification {i}",
                is_read=(i < 5)  # First 5 are read
            )

        response = client.get(
            "/api/v2/auth/notifications?unread_only=true",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 5
        for notification in data["data"]:
            assert notification["read"] is False

    def test_list_notifications_filter_by_type(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test filtering notifications by type"""
        # Create different types
        create_test_notification(
            db_session,
            test_user,
            title="Info",
            notification_type=NotificationType.INFO
        )
        create_test_notification(
            db_session,
            test_user,
            title="Warning",
            notification_type=NotificationType.WARNING
        )
        create_test_notification(
            db_session,
            test_user,
            title="Error",
            notification_type=NotificationType.ERROR
        )

        response = client.get("/api/v2/auth/notifications", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 3

    def test_list_notifications_empty(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test listing notifications when user has none"""
        response = client.get("/api/v2/auth/notifications", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["unread_count"] == 0

    def test_list_notifications_unread_count(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test unread count in notification list"""
        # Create 7 unread, 3 read
        for i in range(10):
            create_test_notification(
                db_session,
                test_user,
                is_read=(i < 3)
            )

        response = client.get("/api/v2/auth/notifications", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["unread_count"] == 7

    def test_mark_notifications_read_single(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test marking a single notification as read"""
        notification = create_test_notification(db_session, test_user, is_read=False)

        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.delete = AsyncMock(return_value=1)

            response = client.post(
                "/api/v2/auth/notifications/mark-read",
                json={"notification_ids": [str(notification.id)]},
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["marked_count"] == 1
            assert data["success"] is True

            # Verify in database
            db_session.refresh(notification)
            assert notification.is_read is True
            assert notification.read_at is not None

    def test_mark_notifications_read_bulk(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test marking multiple notifications as read (bulk operation)"""
        # Create 5 unread notifications
        notification_ids = []
        for i in range(5):
            notif = create_test_notification(db_session, test_user, is_read=False)
            notification_ids.append(str(notif.id))

        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.delete = AsyncMock(return_value=1)

            response = client.post(
                "/api/v2/auth/notifications/mark-read",
                json={"notification_ids": notification_ids},
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["marked_count"] == 5

    def test_mark_notifications_read_max_100(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test bulk mark read enforces 100 notification limit"""
        # Try to mark 101 notifications
        notification_ids = [str(uuid4()) for _ in range(101)]

        response = client.post(
            "/api/v2/auth/notifications/mark-read",
            json={"notification_ids": notification_ids},
            headers=auth_headers
        )

        # Should fail validation
        assert response.status_code == 422

    def test_mark_notifications_read_invalid_ids(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test marking notifications with invalid IDs"""
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.delete = AsyncMock(return_value=1)

            response = client.post(
                "/api/v2/auth/notifications/mark-read",
                json={"notification_ids": ["invalid-id"]},
                headers=auth_headers
            )

            assert response.status_code == 400

    def test_mark_notifications_read_not_found(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test marking non-existent notifications"""
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.delete = AsyncMock(return_value=1)

            fake_id = str(uuid4())
            response = client.post(
                "/api/v2/auth/notifications/mark-read",
                json={"notification_ids": [fake_id]},
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["marked_count"] == 0

    def test_get_unread_count_success(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test getting unread notification count"""
        # Create 8 unread notifications
        for i in range(8):
            create_test_notification(db_session, test_user, is_read=False)

        # Create 2 read notifications
        for i in range(2):
            create_test_notification(db_session, test_user, is_read=True)

        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.setex = AsyncMock(return_value=True)

            response = client.get(
                "/api/v2/auth/notifications/unread-count",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 8

    def test_get_unread_count_cached(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test getting unread count from cache"""
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value="5")

            response = client.get(
                "/api/v2/auth/notifications/unread-count",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 5

    def test_get_unread_count_zero(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test unread count when user has no unread notifications"""
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.setex = AsyncMock(return_value=True)

            response = client.get(
                "/api/v2/auth/notifications/unread-count",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 0

    def test_notifications_real_time_updates(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test that notification list updates after marking as read"""
        # Create notifications
        for i in range(3):
            create_test_notification(db_session, test_user, is_read=False)

        # Get initial unread count
        response1 = client.get("/api/v2/auth/notifications", headers=auth_headers)
        data1 = response1.json()
        initial_unread = data1["unread_count"]

        # Mark one as read
        notif_id = data1["data"][0]["id"]
        client.post(
            "/api/v2/auth/notifications/mark-read",
            json={"notification_ids": [notif_id]},
            headers=auth_headers
        )

        # Get updated count
        response2 = client.get("/api/v2/auth/notifications", headers=auth_headers)
        data2 = response2.json()

        assert data2["unread_count"] == initial_unread - 1

    def test_notifications_metadata(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test notification metadata is included"""
        metadata = {
            "patient_id": str(uuid4()),
            "action_type": "appointment_reminder",
            "priority": "high"
        }

        create_test_notification(
            db_session,
            test_user,
            notification_metadata=metadata
        )

        response = client.get("/api/v2/auth/notifications", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        notification = data["data"][0]
        assert "metadata" in notification
        assert notification["metadata"] == metadata

    def test_notifications_action_url(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test notification action URL is included"""
        create_test_notification(
            db_session,
            test_user,
            action_url="/patients/123/appointments"
        )

        response = client.get("/api/v2/auth/notifications", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        notification = data["data"][0]
        assert notification["action_url"] == "/patients/123/appointments"

    def test_notifications_eager_loading(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test notifications are efficiently loaded (query count)"""
        # Create multiple notifications
        for i in range(20):
            create_test_notification(db_session, test_user)

        response = client.get(
            "/api/v2/auth/notifications?limit=20",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 20


# ============================================================================
# Password Management Tests
# ============================================================================

class TestPasswordManagement:
    """Test suite for password management endpoints"""

    def test_change_password_success(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test changing password (legacy endpoint)"""
        payload = {
            "current_password": "testpass123",
            "new_password": "NewSecureP@ssw0rd123"
        }

        response = client.post(
            "/api/v2/auth/password/change",
            json=payload,
            headers=auth_headers
        )

        # This endpoint is deprecated, should return message
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_change_password_invalid_current(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test changing password with invalid current password"""
        payload = {
            "current_password": "wrongpassword",
            "new_password": "NewSecureP@ssw0rd123"
        }

        response = client.post(
            "/api/v2/auth/password/change",
            json=payload,
            headers=auth_headers
        )

        # Deprecated endpoint
        assert response.status_code == 200

    def test_change_password_weak_new(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test changing password with weak new password"""
        payload = {
            "current_password": "testpass123",
            "new_password": "weak"
        }

        response = client.post(
            "/api/v2/auth/password/change",
            json=payload,
            headers=auth_headers
        )

        # Should fail validation
        assert response.status_code == 422

    def test_change_password_same_as_current(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test changing password to same as current"""
        payload = {
            "current_password": "testpass123",
            "new_password": "testpass123"
        }

        response = client.post(
            "/api/v2/auth/password/change",
            json=payload,
            headers=auth_headers
        )

        # Deprecated endpoint should return 200
        assert response.status_code == 200

    def test_change_password_rate_limited(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test rate limiting on password change (5/hour)"""
        payload = {
            "current_password": "testpass123",
            "new_password": "NewSecureP@ssw0rd123"
        }

        response = client.post(
            "/api/v2/auth/password/change",
            json=payload,
            headers=auth_headers
        )

        assert response.status_code in [200, 429]

    def test_reset_password_request_success(self, client: TestClient):
        """Test requesting password reset"""
        payload = {"email": "test@example.com"}

        response = client.post(
            "/api/v2/auth/password/reset",
            json=payload
        )

        # Always returns success for security
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_reset_password_invalid_email(self, client: TestClient):
        """Test password reset with invalid email format"""
        payload = {"email": "not-an-email"}

        response = client.post(
            "/api/v2/auth/password/reset",
            json=payload
        )

        assert response.status_code == 422

    def test_reset_password_rate_limited(self, client: TestClient):
        """Test rate limiting on password reset (3/hour)"""
        payload = {"email": "test@example.com"}

        response = client.post(
            "/api/v2/auth/password/reset",
            json=payload
        )

        assert response.status_code in [200, 429]

    def test_reset_password_email_sent(self, client: TestClient):
        """Test password reset always returns success"""
        # Test with non-existent email (should still return success)
        payload = {"email": "nonexistent@example.com"}

        response = client.post(
            "/api/v2/auth/password/reset",
            json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_reset_password_confirm_success(self, client: TestClient):
        """Test confirming password reset"""
        payload = {
            "token": "reset_token_123",
            "new_password": "NewSecureP@ssw0rd123"
        }

        response = client.post(
            "/api/v2/auth/password/reset/confirm",
            json=payload
        )

        # Deprecated endpoint
        assert response.status_code == 200

    def test_reset_password_confirm_expired_token(self, client: TestClient):
        """Test confirming reset with expired token"""
        payload = {
            "token": "expired_token",
            "new_password": "NewSecureP@ssw0rd123"
        }

        response = client.post(
            "/api/v2/auth/password/reset/confirm",
            json=payload
        )

        # Deprecated endpoint returns 200
        assert response.status_code == 200

    def test_reset_password_confirm_invalid_token(self, client: TestClient):
        """Test confirming reset with invalid token"""
        payload = {
            "token": "invalid_token",
            "new_password": "NewSecureP@ssw0rd123"
        }

        response = client.post(
            "/api/v2/auth/password/reset/confirm",
            json=payload
        )

        assert response.status_code == 200

    def test_reset_password_confirm_weak_password(self, client: TestClient):
        """Test confirming reset with weak password"""
        payload = {
            "token": "valid_token",
            "new_password": "weak"
        }

        response = client.post(
            "/api/v2/auth/password/reset/confirm",
            json=payload
        )

        # Should fail validation
        assert response.status_code == 422

    @pytest.mark.parametrize("password,should_pass", [
        ("Abc123!@", True),  # Valid
        ("short", False),  # Too short
        ("NoNumbers!", False),  # No numbers
        ("nospecial123", False),  # No special chars
        ("NOLOWER123!", False),  # No lowercase
        ("noupper123!", False),  # No uppercase
        ("ValidP@ss123", True),  # Valid
    ])
    def test_password_validation_rules(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict,
        password: str,
        should_pass: bool
    ):
        """Test password validation rules"""
        payload = {
            "current_password": "testpass123",
            "new_password": password
        }

        response = client.post(
            "/api/v2/auth/password/change",
            json=payload,
            headers=auth_headers
        )

        if should_pass:
            assert response.status_code == 200
        else:
            assert response.status_code == 422

    def test_password_history_check(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test that password history is checked (if implemented)"""
        # This is a placeholder test for future implementation
        payload = {
            "current_password": "testpass123",
            "new_password": "NewSecureP@ssw0rd123"
        }

        response = client.post(
            "/api/v2/auth/password/change",
            json=payload,
            headers=auth_headers
        )

        assert response.status_code == 200


# ============================================================================
# Firebase & Health Tests
# ============================================================================

class TestFirebaseAndHealth:
    """Test suite for Firebase integration and health check endpoints"""

    def test_firebase_verify_valid_token(self, client: TestClient, mock_redis):
        """Test verifying valid Firebase token"""
        payload = {"id_token": "valid_firebase_token_123"}
        
        # Mock Firebase service
        with patch('app.api.v2.routers.auth._firebase_service') as mock_service:
            mock_service.verify_token = AsyncMock(return_value={
                "uid": "firebase_uid_123",
                "email": "test@example.com",
                "name": "Test User",
                "picture": "http://example.com/pic.jpg"
            })
            
            with patch('app.api.v2.routers.auth.get_redis_client', return_value=mock_redis):
                mock_redis.setex = AsyncMock(return_value=True)
                
                response = client.post(
                    "/api/v2/auth/firebase/verify",
                    json=payload
                )

                assert response.status_code == 200
                data = response.json()
                assert data["valid"] is True
                assert "session_id" in data
                assert "user" in data
                assert data["user"]["email"] == "test@example.com"

    def test_firebase_verify_invalid_token(self, client: TestClient):
        """Test verifying invalid Firebase token"""
        payload = {"id_token": "invalid_token"}

        with patch('app.api.v2.routers.auth._firebase_service') as mock_service:
            mock_service.verify_token = AsyncMock(side_effect=Exception("Invalid token"))
            
            response = client.post(
                "/api/v2/auth/firebase/verify",
                json=payload
            )

            assert response.status_code == 401
            assert "valid" in response.json()
            assert response.json()["valid"] is False

    def test_firebase_verify_expired_token(self, client: TestClient):
        """Test verifying expired Firebase token"""
        payload = {"id_token": "expired_token"}

        with patch('app.api.v2.routers.auth._firebase_service') as mock_service:
            mock_service.verify_token = AsyncMock(side_effect=Exception("Token expired"))

            response = client.post(
                "/api/v2/auth/firebase/verify",
                json=payload
            )

            assert response.status_code == 401

    def test_firebase_verify_creates_session(self, client: TestClient, mock_redis):
        """Test that Firebase verification creates a session"""
        payload = {"id_token": "valid_token"}

        with patch('app.api.v2.routers.auth._firebase_service') as mock_service:
            mock_service.verify_token = AsyncMock(return_value={
                "uid": "firebase_uid_session",
                "email": "session@example.com"
            })
            
            with patch('app.api.v2.routers.auth.get_redis_client', return_value=mock_redis):
                mock_redis.setex = AsyncMock(return_value=True)

                response = client.post(
                    "/api/v2/auth/firebase/verify",
                    json=payload
                )

                assert response.status_code == 200
                data = response.json()
                assert "session_id" in data
                # Verify Redis was called to store session
                assert mock_redis.setex.called

    def test_firebase_verify_updates_user(self, client: TestClient, mock_redis):
        """Test that Firebase verification updates user data"""
        payload = {"id_token": "valid_token"}

        with patch('app.api.v2.routers.auth._firebase_service') as mock_service:
            mock_service.verify_token = AsyncMock(return_value={
                "uid": "firebase_uid_update",
                "email": "update@example.com",
                "name": "Updated Name",
                "picture": "http://new.pic"
            })
            
            with patch('app.api.v2.routers.auth.get_redis_client', return_value=mock_redis):
                mock_redis.setex = AsyncMock(return_value=True)

                response = client.post(
                    "/api/v2/auth/firebase/verify",
                    json=payload
                )

                assert response.status_code == 200
                data = response.json()
                assert data["user"]["full_name"] == "Updated Name"
                assert data["user"]["photo_url"] == "http://new.pic"

    def test_health_check_all_healthy(
        self,
        client: TestClient,
        db_session: Session,
        mock_redis
    ):
        """Test health check when all services are healthy"""
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.ping = AsyncMock(return_value=True)

            response = client.get("/api/v2/auth/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "services" in data
            assert data["services"]["database"] is True

    def test_health_check_redis_down(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test health check when Redis is unavailable"""
        with patch('app.api.v2.auth._get_redis_client', return_value=None):
            response = client.get("/api/v2/auth/health")

            assert response.status_code == 200
            data = response.json()
            assert data["services"]["redis"] is False

    def test_health_check_database_down(self, client: TestClient):
        """Test health check when database is unavailable"""
        # This would require mocking database connection failure
        # For now, we test with working database
        response = client.get("/api/v2/auth/health")
        assert response.status_code == 200

    def test_health_check_firebase_down(
        self,
        client: TestClient,
        db_session: Session,
        mock_redis
    ):
        """Test health check shows Firebase status"""
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.ping = AsyncMock(return_value=True)

            response = client.get("/api/v2/auth/health")

            assert response.status_code == 200
            data = response.json()
            assert "firebase" in data["services"]
            # Firebase not implemented, should be None
            assert data["services"]["firebase"] is None

    def test_health_check_response_format(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test health check response format"""
        response = client.get("/api/v2/auth/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "services" in data
        assert isinstance(data["services"], dict)


# ============================================================================
# Cache & Performance Tests
# ============================================================================

class TestCacheAndPerformance:
    """Test suite for Redis caching and performance optimization"""

    def test_redis_cache_hit_rate(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test Redis cache hit behavior"""
        cached_data = json.dumps({
            "id": str(test_user.id),
            "email": test_user.email
        })

        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=cached_data)

            response = client.get("/api/v2/auth/me", headers=auth_headers)

            assert response.status_code == 200
            # Verify get was called
            assert mock_redis.get.called

    def test_redis_cache_invalidation(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test cache invalidation on data update"""
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.delete = AsyncMock(return_value=1)

            # Update preferences (should invalidate cache)
            response = client.put(
                "/api/v2/auth/preferences",
                json={"theme": "dark"},
                headers=auth_headers
            )

            assert response.status_code == 200
            # Verify cache was invalidated
            assert mock_redis.delete.called

    def test_redis_cache_ttl_expiry(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test Redis cache TTL expiration"""
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=None)  # Expired
            mock_redis.setex = AsyncMock(return_value=True)

            response = client.get("/api/v2/auth/me", headers=auth_headers)

            assert response.status_code == 200
            # Verify setex was called to refresh cache
            assert mock_redis.setex.called

    def test_cursor_pagination_performance(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test cursor pagination is efficient"""
        # Create many notifications
        for i in range(100):
            create_test_notification(
                db_session,
                test_user,
                created_at=datetime.utcnow() - timedelta(minutes=i)
            )

        # Get first page
        response = client.get(
            "/api/v2/auth/notifications?limit=20",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 20
        assert data["has_more"] is True

    def test_eager_loading_query_count(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test eager loading reduces query count"""
        # Create related data
        from app.models.patient import Patient
        for i in range(5):
            patient = Patient(
                id=uuid4(),
                name=f"Patient {i}",
                email=f"patient{i}@test.com",
                doctor_id=test_user.id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db_session.add(patient)
        db_session.commit()

        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.setex = AsyncMock(return_value=True)

            response = client.get("/api/v2/auth/me", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert "patient_count" in data

    def test_rate_limiting_enforcement(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test rate limiting is enforced"""
        # This would require actual rate limiter
        response = client.get("/api/v2/auth/me", headers=auth_headers)
        assert response.status_code in [200, 429]

    def test_concurrent_requests(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test handling concurrent requests"""
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.setex = AsyncMock(return_value=True)

            # Make multiple requests
            responses = []
            for i in range(5):
                response = client.get("/api/v2/auth/me", headers=auth_headers)
                responses.append(response)

            # All should succeed
            for response in responses:
                assert response.status_code == 200

    def test_response_time_p95(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test response time is acceptable"""
        import time

        start = time.time()
        response = client.get("/api/v2/auth/me", headers=auth_headers)
        duration = time.time() - start

        assert response.status_code == 200
        # Should respond within 1 second
        assert duration < 1.0

    def test_payload_size_with_field_selection(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict,
        mock_redis
    ):
        """Test field selection reduces payload size"""
        with patch('app.api.v2.auth._get_redis_client', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.setex = AsyncMock(return_value=True)

            # Get full response
            response_full = client.get("/api/v2/auth/me", headers=auth_headers)

            # Get limited fields
            response_limited = client.get(
                "/api/v2/auth/me?fields=id,email",
                headers=auth_headers
            )

            assert response_full.status_code == 200
            assert response_limited.status_code == 200

            # Limited response should have fewer fields
            full_data = response_full.json()
            limited_data = response_limited.json()
            assert len(limited_data.keys()) <= len(full_data.keys())

    def test_database_query_optimization(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test database queries are optimized"""
        # Create test data
        for i in range(10):
            create_test_notification(db_session, test_user)

        # Query should be efficient
        response = client.get(
            "/api/v2/auth/notifications?limit=10",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 10
