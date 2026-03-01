# Phase 32 Research: Test Coverage

## Summary

Phase 32 adds a comprehensive test suite for the saga orchestrator and flow integration chain.  The saga codebase already has substantial test coverage from Phases 29-31 (audit, trace, and integrity verification tests).  This phase fills the remaining gaps: an end-to-end integration test for the happy path (TEST-01), per-handler compensation exercise tests (TEST-02), edge-case stress tests (TEST-03), symbol-level shim contract tests (TEST-04), and flow lifecycle tests (TEST-05).

The main findings are:

1. **Existing tests are structural assertions**, not behavioral exercises.  Phase 31 tests read source code and assert patterns statically; Phase 32 must execute the code paths and observe outcomes.
2. **SyncToAsyncSessionAdapter** in `tests/conftest.py` is the key enabler: it wraps a sync SQLite session so async saga code runs within a single test transaction that can be inspected after execution.
3. **Six v1.3 flow shims** already have split-contract tests, but they check class identity (`shim.X is canonical.X`), not symbol-set parity (`set(shim.__all__) == expected_symbols`).  TEST-04 requires the latter.
4. **Flow lifecycle (pause/resume/cancel)** tests exist for cancel and auto-resume but not for pause-mid-saga or resume-after-pause scenarios.

---

## Phase Requirements

| Requirement | Description | Plans |
|-------------|-------------|-------|
| TEST-01 | Integration test covers full onboarding saga happy path (create, execute steps, complete) | 32-01 |
| TEST-02 | Compensation test suite verifies each step's rollback handler produces correct cleanup | 32-02 |
| TEST-03 | Edge case tests for saga: timeout handling, concurrent saga execution, step retry exhaustion | 32-03 |
| TEST-04 | Split contract tests verify all shim exports match canonical package exports (no v1.3 regressions) | 32-04 |
| TEST-05 | Flow state operation tests: pause mid-saga, resume after pause, cancel during execution | 32-03 |

---

## Standard Stack

| Component | Technology | Version Constraint |
|-----------|------------|-------------------|
| Test runner | pytest | >=8.0 |
| Async tests | pytest-asyncio | asyncio_mode = "auto" |
| HTTP client | httpx.AsyncClient (via `from httpx import AsyncClient`) | Used in `client` fixture |
| DB engine | SQLite in-memory (default) or local Postgres (`USE_TEST_POSTGRES=1`) | SQLAlchemy 2.x |
| Mocking | unittest.mock (MagicMock, AsyncMock, patch) | stdlib |
| Async adapter | SyncToAsyncSessionAdapter (tests/conftest.py) | Project-internal |
| Saga fixtures | tests/fixtures/saga_fixtures.py | Project-internal |
| Markers | @pytest.mark.integration, @pytest.mark.asyncio (implicit with auto mode) | - |

---

## Architecture Patterns

### 1. Existing Test Inventory

The saga test suite currently has the following files and their focus:

| File | Tests | Focus | Phase |
|------|-------|-------|-------|
| `tests/orchestration/test_saga_orchestrator.py` | ~15 | Happy path, failures, resume, idempotency | Pre-v1.5 |
| `tests/services/test_saga_compensation.py` | ~25 | Retry logic, per-handler compensation, error tracking | Pre-v1.5 |
| `tests/integration/test_patient_saga.py` | ~5 | Real-DB integration: complete registration, compensation, concurrent, timeout | Pre-v1.5 |
| `tests/unit/orchestration/test_saga_module_audit.py` | ~15 | Phase 29: identity checks, __all__ completeness, SagaLogEntry fields | 29 |
| `tests/unit/orchestration/test_saga_orchestrator_split_contract.py` | 8 | Split contracts: import identity, metrics, LOC, phone format | 29 |
| `tests/unit/orchestration/test_saga_compensation_split_contract.py` | 6 | Split contracts: compensator identity, handler imports, LOC | 29 |
| `tests/unit/orchestration/test_saga_compensation_integrity.py` | 19 | Phase 31: step-handler mapping, reverse order, tx boundaries, idempotency guards | 31 |

**Key gap:** Phase 31 tests use static source-code reading (`_read_source()`, `_extract_async_method()`) to assert patterns exist.  Phase 32 must _execute_ the saga code and observe behavioral outcomes: records created, records cleaned up, state transitions completed.

### 2. Saga Step / Compensation Handler Matrix

The saga has 3 active forward steps and 3 compensation handlers (step 2 is deprecated/skipped):

