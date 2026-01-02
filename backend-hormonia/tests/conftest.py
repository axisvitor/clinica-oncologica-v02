
import os
import json
from typing import Generator
from uuid import uuid4

import pytest
from dotenv import load_dotenv

os.environ.setdefault("APP_ENVIRONMENT", "development")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("ENCRYPTION_KEY", "32byte-secret-key-for-testing-123")
os.environ.setdefault("ENCRYPTION_SALT", "test-salt-16bytes")

from sqlalchemy import create_engine, TypeDecorator, Text, Index
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB, INET, BYTEA
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
from app.dependencies.auth_dependencies import get_current_user

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
                elif str(column.type) == 'BYTEA' or isinstance(column.type, BYTEA):
                    column.type = BLOB()
                
                # Strip PG server defaults for SQLite
                if column.server_default is not None and hasattr(column.server_default, 'arg'):
                    arg_str = str(column.server_default.arg).lower()
                    if 'gen_random_uuid()' in arg_str:
                        column.server_default = None
            
            # Strip PG indexes for SQLite but preserve uniqueness
            new_indexes = set()
            for idx in table.indexes:
                # If it's a unique index with PG-specific where, create a plain unique index for SQLite
                if idx.unique and any(hasattr(idx, k) and getattr(idx, k) is not None for k in ['postgresql_where']):
                    new_idx = Index(
                        idx.name,
                        *[c for c in idx.columns],
                        unique=True
                    )
                    new_indexes.add(new_idx)
                elif not any(hasattr(idx, k) and getattr(idx, k) is not None 
                           for k in ['postgresql_where', 'postgresql_concurrently']):
                    new_indexes.add(idx)
            
            table.indexes = new_indexes

def _apply_sqlite_type_fixes():
    """Apply SQLite compatibility fixes to all models in Base.metadata."""
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSONBCompat()
            elif isinstance(column.type, INET):
                column.type = INETCompat()
            elif str(column.type) == 'BYTEA' or isinstance(column.type, BYTEA):
                column.type = BLOB()

            # Strip PG server defaults for SQLite
            if column.server_default is not None and hasattr(column.server_default, 'arg'):
                arg_str = str(column.server_default.arg).lower()
                if 'gen_random_uuid()' in arg_str:
                    column.server_default = None

        # Strip PG-specific indexes
        new_indexes = set()
        for idx in list(table.indexes):
            if idx.unique and any(hasattr(idx, k) and getattr(idx, k) is not None for k in ['postgresql_where']):
                new_idx = Index(
                    idx.name,
                    *[c for c in idx.columns],
                    unique=True
                )
                new_indexes.add(new_idx)
            elif not any(hasattr(idx, k) and getattr(idx, k) is not None
                       for k in ['postgresql_where', 'postgresql_concurrently']):
                new_indexes.add(idx)

        table.indexes = new_indexes


@pytest.fixture(scope="session")
def test_engine():
    # Detect if we should use Postgres or SQLite
    db_url = os.getenv("DATABASE_URL")
    if db_url and "postgresql" in db_url and os.getenv("APP_ENVIRONMENT") == "testing":
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

    # Drop all tables first to ensure clean state, then create all
    try:
        Base.metadata.drop_all(bind=engine)
    except Exception as e:
        print(f"Warning during drop_all: {e}")

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
def client(db_session: Session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

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

@pytest.fixture
def test_user(db_session):
    """Return user dict with credentials for login tests."""
    password = "testpass123"
    user = create_test_user(db_session, password=password)
    return {
        "id": str(user.id),
        "email": user.email,
        "password": password,
        "full_name": user.full_name,
        "role": user.role,
        "user": user  # Keep User object for tests that need it
    }


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
    app.dependency_overrides[get_current_user] = lambda: user_obj
    client.headers["Authorization"] = f"Bearer test_token_{user_obj.id}"
    return client
