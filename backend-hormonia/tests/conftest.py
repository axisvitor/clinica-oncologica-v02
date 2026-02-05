
import os
import json
from urllib.parse import urlparse
from typing import Generator
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from tests.utils.sync_executor import SyncExecutor

os.environ.setdefault("APP_ENVIRONMENT", "development")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("ENCRYPTION_KEY", "32byte-secret-key-for-testing-123")
os.environ.setdefault("ENCRYPTION_SALT", "test-salt-16bytes")

from sqlalchemy import create_engine, TypeDecorator, Text, Index, ARRAY
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB, INET, BYTEA
from fastapi import Request
from fastapi.testclient import TestClient

# Load environment variables
_env_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".env")
)
if os.path.exists(_env_path):
    load_dotenv(_env_path)

from app.db.base import Base
# Import all models to ensure tables are registered with Base.metadata
import app.models  # This imports all SQLAlchemy models for table creation
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.utils.security import get_password_hash
from app.main import app
from app.database import get_db
from app.dependencies.auth_dependencies import (
    get_current_user,
    get_current_user_from_session,
    get_current_user_object_from_session,
    get_permissions_for_role,
)

# SQLite Compatibility Decorators
class JSONBCompat(TypeDecorator):
    impl = Text
    cache_ok = True
    def process_bind_param(self, value, dialect):
        return json.dumps(value) if value is not None else value
    def process_result_value(self, value, dialect):
        return json.loads(value) if value is not None else value

class INETCompat(TypeDecorator):
    impl = Text
    cache_ok = True
    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else value
    def process_result_value(self, value, dialect):
        return value

from sqlalchemy.types import BLOB

# ... (JSONBCompat e INETCompat)

def _replace_postgres_types_with_sqlite(engine):
    if engine.dialect.name == 'sqlite':
        for table in Base.metadata.tables.values():
            for column in table.columns:
                if isinstance(column.type, JSONB):
                    column.type = JSONBCompat()
                elif isinstance(column.type, INET):
                    column.type = INETCompat()
                elif isinstance(column.type, ARRAY):
                    column.type = JSONBCompat()
                elif str(column.type) == 'BYTEA' or isinstance(column.type, BYTEA):
                    column.type = BLOB()
                
                # Strip PG server defaults for SQLite
                if column.server_default is not None and hasattr(column.server_default, 'arg'):
                    arg_str = str(column.server_default.arg).lower()
                    if 'gen_random_uuid()' in arg_str:
                        column.server_default = None
            
            # Strip PG indexes for SQLite but preserve uniqueness (dedupe by name)
            index_by_name = {}
            for idx in table.indexes:
                # If it's a unique index with PG-specific where, create a plain unique index for SQLite
                if idx.unique and any(hasattr(idx, k) and getattr(idx, k) is not None for k in ['postgresql_where']):
                    new_idx = Index(
                        idx.name,
                        *[c for c in idx.columns],
                        unique=True
                    )
                    index_by_name.setdefault(new_idx.name, new_idx)
                elif not any(hasattr(idx, k) and getattr(idx, k) is not None 
                           for k in ['postgresql_where', 'postgresql_concurrently']):
                    index_by_name.setdefault(idx.name, idx)

            table.indexes = set(index_by_name.values())

