"""
Test configuration and fixtures for backend tests.

Provides common fixtures for database testing, authentication,
session management, and security testing.
"""

import pytest
import asyncio
import redis
from unittest.mock import Mock, AsyncMock, patch
from typing import AsyncGenerator, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from fastapi.testclient import TestClient
import httpx
import json
import os
import tempfile
from datetime import datetime, timedelta

from app.config import settings
from app.core.database import Base
from tests.helpers.jwt_helper import jwt_helper

# Import session service if available
try:
    from app.services.session_service import SessionService
except ImportError:
    SessionService = None

# Import main app if available
try:
    from app.main import app
except ImportError:
    app = None


# Event loop fixture for pytest-asyncio
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Test database engine
@pytest.fixture(scope="session")
def test_engine():
    """
    Create test database engine.

    Uses the same DATABASE_URL as production but with a synchronous connection
    for test setup/teardown.
    """
    # Convert async URL to sync if needed
    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    elif database_url.startswith("postgresql://"):
        # Add psycopg driver for Python 3.13 compatibility
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://")

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        echo=False  # Set to True for SQL debugging
    )

    yield engine

    engine.dispose()


# Async test database engine
@pytest.fixture(scope="session")
async def async_test_engine():
    """
    Create async test database engine.

    For async tests that require AsyncEngine.
    """
    # Convert to async URL if needed
    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql+psycopg://"):
        database_url = database_url.replace("postgresql+psycopg://", "postgresql+asyncpg://")
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
        echo=False,
        poolclass=NullPool,  # Disable connection pooling for tests
        connect_args={
            "server_settings": {
                "jit": "off"  # Disable JIT for faster tests
            },
            "statement_cache_size": 0  # Disable prepared statements for direct connection
        }
    )

    yield engine

    await engine.dispose()


