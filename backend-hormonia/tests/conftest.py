
import os
import json
import inspect
import fnmatch
import uuid
from urllib.parse import urlparse
from typing import Generator
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from tests.utils.async_test_client import AsyncTestClient
from tests.utils.sync_executor import SyncExecutor

# Legacy/superseded suites intentionally excluded from default collection.
# These files are retained for historical reference only.
collect_ignore_glob = [
    "api/critical/test_auth_login.py",
    "api/critical/test_auth_refresh.py",
    "middleware/test_refactor_validation.py",
    "unit/services/test_idempotent_message.py",
    "unit/services/test_message_scheduler.py",
    "services/alerts/integration/test_*.py",
    "services/alerts/test_*.py",
    "tests/services/alerts/integration/test_*.py",
    "tests/services/alerts/test_*.py",
    "services/audit/test_*.py",
    "tests/services/audit/test_*.py",
    "security/test_*.py",
    "tests/security/test_*.py",
    "validation/daily_flow_30_days/test_*.py",
    "tests/validation/daily_flow_30_days/test_*.py",
]

os.environ.setdefault("APP_ENVIRONMENT", "development")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("ENCRYPTION_KEY", "32byte-secret-key-for-testing-123")
os.environ.setdefault("ENCRYPTION_SALT", "test-salt-16bytes")

from sqlalchemy import create_engine, TypeDecorator, Text, Index, ARRAY, text, inspect as sa_inspect
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB, INET, BYTEA, UUID as PGUUID
from fastapi import Request

# Load environment variables
_env_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".env")
)
if os.path.exists(_env_path):
    load_dotenv(_env_path)

from app.database import Base
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
    get_optional_user,
    get_redis_cache,
)
from app.dependencies import RequestContext, get_request_context

# SQLite Compatibility Decorators
class JSONBCompat(TypeDecorator):
    impl = Text
    cache_ok = True
    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, str):
            # Preserve pre-serialized JSON strings.
            try:
                json.loads(value)
                return value
            except json.JSONDecodeError:
                return json.dumps(value)
        return json.dumps(value)
    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, (bytes, bytearray)):
            value = value.decode()
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

class INETCompat(TypeDecorator):
    impl = Text
    cache_ok = True
    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else value
    def process_result_value(self, value, dialect):
        return value

class UUIDCompat(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value.hex
        try:
            return uuid.UUID(str(value)).hex
        except (ValueError, TypeError, AttributeError):
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (ValueError, TypeError, AttributeError):
            return value

from sqlalchemy.types import BLOB

# ... (JSONBCompat e INETCompat)

def _replace_postgres_types_with_sqlite(engine):
    if engine.dialect.name == 'sqlite':
        for table in Base.metadata.tables.values():
            for column in table.columns:
                if isinstance(column.type, JSONB):
                    column.type = JSONBCompat()
                elif isinstance(column.type, PGUUID):
                    column.type = UUIDCompat()
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
            elif isinstance(column.type, PGUUID):
                column.type = UUIDCompat()
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


def _ensure_patients_whatsapp_opt_out_column(engine):
    """Ensure Postgres test schemas include patients.messaging_stopped_at."""
    if engine.dialect.name != "postgresql":
        return

    inspector = sa_inspect(engine)
    if not inspector.has_table("patients"):
        print("[tests.conftest] patients table missing; skipping messaging_stopped_at guard")
        return

    patient_columns = {column["name"] for column in inspector.get_columns("patients")}
    if "messaging_stopped_at" in patient_columns:
        return

    print("[tests.conftest] Applying schema patch: add patients.messaging_stopped_at")
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE patients "
                "ADD COLUMN IF NOT EXISTS messaging_stopped_at TIMESTAMPTZ NULL"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_patients_messaging_stopped "
                "ON patients (messaging_stopped_at) "
                "WHERE messaging_stopped_at IS NOT NULL"
            )
        )