def _apply_sqlite_type_fixes():
    """Apply SQLite compatibility fixes to all models in Base.metadata."""
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSONBCompat()
            elif isinstance(column.type, INET):
                column.type = INETCompat()
            elif isinstance(column.type, ARRAY):
                column.type = JSONBCompat()
            elif str(column.type) == 'BYTEA' or isinstance(column.type, BYTEA):
                column.type = BLOB()

            # Strip PG server defaults for SQLite
            if column.server_default is not None and hasattr(column.server_default, 'arg'):
                arg_str = str(column.server_default.arg).lower()
                if 'gen_random_uuid()' in arg_str:
                    column.server_default = None

        # Strip PG-specific indexes (dedupe by name)
        index_by_name = {}
        for idx in list(table.indexes):
            if idx.unique and any(hasattr(idx, k) and getattr(idx, k) is not None for k in ['postgresql_where']):
                new_idx = Index(
                    idx.name,
                    *[c for c in idx.columns],
                    unique=True
                )
                index_by_name.setdefault(new_idx.name, new_idx)
            elif not any(hasattr(idx, k) and getattr(idx, k) is not None
                       for k in ['postgresql_where', 'postgresql_concurrently']):
                index_by_name.setdefault(idx.name, idx)

        table.indexes = set(index_by_name.values())


@pytest.fixture(scope="session")
def test_engine():
    # Detect if we should use Postgres or SQLite
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    allow_postgres = os.getenv("USE_TEST_POSTGRES", "").lower() in ("1", "true", "yes")
    db_host = urlparse(db_url).hostname if db_url else None
    is_local_host = db_host in {"localhost", "127.0.0.1", "::1"}
    # Allow running tests against local postgres if available, even in dev mode
    # ensuring we never run against prod is handled by the user ensuring they are local
    if db_url and "postgresql" in db_url and (allow_postgres or is_local_host):
        # USE TEST POSTGRES
        # Do not use StaticPool for Postgres as it prevents multiple connections
        engine = create_engine(
            db_url,
            pool_pre_ping=True
        )
    else:
        # USE FILE-BASED SQLITE FOR THREAD SAFETY
        import tempfile
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)

        db_url = f"sqlite:///{db_path}"
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        # Apply SQLite compatibility fixes BEFORE create_all
        _apply_sqlite_type_fixes()

    # Legacy call for any remaining issues (now mostly redundant for SQLite)
    _replace_postgres_types_with_sqlite(engine)

    # DANGER: Skipping drop_all to avoid wiping local dev DB during ad-hoc testing
    # try:
    #     Base.metadata.drop_all(bind=engine)
    # except Exception as e:
    #     print(f"Warning during drop_all: {e}")

    # Create all tables with checkfirst to avoid errors
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except Exception as e:
        print(f"Warning during create_all: {e}")

    try:
        yield engine
    finally:
        engine.dispose()
        if 'db_path' in locals() and os.path.exists(db_path):
            try:
                os.remove(db_path)
            except:
                pass

@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(bind=connection)
    session = TestingSessionLocal()
    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def db(db_session: Session):
    yield db_session

@pytest.fixture
def client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db_session

    # Force thread-safe ServiceProvider to use the test session.
    from app import dependencies as app_dependencies
    from app.service_provider import ServiceProvider

    def _override_thread_safe_service_provider():
        provider = ServiceProvider(db_session, redis_client=None)
        yield provider

    monkeypatch.setattr(
        app_dependencies,
        "get_thread_safe_service_provider",
        _override_thread_safe_service_provider,
    )

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def reset_redis_singletons():
    """Reset Redis singletons to avoid event-loop bound clients across tests."""
    from app.core.redis_manager import utils as redis_utils
    from app.core import distributed_lock

    redis_utils._redis_manager = None
    redis_utils._redis_cache_manager = None
    redis_utils._redis_broker_manager = None
    distributed_lock._default_lock = None
    yield
    distributed_lock._default_lock = None
    redis_utils._redis_manager = None
    redis_utils._redis_cache_manager = None
    redis_utils._redis_broker_manager = None

