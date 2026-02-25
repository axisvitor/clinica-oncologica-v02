"""
Critical API Test Configuration

Provides authenticated fixtures with CSRF token handling.
Uses lazy app loading to avoid slow startup at import time.
"""
import os
import json
import pytest
import requests
from typing import Generator
from uuid import uuid4
from urllib.parse import urlparse

from dotenv import load_dotenv

# Set test environment BEFORE any app imports
os.environ["APP_ENVIRONMENT"] = "testing"
os.environ["ENVIRONMENT"] = "testing"
os.environ.setdefault("ENCRYPTION_KEY", "32byte-secret-key-for-testing-123")
os.environ.setdefault("ENCRYPTION_SALT", "test-salt-16bytes")
os.environ.setdefault("SKIP_FIREBASE_TOKEN", "true")

USE_REAL_AUTH = os.getenv("USE_REAL_AUTH", "").lower() in ("1", "true", "yes")

from sqlalchemy import create_engine, TypeDecorator, Text, text, Index, ARRAY, inspect as sa_inspect
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool, NullPool
from sqlalchemy.dialects.postgresql import JSONB, INET, BYTEA
from sqlalchemy.types import BLOB
from fastapi.testclient import TestClient

# Load environment variables from backend .env
_env_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
)
if os.path.exists(_env_path):
    load_dotenv(_env_path, override=True)

# Also load frontend .env for Firebase Web API Key
_frontend_env_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "frontend-hormonia", ".env")
)
if os.path.exists(_frontend_env_path):
    load_dotenv(_frontend_env_path, override=False)

# Firebase Web API Key
FIREBASE_API_KEY = os.getenv("VITE_FIREBASE_API_KEY", "AIzaSyDbZHMNV2eZQty03TgA4yNo_3L6UDSpHdI")

# Add timestamp for unique test data
pytest.timestamp = int(__import__("time").time())

# Pre-computed bcrypt hash for "testpass123" - avoids 27s bcrypt delay per test
_TEST_PASSWORD = "testpass123"
_CACHED_PASSWORD_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.Gj6VTzWAx3.B/K"


# SQLite Compatibility
class JSONBCompat(TypeDecorator):
    impl = Text
    cache_ok = True
    def process_bind_param(self, value, dialect):
        return json.dumps(value) if value is not None else value
    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8")
        if isinstance(value, str):
            return json.loads(value)
        return value

class INETCompat(TypeDecorator):
    impl = Text
    cache_ok = True
    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else value
    def process_result_value(self, value, dialect):
        return value


def _ensure_patients_whatsapp_opt_out_column(engine):
    """Ensure Postgres critical-suite schemas include patients.messaging_stopped_at."""
    if engine.dialect.name != "postgresql":
        return

    inspector = sa_inspect(engine)
    if not inspector.has_table("patients"):
        print("[critical.conftest] patients table missing; skipping messaging_stopped_at guard")
        return

    patient_columns = {column["name"] for column in inspector.get_columns("patients")}
    if "messaging_stopped_at" in patient_columns:
        return

    print("[critical.conftest] Applying schema patch: add patients.messaging_stopped_at")
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
    """Ensure Postgres critical-suite schemas include notifications.notification_type."""
    if engine.dialect.name != "postgresql":
        return

    inspector = sa_inspect(engine)
    if not inspector.has_table("notifications"):
        print("[critical.conftest] notifications table missing; skipping notification_type guard")
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

    print("[critical.conftest] Applying schema patch: align notifications columns")
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