# Synchronous session fixture
@pytest.fixture
def db_session(test_engine):
    """
    Create a synchronous database session for testing.

    Provides a clean transaction that is rolled back after each test.
    """
    connection = test_engine.connect()
    transaction = connection.begin()

    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=connection
    )
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# Async session fixture
@pytest.fixture
async def async_db_session(async_test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create an async database session for testing.

    Provides a clean async transaction that is rolled back after each test.
    """
    async with async_test_engine.connect() as connection:
        async with connection.begin() as transaction:
            SessionLocal = async_sessionmaker(
                connection,
                class_=AsyncSession,
                expire_on_commit=False
            )

            async with SessionLocal() as session:
                yield session

            await transaction.rollback()


# RLS context helper
@pytest.fixture
def set_rls_context():
    """
    Helper fixture to set RLS context in a session.

    Usage:
        def test_something(db_session, set_rls_context):
            set_rls_context(db_session, firebase_uid="test_uid_123")
            # Now queries will use RLS context
    """
    def _set_context(session, firebase_uid: str, role: str = "authenticated"):
        """
        Set RLS context for a session.

        Args:
            session: Database session (sync or async)
            firebase_uid: Firebase user ID
            role: User role (default: "authenticated")
        """
        jwt_claims = f'{{"sub": "{firebase_uid}", "role": "{role}"}}'

        # For sync sessions
        if hasattr(session, 'execute'):
            session.execute(
                text("SELECT set_config('request.jwt.claims', :jwt_claims, true);"),
                {"jwt_claims": jwt_claims}
            )
            session.commit()

    return _set_context


# Async RLS context helper
@pytest.fixture
def set_async_rls_context():
    """
    Helper fixture to set RLS context in an async session.

    Usage:
        async def test_something(async_db_session, set_async_rls_context):
            await set_async_rls_context(async_db_session, firebase_uid="test_uid_123")
            # Now queries will use RLS context
    """
    async def _set_context(session: AsyncSession, firebase_uid: str, role: str = "authenticated"):
        """
        Set RLS context for an async session.

        Args:
            session: Async database session
            firebase_uid: Firebase user ID
            role: User role (default: "authenticated")
        """
        jwt_claims = f'{{"sub": "{firebase_uid}", "role": "{role}"}}'

        await session.execute(
            text("SELECT set_config('request.jwt.claims', :jwt_claims, true);"),
            {"jwt_claims": jwt_claims}
        )
        await session.commit()

    return _set_context


# Test user fixtures
@pytest.fixture
def test_doctor_firebase_uid():
    """Firebase UID for test doctor."""
    return "test_firebase_doctor_001"


@pytest.fixture
def test_admin_firebase_uid():
    """Firebase UID for test admin."""
    return "test_firebase_admin_001"


# Cleanup fixture
@pytest.fixture(autouse=True)
def cleanup_after_test(db_session):
    """
    Automatically cleanup after each test.

    Runs after every test to ensure clean state.
    """
    yield

    # Cleanup happens in session fixture via rollback
    # Additional cleanup can be added here if needed


# ============================================================================
# API TESTING FIXTURES (for RLS testing via HTTP)
# ============================================================================

@pytest.fixture(scope="session")
def api_base_url() -> str:
    """
    Base URL for API testing.

    Returns:
        Base URL for the backend API
    """
    # Use environment variable if available, otherwise default to localhost
    import os
    return os.getenv("API_BASE_URL", "http://localhost:8000")


@pytest.fixture
def doctor_a_credentials() -> Dict[str, str]:
    """
    Create credentials for Doctor A (for isolation testing).

    Returns:
        Dictionary with firebase_uid, email, name, and JWT token
    """
    return jwt_helper.create_doctor_token(
        doctor_id="firebase_doctor_a_test",
        email="doctor.a@test.clinica.com",
        name="Dr. Alice Test"
    )


@pytest.fixture
def doctor_b_credentials() -> Dict[str, str]:
    """
    Create credentials for Doctor B (for isolation testing).

    Returns:
        Dictionary with firebase_uid, email, name, and JWT token
    """
    return jwt_helper.create_doctor_token(
        doctor_id="firebase_doctor_b_test",
        email="doctor.b@test.clinica.com",
        name="Dr. Bob Test"
    )


@pytest.fixture
def admin_credentials() -> Dict[str, str]:
    """
    Create credentials for Admin user.

    Returns:
        Dictionary with firebase_uid, email, and JWT token
    """
    return jwt_helper.create_admin_token(
        admin_id="firebase_admin_test",
        email="admin@test.clinica.com"
    )


@pytest.fixture
def expired_token_credentials() -> Dict[str, str]:
    """
    Create expired JWT token for testing authentication failures.

    Returns:
        Dictionary with expired JWT token
    """
    expired_token = jwt_helper.create_expired_token(
        firebase_uid="firebase_expired_test",
        email="expired@test.clinica.com"
    )
    return {
        "firebase_uid": "firebase_expired_test",
        "email": "expired@test.clinica.com",
        "token": expired_token
    }


@pytest.fixture
async def http_client(api_base_url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Create HTTP client for API testing.

    Args:
        api_base_url: Base URL for API

    Yields:
        Async HTTP client configured for API testing
    """
    async with httpx.AsyncClient(
        base_url=api_base_url,
        timeout=30.0,
        follow_redirects=True
    ) as client:
        yield client


@pytest.fixture
def auth_headers() -> callable:
    """
    Helper to create authorization headers from credentials.

    Returns:
        Function that takes credentials dict and returns headers dict
    """
    def _create_headers(credentials: Dict[str, str]) -> Dict[str, str]:
        """Create auth headers from credentials."""
        return {
            "Authorization": f"Bearer {credentials['token']}",
            "Content-Type": "application/json"
        }

    return _create_headers


# ============================================================================
# ADDITIONAL FIXTURES FOR WAVE 2 PHASE 2 ENDPOINT TESTS
# ============================================================================

@pytest.fixture
def medico_credentials() -> Dict[str, str]:
    """
    Create credentials for a medico/doctor user.

    Returns:
        Dictionary with firebase_uid, email, and JWT token
    """
    return jwt_helper.create_doctor_token(
        doctor_id="firebase_medico_test",
        email="medico@test.clinica.com",
        name="Dr. Medico Test"
    )


@pytest.fixture
def physician_credentials() -> Dict[str, str]:
    """
    Create credentials for a physician user (alias for doctor).

    Returns:
        Dictionary with firebase_uid, email, and JWT token
    """
    return jwt_helper.create_doctor_token(
        doctor_id="firebase_physician_test",
        email="physician@test.clinica.com",
        name="Dr. Physician Test"
    )


@pytest.fixture
def empty_db(db_session):
    """
    Empty database for testing edge cases.

    Clears all test data from key tables.
    """
    from app.models.patient import Patient
    from app.models.alert import Alert
    from app.models.message import Message
    from app.models.user import User

    # Clear tables (order matters due to foreign keys)
    db_session.query(Alert).delete()
    db_session.query(Message).delete()
    db_session.query(Patient).delete()
    # Don't delete users as auth fixtures need them
    db_session.commit()

    yield db_session

    # Cleanup happens automatically via session rollback


# ============================================================================
# SESSION MANAGEMENT TESTING FIXTURES
# ============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock_redis = Mock()

    # Mock Redis methods
    mock_redis.get = Mock(return_value=None)
    mock_redis.set = Mock(return_value=True)
    mock_redis.delete = Mock(return_value=1)
    mock_redis.exists = Mock(return_value=0)
    mock_redis.expire = Mock(return_value=True)
    mock_redis.ttl = Mock(return_value=3600)
    mock_redis.flushdb = Mock(return_value=True)

    # Mock pipeline
    mock_pipeline = Mock()
    mock_pipeline.set = Mock(return_value=mock_pipeline)
    mock_pipeline.expire = Mock(return_value=mock_pipeline)
    mock_pipeline.execute = Mock(return_value=[True, True])
    mock_redis.pipeline = Mock(return_value=mock_pipeline)

    return mock_redis


@pytest.fixture
def session_service(mock_redis):
    """Session service with mocked Redis."""
    if SessionService is None:
        # Create mock session service if not available
        mock_service = Mock()
        mock_service.create_session = AsyncMock(return_value="test-session-123")
        mock_service.validate_session = AsyncMock(return_value=True)
        mock_service.get_session = AsyncMock(return_value={"user_id": "test-user"})
        mock_service.delete_session = AsyncMock(return_value=True)
        mock_service.cleanup_expired_sessions = AsyncMock(return_value=5)
        return mock_service

    with patch('app.services.session_service.redis_client', mock_redis):
        service = SessionService()
        yield service


@pytest.fixture
def test_client():
    """FastAPI test client."""
    if app is None:
        # Mock client if app not available
        return Mock()

    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "id": "test-user-123",
        "email": "test@example.com",
        "name": "Test User",
        "role": "user",
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_session_data(sample_user_data):
    """Sample session data for testing."""
    return {
        "session_id": "test-session-123",
        "user_id": sample_user_data["id"],
        "user_data": sample_user_data,
        "created_at": datetime.utcnow().isoformat(),
        "last_accessed": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
        "csrf_token": "test-csrf-token-123",
        "ip_address": "127.0.0.1",
        "user_agent": "test-agent"
    }


@pytest.fixture
def mock_firebase_auth():
    """Mock Firebase authentication."""
    with patch('firebase_admin.auth') as mock_auth:
        mock_auth.verify_id_token = Mock(return_value={
            "uid": "firebase-user-123",
            "email": "test@example.com",
            "email_verified": True,
            "name": "Test User"
        })
        mock_auth.create_custom_token = Mock(return_value=b"custom-token")
        mock_auth.get_user = Mock(return_value=Mock(
            uid="firebase-user-123",
            email="test@example.com",
            display_name="Test User"
        ))
        yield mock_auth


@pytest.fixture
def rate_limit_storage():
    """In-memory storage for rate limiting tests."""
    return {}


@pytest.fixture
def mock_rate_limiter(rate_limit_storage):
    """Mock rate limiter."""
    class MockRateLimiter:
        def __init__(self, storage):
            self.storage = storage

        def is_allowed(self, key: str, limit: int, window: int) -> bool:
            now = datetime.utcnow().timestamp()
            if key not in self.storage:
                self.storage[key] = []

            # Remove old entries
            self.storage[key] = [
                timestamp for timestamp in self.storage[key]
                if now - timestamp < window
            ]

            if len(self.storage[key]) >= limit:
                return False

            self.storage[key].append(now)
            return True

        def reset(self, key: str):
            if key in self.storage:
                del self.storage[key]

    return MockRateLimiter(rate_limit_storage)


@pytest.fixture
def security_test_payloads():
    """Common security test payloads."""
    return {
        "sql_injection": [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "1; DELETE FROM sessions WHERE 1=1; --",
            "admin'--",
            "' OR 1=1#"
        ],
        "xss_payloads": [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "';alert('XSS');//"
        ],
        "csrf_tokens": [
            "",
            "invalid-token",
            "token-with-wrong-format",
            "expired-token-123",
            None
        ],
        "session_ids": [
            "",
            "invalid-session",
            "../../etc/passwd",
            "../admin",
            None
        ]
    }


@pytest.fixture
def performance_timer():
    """Timer for performance testing."""
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = datetime.utcnow()

        def stop(self):
            self.end_time = datetime.utcnow()
            return (self.end_time - self.start_time).total_seconds()

        def elapsed(self):
            if self.start_time and self.end_time:
                return (self.end_time - self.start_time).total_seconds()
            return None

    return Timer()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "security: mark test as security-related"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance-related"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )


# Custom assertions
def assert_response_time(response_time: float, max_time: float = 1.0):
    """Assert response time is within acceptable limits."""
    assert response_time <= max_time, f"Response time {response_time}s exceeds maximum {max_time}s"


def assert_no_sql_injection(response_data: Any):
    """Assert response doesn't contain SQL injection indicators."""
    response_str = str(response_data).lower()
    sql_keywords = ['drop', 'delete', 'insert', 'update', 'select', 'union', 'or 1=1']
    for keyword in sql_keywords:
        assert keyword not in response_str, f"Potential SQL injection detected: {keyword}"


def assert_no_xss(response_data: Any):
    """Assert response doesn't contain XSS indicators."""
    response_str = str(response_data)
    xss_patterns = ['<script', 'javascript:', 'onerror=', 'onload=']
    for pattern in xss_patterns:
        assert pattern not in response_str, f"Potential XSS detected: {pattern}"
