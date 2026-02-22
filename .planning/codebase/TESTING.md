# Testing Patterns

**Analysis Date:** 2026-02-22

## Test Framework

**Runner:**
- pytest 7.0+ (minversion = "7.0")
- Config: `backend-hormonia/pyproject.toml` under `[tool.pytest.ini_options]`

**Key Plugins:**
- `pytest-asyncio` 0.23.x — async test support (`asyncio_mode = "auto"`)
- `pytest-cov` 5.x — coverage reporting
- `pytest-xdist` 3.x — parallel test execution (`-n auto`)
- `fakeredis` 2.x — in-memory Redis for Redis-dependent tests
- `faker` 21.x — fake data generation (used in limited contexts)

**Assertion Library:**
- pytest built-in assertions (no additional library)

**Run Commands:**
```bash
pytest                                          # Run all tests
pytest -m "not slow and not integration and not performance"  # Fast subset
pytest -n auto -m "unit and not slow"           # Unit tests in parallel (xdist)
pytest --cov=app --cov-report=html --cov-report=term-missing  # With coverage
pytest -m integration tests/integration/       # Integration tests only
pytest -m "not integration"                    # Skip integration tests
```

## Test File Organization

**Location:**
- All tests in `backend-hormonia/tests/` — separate from application code (not co-located)

**Directory Structure:**
```
tests/
├── conftest.py                  # Root fixtures: db engine, db_session, client, auth_headers
├── api/
│   ├── conftest.py              # API-level fixtures, CSRF injection
│   ├── critical/                # P0 smoke tests (auth, patients, quiz)
│   └── v2/
│       ├── conftest.py          # V2 fixtures: auth headers by role, patient factories
│       └── test_*.py            # Endpoint tests organized by domain
├── unit/
│   ├── services/                # Service unit tests (mocked dependencies)
│   └── test_*.py                # Standalone unit tests
├── integration/
│   ├── conftest.py              # Real DB integration fixtures
│   └── test_*.py                # Integration tests (real DB, no mocks)
├── services/                    # Service-specific test suites
│   ├── follow_up/
│   ├── webhook/
│   └── websocket/
├── validation/                  # Data validation tests
├── performance/                 # Performance benchmark tests
├── security/                    # Security tests (currently excluded from default collection)
└── utils/                       # Test utilities
    ├── async_test_client.py     # AsyncTestClient (httpx-backed sync-friendly client)
    └── sync_executor.py         # SyncExecutor for SQLite thread-safety
```

**Naming:**
- Files: `test_<domain>.py` or `test_<specific_scenario>.py`
- Classes: `class Test<Domain>:` or `class Test<ScenarioGroup>:`
- Functions: `def test_<verb>_<subject>_<condition>(self, ...):`

**Excluded from Default Collection:**
`tests/conftest.py` defines `collect_ignore_glob` that excludes superseded test suites:
- `api/critical/test_auth_login.py`, `api/critical/test_auth_refresh.py` — superseded
- `security/test_*.py` — not included in default run
- `validation/daily_flow_30_days/test_*.py` — db-dependent, excluded by default

## Test Structure

**Suite Organization:**
```python
class TestPatientsV2:
    """Test suite for patients v2 endpoints"""

    def test_list_patients_basic(self, client, db, auth_headers):
        """Test basic patient listing"""
        response = client.get("/api/v2/patients", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "next_cursor" in data

    def test_get_patient_by_id_not_found(self, client, auth_headers):
        """Test 404 for missing patient"""
        response = client.get(f"/api/v2/patients/{uuid4()}", headers=auth_headers)
        assert response.status_code == 404
```

**Async Test Pattern:**
```python
@pytest.mark.asyncio
async def test_session_id_priority_cookie_first(monkeypatch):
    """Cookie should take priority over header and bearer."""
    monkeypatch.setattr(settings, "ENABLE_COOKIE_PRIORITY", True)
    request = _build_request()
    redis_cache = _build_redis_cache(firebase_uid="b" * 28)
    result = await get_current_user_from_session(
        request=request,
        session_cookie_id="cookie-session",
        ...
        redis_cache=redis_cache,
    )
    assert result["id"] == "user-123"
```

**Integration Test Pattern (class + marks):**
```python
@pytest.mark.integration
class TestPatientOnboardingSaga:
    def test_complete_patient_registration_saga(
        self,
        real_db_session: Session,
        real_saga_orchestrator: SagaOrchestrator,
        sample_patient_data: dict,
        cleanup_patients,
        cleanup_sagas,
    ):
        patient = Patient(**sample_patient_data)
        real_db_session.add(patient)
        real_db_session.commit()
        ...
        assert patient.id is not None
```

**Patterns:**
- `autouse=True` fixtures for common setup/teardown (CSRF injection, circuit breaker reset, flow template seeding)
- `yield` fixtures for setup/teardown with cleanup:
  ```python
  @pytest.fixture
  def auth_headers_admin(test_admin_user):
      app.dependency_overrides[get_current_user] = _override_current_user
      yield headers
      app.dependency_overrides.pop(get_current_user, None)
  ```