def _ensure_audit_logs_firebase_uid_column(engine):
    """Ensure Postgres critical-suite schemas include modern audit_logs columns."""
    if engine.dialect.name != "postgresql":
        return

    inspector = sa_inspect(engine)
    if not inspector.has_table("audit_logs"):
        print("[critical.conftest] audit_logs table missing; skipping firebase_uid guard")
        return

    audit_columns = {column["name"] for column in inspector.get_columns("audit_logs")}
    missing_columns = {
        "event_category",
        "event_status",
        "status",
        "user_email",
        "user_role",
        "firebase_uid",
        "session_id",
        "session_token_hash",
        "device_fingerprint",
        "geolocation",
        "user_agent",
        "resource",
        "action",
        "resource_type",
        "resource_id",
        "resource_identifiers",
        "operation",
        "http_method",
        "endpoint",
        "event_metadata",
        "query_params",
        "request_body_hash",
        "changes_before",
        "changes_after",
        "changed_fields",
        "description",
        "message",
        "error_details",
        "http_status_code",
        "error_code",
        "error_stack_trace",
        "duration_ms",
        "checksum",
        "previous_checksum",
        "integrity_verified",
        "reviewed",
        "reviewed_at",
        "reviewed_by",
        "review_notes",
        "is_anomalous",
        "anomaly_score",
        "anomaly_reasons",
        "alert_generated",
        "alert_sent_at",
        "alert_recipients",
        "retention_period_years",
        "archive_eligible_at",
        "archived",
        "archived_at",
        "archive_location",
    } - audit_columns

    if not missing_columns:
        return

    print("[critical.conftest] Applying schema patch: align audit_logs columns")
    with engine.begin() as connection:
        if "event_category" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS event_category VARCHAR(50)"))
        if "event_status" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS event_status VARCHAR(50)"))
            connection.execute(text("UPDATE audit_logs SET event_status = 'success' WHERE event_status IS NULL"))
        if "status" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS status VARCHAR(20)"))
        if "user_email" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_email VARCHAR(255)"))
        if "user_role" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_role VARCHAR(50)"))
        if "firebase_uid" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS firebase_uid VARCHAR(255)"))
        if "session_id" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS session_id VARCHAR(255)"))
        if "session_token_hash" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS session_token_hash VARCHAR(64)"))
        if "device_fingerprint" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS device_fingerprint VARCHAR(64)"))
        if "geolocation" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS geolocation JSONB"))
        if "user_agent" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_agent TEXT"))
        if "resource" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS resource VARCHAR(255)"))
        if "action" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS action VARCHAR(255)"))
        if "resource_type" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS resource_type VARCHAR(50)"))
        if "resource_id" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS resource_id UUID"))
        if "resource_identifiers" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS resource_identifiers JSONB"))
        if "operation" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS operation VARCHAR(20)"))
        if "http_method" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS http_method VARCHAR(10)"))
        if "endpoint" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS endpoint VARCHAR(500)"))
        if "event_metadata" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS event_metadata JSONB"))
            connection.execute(text("UPDATE audit_logs SET event_metadata = '{}'::jsonb WHERE event_metadata IS NULL"))
        if "query_params" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS query_params JSONB"))
        if "request_body_hash" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS request_body_hash VARCHAR(64)"))
        if "changes_before" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS changes_before JSONB"))
        if "changes_after" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS changes_after JSONB"))
        if "changed_fields" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS changed_fields TEXT[]"))
        if "description" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS description TEXT"))
        if "message" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS message TEXT"))
        if "error_details" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS error_details TEXT"))
        if "http_status_code" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS http_status_code INTEGER"))
        if "error_code" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS error_code VARCHAR(50)"))
        if "error_stack_trace" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS error_stack_trace TEXT"))
        if "duration_ms" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS duration_ms INTEGER"))
        if "checksum" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS checksum VARCHAR(64)"))
        if "previous_checksum" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS previous_checksum VARCHAR(64)"))
        if "integrity_verified" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS integrity_verified BOOLEAN"))
        if "reviewed" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS reviewed BOOLEAN"))
        if "reviewed_at" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ"))
        if "reviewed_by" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS reviewed_by UUID"))
        if "review_notes" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS review_notes TEXT"))
        if "is_anomalous" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS is_anomalous BOOLEAN"))
        if "anomaly_score" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS anomaly_score NUMERIC(5,2)"))
        if "anomaly_reasons" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS anomaly_reasons TEXT[]"))
        if "alert_generated" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS alert_generated BOOLEAN"))
        if "alert_sent_at" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS alert_sent_at TIMESTAMPTZ"))
        if "alert_recipients" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS alert_recipients TEXT[]"))
        if "retention_period_years" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS retention_period_years INTEGER"))
        if "archive_eligible_at" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS archive_eligible_at TIMESTAMPTZ"))
        if "archived" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS archived BOOLEAN"))
        if "archived_at" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ"))
        if "archive_location" in missing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS archive_location VARCHAR(500)"))

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_audit_firebase_time "
                "ON audit_logs (firebase_uid, created_at)"
            )
        )