| Step # | Forward Step Method | Compensation Handler | What It Does |
|--------|-------------------|---------------------|--------------|
| 1 | `step_create_patient(saga, patient_data, doctor_id, idempotency_key)` | `compensate_patient(db, saga, patient_repo)` | Creates Patient record; compensation soft-deletes via `is_active=False` |
| 3 | `step_initialize_flow(saga, patient, current_user, idempotency_key)` | `compensate_flow(db, saga)` | Creates PatientFlowState; compensation deletes the flow record |
| 4 | `step_send_welcome_message(saga, patient, idempotency_key)` | `compensate_message(db, saga)` | Schedules Message; compensation marks message CANCELLED |

Compensation runs in **reverse order**: 4 -> 3 -> 1 (skipping 2).

**Idempotency guard** in each handler: checks `step_data.get("compensated_steps", [])` before acting, and appends step name after completion.

### 3. Orchestrator Public API

```python
class SagaOrchestrator(SagaDBAdapterMixin):
    def __init__(self, db, redis_client=None, evolution_client=None)

    async def execute_patient_onboarding_saga(
        self, patient_data: PatientCreate, doctor_id=None,
        current_user=None, idempotency_key=None
    ) -> Optional[Patient]

    async def resume_saga(self, saga_id: UUID) -> ResumeResult

    async def get_saga_status(self, saga_id: UUID) -> Optional[SagaStatusInfo]

    async def list_failed_sagas(self, limit=10) -> List[FailedSagaSummary]
```

**Dependency injection points** (mockable for unit tests):
- `self.patient_repo` (PatientRepository)
- `self.flow_service` (PatientFlowService)
- `self.whatsapp_service` (UnifiedWhatsAppService)
- `self.message_service` (MessageService)
- `self.redis` (Redis client)
- `self.evolution_client` (EvolutionClient)
- `acquire_lock` (distributed lock context manager, patched with `_noop_acquire_lock` in existing tests)

### 4. Six v1.3 Shim Registry

| Shim File | Canonical Package | Exported Symbols | Existing Test File |
|-----------|------------------|------------------|--------------------|
| `app/services/flow_core.py` | `app/services/flow/core/service.py` | FlowCore, NotFoundError, ValidationError, FLOW_ACTIVE_STATUSES, FLOW_TERMINAL_STATUSES, FLOW_PAUSEABLE_STATUSES | `tests/unit/services/test_flow_core_split_contract.py` (3 tests) |
| `app/services/enhanced_flow_engine.py` | `app/services/enhanced_flow_engine_pkg/` | EnhancedFlowEngine, FlowContext, FlowType, create_enhanced_flow_engine, get_enhanced_flow_engine | `tests/unit/services/test_enhanced_flow_engine_split_contract.py` (7 tests) |
| `app/services/flow_management.py` | `app/services/flow/management/service.py` | FlowManagementService, FLOW_ACTIVE_STATUSES, FLOW_TERMINAL_STATUSES, FLOW_PAUSEABLE_STATUSES, EnhancedFlowEngine, now_sao_paulo | `tests/unit/services/test_flow_management_split_contract.py` (3 tests) |
| `app/services/flow_dashboard.py` | `app/services/flow_dashboard_pkg/` | FlowDashboardService, DashboardTimeframe, TrendDirection, get_flow_dashboard_service | `tests/unit/services/test_flow_dashboard_split_contract.py` (5 tests) |
| `app/services/flow_monitoring.py` | `app/services/flow_monitoring_pkg/` | FlowMonitoringService, HealthStatus, PerformanceMetrics, SystemAlert, AlertSeverity | `tests/unit/services/test_flow_monitoring_split_contract.py` (4 tests) |
| `app/services/flow_integrity.py` | `app/services/flow_integrity_pkg/` | FlowIntegrityService, get_flow_integrity_service | `tests/unit/services/test_flow_integrity_split_contract.py` (9 tests) |

**Current test pattern:** Identity checks (`assert shim.X is canonical.X`) and basic import verification.

**TEST-04 gap:** Must add symbol-set parity assertions.  For each shim, collect all symbols re-exported and compare against the expected set to detect any missing or stale re-exports at import time.

### 5. Flow State Machine (Pause / Resume / Cancel)

Implementation lives in `app/services/flow/management/pause_resume.py` (FlowManagementPauseResumeMixin):

