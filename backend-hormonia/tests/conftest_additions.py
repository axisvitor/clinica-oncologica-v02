"""
Additional pytest fixtures for comprehensive testing

This module provides shared fixtures for:
- Database mocking and setup
- Redis client mocking
- Authentication and session management
- API client mocking
- Test data factories
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock
from datetime import datetime, timedelta
import asyncio
from typing import Generator, Any

# ==========================================
# Database Fixtures
# ==========================================

@pytest.fixture
def mock_db_session():
    """Mock SQLAlchemy database session"""
    session = MagicMock()
    session.query = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.flush = MagicMock()
    session.close = MagicMock()
    session.begin = MagicMock()
    session.execute = MagicMock()

    return session


@pytest.fixture
async def async_db_session():
    """Mock async database session"""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    return session


@pytest.fixture
def db_transaction(mock_db_session):
    """Database transaction context manager"""
    class TransactionContext:
        def __enter__(self):
            mock_db_session.begin()
            return mock_db_session

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                mock_db_session.rollback()
            else:
                mock_db_session.commit()

    return TransactionContext()


# ==========================================
# Redis Fixtures
# ==========================================

@pytest.fixture
def mock_redis_client():
    """Mock Redis client with common operations"""
    redis = AsyncMock()

    # String operations
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=False)

    # List operations
    redis.lpush = AsyncMock(return_value=1)
    redis.rpush = AsyncMock(return_value=1)
    redis.lpop = AsyncMock(return_value=None)
    redis.rpop = AsyncMock(return_value=None)
    redis.llen = AsyncMock(return_value=0)
    redis.lrange = AsyncMock(return_value=[])

    # Hash operations
    redis.hget = AsyncMock(return_value=None)
    redis.hset = AsyncMock(return_value=1)
    redis.hgetall = AsyncMock(return_value={})
    redis.hdel = AsyncMock(return_value=1)

    # Set operations
    redis.sadd = AsyncMock(return_value=1)
    redis.srem = AsyncMock(return_value=1)
    redis.smembers = AsyncMock(return_value=set())

    # Sorted set operations
    redis.zadd = AsyncMock(return_value=1)
    redis.zrange = AsyncMock(return_value=[])
    redis.zrem = AsyncMock(return_value=1)

    # Key operations
    redis.expire = AsyncMock(return_value=True)
    redis.ttl = AsyncMock(return_value=-1)
    redis.incr = AsyncMock(return_value=1)
    redis.decr = AsyncMock(return_value=0)

    # Pub/Sub operations
    redis.publish = AsyncMock(return_value=0)

    # Pipeline
    redis.pipeline = MagicMock(return_value=redis)
    redis.execute = AsyncMock(return_value=[])

    return redis


@pytest.fixture
def redis_storage(mock_redis_client):
    """Redis storage with helper methods"""
    storage = {}

    async def get(key: str) -> Any:
        return storage.get(key)

    async def set(key: str, value: Any, ex: int = None) -> bool:
        storage[key] = value
        return True

    async def delete(key: str) -> int:
        if key in storage:
            del storage[key]
            return 1
        return 0

    mock_redis_client.get = get
    mock_redis_client.set = set
    mock_redis_client.delete = delete

    return mock_redis_client


# ==========================================
# Authentication Fixtures
# ==========================================

@pytest.fixture
def mock_user():
    """Mock user object"""
    return {
        'id': 'user-123',
        'email': 'test@example.com',
        'name': 'Test User',
        'role': 'user',
        'is_active': True,
        'permissions': ['read', 'write'],
        'created_at': datetime.utcnow()
    }


@pytest.fixture
def mock_admin_user():
    """Mock admin user object"""
    return {
        'id': 'admin-123',
        'email': 'admin@example.com',
        'name': 'Admin User',
        'role': 'admin',
        'is_active': True,
        'permissions': ['read', 'write', 'delete', 'admin'],
        'created_at': datetime.utcnow()
    }


@pytest.fixture
def auth_token():
    """Generate mock authentication token"""
    return 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyJ9.test'


@pytest.fixture
def auth_headers(auth_token):
    """Authentication headers for API requests"""
    return {
        'Authorization': f'Bearer {auth_token}',
        'Content-Type': 'application/json'
    }


# ==========================================
# API Client Fixtures
# ==========================================

@pytest.fixture
def mock_http_client():
    """Mock HTTP client for external API calls"""
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.patch = AsyncMock()
    client.delete = AsyncMock()

    return client


@pytest.fixture
def api_response_factory():
    """Factory for creating mock API responses"""
    def create_response(status_code: int = 200, data: Any = None, headers: dict = None):
        response = Mock()
        response.status_code = status_code
        response.json = Mock(return_value=data or {})
        response.headers = headers or {}
        response.text = str(data) if data else ''
        return response

    return create_response


# ==========================================
# Test Data Factories
# ==========================================

@pytest.fixture
def patient_factory():
    """Factory for creating test patient data"""
    counter = 0

    def create_patient(**kwargs):
        nonlocal counter
        counter += 1

        default = {
            'id': f'patient-{counter}',
            'name': f'Patient {counter}',
            'email': f'patient{counter}@example.com',
            'cpf': f'{counter:011d}',
            'phone': f'+551198765{counter:04d}',
            'date_of_birth': '1990-01-01',
            'created_at': datetime.utcnow()
        }

        default.update(kwargs)
        return default

    return create_patient


@pytest.fixture
def message_factory():
    """Factory for creating test message data"""
    counter = 0

    def create_message(**kwargs):
        nonlocal counter
        counter += 1

        default = {
            'id': f'msg-{counter}',
            'content': f'Test message {counter}',
            'sender': 'system',
            'recipient': 'patient-1',
            'status': 'pending',
            'created_at': datetime.utcnow()
        }

        default.update(kwargs)
        return default

    return create_message


@pytest.fixture
def alert_factory():
    """Factory for creating test alert data"""
    counter = 0

    def create_alert(**kwargs):
        nonlocal counter
        counter += 1

        default = {
            'id': f'alert-{counter}',
            'title': f'Alert {counter}',
            'message': f'Alert message {counter}',
            'priority': 'medium',
            'status': 'new',
            'created_at': datetime.utcnow()
        }

        default.update(kwargs)
        return default

    return create_alert


# ==========================================
# Time and Date Fixtures
# ==========================================

@pytest.fixture
def freeze_time():
    """Freeze time for deterministic testing"""
    frozen_time = datetime(2024, 1, 1, 12, 0, 0)

    class FrozenTime:
        @property
        def now(self):
            return frozen_time

        def advance(self, **kwargs):
            nonlocal frozen_time
            frozen_time += timedelta(**kwargs)

    return FrozenTime()


# ==========================================
# Async Testing Fixtures
# ==========================================

@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_client(mock_http_client):
    """Async HTTP client for testing"""
    return mock_http_client


# ==========================================
# Logging and Monitoring Fixtures
# ==========================================

@pytest.fixture
def mock_logger():
    """Mock logger for testing"""
    logger = MagicMock()
    logger.debug = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.critical = MagicMock()

    return logger


@pytest.fixture
def capture_logs(mock_logger):
    """Capture log messages for assertions"""
    logs = {
        'debug': [],
        'info': [],
        'warning': [],
        'error': [],
        'critical': []
    }

    def capture(level):
        def log_func(*args, **kwargs):
            logs[level].append((args, kwargs))
        return log_func

    mock_logger.debug = capture('debug')
    mock_logger.info = capture('info')
    mock_logger.warning = capture('warning')
    mock_logger.error = capture('error')
    mock_logger.critical = capture('critical')

    return logs


# ==========================================
# Environment and Configuration Fixtures
# ==========================================

@pytest.fixture
def test_env_vars():
    """Test environment variables"""
    return {
        'DATABASE_URL': 'postgresql://test:test@localhost/test',
        'REDIS_URL': 'redis://localhost:6379/0',
        'SECRET_KEY': 'test-secret-key',
        'LGPD_ENCRYPTION_KEY': 'test-encryption-key',
        'PHI_ENCRYPTION_KEY': 'test-phi-key'
    }


@pytest.fixture
def mock_settings(test_env_vars):
    """Mock application settings"""
    settings = MagicMock()

    for key, value in test_env_vars.items():
        setattr(settings, key.lower(), value)

    return settings


# ==========================================
# File and I/O Fixtures
# ==========================================

@pytest.fixture
def temp_file(tmp_path):
    """Create temporary file for testing"""
    def create_temp_file(content: str = '', filename: str = 'test.txt'):
        file_path = tmp_path / filename
        file_path.write_text(content)
        return file_path

    return create_temp_file


@pytest.fixture
def mock_file_upload():
    """Mock file upload for testing"""
    def create_upload(filename: str = 'test.pdf', content: bytes = b'test content'):
        upload = Mock()
        upload.filename = filename
        upload.content_type = 'application/pdf'
        upload.file = Mock()
        upload.file.read = Mock(return_value=content)
        return upload

    return create_upload