def _ensure_audit_logs_event_category_constraint(engine):
    """Ensure Postgres critical-suite schemas support current audit event categories."""
    if engine.dialect.name != "postgresql":
        return

    inspector = sa_inspect(engine)
    if not inspector.has_table("audit_logs"):
        print("[critical.conftest] audit_logs table missing; skipping valid_event_category guard")
        return

    print("[critical.conftest] Applying schema patch: broaden audit_logs valid_event_category constraint")

    constraint_sql = (
        "ALTER TABLE audit_logs ADD CONSTRAINT valid_event_category CHECK ("
        "event_category IN ("
        "'AUTHENTICATION', 'AUTHORIZATION', 'PHI_ACCESS', 'DATA_MODIFICATION', "
        "'SECURITY', 'SYSTEM', 'ADMIN', 'EXPORT', "
        "'access', 'security', 'data_change', 'consent', "
        "'performance', 'business', 'user_action'"
        ")"
        ")"
    )

    with engine.begin() as connection:
        result = connection.execute(
            text(
                "SELECT 1 FROM information_schema.table_constraints "
                "WHERE constraint_name = 'valid_event_category' "
                "AND table_name = 'audit_logs'"
            )
        )
        constraint_exists = result.scalar() is not None

        if constraint_exists:
            connection.execute(
                text(
                    "ALTER TABLE audit_logs "
                    "DROP CONSTRAINT IF EXISTS valid_event_category"
                )
            )

        connection.execute(text(constraint_sql))