**State transitions:**
- **Pause:** `active` -> `paused`, sets `state_data["paused"] = True`, optional `auto_resume_at`
- **Resume:** `paused` -> `active`, sets `state_data["paused"] = False`, clears `auto_resume_at`
- **Cancel:** `active`/`paused` -> `cancelled`, marks pending messages CANCELLED, revokes Celery tasks

**Known issue (Phase 30 finding, MEDIUM severity):**
- API-layer pause uses `state_data["paused"]`
- Agent-layer dispatch guard checks `state_data.get("flow_paused")`
- Auto-resume checks `state_data.get("paused")`
- Dual-key divergence means agent-layer pause check can pass when API-layer has paused the flow

**Cancel / Saga boundary:**
Cancel does NOT trigger saga compensation.  They are independent lifecycles:
- Cancel = flow management cleanup (revoke Celery, mark messages)
- Compensation = saga failure rollback (reverse steps)

**Existing tests:**
- `tests/unit/services/test_flow_cancel.py` — 5 tests (cancel scenarios)
- `tests/unit/tasks/test_auto_resume_flows.py` — 4 tests (auto-resume)
- No tests for: pause-mid-saga, resume-after-pause, or cancel-during-execution

### 6. Test Infrastructure

**Database setup (`tests/conftest.py`):**
- `test_engine` (session-scoped): SQLite in-memory by default with StaticPool; Postgres if `USE_TEST_POSTGRES=1` or local host detected
- `_apply_sqlite_type_fixes()`: patches JSONB -> JSON, UUID -> CHAR(36), INET -> VARCHAR(45) at column-type level
- `_replace_postgres_types_with_sqlite()`: strips PostgreSQL-specific index options
- Multiple `_ensure_*_column()` functions apply schema patches for Postgres test databases

**Session fixtures:**
- `db_session` (function-scoped): sync Session in a transaction that rolls back after each test
- `db` alias: yields `db_session`
- `SyncToAsyncSessionAdapter`: wraps sync session for async code; `execute()` returns `_AwaitableResultProxy`; `commit()` calls `flush()` (keeps data in transaction); `rollback()` is a no-op (preserves test isolation)
- `client` fixture: overrides both `get_db` and `get_async_db` with the adapter

**Saga-specific fixtures (`tests/fixtures/saga_fixtures.py`):**
- `test_patient_data`: factory returning PatientCreate with realistic Brazilian phone
- `mock_redis`: MagicMock with pipeline and Redis lock support
- `mock_evolution_client`: MagicMock for EvolutionClient
- `saga_orchestrator`: creates SagaOrchestrator with real `db_session` + mocked redis/evolution
- `failed_saga_record`: pre-created PatientOnboardingSaga in FAILED state
- `completed_patient_record`: Patient linked to saga step_data
- `completed_flow_state`: PatientFlowState with saga metadata
- `saga_with_partial_completion`: saga at step 3 with step_data capturing step 1 output

**Lock bypass pattern (from existing orchestrator tests):**
```python
@asynccontextmanager
async def _noop_acquire_lock(*args, **kwargs):
    yield

# Patch in test:
with patch("app.orchestration.saga_orchestrator.orchestrator.acquire_lock",
           new=_noop_acquire_lock):
    result = await orchestrator.execute_patient_onboarding_saga(...)
```

**Async test configuration:**
- `pyproject.toml`: `asyncio_mode = "auto"` — no need for `@pytest.mark.asyncio` on every test
- All async test functions are auto-detected

---

## Don't Hand-Roll

| Need | Use This | Location |
|------|----------|----------|
| Saga orchestrator instance | `saga_orchestrator` fixture | `tests/fixtures/saga_fixtures.py` |
| Patient test data | `test_patient_data` fixture (factory) | `tests/fixtures/saga_fixtures.py` |
| Mocked Redis client | `mock_redis` fixture | `tests/fixtures/saga_fixtures.py` |
| Lock bypass | `_noop_acquire_lock` async context manager pattern | `tests/orchestration/test_saga_orchestrator.py` |
| Async DB session | `SyncToAsyncSessionAdapter(db_session)` | `tests/conftest.py` |
| Failed saga fixture | `failed_saga_record` | `tests/fixtures/saga_fixtures.py` |
| Partial-completion saga | `saga_with_partial_completion` | `tests/fixtures/saga_fixtures.py` |
| Source-code static analysis | `_read_source()`, `_extract_async_method()` | `tests/unit/orchestration/test_saga_compensation_integrity.py` |
| Compensation handler mocking | `AsyncMock(return_value=None)` for handler functions | `tests/orchestration/test_saga_orchestrator.py` |
| Phone normalization | `normalize_phone(phone, mode=PhoneValidationMode.BR_TO_E164)` | `app/schemas/validators/phone.py` |

