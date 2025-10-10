"""
Integration tests for authentication system.

Tests complete authentication flows including session management,
Redis integration, Firebase token validation, and security features.
"""

import pytest
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, AsyncGenerator
from unittest.mock import Mock, AsyncMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.application_factory import create_application as create_app
from app.core.database import get_db
from app.models.base import Base
from app.models.user import User, UserRole
from app.core.redis_manager import FirebaseRedisCache, get_redis_manager
from app.core.config import settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db():
    """Create test database with in-memory SQLite."""
    # Use in-memory SQLite for testing
    SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create all tables
    Base.metadata.create_all(bind=engine)

    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
async def test_redis():
    """Create test Redis instance using fake Redis."""
    try:
        import fakeredis

        # Create fake Redis server
        redis_server = fakeredis.FakeServer()
        fake_redis = fakeredis.FakeRedis(server=redis_server, decode_responses=True)

        yield fake_redis

        # Cleanup
        fake_redis.flushall()
    except ImportError:
        pytest.skip("fakeredis not available")


@pytest.fixture
async def test_firebase_cache(test_redis):
    """Create FirebaseRedisCache with test Redis."""
    return FirebaseRedisCache(test_redis)


@pytest.fixture
async def test_app(test_db, test_redis):
    """Create test FastAPI application."""
    app = create_app()

    # Override database dependency
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    return app


@pytest.fixture
async def test_client(test_app):
    """Create test client."""
    with TestClient(test_app) as client:
        yield client


