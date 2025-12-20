"""
Authentication Test Fixtures

Specialized fixtures for authentication testing including:
- Mock Firebase services
- Redis cache mocks
- Session fixtures
- User fixtures with various states
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from sqlalchemy.orm import Session

from app.models.user import User, UserRole, AuthProvider
from app.models.session import Session as SessionModel
from app.utils.security import get_password_hash


# ============================================================================
# User Fixtures
# ============================================================================

@pytest.fixture
def firebase_user(db_session: Session) -> User:
    """Create a user with Firebase authentication."""
    user = User(
        id=uuid4(),
        firebase_uid=f"firebase_{uuid4().hex[:12]}",
        email="firebase_user@clinica.com",
        full_name="Firebase User",
        is_active=True,
        role=UserRole.DOCTOR,
        auth_provider=AuthProvider.FIREBASE,
        firebase_email_verified=True,
        firebase_display_name="Firebase User",
        firebase_created_at=datetime.utcnow(),
        firebase_last_sign_in=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_user(db_session: Session) -> User:
    """Create an inactive user."""
    user = User(
        id=uuid4(),
        email="inactive@clinica.com",
        hashed_password=get_password_hash("Password123!"),
        full_name="Inactive User",
        is_active=False,
        role=UserRole.DOCTOR,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def locked_user(db_session: Session) -> User:
    """Create a locked user."""
    user = User(
        id=uuid4(),
        firebase_uid=f"locked_{uuid4().hex[:12]}",
        email="locked@clinica.com",
        full_name="Locked User",
        is_active=True,
        is_locked=True,
        locked_until=datetime.utcnow() + timedelta(hours=1),
        failed_login_attempts=5,
        role=UserRole.DOCTOR,
        auth_provider=AuthProvider.FIREBASE,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_with_expired_lock(db_session: Session) -> User:
    """Create a user with expired lock."""
    user = User(
        id=uuid4(),
        firebase_uid=f"expired_lock_{uuid4().hex[:12]}",
        email="expired_lock@clinica.com",
        full_name="Expired Lock User",
        is_active=True,
        is_locked=True,
        locked_until=datetime.utcnow() - timedelta(hours=1),  # Expired
        failed_login_attempts=5,
        role=UserRole.DOCTOR,
        auth_provider=AuthProvider.FIREBASE,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ============================================================================
# Session Fixtures
# ============================================================================

@pytest.fixture
def active_session(db_session: Session, test_user: User) -> SessionModel:
    """Create an active session for test_user."""
    session = SessionModel(
        id=uuid4(),
        user_id=test_user.id,
        session_token=f"session_{uuid4().hex}",
        is_active=True,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=5),
        last_activity=datetime.utcnow(),
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0 Test Browser",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


@pytest.fixture
def expired_session(db_session: Session, test_user: User) -> SessionModel:
    """Create an expired session for test_user."""
    session = SessionModel(
        id=uuid4(),
        user_id=test_user.id,
        session_token=f"expired_{uuid4().hex}",
        is_active=True,
        created_at=datetime.utcnow() - timedelta(days=10),
        expires_at=datetime.utcnow() - timedelta(hours=1),
        last_activity=datetime.utcnow() - timedelta(hours=2),
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0 Test Browser",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


@pytest.fixture
def revoked_session(db_session: Session, test_user: User) -> SessionModel:
    """Create a revoked session for test_user."""
    session = SessionModel(
        id=uuid4(),
        user_id=test_user.id,
        session_token=f"revoked_{uuid4().hex}",
        is_active=False,
        created_at=datetime.utcnow() - timedelta(days=1),
        expires_at=datetime.utcnow() + timedelta(days=4),
        last_activity=datetime.utcnow() - timedelta(hours=1),
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0 Test Browser",
        revoked_at=datetime.utcnow() - timedelta(minutes=30),
        revocation_reason="User requested logout",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


@pytest.fixture
def multiple_sessions(db_session: Session, test_user: User) -> list[SessionModel]:
    """Create multiple sessions for test_user (multi-device scenario)."""
    sessions = []
    devices = [
        ("Chrome Desktop", "192.168.1.100"),
        ("Safari Mobile", "192.168.1.101"),
        ("Firefox Laptop", "192.168.1.102"),
    ]

    for user_agent, ip in devices:
        session = SessionModel(
            id=uuid4(),
            user_id=test_user.id,
            session_token=f"multi_{uuid4().hex}",
            is_active=True,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=5),
            last_activity=datetime.utcnow(),
            ip_address=ip,
            user_agent=user_agent,
        )
        db_session.add(session)
        sessions.append(session)

    db_session.commit()
    for s in sessions:
        db_session.refresh(s)

    return sessions


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_firebase_service(mocker):
    """Create mock Firebase service."""
    service = mocker.MagicMock()
    service.verify_token = AsyncMock()
    service.get_user = AsyncMock()
    service.create_user = AsyncMock()
    return service


@pytest.fixture
def mock_redis_cache(mocker):
    """Create mock Redis cache with session methods."""
    cache = mocker.MagicMock()
    cache.create_session = AsyncMock(return_value=True)
    cache.get_session = AsyncMock(return_value=None)
    cache.invalidate_session = AsyncMock(return_value=True)
    cache.invalidate_all_user_sessions = AsyncMock(return_value=0)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.setex = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=1)
    cache.incr = AsyncMock(return_value=1)
    cache.expire = AsyncMock(return_value=True)
    cache.ping = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def mock_rate_limiter(mocker):
    """Create mock rate limiter."""
    limiter = mocker.MagicMock()
    limiter.is_rate_limited = AsyncMock(return_value=False)
    limiter.record_attempt = AsyncMock()
    limiter.clear_attempts = AsyncMock()
    return limiter


# ============================================================================
# Firebase Token Data Fixtures
# ============================================================================

@pytest.fixture
def valid_firebase_token_data() -> dict:
    """Valid Firebase token verification response."""
    return {
        "uid": f"firebase_{uuid4().hex[:12]}",
        "email": "valid@clinica.com",
        "email_verified": True,
        "name": "Valid User",
        "picture": "https://example.com/photo.jpg",
        "custom_claims": {"role": "doctor"},
    }


@pytest.fixture
def admin_firebase_token_data() -> dict:
    """Admin Firebase token verification response."""
    return {
        "uid": f"admin_{uuid4().hex[:12]}",
        "email": "admin@clinica.com",
        "email_verified": True,
        "name": "Admin User",
        "picture": "https://example.com/admin.jpg",
        "custom_claims": {"role": "admin"},
    }


@pytest.fixture
def unverified_email_token_data() -> dict:
    """Firebase token with unverified email."""
    return {
        "uid": f"unverified_{uuid4().hex[:12]}",
        "email": "unverified@clinica.com",
        "email_verified": False,
        "name": "Unverified User",
        "custom_claims": {"role": "doctor"},
    }


# ============================================================================
# Request Context Fixtures
# ============================================================================

@pytest.fixture
def mock_request(mocker):
    """Create mock FastAPI request."""
    request = mocker.MagicMock()
    request.client.host = "192.168.1.100"
    request.headers = {
        "user-agent": "Mozilla/5.0 Test Browser",
        "X-Forwarded-For": "192.168.1.100",
    }
    request.cookies = {}
    return request


@pytest.fixture
def mock_request_with_session(mocker, active_session: SessionModel):
    """Create mock request with session cookie."""
    request = mocker.MagicMock()
    request.client.host = "192.168.1.100"
    request.headers = {
        "user-agent": "Mozilla/5.0 Test Browser",
        "X-Session-ID": str(active_session.id),
    }
    request.cookies = {"session_id": str(active_session.id)}
    return request


# ============================================================================
# Dependency Override Fixtures
# ============================================================================

@pytest.fixture
def override_firebase_verify(mocker, valid_firebase_token_data):
    """Override Firebase token verification."""
    with patch(
        'app.api.v2.routers.auth.verify_token',
        new_callable=AsyncMock
    ) as mock:
        mock.return_value = valid_firebase_token_data
        yield mock


@pytest.fixture
def override_redis_cache(mocker, mock_redis_cache):
    """Override Redis cache dependency."""
    with patch(
        'app.dependencies.auth_dependencies.get_redis_cache'
    ) as mock:
        mock.return_value = mock_redis_cache
        yield mock


# ============================================================================
# Auth Headers Fixtures
# ============================================================================

@pytest.fixture
def firebase_auth_headers(firebase_user: User, client) -> dict:
    """Create auth headers for Firebase user."""
    from app.main import app
    from app.dependencies.auth_dependencies import (
        get_current_user,
        get_current_user_from_session,
        TEST_TOKEN_REGISTRY,
    )

    app.dependency_overrides[get_current_user] = lambda: firebase_user
    app.dependency_overrides[get_current_user_from_session] = lambda: firebase_user
    TEST_TOKEN_REGISTRY[f"firebase_token_{firebase_user.id}"] = firebase_user

    return {"Authorization": f"Bearer firebase_token_{firebase_user.id}"}


@pytest.fixture
def session_auth_headers(test_user: User, active_session: SessionModel, client) -> dict:
    """Create auth headers with session ID."""
    from app.main import app
    from app.dependencies.auth_dependencies import (
        get_current_user_from_session,
        TEST_TOKEN_REGISTRY,
    )

    app.dependency_overrides[get_current_user_from_session] = lambda: test_user
    TEST_TOKEN_REGISTRY[f"session_{active_session.id}"] = test_user

    return {
        "Authorization": f"Bearer session_{active_session.id}",
        "X-Session-ID": str(active_session.id),
    }