def create_test_user(db_session, email="test@example.com", role=UserRole.DOCTOR, **kwargs):
    # Check if user already exists
    existing = db_session.query(User).filter(User.email == email).first()
    if existing:
        return existing

    user = User(
        id=kwargs.get('id', uuid4()),
        email=email,
        hashed_password=get_password_hash(kwargs.get('password', 'testpass123')),
        full_name=kwargs.get('full_name', 'Test User'),
        role=role,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user

class TestUser(dict):
    """Dictionary-backed test user with attribute access for User fields."""

    def __init__(self, user: User, password: str):
        super().__init__(
            id=str(user.id),
            email=user.email,
            password=password,
            full_name=user.full_name,
            role=user.role,
            user=user,
            firebase_uid=getattr(user, "firebase_uid", None),
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else None,
            updated_at=user.updated_at.isoformat() if user.updated_at else None,
            last_login=user.firebase_last_sign_in.isoformat()
            if user.firebase_last_sign_in
            else None,
        )
        self.user = user
        self.password = password
        self.access_token = f"test_session_{user.id}"

    def __getattr__(self, name):
        if hasattr(self.user, name):
            return getattr(self.user, name)
        if name in self:
            return self[name]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name in {"user", "password", "access_token"} or name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        if hasattr(self, "user") and hasattr(self.user, name):
            setattr(self.user, name, value)
            return
        if name in self:
            self[name] = value
            return
        object.__setattr__(self, name, value)

    def session_dict(self) -> dict:
        role = self.user.role.value if hasattr(self.user.role, "value") else str(self.user.role)
        return {
            "id": str(self.user.id),
            "email": self.user.email,
            "full_name": self.user.full_name,
            "role": role,
            "is_active": self.user.is_active,
            "firebase_uid": getattr(self.user, "firebase_uid", None),
            "created_at": self.user.created_at.isoformat() if self.user.created_at else None,
            "updated_at": self.user.updated_at.isoformat() if self.user.updated_at else None,
            "last_login": self.user.firebase_last_sign_in.isoformat()
            if self.user.firebase_last_sign_in
            else None,
            "permissions": get_permissions_for_role(role),
        }

@pytest.fixture
def test_user(db_session):
    """Return user dict with credentials for login tests."""
    password = "testpass123"
    user = create_test_user(db_session, password=password)
    return TestUser(user, password)


@pytest.fixture
def test_user_obj(db_session):
    """Return User object directly for tests that need the model."""
    return create_test_user(db_session)

def create_test_patient(db_session, doctor, name="Test Patient", **kwargs):
    patient = Patient(
        id=kwargs.get('id', uuid4()),
        name=name,
        doctor_id=doctor.id,
        birth_date=kwargs.get('birth_date')
    )
    if 'cpf' in kwargs: patient.set_cpf(kwargs['cpf'])
    if 'email' in kwargs: patient.set_email(kwargs['email'])
    if 'phone' in kwargs: patient.set_phone(kwargs['phone'])
    
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient

@pytest.fixture
def test_patient(db_session, test_user):
    user_obj = test_user["user"] if isinstance(test_user, dict) else test_user
    return create_test_patient(db_session, doctor=user_obj)

@pytest.fixture
def authenticated_client(client, test_user):
    user_obj = test_user["user"] if isinstance(test_user, dict) else test_user
    session_user = (
        test_user.session_dict()
        if isinstance(test_user, TestUser)
        else TestUser(user_obj, getattr(test_user, "password", "testpass123")).session_dict()
    )

    async def _override_session(request: Request):
        request.state.user_id = session_user.get("id")
        request.state.user_role = session_user.get("role")
        return session_user

    async def _override_current_user(request: Request):
        request.state.user = user_obj
        request.state.user_id = str(user_obj.id)
        request.state.user_role = (
            user_obj.role.value if hasattr(user_obj.role, "value") else str(user_obj.role)
        )
        return user_obj

    app.dependency_overrides[get_current_user_from_session] = _override_session
    app.dependency_overrides[get_current_user_object_from_session] = lambda: user_obj
    app.dependency_overrides[get_current_user] = _override_current_user
    client.headers["Authorization"] = f"Bearer test_token_{user_obj.id}"
    return client


@pytest.fixture
def sync_executor():
    """Synchronous executor for testing (avoids SQLite threading issues)."""
    return SyncExecutor()
