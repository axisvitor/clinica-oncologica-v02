# Phase 5: Flow Consolidation — Research

**Researched:** 2026-02-22
**Domain:** Dual Flow System Elimination — Python/FastAPI, SQLAlchemy, Pydantic, Celery
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Feature flag routes by patient type: new patients go to canonical system immediately, existing patients stay on current system until migrated
- All patients should eventually be migrated to the canonical system, even mid-flow
- Full code deletion of the losing system — not tombstoned (breaking from project's tombstone pattern for this case)
- Decommissioning happens within Phase 5, not deferred to a later phase
- Tests must run against real PostgreSQL (not mocked/in-memory)
- New-vs-existing patient routing for feature flag (not percentage-based ramp)

### Claude's Discretion
- Which flow system is canonical (production vs QW-021) — based on analysis of both
- Whether to port concepts from losing system
- FlowDispatcher as temporary migration tool vs permanent facade
- Data parity investigation and migration needs
- Routing audit logging during transition
- Import path for callers (dispatcher vs direct canonical)
- Database artifact cleanup for losing system
- Critical patient scenarios for integration tests
- Alert pipeline inclusion scope for FLOW-03
- Edge case identification from flow state model

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FLOW-01 | Consolidar dual flow systems — escolher sistema canônico (production `flow_core.py` ou QW-021 `services/flow/core/manager.py`) e decomissionar o outro via Strangler Fig pattern | Analysis below confirms production system as canonical; deletion scope identified |
| FLOW-02 | Implementar `FlowDispatcher` facade com feature-flag routing para migração incremental | Existing `FlowFeatureFlags` in `flow/config.py` provides the feature flag infrastructure; FlowDispatcher design documented below |
| FLOW-03 | Testes de integração cobrindo flow system unificado + alert pipeline end-to-end | Integration test infrastructure (conftest.py, real DB fixtures) already exists; alert pipeline via `FlowAlertsService` identified |
</phase_requirements>

---

## Summary

The project has two coexisting flow systems that were built to serve different purposes but now diverge silently when processing patient state. The **production system** lives in flat files (`flow_core.py`, `enhanced_flow_engine.py`, `flow_management.py`, `flow_service.py`) and operates on SQLAlchemy `PatientFlowState` models using a day-based treatment-flow model with AI/ML personalization. The **QW-021 system** lives in `app/services/flow/core/manager.py` and uses step-based execution with Pydantic `FlowContext` objects.

The production system has **59 external import references** across 14 files in API routes, tasks, saga orchestrator, agents, and domain services. The QW-021 system has **7 external import references** — exclusively in `service_provider.py` (which exposes it as `flow_service` property, consumed by one dependency injection point). This is conclusive evidence: the production system is the canonical choice.

Both systems write to the **same database table** (`patient_flow_states`), but with different data layouts: the production system uses `step_data`/`current_step` columns directly, while QW-021 serializes an entire `FlowContext` Pydantic object into the `flow_metadata` JSONB column. This is the root cause of divergence — QW-021 can partially overwrite production records.

**Primary recommendation:** Designate `flow_core.py` / `EnhancedFlowEngine` as canonical. Build `FlowDispatcher` as a thin facade in front of `PatientFlowService.initialize_default_flow()` (the enrollment entry point), controlled by a `FLOW_CANONICAL_SYSTEM=production` env var. Delete the QW-021 `app/services/flow/core/` package. Write integration tests that cover onboarding → advancement → alert evaluation end-to-end against real PostgreSQL.

---

## System Comparison

### Production System (Canonical Recommendation)

**Files:** `app/services/flow_core.py` (846 lines), `app/services/enhanced_flow_engine.py` (967 lines), `app/services/flow_management.py` (687 lines), `app/services/flow_service.py` (443 lines)

**Data model:** `PatientFlowState` (SQLAlchemy ORM, `patient_flow_states` table). Key columns: `patient_id`, `flow_template_version_id`, `current_step` (integer day-based), `step_data` (JSONB), `flow_metadata` (JSONB), `status`, `started_at`, `completed_at`, `next_scheduled_at`, `version` (optimistic lock counter).

**Architecture:** Day-based treatment flow. `FlowCore` is the base class. `EnhancedFlowEngine(FlowCore)` adds Gemini AI client, LangGraph humanization/sentiment, conversation memory, anti-repetition logic. `FlowManagementService` adds optimistic locking for advancement. `FlowService(FlowCore)` is the V2 REST facade with Redis caching and cursor-based pagination.

**Call sites:** 59 import references across:
- `app/api/v2/flows/advanced.py`, `state.py`, `templates.py` — REST endpoints
- `app/api/v2/routers/flows.py`, `patients/flow.py` — routers
- `app/services/flow/sequential_message_handler.py` — webhook message handling
- `app/services/patient/flow_service.py` — patient lifecycle (used by saga)
- `app/services/patient/onboarding_factory.py`
- `app/orchestration/saga_orchestrator/orchestrator.py` and `steps.py`
- `app/domain/quizzes/integration/flow_integration_service.py`
- `app/tasks/flow_automation.py`, `tasks/flows/batch_tasks.py`
- `app/services/hive_mind_integration.py`
- `app/service_provider.py` (as `flow_engine`)

**Unique capabilities (no equivalent in QW-021):**
- `EnhancedFlowEngine.advance_flow_day()` — day-based treatment advancement
- AI message personalization via Gemini + LangGraph humanization graph
- Conversation memory and anti-repetition (`ConversationMemory`)
- Optimistic locking on `PatientFlowState.version`
- `FlowManagementService` with pause/resume/history/template-migration
- `FlowAlertsService` (completion rate, duration anomalies, inconsistent state alerts)
- Redis-cached analytics and V2 REST schemas

### QW-021 System (Losing System)

**Files:** `app/services/flow/core/manager.py` (803 lines), `engine.py` (317 lines), `lifecycle.py` (192 lines), `state_machine.py` (141 lines), `context.py` (280+ lines)

**Data model:** `FlowContext` (Pydantic BaseModel). Step-based (steps_completed list, current_step_id string). Serialized into `patient_flow_states.flow_metadata` JSONB column — same table as production system, but via `flow_metadata` overlay.

**Architecture:** Step-based orchestrator pattern. `FlowManager` coordinates `FlowEngine` (stateless step executor), `FlowValidator`, `FlowTemplateManager` (loads from `flow_template_versions.steps` JSONB), `FlowIntegrationManager` (plugin hooks), `FlowContextRepository` (in-memory cache + DB persistence via `FlowStateRepository`), `FlowLifecycleManager`.

**External call sites (production code only):** 7 references, all in `service_provider.py`:
- `service_provider.flow_service` property returns `FlowManager(self.db)` (line 293-296)
- `dependencies/service_dependencies.py` line 83: `return services.flow_service`
- This is the only injection point — no direct API routes, tasks, or saga steps call FlowManager

**Concepts worth preserving:**
- `FlowFeatureFlags` config in `app/services/flow/config.py` — already has `use_consolidated_flows` and `consolidated_flows_rollout_percentage` — adapt for new-vs-existing routing
- `FlowConfig.should_use_consolidated_for_flow()` — routing logic already exists but uses percentage rollout; adapt for patient-type routing
- `FlowEventBroadcaster` in `app/services/flow/analytics/` — evaluate if complements production broadcasting
- The step-validation framework in `app/services/flow/validation/` — keep only if concepts not in production

**Artifacts that need DB cleanup:**
- `flow_metadata` column contains serialized `FlowContext` for any QW-021-started flows — must be cleared or migrated for rows that have this data format
- No separate table exists for QW-021 — same `patient_flow_states` table used

---

## Architecture Patterns

### Recommended Project Structure After Consolidation

```
app/services/
├── flow_core.py             # CANONICAL — base class, unchanged
├── enhanced_flow_engine.py  # CANONICAL — AI-powered engine, unchanged
├── flow_management.py       # CANONICAL — optimistic locking + history, unchanged
├── flow_service.py          # CANONICAL — V2 REST facade, unchanged
├── flow_alerts.py           # CANONICAL — alert pipeline, unchanged
├── flow_dashboard.py        # CANONICAL — dashboard, unchanged
├── flow/
│   ├── __init__.py          # Keep (exports FlowType, FlowFeatureFlags, etc.)
│   ├── config.py            # Keep (adapt FlowFeatureFlags for new routing)
│   ├── types.py             # CANONICAL FlowType enum — keep
│   ├── flags.py             # Keep (is_awaiting_response, etc.)
│   ├── event_broadcaster.py # Keep
│   ├── context_parsing.py   # Keep
│   ├── constants.py         # Keep
│   ├── template_lookup.py   # Keep (used by production system)
│   ├── sequential_message_handler.py  # Keep
│   ├── sequential_response_gate.py    # Keep
│   ├── analytics/           # Keep
│   ├── templates/           # Keep (FlowTemplateManager loads from DB)
│   ├── monitoring/          # Keep
│   ├── [manager.py]         # KEEP as redirect shim only (next section)
│   └── core/                # DELETE ENTIRE PACKAGE (QW-021)
│       ├── __init__.py      # DELETE
│       ├── context.py       # DELETE
│       ├── engine.py        # DELETE
│       ├── lifecycle.py     # DELETE
│       ├── manager.py       # DELETE
│       └── state_machine.py # DELETE
│   ├── errors/              # DELETE (no production callers)
│   ├── execution/           # DELETE (no production callers)
│   ├── integrations/        # DELETE (no production callers)
│   └── validation/          # DELETE (no production callers)
├── dispatcher.py            # NEW — FlowDispatcher facade (see below)
```

**Note on `flow/manager.py`:** This is already a compatibility wrapper for `from .core.manager import FlowManager`. When `core/` is deleted, convert to: raise `ImportError` with guidance to use `app.services.dispatcher.FlowDispatcher`.

### Pattern 1: FlowDispatcher Facade

**What:** Thin routing layer that intercepts flow initialization and routes based on feature flag. For Phase 5, since canonical = production, the dispatcher always routes to `EnhancedFlowEngine`/`PatientFlowService`. The dispatcher's primary value is as a seam that prevents future dual-system divergence.

**Recommended location:** `app/services/dispatcher.py`

**Feature flag mechanism:** Environment variable `FLOW_CANONICAL_SYSTEM` (default: `"production"`). Read at import time from `settings` (pydantic-settings). No runtime toggle needed — the intent is to complete migration and remove the flag.

**Whether FlowDispatcher is permanent or temporary:** Recommend permanent, but slim. It provides a stable import target (`from app.services.dispatcher import FlowDispatcher`) that API routes and tasks can reference. If the QW-021 system is ever revisited, the seam exists. If not, the class is a simple pass-through with no overhead.

**Example pattern:**
```python
# app/services/dispatcher.py
# Source: direct analysis of production call sites (2026-02-22)

import logging
from typing import Optional
from uuid import UUID

from app.models.flow import PatientFlowState
from app.models.patient import Patient

logger = logging.getLogger(__name__)

# Feature flag: which system handles new enrollments
# Set FLOW_CANONICAL_SYSTEM=production (default) after consolidation
CANONICAL_SYSTEM = "production"  # Read from settings in real impl


class FlowDispatcher:
    """
    Facade over the canonical flow system.

    Routing rule:
      - New patients: canonical system (EnhancedFlowEngine via PatientFlowService)
      - Existing patients mid-flow: same system they started on (production)
      - After full migration: all patients go to canonical, flag removed

    In Phase 5, both new and existing patients route to production system.
    The dispatcher exists to provide a stable seam and audit logging.
    """

    def __init__(self, db):
        self.db = db
        self._logger = logging.getLogger(__name__)

    async def initialize_flow(
        self,
        patient: Patient,
        current_user_id: Optional[UUID] = None,
        auto_commit: bool = True,
    ) -> Optional[PatientFlowState]:
        """Route flow initialization to canonical system."""
        self._logger.info(
            "FlowDispatcher.initialize_flow: patient=%s system=%s",
            patient.id,
            CANONICAL_SYSTEM,
        )
        # Route audit log entry (see pitfall: missing routing audit)
        from app.services.patient.flow_service import PatientFlowService
        service = PatientFlowService(self.db)
        return await service.initialize_default_flow(
            patient=patient,
            current_user_id=current_user_id,
            auto_commit=auto_commit,
        )
```

### Pattern 2: New-vs-Existing Patient Routing

**What:** The feature flag distinguishes new patients (no `PatientFlowState` record) from existing patients (have active flow state). This is the boundary condition during migration.

**How to detect "new patient":**
```python
# Source: analysis of FlowStateRepository and PatientFlowState model (2026-02-22)
existing_flow = flow_state_repo.get_active_flow(patient_id)
is_new_patient = existing_flow is None
```

**Migration path for existing patients:**
The production system already uses `PatientFlowState` for all records. Any QW-021-managed flows would have a `flow_metadata` JSONB column populated with serialized `FlowContext`. Migration means:
1. For rows with `flow_metadata` != NULL: parse the step-based context and map `current_step_id` to day-based `current_step` integer (or simply clear `flow_metadata` after verifying `step_data` is correct)
2. The production system can already read these rows via `state_data`/`step_data` aliases

### Pattern 3: Integration Test Structure

**Framework:** pytest + pytest-asyncio (`asyncio_mode = "auto"` already configured in `pyproject.toml`)
**Real DB:** Use pattern from `tests/integration/conftest.py` — `DATABASE_URL` env var + `CONFIRM_REAL_DB=1` guard + `NullPool` engine + per-function session with cleanup fixtures

**Test scenarios to cover (FLOW-03):**

| Scenario | What to assert |
|----------|---------------|
| New patient onboarding via dispatcher | `PatientFlowState` created, `FlowDispatcher` routed to production, audit log entry written |
| Advance flow to next day | `current_step` incremented, AI message generated (can mock Gemini in integration), `flow_metadata` not corrupted |
| Existing patient mid-flow detection | dispatcher correctly identifies existing flow and routes to production system |
| Completion | `status = "completed"`, `completed_at` populated |
| Alert pipeline evaluation | `FlowAlertsService.evaluate_alerts()` runs against real data, `evaluate_flow_alerts` Celery task callable |

**Alert pipeline scope (FLOW-03):** Yes, include alert pipeline. `FlowAlertsService.evaluate_alerts()` already exists in `app/services/flow_alerts.py` and is triggered by `app/tasks/flows/monitoring.evaluate_flow_alerts` Celery task (registered in `celery_app.py`). Test it with a controlled scenario (create patient flow in "stuck" state, run alert evaluation, assert alert was created via `AlertManager`).

### Anti-Patterns to Avoid

- **Tombstoning the QW-021 package:** The context decision is full deletion, not tombstone. Do not add `raise ImportError(...)` — delete the files entirely with `git rm`.
- **Percentage-based feature flag rollout:** Context explicitly excludes this. Use new-vs-existing patient routing only.
- **Leaving `service_provider.flow_service` returning FlowManager:** After deleting `core/manager.py`, this property must be updated to return the dispatcher or `PatientFlowService` directly.
- **Migrating data with raw SQL scripts without tests:** Migration logic must be covered by a test asserting before/after row state.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Feature flag config | Custom flag system | `FlowFeatureFlags` in `app/services/flow/config.py` | Already exists, env-var backed pydantic-settings |
| DB session in tests | Custom session factory | `real_engine` + `real_db_session` fixtures in `tests/integration/conftest.py` | Already handles NullPool, SSL, cleanup |
| Flow state cleanup in tests | Manual DELETE | `cleanup_flows` fixture in `tests/integration/conftest.py` | Handles FK ordering, rollback |
| Alert routing | Custom alert emitter | `app/services/alerts/alert_manager_refactored.py` | DI-based AlertManager, already wired to monitoring |
| Optimistic locking | Custom version check | `FlowCore._commit_flow_state_with_lock()` | Already implemented with `ConcurrentModificationError` |

---

## Common Pitfalls

### Pitfall 1: `service_provider.flow_service` Still Returns Deleted FlowManager

**What goes wrong:** After deleting `app/services/flow/core/manager.py`, importing `ServiceProvider.flow_service` raises `ImportError` at runtime — potentially crashing the entire FastAPI startup.

**Why it happens:** `service_provider.py` lines 293-296 create `FlowManager(self.db)` via lazy import. If the class is deleted but the import is not updated, the first call to `flow_service` property crashes.

**How to avoid:** In the same PR that deletes `core/manager.py`, update `service_provider.py` `flow_service` property to return the `FlowDispatcher` or remove it if unused.

**Warning signs:** `ImportError: cannot import name 'FlowManager' from 'app.services.flow'` in startup logs.

### Pitfall 2: QW-021 FlowContext in `flow_metadata` Column Corrupts Production Reads

**What goes wrong:** Some `patient_flow_states` rows may have `flow_metadata` containing a serialized `FlowContext` Pydantic object (from QW-021 writes). The production system's `PatientFlowState.state_data` alias reads `step_data` (a different column), but code that reads `flow_metadata` for caching or analytics may encounter QW-021-formatted JSON.

**Why it happens:** QW-021's `FlowContextRepository._persist_to_db()` writes `context.model_dump(mode="json")` to `flow_metadata`. This is distinct from production's use of `step_data` for actual step state.

**How to avoid:** Run a migration query to identify rows with QW-021 `flow_metadata` format (presence of `flow_instance_id`, `steps_completed` keys), and clear `flow_metadata` for those rows after verifying `step_data` is authoritative.

**Warning signs:** Analytics queries on `flow_metadata` returning unexpected structure (`steps_completed`, `variables` keys instead of production-format metadata).

### Pitfall 3: Deleting Shared Files That Production System Imports

**What goes wrong:** `app/services/flow/errors/`, `app/services/flow/execution/`, `app/services/flow/integrations/`, `app/services/flow/validation/` — some may have legitimate imports from production code.

**Why it happens:** It's tempting to delete the entire `app/services/flow/` tree, but significant shared files live there: `types.py`, `flags.py`, `event_broadcaster.py`, `template_lookup.py`, `config.py`, `sequential_message_handler.py`, `sequential_response_gate.py`, `templates/`, `analytics/`, `monitoring/`.

**How to avoid:** Before deleting any file, run `grep -rn "from app.services.flow.X import"` for the specific subpath. Only delete `core/`, `errors/`, `execution/`, `integrations/`, `validation/` after verifying zero production callers (confirmed: these have no production imports).

**Warning signs:** Import errors for `flags.py`, `types.py`, `event_broadcaster.py` which are used by 10+ production files.

### Pitfall 4: Test Isolation — Real DB Tests Polluting State

**What goes wrong:** Integration tests that create patients/flows without cleanup leave orphaned rows that cause subsequent test runs to fail (e.g., "Patient already has active flow" on duplicate phone).

**Why it happens:** Real PostgreSQL tests commit data permanently (no transaction rollback). The existing `conftest.py` uses track+delete pattern, but if a test crashes before registering IDs for cleanup, rows remain.

**How to avoid:** Use unique phone numbers (timestamp-based, already in `conftest.py`), always register IDs immediately after creation (not after assertions), and add `@pytest.mark.integration` + ensure `CONFIRM_REAL_DB=1` is required.

**Warning signs:** `UniqueConstraint` failures on `phone_hash` for seemingly new patients.

### Pitfall 5: FlowDispatcher Adding Unnecessary Abstraction

**What goes wrong:** Building FlowDispatcher as a heavyweight class that reimplements enrollment, advancement, and alert logic, creating a third system.

**Why it happens:** The facade pattern can grow scope creep. The dispatcher should only handle routing, not flow logic.

**How to avoid:** FlowDispatcher wraps `PatientFlowService.initialize_default_flow()` for enrollment. It does NOT replicate `advance_flow`, `pause_patient`, etc. All other operations go directly to production services. The dispatcher is strictly for the enrollment entry point where routing happens.

---

## Deletion Scope — QW-021 Package

Files to `git rm` (confirmed zero production callers outside the QW-021 package itself):

```
app/services/flow/core/__init__.py
app/services/flow/core/context.py
app/services/flow/core/engine.py
app/services/flow/core/lifecycle.py
app/services/flow/core/manager.py
app/services/flow/core/state_machine.py
app/services/flow/errors/__init__.py
app/services/flow/errors/handler.py
app/services/flow/errors/recovery.py
app/services/flow/errors/retry.py
app/services/flow/execution/__init__.py
app/services/flow/execution/conditions.py
app/services/flow/execution/executor.py
app/services/flow/execution/scheduler.py
app/services/flow/execution/transitions.py
app/services/flow/integrations/__init__.py
app/services/flow/integrations/ai_integration.py
app/services/flow/integrations/base.py
app/services/flow/integrations/manager.py
app/services/flow/integrations/plugins.py
app/services/flow/integrations/quiz_integration.py
app/services/flow/validation/__init__.py
app/services/flow/validation/constraints.py
app/services/flow/validation/integrity.py
app/services/flow/validation/rules.py
app/services/flow/validation/validator.py
app/services/flow/manager.py  (compatibility wrapper for deleted FlowManager)
```

Files to **keep** from `app/services/flow/`:
- `__init__.py` (update to remove FlowManager export)
- `config.py` (adapt `FlowFeatureFlags`)
- `types.py` (canonical FlowType enum)
- `flags.py` (is_awaiting_response, message_expects_response)
- `event_broadcaster.py`
- `context_parsing.py`
- `constants.py`
- `template_lookup.py`
- `sequential_message_handler.py`
- `sequential_response_gate.py`
- `analytics/` (entire subdirectory)
- `templates/` (entire subdirectory)
- `monitoring/` (entire subdirectory)

Files to update after deletion:
- `app/service_provider.py` — `flow_service` property (lines 293-296)
- `app/services/flow/__init__.py` — remove `FlowManager` and `get_flow_manager` exports
- `app/services/flow/config.py` — update `FlowFeatureFlags` env vars for Phase 5

---

## Code Examples

### FlowDispatcher — Minimal Implementation

```python
# app/services/dispatcher.py
# Source: analysis of PatientFlowService and production call sites (2026-02-22)

import logging
from typing import Optional
from uuid import UUID

from app.models.flow import PatientFlowState
from app.models.patient import Patient

logger = logging.getLogger(__name__)


class FlowDispatcher:
    """
    Routing facade for flow initialization.
    Routes all enrollments to the canonical production flow system.

    Feature flag: FLOW_CANONICAL_SYSTEM env var (default: 'production').
    After Phase 5 completes and all patients are on production system,
    this class becomes a stable thin pass-through with no routing logic.
    """

    def __init__(self, db):
        self.db = db

    async def initialize_flow(
        self,
        patient: Patient,
        current_user_id: Optional[UUID] = None,
        auto_commit: bool = True,
    ) -> Optional[PatientFlowState]:
        """Enroll patient in canonical flow system."""
        from app.services.patient.flow_service import PatientFlowService

        logger.info(
            "FlowDispatcher: routing patient=%s to production system",
            patient.id,
        )
        service = PatientFlowService(self.db)
        return await service.initialize_default_flow(
            patient=patient,
            current_user_id=current_user_id,
            auto_commit=auto_commit,
        )

    def is_new_patient(self, patient_id: UUID) -> bool:
        """Return True if patient has no active flow state (routing check)."""
        from app.repositories.flow import FlowStateRepository
        repo = FlowStateRepository(self.db)
        return repo.get_active_flow(patient_id) is None
```

### Integration Test — Flow End-to-End

```python
# tests/integration/test_flow_consolidation.py
# Source: analysis of existing integration/conftest.py patterns (2026-02-22)

import pytest
from uuid import UUID
from app.services.dispatcher import FlowDispatcher
from app.models.flow import PatientFlowState
from app.services.flow_alerts import FlowAlertsService


@pytest.mark.integration
@pytest.mark.asyncio
class TestFlowConsolidation:
    """Integration tests for unified flow system (FLOW-03)."""

    async def test_new_patient_onboarding_via_dispatcher(
        self,
        real_db_session,
        sample_patient_data,
        cleanup_patients,
        cleanup_flows,
    ):
        """
        FLOW-01/FLOW-02: New patient routes through FlowDispatcher to production system.
        Asserts: PatientFlowState created, step_data populated, flow_metadata not QW-021 format.
        """
        from app.models.patient import Patient
        # ... create patient, call dispatcher.initialize_flow()
        # ... assert flow_state.step_data is not None
        # ... assert "flow_instance_id" not in (flow_state.flow_metadata or {})  # not QW-021 format

    async def test_alert_pipeline_runs_after_flow_created(
        self,
        real_db_session,
        cleanup_patients,
        cleanup_flows,
    ):
        """
        FLOW-03: Alert pipeline evaluates flow metrics end-to-end.
        """
        # Create a patient flow in a state that triggers completion rate alert
        service = FlowAlertsService(real_db_session)
        alerts = await service.evaluate_alerts()
        # Assert evaluate_alerts() returns without error (smoke test)
        assert isinstance(alerts, list)
```

### Feature Flag Configuration Update

```python
# Adapted FlowFeatureFlags for Phase 5 (patient-type routing)
# Source: existing app/services/flow/config.py (2026-02-22)

class FlowFeatureFlags(BaseSettings):
    # Phase 5: which system is canonical
    canonical_system: str = Field(
        default="production",
        description="Canonical flow system: 'production' (flat files) or 'qw021' (deprecated)",
    )
    # New-vs-existing patient routing (replaces percentage rollout)
    route_new_patients_to_canonical: bool = Field(
        default=True,
        description="Route new patients to canonical system immediately",
    )
    route_existing_patients_to_canonical: bool = Field(
        default=True,  # True = migration complete, all patients on canonical
        description="Route existing patients to canonical system",
    )
    # Audit logging during transition
    log_dispatcher_routing: bool = Field(
        default=True,
        description="Log routing decisions for audit during migration",
    )

    model_config = {"env_prefix": "FLOW_FEATURE_"}
```

---

## State of the Art

| Old Approach | Current Approach | Impact for Phase 5 |
|--------------|------------------|-------------------|
| Two independent flow systems | One canonical + FlowDispatcher | Dispatcher routes all calls to production system |
| QW-021 FlowContext in flow_metadata | Production step_data only | Clear/ignore flow_metadata for migrated rows |
| Percentage-based rollout flag | New-vs-existing patient routing | Simpler: new patients go to canonical immediately |
| Tombstone pattern for dead code | Full deletion for QW-021 | `git rm` the entire `core/` package |

**Deprecated after Phase 5:**
- `FlowManager` class (QW-021): replaced by `FlowDispatcher` → `PatientFlowService` → `EnhancedFlowEngine`
- `FlowContext` Pydantic model (from `flow/types.py`): step-based context, no production use
- `FlowFeatureFlags.use_consolidated_flows` / `consolidated_flows_rollout_percentage`: replaced by `canonical_system` + patient-type routing
- `service_provider.flow_service` returning FlowManager: update to return dispatcher or remove

---

## Open Questions

1. **`flow_metadata` column data: how many rows have QW-021 format?**
   - What we know: QW-021 FlowManager is only wired via `service_provider.flow_service`, and that property is consumed only via `service_dependencies.py` which injects it via FastAPI DI. Whether any actual patient flows were started via this path in production is unknown.
   - What's unclear: Has `service_provider.flow_service` ever been called in production with a real patient? If no, there are zero QW-021-format rows to migrate.
   - Recommendation: Run a migration check query: `SELECT COUNT(*) FROM patient_flow_states WHERE flow_metadata ? 'flow_instance_id'` — this key is unique to QW-021 FlowContext. If count = 0, skip DB migration step.

2. **`app/services/flow/__init__.py` exports after deletion**
   - What we know: `__init__.py` exports `FlowManager`, `get_flow_manager`, `FlowFeatureFlags`, `FlowType`, and various other symbols. Some callers import `from app.services.flow import FlowType` which must continue working.
   - What's unclear: Exactly which exports from the `flow/__init__.py` are in active production use vs only used within the QW-021 package.
   - Recommendation: During planning, grep `from app.services.flow import` to enumerate all external callers before modifying `__init__.py`.

3. **Alert pipeline test scope: mock Gemini or not?**
   - What we know: `FlowAlertsService.evaluate_alerts()` calls SQL queries + `AlertManager.process_alert()`. No Gemini calls. Safe to run against real PostgreSQL without mocking AI.
   - What's unclear: Whether the test database has enough `patient_flow_states` data for completion-rate alert thresholds to trigger.
   - Recommendation: Create minimum test data in the test (e.g., 2 flows in `completed` status, 3 in `active`) to guarantee alert evaluation has data to work with.

---

## Sources

### Primary (HIGH confidence)
- Direct code analysis: `app/services/flow_core.py`, `app/services/enhanced_flow_engine.py`, `app/services/flow_management.py` — production system architecture confirmed
- Direct code analysis: `app/services/flow/core/manager.py`, `context.py` — QW-021 architecture confirmed
- Direct code analysis: `app/services/flow/config.py` — `FlowFeatureFlags` confirmed with existing env-var infrastructure
- Direct code analysis: `app/services/patient/flow_service.py` — `PatientFlowService` confirmed as enrollment entry point used by saga
- Direct code analysis: `app/services/flow_alerts.py` + `app/tasks/flows/monitoring.py` — alert pipeline confirmed
- Direct code analysis: `tests/integration/conftest.py` — real PostgreSQL test infrastructure confirmed
- Direct code analysis: `app/models/flow.py` — shared `patient_flow_states` table confirmed

### Secondary (MEDIUM confidence)
- Call site grep analysis: 59 production imports of `EnhancedFlowEngine`, 7 of `FlowManager` (all in `service_provider.py`) — supports canonical system choice
- `app/service_provider.py` — `flow_service` property returns `FlowManager`, `flow_engine` property returns `EnhancedFlowEngine` — routing gap confirmed

---

## Metadata

**Confidence breakdown:**
- Canonical system choice: HIGH — call site analysis is definitive (59 vs 7 external references)
- Architecture patterns: HIGH — based on direct code analysis
- Deletion scope: HIGH — verified zero production callers for `core/`, `errors/`, `execution/`, `integrations/`, `validation/`
- Pitfalls: HIGH — identified from actual code (e.g., `service_provider.flow_service` import chain)
- Integration test approach: HIGH — existing conftest.py infrastructure reused

**Research date:** 2026-02-22
**Valid until:** 2026-03-22 (30 days — codebase is stable, no fast-moving dependencies)