---

## Common Pitfalls

### 1. SyncToAsyncSessionAdapter.commit() flushes but does not commit
The adapter's `commit()` calls `self._sync_session.flush()`, NOT `commit()`.  This keeps all data within the test transaction for inspection.  Tests that check DB state after saga completion will find records via the same session.  But tests that expect a real commit boundary (e.g., testing isolation between steps) must use `begin_nested()` savepoints.

### 2. SQLite JSON limitations
SQLite uses TEXT for JSONB columns.  Tests must not rely on PostgreSQL JSONB operators (`->`, `->>`, `@>`).  Use Python-side assertions on deserialized `step_data` instead of SQL JSON path queries.

### 3. Distributed lock is mandatory for saga execution
`execute_patient_onboarding_saga` uses `async with acquire_lock(...)`.  Without patching, tests will try to connect to Redis.  Always patch with `_noop_acquire_lock` for unit tests, or provide a mock Redis client for the saga's `self.redis`.

### 4. Step 2 is deprecated but still referenced
The orchestrator skips step 2 (Firebase setup).  Tests should NOT create a handler for step 2.  Compensation tests should verify that the reverse sequence is 4 -> 3 -> 1, not 4 -> 3 -> 2 -> 1.

### 5. Phone normalization in test data
`execute_patient_onboarding_saga` calls `normalize_phone()` on `patient_data.phone`.  Test phone numbers must be valid Brazilian format.  The `test_patient_data` fixture already provides `"+5511999887766"` which normalizes correctly.

### 6. Saga status enum values
Use `SagaStatus.STARTED`, `SagaStatus.COMPLETED`, `SagaStatus.COMPLETED_WITH_WARNINGS`, `SagaStatus.FAILED`, `SagaStatus.COMPENSATED` from `app/models/enums.py`.  Do not hardcode string values.

### 7. Idempotency key hashing
The saga constructs a lock key from a SHA-256 hash of the normalized phone.  Tests that exercise concurrent saga execution must use different phone numbers or the same phone with different idempotency keys.

### 8. Dual pause key divergence
When testing pause-mid-saga, set `state_data["paused"] = True` (API convention).  Be aware that agent-layer code checks `state_data.get("flow_paused")`, not `state_data["paused"]`.  This is a known MEDIUM-severity finding from Phase 30.

---

## Code Examples

### Happy-path integration test pattern

```python
async def test_onboarding_saga_happy_path(db_session, mock_redis, mock_evolution_client, test_patient_data):
    """TEST-01: Full onboarding saga creates patient, flow, and message."""
    from app.orchestration.saga_orchestrator import SagaOrchestrator
    from app.models.enums import SagaStatus

    adapter = SyncToAsyncSessionAdapter(db_session)
    orchestrator = SagaOrchestrator(
        db=adapter,
        redis_client=mock_redis,
        evolution_client=mock_evolution_client,
    )

    patient_data = test_patient_data()

    with patch("app.orchestration.saga_orchestrator.orchestrator.acquire_lock",
               new=_noop_acquire_lock):
        patient = await orchestrator.execute_patient_onboarding_saga(
            patient_data=patient_data,
            doctor_id=uuid.uuid4(),
        )

    assert patient is not None
    assert patient.phone == "+5511999887766"

    # Verify saga record
    saga = db_session.query(PatientOnboardingSaga).first()
    assert saga.status in (SagaStatus.COMPLETED, SagaStatus.COMPLETED_WITH_WARNINGS)
    assert saga.completed_at is not None

    # Verify flow state created
    flow = db_session.query(PatientFlowState).filter_by(patient_id=patient.id).first()
    assert flow is not None

    # Verify message scheduled
    msg = db_session.query(Message).filter_by(patient_id=patient.id).first()
    # Message may or may not exist depending on WhatsApp mock behavior
```

### Per-handler compensation exercise pattern

