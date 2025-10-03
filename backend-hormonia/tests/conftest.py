"""
Test configuration and fixtures for backend tests.

Provides common fixtures for database testing, authentication,
and RLS context setup.
"""

import pytest
import asyncio
from typing import AsyncGenerator, Dict
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import httpx

from app.config import settings
from app.core.database import Base
from tests.helpers.jwt_helper import jwt_helper


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
