"""
Comprehensive tests for SessionService
Coverage target: 100% of session management functionality
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from app.services.session_service import SessionService
from app.core.exceptions import SessionExpiredError, InvalidSessionError


class TestSessionServiceCreation:
    """Test session creation scenarios"""

    @pytest.fixture
    def session_service(self):
        return SessionService()

    async def test_create_session_success(self, session_service):
        """Should create new session with valid user data"""
        user_data = {
            'user_id': 'user123',
            'email': 'test@example.com',
            'roles': ['user']
        }

        session = await session_service.create_session(user_data)

        assert session['user_id'] == 'user123'
        assert session['email'] == 'test@example.com'
        assert 'session_id' in session
        assert 'expires_at' in session

    async def test_create_session_with_custom_ttl(self, session_service):
        """Should create session with custom expiration time"""
        user_data = {'user_id': 'user123', 'email': 'test@example.com'}
        custom_ttl = 7200  # 2 hours

        session = await session_service.create_session(user_data, ttl=custom_ttl)

        expires_at = datetime.fromisoformat(session['expires_at'])
        expected_expiry = datetime.utcnow() + timedelta(seconds=custom_ttl)

        assert abs((expires_at - expected_expiry).total_seconds()) < 5

    async def test_create_session_with_metadata(self, session_service):
        """Should store additional metadata in session"""
        user_data = {'user_id': 'user123', 'email': 'test@example.com'}
        metadata = {'ip_address': '192.168.1.1', 'user_agent': 'Mozilla/5.0'}

        session = await session_service.create_session(user_data, metadata=metadata)

        assert session['metadata'] == metadata


class TestSessionValidation:
    """Test session validation and verification"""

    @pytest.fixture
    def session_service(self):
        return SessionService()

    async def test_validate_session_success(self, session_service):
        """Should validate active session successfully"""
        user_data = {'user_id': 'user123', 'email': 'test@example.com'}
        session = await session_service.create_session(user_data)

        is_valid = await session_service.validate_session(session['session_id'])

        assert is_valid is True

    async def test_validate_expired_session(self, session_service):
        """Should reject expired session"""
        user_data = {'user_id': 'user123', 'email': 'test@example.com'}
        session = await session_service.create_session(user_data, ttl=1)

        # Wait for session to expire
        await asyncio.sleep(2)

        with pytest.raises(SessionExpiredError):
            await session_service.validate_session(session['session_id'])

    async def test_validate_invalid_session_id(self, session_service):
        """Should reject non-existent session ID"""
        invalid_session_id = 'invalid-session-123'

        with pytest.raises(InvalidSessionError):
            await session_service.validate_session(invalid_session_id)

    async def test_validate_session_format(self, session_service):
        """Should reject malformed session IDs"""
        malformed_ids = ['', None, 'short', 'invalid@format', '../../etc/passwd']

        for session_id in malformed_ids:
            with pytest.raises(InvalidSessionError):
                await session_service.validate_session(session_id)


class TestSessionRefresh:
    """Test session refresh and extension"""

    @pytest.fixture
    def session_service(self):
        return SessionService()

    async def test_refresh_session_success(self, session_service):
        """Should extend session expiration time"""
        user_data = {'user_id': 'user123', 'email': 'test@example.com'}
        session = await session_service.create_session(user_data, ttl=3600)

        original_expiry = datetime.fromisoformat(session['expires_at'])

        # Refresh session
        refreshed = await session_service.refresh_session(session['session_id'])
        new_expiry = datetime.fromisoformat(refreshed['expires_at'])

        assert new_expiry > original_expiry

    async def test_refresh_expired_session_fails(self, session_service):
        """Should not allow refreshing expired session"""
        user_data = {'user_id': 'user123', 'email': 'test@example.com'}
        session = await session_service.create_session(user_data, ttl=1)

        await asyncio.sleep(2)

        with pytest.raises(SessionExpiredError):
            await session_service.refresh_session(session['session_id'])


class TestSessionDestruction:
    """Test session termination and cleanup"""

    @pytest.fixture
    def session_service(self):
        return SessionService()

    async def test_destroy_session_success(self, session_service):
        """Should successfully destroy active session"""
        user_data = {'user_id': 'user123', 'email': 'test@example.com'}
        session = await session_service.create_session(user_data)

        result = await session_service.destroy_session(session['session_id'])

        assert result is True

        # Verify session is destroyed
        with pytest.raises(InvalidSessionError):
            await session_service.validate_session(session['session_id'])

    async def test_destroy_nonexistent_session(self, session_service):
        """Should handle destroying non-existent session gracefully"""
        result = await session_service.destroy_session('nonexistent-123')

        assert result is False

    async def test_destroy_all_user_sessions(self, session_service):
        """Should destroy all sessions for a user"""
        user_data = {'user_id': 'user123', 'email': 'test@example.com'}

        # Create multiple sessions
        session1 = await session_service.create_session(user_data)
        session2 = await session_service.create_session(user_data)
        session3 = await session_service.create_session(user_data)

        destroyed_count = await session_service.destroy_user_sessions('user123')

        assert destroyed_count == 3


class TestSessionQuery:
    """Test session querying and retrieval"""

    @pytest.fixture
    def session_service(self):
        return SessionService()

    async def test_get_session_data(self, session_service):
        """Should retrieve complete session data"""
        user_data = {'user_id': 'user123', 'email': 'test@example.com', 'name': 'Test User'}
        session = await session_service.create_session(user_data)

        retrieved = await session_service.get_session(session['session_id'])

        assert retrieved['user_id'] == 'user123'
        assert retrieved['email'] == 'test@example.com'
        assert retrieved['name'] == 'Test User'

    async def test_list_user_sessions(self, session_service):
        """Should list all active sessions for user"""
        user_data = {'user_id': 'user123', 'email': 'test@example.com'}

        await session_service.create_session(user_data)
        await session_service.create_session(user_data)

        sessions = await session_service.list_user_sessions('user123')

        assert len(sessions) == 2


class TestSessionSecurity:
    """Test session security features"""

    @pytest.fixture
    def session_service(self):
        return SessionService()

    async def test_session_id_uniqueness(self, session_service):
        """Should generate unique session IDs"""
        user_data = {'user_id': 'user123', 'email': 'test@example.com'}

        session_ids = set()
        for _ in range(100):
            session = await session_service.create_session(user_data)
            session_ids.add(session['session_id'])

        assert len(session_ids) == 100

    async def test_session_id_cryptographic_strength(self, session_service):
        """Should generate cryptographically strong session IDs"""
        user_data = {'user_id': 'user123', 'email': 'test@example.com'}
        session = await session_service.create_session(user_data)

        session_id = session['session_id']

        # Should be long enough
        assert len(session_id) >= 32

        # Should contain mix of characters
        assert any(c.isalpha() for c in session_id)
        assert any(c.isdigit() for c in session_id)