- `scope="session"` for expensive setup (test engine creation)
- `scope="function"` (default) for DB sessions (per-test transaction rollback)

## Mocking

**Framework:** `unittest.mock` (`MagicMock`, `AsyncMock`, `patch`)

**Standard Mocking Pattern:**
```python
from unittest.mock import MagicMock, AsyncMock, patch

@pytest.fixture
def response_processor(mock_db, mock_config):
    with patch("app.services.response_processor.processor.get_platform_sync_service") as mock_sync, \
         patch("app.services.response_processor.processor.flow_event_broadcaster") as mock_broadcaster:
        mock_sync_service = AsyncMock()
        mock_sync_service.sync_patient_record_update = AsyncMock()
        mock_sync.return_value = mock_sync_service
        mock_broadcaster.broadcast_patient_interaction = AsyncMock()

        processor = ResponseProcessor(mock_db, mock_config)
        # Override repositories for isolation
        processor.message_repo = MagicMock()
        processor.patient_repo = MagicMock()
        return processor
```

**FastAPI Dependency Override Pattern:**
All auth dependencies are overridden via `app.dependency_overrides`:
```python
async def _override_current_user(request: Request):
    request.state.user = test_admin_user
    return test_admin_user

app.dependency_overrides[get_current_user] = _override_current_user
yield headers
app.dependency_overrides.pop(get_current_user, None)  # Cleanup in finally
```

**Firebase Mock Pattern:**
```python
@pytest.fixture
def mock_firebase():
    with patch('firebase_admin.auth') as mock_auth:
        mock_auth.verify_id_token = MagicMock()
        with patch("app.api.v2.routers.auth.verify_token", new_callable=AsyncMock) as mock_router_verify:
            async def _bridge_verify_token(id_token: str):
                result = mock_auth.verify_id_token(id_token)
                if inspect.isawaitable(result):
                    return await result
                return result
            mock_router_verify.side_effect = _bridge_verify_token
            yield mock_auth
```

**Redis Mock Pattern:**
- Unit tests: `MagicMock()` for sync Redis operations
- Integration tests: `_NoopRedisCache` in-memory implementation (defined in `tests/conftest.py`)
- Deduplication tests: `fakeredis.aioredis.FakeRedis()` for async Redis

**What to Mock:**
- External services: Firebase, WhatsApp/Evolution API, Gemini AI
- Redis (except integration tests that have `_NoopRedisCache`)
- External API calls via `patch` on the import path

**What NOT to Mock:**
- The database (use SQLite in-memory via `test_engine` fixture, or real Postgres for integration tests)
- SQLAlchemy models and repositories (use real instances against test DB)
- Application logic under test (mock only external boundaries)

## Fixtures and Factories

**Database Fixtures (root `conftest.py`):**
```python
@pytest.fixture(scope="session")
def test_engine():
    # Auto-detects TEST_DATABASE_URL; falls back to SQLite in-memory
    # USE_TEST_POSTGRES=1 or localhost URL activates Postgres
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    ...
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    _apply_sqlite_type_fixes()  # Replaces JSONB/INET/UUID/ARRAY with SQLite-compatible types
    Base.metadata.create_all(bind=engine, checkfirst=True)
    yield engine

@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection, expire_on_commit=False)
    yield session
    session.close()
    transaction.rollback()  # Automatic rollback for test isolation
```

**Factory Fixture Pattern (v2 conftest):**
```python
@pytest.fixture
def create_test_patient(db_session: Session, test_doctor_user: User):
    """Factory fixture to create test patients."""
    def _create_patient(**kwargs):
        patient = Patient(
            id=kwargs.get('id', uuid4()),
            name=kwargs.get('name', 'Test Patient'),
            doctor_id=kwargs.get('doctor_id', test_doctor_user.id),
            ...
        )
        if 'email' in kwargs:
            patient.set_email(kwargs['email'])  # Handles LGPD encryption
        db_session.add(patient)
        db_session.commit()
        db_session.refresh(patient)
        return patient
    return _create_patient
```

**Auth Header Fixtures (yield pattern with cleanup):**
```python
@pytest.fixture
def auth_headers_admin(test_admin_user: User) -> dict:
    # Sets app.dependency_overrides for all auth dependencies
    app.dependency_overrides[get_current_user_from_session] = _override_session
    app.dependency_overrides[get_current_user] = _override_current_user
    ...
    yield {"X-Session-ID": ..., "Authorization": ..., "X-CSRF-Token": ..., "Cookie": ...}
    # Cleanup: remove all overrides
    app.dependency_overrides.pop(get_current_user_from_session, None)
    ...
```

**Standard Fixture Names:**
- `db_session` / `db` — SQLAlchemy Session (function scope, auto-rollback)
- `client` / `test_client` — `AsyncTestClient` (wraps FastAPI app)
- `auth_headers` — defaults to doctor role
- `auth_headers_admin` / `admin_headers` — admin role
- `auth_headers_doctor` / `doctor_headers` — doctor role
- `test_admin_user` / `test_doctor_user` — SQLAlchemy User instances
- `create_test_patient` — factory function fixture
- `test_patient_instance` / `test_patient` — single Patient instance
- `generate_patients` — bulk patient factory