```python
async def test_compensate_message_marks_cancelled(db_session, mock_redis):
    """TEST-02: compensate_message sets message status to CANCELLED."""
    from app.orchestration.saga_orchestrator.compensation_handlers import compensate_message

    adapter = SyncToAsyncSessionAdapter(db_session)

    # Create prerequisite records
    saga = PatientOnboardingSaga(id=uuid.uuid4(), status=SagaStatus.FAILED, ...)
    message = Message(patient_id=patient.id, status="pending", ...)
    db_session.add_all([saga, message])
    db_session.flush()

    saga.step_data = {"message_id": str(message.id), "compensated_steps": []}

    await compensate_message(adapter, saga)

    db_session.refresh(message)
    assert message.status == "CANCELLED"
    assert "message" in saga.step_data["compensated_steps"]
```

### Shim symbol parity pattern

```python
def test_flow_core_shim_exports_all_canonical_symbols():
    """TEST-04: Shim re-exports match expected symbol set."""
    import app.services.flow_core as shim

    expected_symbols = {
        "FlowCore", "NotFoundError", "ValidationError",
        "FLOW_ACTIVE_STATUSES", "FLOW_TERMINAL_STATUSES", "FLOW_PAUSEABLE_STATUSES",
    }

    shim_symbols = {name for name in dir(shim) if not name.startswith("_")}
    missing = expected_symbols - shim_symbols
    assert not missing, f"Shim missing symbols: {missing}"
```

---

## Sources

| Source | Path | Relevance |
|--------|------|-----------|
| Saga orchestrator | `backend-hormonia/app/orchestration/saga_orchestrator/orchestrator.py` | Public API, step execution sequence |
| Saga steps | `backend-hormonia/app/orchestration/saga_orchestrator/steps.py` | 3 forward steps, dual-mode DB execution |
| Compensation handlers | `backend-hormonia/app/orchestration/saga_orchestrator/compensation_handlers.py` | 3 handlers + track_compensation_failure |
| Saga __init__ | `backend-hormonia/app/orchestration/saga_orchestrator/__init__.py` | 16 exported symbols |
| Saga fixtures | `backend-hormonia/tests/fixtures/saga_fixtures.py` | Reusable fixtures for saga testing |
| Orchestrator tests | `backend-hormonia/tests/orchestration/test_saga_orchestrator.py` | Existing happy path + failure tests |
| Compensation tests | `backend-hormonia/tests/services/test_saga_compensation.py` | Per-handler compensation tests |
| Integration tests | `backend-hormonia/tests/integration/test_patient_saga.py` | Real-DB integration tests |
| Phase 31 integrity | `backend-hormonia/tests/unit/orchestration/test_saga_compensation_integrity.py` | Static analysis verification |
| Saga audit tests | `backend-hormonia/tests/unit/orchestration/test_saga_module_audit.py` | Module identity + __all__ tests |
| Orchestrator split | `backend-hormonia/tests/unit/orchestration/test_saga_orchestrator_split_contract.py` | Split contract tests |
| Compensation split | `backend-hormonia/tests/unit/orchestration/test_saga_compensation_split_contract.py` | Split contract tests |
| Flow cancel tests | `backend-hormonia/tests/unit/services/test_flow_cancel.py` | Cancel path tests |
| Auto-resume tests | `backend-hormonia/tests/unit/tasks/test_auto_resume_flows.py` | Auto-resume task tests |
| Pause/resume impl | `backend-hormonia/app/services/flow/management/pause_resume.py` | FlowManagementPauseResumeMixin |
| Root conftest | `backend-hormonia/tests/conftest.py` | DB engine, sessions, SyncToAsyncSessionAdapter |
| 6 shim files | `backend-hormonia/app/services/flow_core.py`, `enhanced_flow_engine.py`, `flow_management.py`, `flow_dashboard.py`, `flow_monitoring.py`, `flow_integrity.py` | v1.3 split re-exports |
| 6 split contract tests | `backend-hormonia/tests/unit/services/test_flow_*_split_contract.py` | Existing identity-level tests |
| Phase 29 research | `.planning/phases/29-saga-module-audit/29-RESEARCH.md` | Saga module structure |
| Phase 30 research | `.planning/phases/30-flow-integration-trace/30-RESEARCH.md` | Flow trace findings |
| Phase 31 research | `.planning/phases/31-compensation-integrity/31-RESEARCH.md` | Compensation integrity findings |
| Phase 31 plans | `.planning/phases/31-compensation-integrity/31-01-PLAN.md`, `31-02-PLAN.md` | Implementation details |
| pyproject.toml | `backend-hormonia/pyproject.toml` | asyncio_mode = "auto" |