def _ensure_notifications_type_column(engine):
    """Ensure Postgres test schemas include notifications.notification_type."""
    if engine.dialect.name != "postgresql":
        return

    inspector = sa_inspect(engine)
    if not inspector.has_table("notifications"):
        print("[tests.conftest] notifications table missing; skipping notification_type guard")
        return

    notification_columns = {column["name"] for column in inspector.get_columns("notifications")}
    missing_columns = {
        "notification_type",
        "priority",
        "title",
        "message",
        "action_url",
        "action_label",
        "notification_metadata",
        "is_read",
        "read_at",
        "is_archived",
        "archived_at",
        "expires_at",
    } - notification_columns

    if not missing_columns:
        return

    print("[tests.conftest] Applying schema patch: align notifications columns")
    with engine.begin() as connection:
        if "notification_type" in missing_columns:
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ADD COLUMN IF NOT EXISTS notification_type VARCHAR(50)"
                )
            )
            connection.execute(
                text(
                    "UPDATE notifications "
                    "SET notification_type = 'INFO' "
                    "WHERE notification_type IS NULL"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ALTER COLUMN notification_type SET NOT NULL"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_notifications_notification_type "
                    "ON notifications (notification_type)"
                )
            )

        if "priority" in missing_columns:
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ADD COLUMN IF NOT EXISTS priority VARCHAR(20)"
                )
            )
            connection.execute(
                text(
                    "UPDATE notifications "
                    "SET priority = 'MEDIUM' "
                    "WHERE priority IS NULL"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ALTER COLUMN priority SET NOT NULL"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_notifications_priority "
                    "ON notifications (priority)"
                )
            )

        if "title" in missing_columns:
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ADD COLUMN IF NOT EXISTS title VARCHAR(200)"
                )
            )
            connection.execute(
                text(
                    "UPDATE notifications "
                    "SET title = 'Notification' "
                    "WHERE title IS NULL"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ALTER COLUMN title SET NOT NULL"
                )
            )

        if "message" in missing_columns:
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ADD COLUMN IF NOT EXISTS message TEXT"
                )
            )
            connection.execute(
                text(
                    "UPDATE notifications "
                    "SET message = 'Notification message' "
                    "WHERE message IS NULL"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ALTER COLUMN message SET NOT NULL"
                )
            )

        if "action_url" in missing_columns:
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ADD COLUMN IF NOT EXISTS action_url VARCHAR(500)"
                )
            )

        if "action_label" in missing_columns:
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ADD COLUMN IF NOT EXISTS action_label VARCHAR(100)"
                )
            )

        if "notification_metadata" in missing_columns:
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ADD COLUMN IF NOT EXISTS notification_metadata JSONB"
                )
            )

        if "is_read" in missing_columns:
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ADD COLUMN IF NOT EXISTS is_read BOOLEAN"
                )
            )
            connection.execute(
                text(
                    "UPDATE notifications "
                    "SET is_read = FALSE "
                    "WHERE is_read IS NULL"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ALTER COLUMN is_read SET NOT NULL"
                )
            )

        if "read_at" in missing_columns:
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ADD COLUMN IF NOT EXISTS read_at TIMESTAMPTZ NULL"
                )
            )

        if "is_archived" in missing_columns:
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ADD COLUMN IF NOT EXISTS is_archived BOOLEAN"
                )
            )
            connection.execute(
                text(
                    "UPDATE notifications "
                    "SET is_archived = FALSE "
                    "WHERE is_archived IS NULL"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ALTER COLUMN is_archived SET NOT NULL"
                )
            )

        if "archived_at" in missing_columns:
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ NULL"
                )
            )

        if "expires_at" in missing_columns:
            connection.execute(
                text(
                    "ALTER TABLE notifications "
                    "ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ NULL"
                )
            )


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
        # USE SHARED IN-MEMORY SQLITE FOR TEST ISOLATION + STABILITY
        db_url = "sqlite://"
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

    _ensure_patients_whatsapp_opt_out_column(engine)
    _ensure_notifications_type_column(engine)

    try:
        yield engine
    finally:
        engine.dispose()

