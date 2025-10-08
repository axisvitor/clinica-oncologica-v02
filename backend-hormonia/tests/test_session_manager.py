"""
Test Suite: Session Manager
Tests: 15 comprehensive session management tests
Coverage: Session creation, validation, expiry, concurrency, security
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import asyncio
import json
from app.core.session_manager import SessionManager
from app.models.session import Session


class TestSessionCreation:
    """Test session creation and initialization"""

    @pytest.fixture
    def session_manager(self):
        return SessionManager()

    def test_create_new_session_with_valid_data(self, session_manager):
        """Test creating a session with valid user data"""
        user_id = "user_123"
        session_data = {
            "role": "patient",
            "permissions": ["read", "write"]
        }

        session = session_manager.create_session(user_id, session_data)

        assert session is not None
        assert session.user_id == user_id
        assert session.data == session_data
        assert session.created_at is not None
        assert session.expires_at > datetime.utcnow()

    def test_create_session_with_custom_expiry(self, session_manager):
        """Test creating a session with custom expiration time"""
        user_id = "user_456"
        expiry_hours = 2

        session = session_manager.create_session(
            user_id,
            {},
            expiry_hours=expiry_hours
        )

        expected_expiry = datetime.utcnow() + timedelta(hours=expiry_hours)
        assert abs((session.expires_at - expected_expiry).total_seconds()) < 5

    def test_create_session_generates_unique_token(self, session_manager):
        """Test that each session gets a unique token"""
        session1 = session_manager.create_session("user_1", {})
        session2 = session_manager.create_session("user_2", {})

        assert session1.token != session2.token
        assert len(session1.token) >= 32


class TestSessionValidation:
    """Test session validation and verification"""

    @pytest.fixture
    def session_manager(self):
        return SessionManager()

    def test_validate_active_session(self, session_manager):
        """Test validating an active, non-expired session"""
        session = session_manager.create_session("user_789", {})

        is_valid = session_manager.validate_session(session.token)

        assert is_valid is True

    def test_reject_expired_session(self, session_manager):
        """Test that expired sessions are rejected"""
        session = session_manager.create_session(
            "user_expired",
            {},
            expiry_hours=-1  # Already expired
        )

        is_valid = session_manager.validate_session(session.token)

        assert is_valid is False

    def test_reject_invalid_token(self, session_manager):
        """Test that invalid tokens are rejected"""
        invalid_token = "invalid_token_12345"

        is_valid = session_manager.validate_session(invalid_token)

        assert is_valid is False


class TestSessionExpiry:
    """Test session expiration and renewal"""

    @pytest.fixture
    def session_manager(self):
        return SessionManager()

    def test_session_auto_expires(self, session_manager):
        """Test that sessions expire after the specified time"""
        with patch('app.core.session_manager.datetime') as mock_datetime:
            # Create session
            mock_datetime.utcnow.return_value = datetime(2025, 1, 1, 12, 0)
            session = session_manager.create_session("user_auto", {}, expiry_hours=1)

            # Fast forward time
            mock_datetime.utcnow.return_value = datetime(2025, 1, 1, 13, 30)

            is_valid = session_manager.validate_session(session.token)
            assert is_valid is False

    def test_renew_session_extends_expiry(self, session_manager):
        """Test that renewing a session extends its expiration time"""
        session = session_manager.create_session("user_renew", {}, expiry_hours=1)
        original_expiry = session.expires_at

        renewed_session = session_manager.renew_session(session.token, hours=2)

        assert renewed_session.expires_at > original_expiry
        assert renewed_session.user_id == session.user_id

    def test_cannot_renew_expired_session(self, session_manager):
        """Test that expired sessions cannot be renewed"""
        session = session_manager.create_session(
            "user_cant_renew",
            {},
            expiry_hours=-1
        )

        with pytest.raises(ValueError, match="expired"):
            session_manager.renew_session(session.token)


class TestConcurrentSessions:
    """Test concurrent session handling"""

    @pytest.fixture
    def session_manager(self):
        return SessionManager()

    @pytest.mark.asyncio
    async def test_multiple_concurrent_sessions_per_user(self, session_manager):
        """Test that a user can have multiple active sessions"""
        user_id = "user_multi"

        # Create multiple sessions concurrently
        sessions = await asyncio.gather(*[
            asyncio.to_thread(session_manager.create_session, user_id, {"device": f"device_{i}"})
            for i in range(5)
        ])

        # All sessions should be valid
        validations = await asyncio.gather(*[
            asyncio.to_thread(session_manager.validate_session, s.token)
            for s in sessions
        ])

        assert all(validations)
        assert len(set(s.token for s in sessions)) == 5

    @pytest.mark.asyncio
    async def test_concurrent_validation_requests(self, session_manager):
        """Test handling multiple concurrent validation requests"""
        session = session_manager.create_session("user_concurrent", {})

        # Validate same session concurrently
        results = await asyncio.gather(*[
            asyncio.to_thread(session_manager.validate_session, session.token)
            for _ in range(100)
        ])

        assert all(results)

    def test_max_sessions_per_user_limit(self, session_manager):
        """Test that users cannot exceed maximum session limit"""
        user_id = "user_limit"
        max_sessions = 10

        # Create max allowed sessions
        for i in range(max_sessions):
            session_manager.create_session(user_id, {"session": i})

        # Next session should fail or invalidate oldest
        with pytest.raises(ValueError, match="maximum sessions"):
            session_manager.create_session(user_id, {"session": "overflow"})


class TestSessionSecurity:
    """Test session security features"""

    @pytest.fixture
    def session_manager(self):
        return SessionManager()

    def test_session_data_is_encrypted(self, session_manager):
        """Test that sensitive session data is encrypted"""
        sensitive_data = {
            "password_hash": "secret_hash_123",
            "api_key": "sk-123456"
        }

        session = session_manager.create_session("user_secure", sensitive_data)

        # Data should be encrypted in storage
        stored_data = session_manager._get_raw_session_data(session.token)
        assert "password_hash" not in str(stored_data)
        assert "api_key" not in str(stored_data)

    def test_session_token_is_cryptographically_secure(self, session_manager):
        """Test that session tokens are generated securely"""
        tokens = [
            session_manager.create_session(f"user_{i}", {}).token
            for i in range(1000)
        ]

        # Check uniqueness
        assert len(tokens) == len(set(tokens))

        # Check minimum entropy
        for token in tokens:
            assert len(token) >= 32
            assert any(c.isdigit() for c in token)
            assert any(c.isalpha() for c in token)

    def test_session_hijacking_prevention(self, session_manager):
        """Test that sessions cannot be hijacked with IP changes"""
        session = session_manager.create_session(
            "user_protected",
            {"ip": "192.168.1.1"}
        )

        # Attempt to validate from different IP
        with pytest.raises(SecurityError, match="IP mismatch"):
            session_manager.validate_session(
                session.token,
                client_ip="10.0.0.1"
            )


class TestSessionPersistence:
    """Test session persistence and recovery"""

    @pytest.fixture
    def session_manager(self):
        return SessionManager()

    def test_sessions_persist_across_restarts(self, session_manager):
        """Test that sessions are persisted and can be recovered"""
        session = session_manager.create_session("user_persist", {"data": "test"})
        token = session.token

        # Simulate restart
        new_manager = SessionManager()

        # Session should still be valid
        assert new_manager.validate_session(token) is True

    def test_cleanup_expired_sessions(self, session_manager):
        """Test that expired sessions are cleaned up"""
        # Create expired sessions
        for i in range(10):
            session_manager.create_session(
                f"user_cleanup_{i}",
                {},
                expiry_hours=-1
            )

        # Run cleanup
        deleted_count = session_manager.cleanup_expired_sessions()

        assert deleted_count == 10

    def test_session_recovery_after_corruption(self, session_manager):
        """Test graceful handling of corrupted session data"""
        session = session_manager.create_session("user_corrupt", {})

        # Corrupt the session data
        session_manager._corrupt_session(session.token)

        # Should return False, not raise exception
        assert session_manager.validate_session(session.token) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.core.session_manager"])