def get_firebase_id_token(email: str, password: str) -> str | None:
    """Get Firebase ID token via REST API (signInWithPassword)."""
    if os.getenv("SKIP_FIREBASE_TOKEN", "").lower() in ("1", "true", "yes"):
        return None
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    try:
        response = requests.post(url, json={
            "email": email,
            "password": password,
            "returnSecureToken": True
        }, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("idToken")
        else:
            print(f"Firebase auth failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"Firebase auth error: {e}")
        return None


# Cached Firebase token
_cached_firebase_token = None


@pytest.fixture(scope="session")
def firebase_token():
    """Get a Firebase ID token for the real admin user."""
    global _cached_firebase_token
    if _cached_firebase_token is None:
        _cached_firebase_token = get_firebase_id_token(
            "admin@neoplasiaslitoral.com",
            "Admin@123456!"
        )
    return _cached_firebase_token


@pytest.fixture(scope="session")
def app_instance():
    """Load the FastAPI app lazily - only when first needed."""
    from app.main import app
    return app


@pytest.fixture(scope="session")
def app_modules():
    """Load app modules lazily."""
    import app.models  # Ensure all models are registered for Base.metadata
    from app.database import Base
    from app.models.user import User, UserRole
    from app.models.patient import Patient
    from app.database import get_db, get_async_db
    from app.dependencies.auth_dependencies import get_current_user, get_current_user_from_session
    return {
        'Base': Base,
        'User': User,
        'UserRole': UserRole,
        'Patient': Patient,
        'get_db': get_db,
        'get_async_db': get_async_db,
        'get_current_user': get_current_user,
        'get_current_user_from_session': get_current_user_from_session,
    }


@pytest.fixture(scope="function")
def test_engine(app_modules):
    """Create test database engine - uses real PostgreSQL."""
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    allow_postgres = os.getenv("USE_TEST_POSTGRES", "").lower() in ("1", "true", "yes")
    db_host = urlparse(db_url).hostname if db_url else None
    is_local_host = db_host in {"localhost", "127.0.0.1", "::1"}
    Base = app_modules['Base']

    # Preserve global metadata state to avoid cross-suite contamination.
    original_column_types = {}
    original_server_defaults = {}
    original_indexes = {}
    for table in Base.metadata.tables.values():
        original_indexes[table.name] = set(table.indexes)
        for column in table.columns:
            key = (table.name, column.name)
            original_column_types[key] = column.type
            original_server_defaults[key] = column.server_default

    engine = None
    try:
        if db_url and "postgresql" in db_url and (allow_postgres or is_local_host):
            engine = create_engine(db_url, pool_pre_ping=True, poolclass=NullPool)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            _ensure_patients_whatsapp_opt_out_column(engine)
            _ensure_notifications_type_column(engine)
            _ensure_audit_logs_firebase_uid_column(engine)
            _ensure_audit_logs_event_category_constraint(engine)
        else:
            import tempfile
            db_fd, db_path = tempfile.mkstemp(suffix=".db")
            os.close(db_fd)
            db_url = f"sqlite:///{db_path}"
            engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
            # SQLite type compatibility
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
                        if column.server_default is not None and hasattr(column.server_default, 'arg'):
                            arg_str = str(column.server_default.arg).lower()
                            if 'gen_random_uuid()' in arg_str:
                                column.server_default = None
                    # Strip PG-specific indexes (dedupe by name)
                    index_by_name = {}
                    for idx in list(table.indexes):
                        if idx.unique and any(
                            hasattr(idx, k) and getattr(idx, k) is not None for k in ["postgresql_where"]
                        ):
                            new_idx = Index(
                                idx.name,
                                *[c for c in idx.columns],
                                unique=True,
                            )
                            index_by_name.setdefault(new_idx.name, new_idx)
                        elif not any(
                            hasattr(idx, k) and getattr(idx, k) is not None
                            for k in ["postgresql_where", "postgresql_concurrently"]
                        ):
                            index_by_name.setdefault(idx.name, idx)

                    table.indexes = set(index_by_name.values())
            try:
                Base.metadata.create_all(bind=engine)
            except Exception as e:
                print(f"Warning during create_all: {e}")
            _ensure_patients_whatsapp_opt_out_column(engine)
            _ensure_notifications_type_column(engine)
            _ensure_audit_logs_firebase_uid_column(engine)
            _ensure_audit_logs_event_category_constraint(engine)

        yield engine
    finally:
        if engine is not None:
            engine.dispose()

        # Restore metadata so non-critical suites keep their own type strategy.
        for table in Base.metadata.tables.values():
            for column in table.columns:
                key = (table.name, column.name)
                if key in original_column_types:
                    column.type = original_column_types[key]
                if key in original_server_defaults:
                    column.server_default = original_server_defaults[key]
            table.indexes = set(original_indexes.get(table.name, set()))


@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """Create a database session for each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(bind=connection)
    session = TestingSessionLocal()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


def _get_csrf_token(client: TestClient) -> str:
    """Get a CSRF token from the API."""
    response = client.get("/csrf-token")
    if response.status_code == 200:
        data = response.json()
        return data.get("csrf_token", "")
    return ""


class SyncToAsyncSessionAdapter:
    """Async-compatible adapter over sync SQLAlchemy Session for tests."""

    def __init__(self, sync_session: Session):
        self._sync_session = sync_session

    async def execute(self, statement, *args, **kwargs):
        return self._sync_session.execute(statement, *args, **kwargs)

    async def commit(self):
        self._sync_session.flush()

    async def rollback(self):
        return None

    async def close(self):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def __getattr__(self, name):
        return getattr(self._sync_session, name)


@pytest.fixture
def client(db_session: Session, app_instance, app_modules) -> TestClient:
    """Create unauthenticated test client with CSRF token."""
    get_db = app_modules['get_db']
    get_async_db = app_modules['get_async_db']

    async def override_get_async_db():
        yield SyncToAsyncSessionAdapter(db_session)

    app_instance.dependency_overrides[get_db] = lambda: db_session
    app_instance.dependency_overrides[get_async_db] = override_get_async_db
    with TestClient(app_instance, raise_server_exceptions=False) as test_client:
        # Get CSRF token and set in headers
        csrf_token = _get_csrf_token(test_client)
        if csrf_token:
            test_client.headers["X-CSRF-Token"] = csrf_token
        yield test_client
    app_instance.dependency_overrides.clear()


@pytest.fixture(scope="session")
def real_client(app_instance) -> TestClient:
    """Create real client without DB overrides (for real auth/session testing)."""
    if not USE_REAL_AUTH:
        pytest.skip("USE_REAL_AUTH not enabled")
    with TestClient(app_instance, raise_server_exceptions=False) as test_client:
        csrf_token = _get_csrf_token(test_client)
        if csrf_token:
            test_client.headers["X-CSRF-Token"] = csrf_token
        yield test_client


@pytest.fixture
def test_user(db_session: Session, app_modules) -> dict:
    """Create and return a test user dict."""
    User = app_modules['User']
    UserRole = app_modules['UserRole']

    user = User(
        id=uuid4(),
        email=f"test_{pytest.timestamp}@example.com",
        hashed_password=_CACHED_PASSWORD_HASH,
        full_name='Test Admin',
        role=UserRole.ADMIN,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return {
        "id": str(user.id),
        "email": user.email,
        "password": _TEST_PASSWORD,
        "full_name": user.full_name,
        "role": user.role,
        "user": user
    }


@pytest.fixture
def authenticated_client(client: TestClient, test_user: dict, firebase_token: str | None, app_instance, app_modules) -> TestClient:
    """Create authenticated test client with CSRF and auth."""
    if USE_REAL_AUTH:
        pytest.skip("Use real_authenticated_client for real auth tests")
    user_obj = test_user["user"]
    get_current_user = app_modules['get_current_user']
    get_current_user_from_session = app_modules['get_current_user_from_session']

    # FIX: Authorization code expects a dict, not a SQLAlchemy model
    # The require_role decorator calls current_user.get("role") which fails on model objects
    user_dict = {
        "id": str(user_obj.id),
        "email": user_obj.email,
        "role": user_obj.role.value if hasattr(user_obj.role, 'value') else str(user_obj.role),
        "full_name": user_obj.full_name,
        "is_active": user_obj.is_active,
        "firebase_uid": getattr(user_obj, 'firebase_uid', None),
    }

    # Override the auth dependency to use our test user as dict
    app_instance.dependency_overrides[get_current_user] = lambda: user_dict
    app_instance.dependency_overrides[get_current_user_from_session] = lambda: user_dict

    # Set authorization header
    if firebase_token:
        client.headers["Authorization"] = f"Bearer {firebase_token}"
    else:
        client.headers["Authorization"] = f"Bearer test_token_{user_obj.id}"

    return client


@pytest.fixture(scope="session")
def real_session_id(real_client: TestClient, firebase_token: str | None) -> str:
    """Create a real Redis-backed session using Firebase token."""
    if not firebase_token:
        pytest.skip("Firebase token unavailable; set SKIP_FIREBASE_TOKEN=false")
    response = real_client.post(
        "/api/v2/auth/firebase/verify",
        json={"id_token": firebase_token},
    )
    if response.status_code != 200:
        pytest.fail(f"Firebase verify failed: {response.status_code} {response.text}")
    session_id = response.json().get("session_id")
    if not session_id:
        pytest.fail(f"No session_id returned: {response.text}")
    return session_id


@pytest.fixture(scope="session")
def real_authenticated_client(real_client: TestClient, real_session_id: str) -> TestClient:
    """Authenticated client using real Redis session ID."""
    real_client.headers["Authorization"] = f"Bearer {real_session_id}"
    return real_client


@pytest.fixture
def mock_saga_patient(db_session: Session, app_modules, app_instance):
    """
    Mock onboarding coordinator to avoid saga transaction conflicts.

    The saga pattern makes 4 internal commits that conflict with test fixture's
    outer transaction rollback. This fixture patches BOTH the factory module AND
    the route module to ensure the mock is used regardless of import order.

    CRITICAL: This fixture must be used WITH authenticated_client to work properly.
    The patch is applied at multiple levels to intercept the coordinator.
    """
    from unittest.mock import AsyncMock, MagicMock, patch
    Patient = app_modules['Patient']

    created_patients = []

    async def mock_create_patient(patient_data, doctor_id, current_user=None, idempotency_key=None):
        """Mock coordinator that creates patient directly in test session."""
        print(f"🎯 MOCK: create_patient called with name={getattr(patient_data, 'name', 'N/A')}")
        from app.models.enums import FlowState
        patient = Patient(
            id=uuid4(),
            doctor_id=doctor_id,
            flow_state=FlowState.ONBOARDING  # Use correct enum value
        )

        # Handle Pydantic model input (PatientCreate)
        if hasattr(patient_data, 'name'):
            patient.name = patient_data.name
        if hasattr(patient_data, 'phone') and patient_data.phone:
            patient.set_phone(patient_data.phone)
            # Emulate duplicate phone detection (same doctor, not deleted)
            existing = (
                db_session.query(Patient)
                .filter(
                    Patient.phone_hash == patient.phone_hash,
                    Patient.doctor_id == doctor_id,
                    Patient.deleted_at.is_(None),
                )
                .first()
            )
            if existing:
                raise ValueError("Duplicate phone")
        if hasattr(patient_data, 'email') and patient_data.email:
            patient.set_email(patient_data.email)
        if hasattr(patient_data, 'cpf') and patient_data.cpf:
            patient.set_cpf(patient_data.cpf)
        if hasattr(patient_data, 'birth_date') and patient_data.birth_date:
            patient.birth_date = patient_data.birth_date
        if hasattr(patient_data, 'treatment_type') and patient_data.treatment_type:
            patient.treatment_type = patient_data.treatment_type
        if hasattr(patient_data, 'treatment_start_date') and patient_data.treatment_start_date:
            patient.treatment_start_date = patient_data.treatment_start_date

        db_session.add(patient)
        db_session.flush()  # Get ID without committing
        db_session.refresh(patient)
        created_patients.append(patient)
        return patient

    # Create mock coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.create_patient = AsyncMock(side_effect=mock_create_patient)

    # Mock factory function that returns our mock coordinator
    def mock_get_coordinator(db, saga_orchestrator=None):
        """Mocked factory function."""
        print("🔧 MOCK: get_onboarding_coordinator called (returning mock)")
        return mock_coordinator

    # Patch at the SOURCE module (where function is defined)
    # The crud.py imports it locally inside the function, so we only need to patch the source
    patchers = [
        patch(
            "app.services.patient.onboarding_factory.get_onboarding_coordinator",
            side_effect=mock_get_coordinator
        ),
    ]

    for patcher in patchers:
        patcher.start()

    yield {
        "coordinator": mock_coordinator,
        "patients": created_patients
    }

    # Stop all patchers
    for patcher in patchers:
        patcher.stop()