@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(bind=connection, expire_on_commit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()

@pytest.fixture
def db(db_session: Session):
    yield db_session

@pytest.fixture
def client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> AsyncTestClient:
    async def _override_get_db():
        return db_session

    app.dependency_overrides[get_db] = _override_get_db

    # Avoid threadpool-based sync dependency execution in async test client,
    # which can intermittently deadlock under heavy test parallelism.
    from app.api.v2.dependencies import (
        get_field_selection,
        get_field_selection_async,
        get_pagination_params,
        get_pagination_params_async,
        get_eager_load_params,
        get_eager_load_params_async,
    )

    app.dependency_overrides[get_field_selection] = get_field_selection_async
    app.dependency_overrides[get_pagination_params] = get_pagination_params_async
    app.dependency_overrides[get_eager_load_params] = get_eager_load_params_async

    # Enhanced analytics still declares a sync service factory dependency.
    # Override with async variant to avoid threadpool deadlocks in AsyncTestClient.
    try:
        from app.api.v2.routers.enhanced_analytics import (
            get_enhanced_analytics_service,
        )
        from app.services.analytics import EnhancedAnalyticsService

        async def _override_enhanced_analytics_service():
            return EnhancedAnalyticsService(db_session)

        app.dependency_overrides[get_enhanced_analytics_service] = (
            _override_enhanced_analytics_service
        )
    except Exception:
        pass

    class _NoopRedisCache:
        def __init__(self):
            self._kv = {}
            self._sets = {}
            self._zsets = {}

        async def get(self, key):
            return self._kv.get(key)

        async def set(self, key, value, ttl=300, ex=None, px=None, **kwargs):
            # Keep compatibility with redis-py style args (`ex`, `px`, etc.).
            _ = ttl, ex, px, kwargs
            self._kv[key] = value
            return True

        async def delete(self, key):
            self._kv.pop(key, None)
            self._sets.pop(key, None)
            return True

        async def delete_pattern(self, pattern):
            # Compatibility: some tests patch RedisManager.delete_pattern directly.
            from unittest.mock import Mock
            from app.core.redis_manager import RedisManager

            patched = getattr(RedisManager, "delete_pattern", None)
            if isinstance(patched, Mock):
                result = patched(pattern)
                if inspect.isawaitable(result):
                    return await result
                return result
            keys_to_delete = [
                key for key in list(self._kv.keys()) if fnmatch.fnmatch(key, pattern)
            ]
            for key in keys_to_delete:
                self._kv.pop(key, None)
            set_keys_to_delete = [
                key for key in list(self._sets.keys()) if fnmatch.fnmatch(key, pattern)
            ]
            for key in set_keys_to_delete:
                self._sets.pop(key, None)
            return True

        async def sadd(self, key, *values):
            target = self._sets.setdefault(key, set())
            before = len(target)
            target.update(str(v) for v in values)
            return len(target) - before

        async def smembers(self, key):
            return set(self._sets.get(key, set()))

        async def expire(self, key, ttl):
            # No-op for tests; key expiry isn't required for correctness here.
            _ = key, ttl
            return True

        async def zadd(self, key, mapping):
            zset = self._zsets.setdefault(key, {})
            added = 0
            for member, score in dict(mapping).items():
                member_key = str(member)
                if member_key not in zset:
                    added += 1
                zset[member_key] = float(score)
            return added

        async def zrange(self, key, start, end, withscores=False):
            zset = self._zsets.get(key, {})
            ordered = sorted(zset.items(), key=lambda item: (item[1], item[0]))
            if end == -1:
                sliced = ordered[start:]
            else:
                sliced = ordered[start : end + 1]

            if withscores:
                return sliced
            return [member for member, _score in sliced]

        async def get_session(self, session_id):
            # Compatibility: some tests patch RedisManager.get_session directly.
            from unittest.mock import Mock
            from app.core.redis_manager import RedisManager

            patched = getattr(RedisManager, "get_session", None)
            if isinstance(patched, Mock):
                result = patched(session_id)
                if inspect.isawaitable(result):
                    return await result
                return result
            return None

        async def get_user_by_uid(self, firebase_uid):
            # Compatibility: some tests patch RedisManager.get_user_by_uid directly.
            from unittest.mock import Mock
            from app.core.redis_manager import RedisManager

            patched = getattr(RedisManager, "get_user_by_uid", None)
            if isinstance(patched, Mock):
                result = patched(firebase_uid)
                if inspect.isawaitable(result):
                    return await result
                return result
            return None

        async def update_session_activity(self, session_id, extend_ttl=True, custom_ttl=None):
            return True

        async def create_session(self, session_id, user_id, firebase_uid, ttl=86400):
            return True

        async def cache_user_data(self, firebase_uid, user_data, ttl=900):
            return True

    _noop_redis_cache = _NoopRedisCache()

    async def _override_redis_cache():
        return _noop_redis_cache

    app.dependency_overrides[get_redis_cache] = _override_redis_cache
    try:
        from app.api.v2.routers.monthly_quiz_operations import _shared as monthly_quiz_shared

        app.dependency_overrides[monthly_quiz_shared.get_redis_cache] = _override_redis_cache
    except Exception:
        # Monthly quiz modules are optional in some test slices.
        pass

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

    previous_testing = os.environ.get("TESTING")
    os.environ["TESTING"] = "1"

    try:
        test_client = AsyncTestClient(app)
        yield test_client
    finally:
        try:
            test_client.close()
        except Exception:
            pass
        if previous_testing is None:
            os.environ.pop("TESTING", None)
        else:
            os.environ["TESTING"] = previous_testing
        app.dependency_overrides.clear()

@pytest.fixture
def test_client(client: AsyncTestClient) -> AsyncTestClient:
    """Alias for legacy tests that expect a test_client fixture."""
    return client

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
        is_active=kwargs.get('is_active', True),
        firebase_uid=kwargs.get('firebase_uid'),
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

    async def _override_current_user_object():
        return user_obj

    app.dependency_overrides[get_current_user_from_session] = _override_session
    app.dependency_overrides[get_current_user_object_from_session] = _override_current_user_object
    app.dependency_overrides[get_current_user] = _override_current_user
    client.headers["Authorization"] = f"Bearer test_token_{user_obj.id}"
    return client


@pytest.fixture
def auth_headers(test_user):
    from app.main import app
    from app.middleware.csrf import get_csrf_token

    user_obj = test_user.user if isinstance(test_user, TestUser) else test_user
    session_user = (
        test_user.session_dict()
        if isinstance(test_user, TestUser)
        else TestUser(user_obj, getattr(test_user, "password", "testpass123")).session_dict()
    )
    session_id = f"test-session-{user_obj.id}"

    async def _override_session(request: Request):
        request.state.user_id = session_user.get("id")
        request.state.user_role = session_user.get("role")
        request.state.session_id = session_id
        return session_user

    async def _override_current_user(request: Request):
        request.state.user = user_obj
        request.state.user_id = str(user_obj.id)
        request.state.user_role = (
            user_obj.role.value if hasattr(user_obj.role, "value") else str(user_obj.role)
        )
        request.state.session_id = session_id
        return user_obj

    async def _override_optional_user(credentials=None, services=None):
        return user_obj

    async def _override_current_user_object():
        return user_obj

    async def _override_request_context(request: Request):
        return RequestContext(
            ip_address="127.0.0.1",
            user_agent="pytest",
            user_id=user_obj.id,
            session_id=session_id,
        )

    app.dependency_overrides[get_current_user_from_session] = _override_session
    app.dependency_overrides[get_current_user_object_from_session] = _override_current_user_object
    app.dependency_overrides[get_current_user] = _override_current_user
    app.dependency_overrides[get_optional_user] = _override_optional_user
    app.dependency_overrides[get_request_context] = _override_request_context

    csrf_token = get_csrf_token()
    headers = {
        "X-Session-ID": session_id,
        "Authorization": f"Bearer test-token-{user_obj.id}",
        "X-CSRF-Token": csrf_token,
        "Cookie": f"csrf_token={csrf_token}",
    }
    yield headers
    app.dependency_overrides.pop(get_current_user_from_session, None)
    app.dependency_overrides.pop(get_current_user_object_from_session, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_user, None)
    app.dependency_overrides.pop(get_request_context, None)


@pytest.fixture
def sync_executor():
    """Synchronous executor for testing (avoids SQLite threading issues)."""
    return SyncExecutor()