**Location:**
- Root fixtures: `tests/conftest.py`
- API fixtures: `tests/api/conftest.py`
- V2 fixtures: `tests/api/v2/conftest.py`
- Integration fixtures: `tests/integration/conftest.py`

## Coverage

**Requirements:** No numeric target enforced in `pyproject.toml` (tool configured, threshold not set)

**View Coverage:**
```bash
pytest --cov=app --cov-report=html --cov-report=term-missing
# HTML report: backend-hormonia/htmlcov/
```

**Coverage Config (`pyproject.toml`):**
- Source: `app/`
- Excluded from coverage: `pragma: no cover`, `def __repr__`, `raise AssertionError`, `raise NotImplementedError`, `if __name__ == '__main__':`, `if TYPE_CHECKING:`, `@abstractmethod`

## Test Types

**Unit Tests (`tests/unit/`):**
- Scope: Single service class or function; all dependencies mocked
- Async: `@pytest.mark.asyncio` on async test functions
- DB: No DB usage — MagicMock for repositories
- Speed: Fast; run in parallel with `pytest -n auto -m unit`

**API Tests (`tests/api/v2/`):**
- Scope: FastAPI router + handler + serialization; real DB (SQLite), mocked external services
- Client: `AsyncTestClient` (sync-friendly httpx wrapper)
- Auth: FastAPI `dependency_overrides` for all auth dependencies
- CSRF: Auto-injected via `autouse=True` monkeypatch fixture in conftest

**Integration Tests (`tests/integration/`):**
- Scope: Full flow from API through services to DB; real Postgres preferred
- Mark: `@pytest.mark.integration` — skipped in fast test runs
- DB: Real DB connection (requires `TEST_DATABASE_URL` for Postgres, or SQLite fallback)
- Cleanup: Manual `cleanup_patients` / `cleanup_sagas` fixtures (no rollback)
- No mocking of internal application logic

**Validation Tests (`tests/validation/`):**
- Scope: Data validation scenarios, 30-day flow simulation
- Currently excluded from default collection (`collect_ignore_glob` in root conftest)

**Performance Tests (`tests/performance/`):**
- Mark: `@pytest.mark.performance` — excluded from fast suite
- Uses `benchmark_timer` fixture for timing assertions

## Custom Test Infrastructure

**AsyncTestClient (`tests/utils/async_test_client.py`):**
A synchronous-API client backed by `httpx.AsyncClient + ASGITransport`. Runs async code in a separate thread to avoid event loop conflicts. Preferred over `fastapi.testclient.TestClient` to avoid `BlockingPortal` deadlocks under heavy parallelism.

**SyncExecutor (`tests/utils/sync_executor.py`):**
Mimics `ThreadPoolExecutor` interface but runs tasks synchronously in the current thread. Prevents SQLite "wrong thread" errors during tests.

**SQLite Compatibility Layer (root `conftest.py`):**
`_apply_sqlite_type_fixes()` replaces PostgreSQL-specific column types with SQLite equivalents before `create_all`:
- `JSONB` → `JSONBCompat` (Text + JSON serialize/deserialize)
- `PGUUID` → `UUIDCompat` (Text + UUID conversion)
- `INET` → `INETCompat` (Text passthrough)
- `ARRAY` → `JSONBCompat`
- `BYTEA` → `BLOB`
- PostgreSQL server defaults (`gen_random_uuid()`) stripped
- PostgreSQL-specific indexes stripped

**pytest Markers:**
```
api, unit, slow, integration, asyncio, auth, crud, quiz, patient,
patients, routes, security, critical, p0, performance, timeout,
lgpd, idempotency, saga, encryption
```

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_process_inbound_message_success(response_processor):
    inbound = InboundMessage(patient_phone="5511999999999", content="Hello", whatsapp_id="wamid.123")
    patient = MagicMock(spec=Patient)
    patient.id = uuid4()
    response_processor.patient_repo.get_by_phone.return_value = patient

    result = await response_processor.process_inbound_message(inbound)
    assert result.success is True
```

**Error/Status Testing:**
```python
def test_get_patient_unauthorized(self, client, db):
    """Test 401 without auth headers"""
    response = client.get(f"/api/v2/patients/{uuid4()}")
    assert response.status_code in (401, 403)

def test_get_patient_not_found(self, client, auth_headers):
    """Test 404 for non-existent patient"""
    response = client.get(f"/api/v2/patients/{uuid4()}", headers=auth_headers)
    assert response.status_code == 404
```

**Circuit Breaker Reset (autouse):**
```python
@pytest.fixture(autouse=True)
def reset_db_circuit_breaker_state():
    """Prevent global DB circuit breaker state leakage across tests."""
    reset_circuit_breaker()
    yield
    reset_circuit_breaker()
```

**Redis Singleton Reset (autouse in root conftest):**
```python
@pytest.fixture(autouse=True)
def reset_redis_singletons():
    redis_utils._redis_manager = None
    yield
    redis_utils._redis_manager = None
```

---

*Testing analysis: 2026-02-22*