@pytest.fixture
async def test_user(test_db):
    """Create test user in database."""
    user = User(
        firebase_uid="test-firebase-uid",
        email="test@example.com",
        full_name="Test User",
        role=UserRole.DOCTOR,
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def mock_firebase_token():
    """Mock Firebase token validation."""
    return {
        "uid": "test-firebase-uid",
        "email": "test@example.com",
        "name": "Test User",
        "picture": "https://example.com/photo.jpg"
    }


class TestSessionFlow:
    """Test complete session management flow."""

    @pytest.mark.asyncio
    async def test_create_session_complete_flow(
        self,
        test_client,
        test_user,
        test_firebase_cache,
        mock_firebase_token
    ):
        """Test complete session creation flow."""
        with patch('app.routers.auth.verify_firebase_token', return_value=mock_firebase_token):
            with patch('app.routers.auth.get_redis_cache', return_value=test_firebase_cache):

                # Create session
                response = test_client.post(
                    "/api/v1/auth/session",
                    json={"id_token": "valid-firebase-token"},
                    headers={"Content-Type": "application/json"}
                )

                assert response.status_code == 201
                data = response.json()

                # Verify response structure
                assert "session_id" in data
                assert "user" in data
                assert "expires_in" in data

                # Verify user data
                user_data = data["user"]
                assert user_data["email"] == test_user.email
                assert user_data["firebase_uid"] == test_user.firebase_uid
                assert user_data["role"] == test_user.role.value

                # Verify session was created in Redis
                session_id = data["session_id"]
                session_data = await test_firebase_cache.get_session(session_id)
                assert session_data is not None
                assert session_data["firebase_uid"] == test_user.firebase_uid

    @pytest.mark.asyncio
    async def test_session_validation_flow(
        self,
        test_client,
        test_user,
        test_firebase_cache
    ):
        """Test session validation flow."""
        # Create session directly in Redis
        session_id = str(uuid.uuid4())
        await test_firebase_cache.create_session(
            session_id=session_id,
            user_id=str(test_user.id),
            firebase_uid=test_user.firebase_uid,
            ttl=3600
        )

        # Cache user data
        user_data = {
            "firebase_uid": test_user.firebase_uid,
            "email": test_user.email,
            "full_name": test_user.full_name,
            "role": test_user.role.value,
            "is_active": test_user.is_active,
            "id": str(test_user.id)
        }
        await test_firebase_cache.cache_user_data(test_user.firebase_uid, user_data)

        with patch('app.dependencies.auth_dependencies.get_redis_cache', return_value=test_firebase_cache):
            # Test /me endpoint
            response = test_client.get(
                "/api/v1/auth/me",
                headers={"X-Session-ID": session_id}
            )

            assert response.status_code == 200
            data = response.json()

            assert data["email"] == test_user.email
            assert data["firebase_uid"] == test_user.firebase_uid

    @pytest.mark.asyncio
    async def test_logout_flow(
        self,
        test_client,
        test_user,
        test_firebase_cache
    ):
        """Test logout flow."""
        # Create session
        session_id = str(uuid.uuid4())
        await test_firebase_cache.create_session(
            session_id=session_id,
            user_id=str(test_user.id),
            firebase_uid=test_user.firebase_uid,
            ttl=3600
        )

        with patch('app.routers.auth.get_redis_cache', return_value=test_firebase_cache):
            # Logout
            response = test_client.post(
                "/api/v1/auth/logout",
                headers={"X-Session-ID": session_id}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Logout successful"

            # Verify session was deleted from Redis
            session_data = await test_firebase_cache.get_session(session_id)
            assert session_data is None

    @pytest.mark.asyncio
    async def test_logout_all_flow(
        self,
        test_client,
        test_user,
        test_firebase_cache
    ):
        """Test logout all sessions flow."""
        # Create multiple sessions
        session_ids = []
        for i in range(3):
            session_id = str(uuid.uuid4())
            await test_firebase_cache.create_session(
                session_id=session_id,
                user_id=str(test_user.id),
                firebase_uid=test_user.firebase_uid,
                ttl=3600
            )
            session_ids.append(session_id)

        # Cache user data for authentication
        user_data = {
            "firebase_uid": test_user.firebase_uid,
            "email": test_user.email,
            "full_name": test_user.full_name,
            "role": test_user.role.value,
            "is_active": test_user.is_active,
            "id": str(test_user.id)
        }
        await test_firebase_cache.cache_user_data(test_user.firebase_uid, user_data)

        with patch('app.routers.auth.get_redis_cache', return_value=test_firebase_cache):
            with patch('app.dependencies.auth_dependencies.get_redis_cache', return_value=test_firebase_cache):
                # Logout all
                response = test_client.post(
                    "/api/v1/auth/logout-all",
                    headers={"X-Session-ID": session_ids[0]}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["sessions_deleted"] == 3

                # Verify all sessions were deleted
                for session_id in session_ids:
                    session_data = await test_firebase_cache.get_session(session_id)
                    assert session_data is None


class TestErrorHandling:
    """Test error handling in authentication flows."""

    @pytest.mark.asyncio
    async def test_invalid_firebase_token(self, test_client):
        """Test session creation with invalid Firebase token."""
        with patch('app.routers.auth.verify_firebase_token', return_value=None):
            response = test_client.post(
                "/api/v1/auth/session",
                json={"id_token": "invalid-token"},
                headers={"Content-Type": "application/json"}
            )

            assert response.status_code == 401
            data = response.json()
            assert "Invalid or expired Firebase token" in data["detail"]

    @pytest.mark.asyncio
    async def test_inactive_user_session(
        self,
        test_client,
        test_db,
        test_firebase_cache,
        mock_firebase_token
    ):
        """Test session creation with inactive user."""
        # Create inactive user
        inactive_user = User(
            firebase_uid="inactive-firebase-uid",
            email="inactive@example.com",
            full_name="Inactive User",
            role=UserRole.DOCTOR,
            is_active=False
        )
        test_db.add(inactive_user)
        test_db.commit()
        test_db.refresh(inactive_user)

        # Mock Firebase token for inactive user
        inactive_token = {
            "uid": "inactive-firebase-uid",
            "email": "inactive@example.com",
            "name": "Inactive User"
        }

        with patch('app.routers.auth.verify_firebase_token', return_value=inactive_token):
            with patch('app.routers.auth.get_redis_cache', return_value=test_firebase_cache):
                response = test_client.post(
                    "/api/v1/auth/session",
                    json={"id_token": "valid-token"},
                    headers={"Content-Type": "application/json"}
                )

                assert response.status_code == 403
                data = response.json()
                assert "User account is inactive" in data["detail"]

    @pytest.mark.asyncio
    async def test_invalid_session_validation(
        self,
        test_client,
        test_firebase_cache
    ):
        """Test authentication with invalid session."""
        invalid_session_id = str(uuid.uuid4())

        with patch('app.dependencies.auth_dependencies.get_redis_cache', return_value=test_firebase_cache):
            response = test_client.get(
                "/api/v1/auth/me",
                headers={"X-Session-ID": invalid_session_id}
            )

            assert response.status_code == 401
            data = response.json()
            assert "Invalid or expired session" in data["detail"]

    @pytest.mark.asyncio
    async def test_missing_session_id(self, test_client):
        """Test authentication without session ID."""
        response = test_client.get("/api/v1/auth/me")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_redis_connection_failure(self, test_client, mock_firebase_token):
        """Test session creation with Redis connection failure."""
        # Mock Redis cache that fails
        failing_cache = AsyncMock(spec=FirebaseRedisCache)
        failing_cache.get_or_create_user.return_value = None

        with patch('app.routers.auth.verify_firebase_token', return_value=mock_firebase_token):
            with patch('app.routers.auth.get_redis_cache', return_value=failing_cache):
                response = test_client.post(
                    "/api/v1/auth/session",
                    json={"id_token": "valid-token"},
                    headers={"Content-Type": "application/json"}
                )

                assert response.status_code == 500


class TestSecurityFeatures:
    """Test security features of authentication system."""

    @pytest.mark.asyncio
    async def test_session_expiration(
        self,
        test_client,
        test_user,
        test_firebase_cache
    ):
        """Test session expiration behavior."""
        # Create session with short TTL
        session_id = str(uuid.uuid4())
        await test_firebase_cache.create_session(
            session_id=session_id,
            user_id=str(test_user.id),
            firebase_uid=test_user.firebase_uid,
            ttl=1  # 1 second TTL
        )

        # Wait for expiration
        await asyncio.sleep(2)

        with patch('app.dependencies.auth_dependencies.get_redis_cache', return_value=test_firebase_cache):
            response = test_client.get(
                "/api/v1/auth/me",
                headers={"X-Session-ID": session_id}
            )

            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_session_activity_update(
        self,
        test_client,
        test_user,
        test_firebase_cache
    ):
        """Test that session activity is updated on access."""
        # Create session
        session_id = str(uuid.uuid4())
        await test_firebase_cache.create_session(
            session_id=session_id,
            user_id=str(test_user.id),
            firebase_uid=test_user.firebase_uid,
            ttl=3600
        )

        # Cache user data
        user_data = {
            "firebase_uid": test_user.firebase_uid,
            "email": test_user.email,
            "full_name": test_user.full_name,
            "role": test_user.role.value,
            "is_active": test_user.is_active,
            "id": str(test_user.id)
        }
        await test_firebase_cache.cache_user_data(test_user.firebase_uid, user_data)

        # Get initial session data
        initial_session = await test_firebase_cache.get_session(session_id)
        initial_activity = initial_session["last_activity"]

        # Wait a moment
        await asyncio.sleep(0.1)

        with patch('app.dependencies.auth_dependencies.get_redis_cache', return_value=test_firebase_cache):
            response = test_client.get(
                "/api/v1/auth/me",
                headers={"X-Session-ID": session_id}
            )

            assert response.status_code == 200

            # Check that activity was updated
            updated_session = await test_firebase_cache.get_session(session_id)
            updated_activity = updated_session["last_activity"]

            assert updated_activity > initial_activity

    @pytest.mark.asyncio
    async def test_concurrent_sessions(
        self,
        test_client,
        test_user,
        test_firebase_cache,
        mock_firebase_token
    ):
        """Test multiple concurrent sessions for same user."""
        sessions = []

        with patch('app.routers.auth.verify_firebase_token', return_value=mock_firebase_token):
            with patch('app.routers.auth.get_redis_cache', return_value=test_firebase_cache):

                # Create multiple sessions
                for i in range(3):
                    response = test_client.post(
                        "/api/v1/auth/session",
                        json={"id_token": "valid-token"},
                        headers={"Content-Type": "application/json"}
                    )

                    assert response.status_code == 201
                    data = response.json()
                    sessions.append(data["session_id"])

                # Verify all sessions are valid
                for session_id in sessions:
                    session_data = await test_firebase_cache.get_session(session_id)
                    assert session_data is not None
                    assert session_data["firebase_uid"] == test_user.firebase_uid

    @pytest.mark.asyncio
    async def test_session_isolation(
        self,
        test_client,
        test_db,
        test_firebase_cache
    ):
        """Test that sessions are isolated between users."""
        # Create two users
        user1 = User(
            firebase_uid="user1-firebase-uid",
            email="user1@example.com",
            full_name="User One",
            role=UserRole.DOCTOR,
            is_active=True
        )
        user2 = User(
            firebase_uid="user2-firebase-uid",
            email="user2@example.com",
            full_name="User Two",
            role=UserRole.ADMIN,
            is_active=True
        )
        test_db.add(user1)
        test_db.add(user2)
        test_db.commit()
        test_db.refresh(user1)
        test_db.refresh(user2)

        # Create sessions for both users
        session1 = str(uuid.uuid4())
        session2 = str(uuid.uuid4())

        await test_firebase_cache.create_session(
            session_id=session1,
            user_id=str(user1.id),
            firebase_uid=user1.firebase_uid,
            ttl=3600
        )

        await test_firebase_cache.create_session(
            session_id=session2,
            user_id=str(user2.id),
            firebase_uid=user2.firebase_uid,
            ttl=3600
        )

        # Cache user data
        await test_firebase_cache.cache_user_data(user1.firebase_uid, {
            "firebase_uid": user1.firebase_uid,
            "email": user1.email,
            "role": user1.role.value,
            "is_active": True,
            "id": str(user1.id)
        })

        await test_firebase_cache.cache_user_data(user2.firebase_uid, {
            "firebase_uid": user2.firebase_uid,
            "email": user2.email,
            "role": user2.role.value,
            "is_active": True,
            "id": str(user2.id)
        })

        with patch('app.dependencies.auth_dependencies.get_redis_cache', return_value=test_firebase_cache):
            # Test user1 session
            response1 = test_client.get(
                "/api/v1/auth/me",
                headers={"X-Session-ID": session1}
            )

            assert response1.status_code == 200
            data1 = response1.json()
            assert data1["email"] == user1.email
            assert data1["role"] == user1.role.value

            # Test user2 session
            response2 = test_client.get(
                "/api/v1/auth/me",
                headers={"X-Session-ID": session2}
            )

            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["email"] == user2.email
            assert data2["role"] == user2.role.value

            # Verify sessions are isolated
            assert data1["email"] != data2["email"]
            assert data1["firebase_uid"] != data2["firebase_uid"]


class TestCacheIntegration:
    """Test Redis cache integration."""

    @pytest.mark.asyncio
    async def test_user_cache_hit(
        self,
        test_client,
        test_user,
        test_firebase_cache
    ):
        """Test user data cache hit scenario."""
        # Pre-populate user cache
        user_data = {
            "firebase_uid": test_user.firebase_uid,
            "email": test_user.email,
            "full_name": test_user.full_name,
            "role": test_user.role.value,
            "is_active": test_user.is_active,
            "id": str(test_user.id)
        }
        await test_firebase_cache.cache_user_data(test_user.firebase_uid, user_data)

        # Create session
        session_id = str(uuid.uuid4())
        await test_firebase_cache.create_session(
            session_id=session_id,
            user_id=str(test_user.id),
            firebase_uid=test_user.firebase_uid,
            ttl=3600
        )

        with patch('app.dependencies.auth_dependencies.get_redis_cache', return_value=test_firebase_cache):
            # Should use cached data, not hit database
            response = test_client.get(
                "/api/v1/auth/me",
                headers={"X-Session-ID": session_id}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["email"] == test_user.email

    @pytest.mark.asyncio
    async def test_token_cache_integration(self, test_firebase_cache):
        """Test Firebase token caching."""
        token = "test-firebase-token"
        firebase_data = {
            "uid": "test-firebase-uid",
            "email": "test@example.com",
            "name": "Test User"
        }

        # Cache token
        test_firebase_cache.cache_validated_token(token, firebase_data)

        # Retrieve cached token
        cached_data = test_firebase_cache.get_cached_token(token)

        assert cached_data is not None
        assert cached_data["firebase_uid"] == firebase_data["uid"]
        assert cached_data["email"] == firebase_data["email"]


class TestPerformance:
    """Test performance aspects of authentication."""

    @pytest.mark.asyncio
    async def test_cache_performance(self, test_firebase_cache):
        """Test that caching improves performance."""
        firebase_uid = "performance-test-uid"

        # Measure cache miss (should be slower)
        start_time = datetime.utcnow()
        result_miss = await test_firebase_cache.get_user_by_uid(firebase_uid)
        miss_duration = (datetime.utcnow() - start_time).total_seconds()

        assert result_miss is None

        # Cache data
        user_data = {
            "firebase_uid": firebase_uid,
            "email": "performance@example.com",
            "role": "doctor",
            "is_active": True
        }
        await test_firebase_cache.cache_user_data(firebase_uid, user_data)

        # Measure cache hit (should be faster)
        start_time = datetime.utcnow()
        result_hit = await test_firebase_cache.get_user_by_uid(firebase_uid)
        hit_duration = (datetime.utcnow() - start_time).total_seconds()

        assert result_hit is not None
        assert result_hit["firebase_uid"] == firebase_uid

        # Cache hit should be faster (though in tests with fake Redis,
        # the difference might be minimal)
        assert hit_duration <= miss_duration * 2  # Allow some variance


if __name__ == "__main__":
    pytest.main([__file__, "-v"])