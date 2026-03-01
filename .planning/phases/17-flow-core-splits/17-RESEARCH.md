# Phase 17: Flow Core Splits - Research

**Researched:** 2026-02-25
**Domain:** Python module splitting, SQLAlchemy async/sync bridging, FastAPI dependency overrides, saga orchestrator payload validation
**Confidence:** HIGH

## Summary

Phase 17 has been executing for 9 plans. The structural work — splitting `_flow_functions.py`, `flow_core.py`, and `flow_management.py` into focused sub-modules under 500 lines each — is completely done and verified (12/13 truths pass). Shims are in place, split-contract tests pass (9 tests, all green), and all module line counts are confirmed under the 500-line ceiling.

The only remaining blocker is a single test-level failure: `tests/api/test_patients_endpoints.py::TestPatientCRUDEndpoints::test_create_patient_success` returns `422 != 201`. The root cause, now fully diagnosed after 17-09, is that the onboarding saga step (`saga_orchestrator/steps.py`) calls `Patient(**patient_dict)` with an unfiltered payload dict from `PatientCreate.dict(exclude_unset=True)`, which includes clinical-only schema fields (`allergies`, `current_medications`, `comorbidities`, `blood_type`, `emergency_contact_name`, `emergency_contact_phone`) that have no column or property setter on the `Patient` SQLAlchemy model. SQLAlchemy's declarative constructor raises `TypeError: 'allergies' is an invalid keyword argument for Patient`, which propagates as a saga step failure and the endpoint returns 422.

Plan 17-10 (already created) addresses this exact blocker by adding a `_PATIENT_MODEL_FIELDS` frozenset filter in `steps.py` to route clinical extras into `patient_data` JSONB metadata before constructing the `Patient` object. No other known blockers remain after this fix is applied, though the deferred-items log documents that the suite historically surfaces new first failures sequentially — each one resolved independently over plans 17-06 through 17-09.

**Primary recommendation:** Execute plan 17-10 as written. The saga step payload filter is a targeted, single-file change to `app/orchestration/saga_orchestrator/steps.py` that does not touch any production model, schema, or endpoint code.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SPLIT-05 | `_flow_functions.py` (887 LOC) split into message flow + response flow + orchestration utils | SATISFIED in 17-01/17-04/17-05/17-06. Split modules: `_flow_message_flow.py` (364), `_flow_response_flow.py` (242), `_flow_orchestration_utils.py` (325). Shim at original path. 3/3 split-contract tests pass. |
| SPLIT-06 | `flow_core.py` (882 LOC) split into base operations + phase transitions + template binding | SATISFIED in 17-02/17-04/17-05/17-06. Split modules: `core/operations.py` (339), `core/transitions.py` (261), `core/template_binding.py` (75), `core/service.py` (28). Shim at original path. Contract tests pass. |
| SPLIT-07 | `flow_management.py` (694 LOC) split into state management + advancement + pause/resume | SATISFIED in 17-03/17-04/17-05/17-06. Split modules: `management/state_management.py` (297), `management/advancement.py` (196), `management/pause_resume.py` (289), `management/service.py` (48). Shim at original path. Contract tests pass. |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python/SQLAlchemy | 2.x (in use) | ORM and model constructor | Project standard; declarative `__init__` rejects unknown kwargs |
| pytest / pytest-asyncio | In use | Test runner + async test support | Project standard |
| FastAPI | In use | Dependency injection via `Depends()` | Project standard; `dependency_overrides` is the canonical test override mechanism |
| Pydantic v2 | In use | Schema serialization via `.dict(exclude_unset=True)` | Schema layer produces the over-wide dict that triggers the blocker |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `frozenset` (stdlib) | Any | Immutable allowlist of valid model fields | Module-level constant for filter logic in saga steps |
| `sqlalchemy.ext.asyncio.AsyncSession` | 2.x | Async DB access in endpoints | Overridden in tests with `SyncToAsyncSessionAdapter` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `_PATIENT_MODEL_FIELDS` frozenset filter | Modify `Patient.__init__` to accept `**kwargs` and silently drop extras | Worse: would hide model contract violations in production, not just tests |
| Route clinical fields at endpoint layer (already done for HTTP path) | Route at saga step layer (the fix in 17-10) | Saga path must independently protect itself since it bypasses endpoint input processing |

## Architecture Patterns

### Recommended Project Structure (Already in Place)

```
app/services/flow/
├── _flow_functions.py          # Backward-compat shim (35 LOC)
├── _flow_message_flow.py       # Message flow context + dispatch (364 LOC)
├── _flow_response_flow.py      # Response flow context + continuation (242 LOC)
├── _flow_orchestration_utils.py # Shared state/thread/send-mode helpers (325 LOC)
├── core/
│   ├── service.py              # Composed FlowCore (28 LOC)
│   ├── operations.py           # FlowCoreOperationsMixin (339 LOC)
│   ├── transitions.py          # FlowCoreTransitionsMixin (261 LOC)
│   └── template_binding.py     # FlowCoreTemplateBindingMixin (75 LOC)
└── management/
    ├── service.py              # Composed FlowManagementService (48 LOC)
    ├── state_management.py     # FlowManagementStateMixin (297 LOC)
    ├── advancement.py          # FlowManagementAdvancementMixin (196 LOC)
    └── pause_resume.py         # FlowManagementPauseResumeMixin (289 LOC)

app/services/
├── flow_core.py                # Shim: re-exports from flow/core/service.py
└── flow_management.py          # Shim: re-exports from flow/management/service.py

app/orchestration/saga_orchestrator/
└── steps.py                    # Needs _PATIENT_MODEL_FIELDS filter (459 LOC)
```

### Pattern 1: Shim Re-export Pattern (In Place)

**What:** Original module kept as a thin `from canonical import X; __all__ = [...]` file.
**When to use:** Any file split that has existing callers that cannot be migrated in-scope.
**Example (flow_core.py shim):**
```python
"""Compatibility shim for FlowCore split modules."""

from app.services.flow.core.service import (
    FLOW_ADVANCE_BLOCKED_CODE,
    FLOW_ADVANCE_BLOCKED_MESSAGE,
    FLOW_ADVANCE_BLOCKED_REASON,
    FlowCore,
    NotFoundError,
    ValidationError,
)

__all__ = [
    "FLOW_ADVANCE_BLOCKED_CODE",
    "FLOW_ADVANCE_BLOCKED_MESSAGE",
    "FLOW_ADVANCE_BLOCKED_REASON",
    "FlowCore",
    "NotFoundError",
    "ValidationError",
]
```

### Pattern 2: Mixin Composition (In Place)

**What:** Large service class broken into responsibility mixins, composed by a thin service class.
**When to use:** Service has 3+ distinct concerns; methods per concern are self-contained.
**Example (FlowCore):**
```python
class FlowCore(
    FlowCoreTransitionsMixin,
    FlowCoreTemplateBindingMixin,
    FlowCoreOperationsMixin,
):
    """Composed flow core service preserving legacy contract."""
```

### Pattern 3: Payload Allowlist Filter (Needed for 17-10)

**What:** Before constructing a SQLAlchemy model instance from a Pydantic dict, filter keys through a frozenset of valid model fields.
**When to use:** Schema has more fields than the model (clinical extras, metadata-routed fields, computed properties not accepted by `__init__`).
**Example (what 17-10 will add to steps.py):**
```python
# Module-level frozenset — valid Patient(**kwargs) keys
_PATIENT_MODEL_FIELDS = frozenset({
    # Columns
    "doctor_id", "name", "birth_date", "treatment_type",
    "treatment_start_date", "flow_state", "current_day",
    "cpf_encrypted", "cpf_hash", "email_encrypted", "email_hash",
    "phone_encrypted", "phone_hash", "diagnosis", "treatment_phase",
    "doctor_notes", "patient_data", "idempotency_key",
    "deleted_at", "messaging_stopped_at",
    # Property setters (accepted via __init__ -> setattr)
    "cpf", "email", "phone", "timezone", "doctor_name", "enrollment_date",
})

# Inside step_create_patient:
patient_dict = patient_data.dict(exclude_unset=True)
metadata = patient_dict.pop("metadata", {})

clinical_extras = {}
filtered_dict = {}
for key, value in patient_dict.items():
    if key in _PATIENT_MODEL_FIELDS:
        filtered_dict[key] = value
    else:
        clinical_extras[key] = value

if clinical_extras:
    metadata = metadata or {}
    metadata["clinical_info"] = clinical_extras

if doctor_id:
    filtered_dict["doctor_id"] = doctor_id
if metadata:
    filtered_dict["patient_data"] = metadata
if idempotency_key:
    filtered_dict["idempotency_key"] = idempotency_key

patient = Patient(**filtered_dict)
```

### Pattern 4: SyncToAsyncSessionAdapter (Already in Place in conftest.py)

**What:** Test fixture adapter that wraps a sync SQLAlchemy `Session` with async method signatures so FastAPI endpoints using `AsyncSession = Depends(get_async_db)` receive a session that delegates to the transactional sync session.
**Key detail:** The `execute()` method returns an `_AwaitableResultProxy` that forwards `.scalars()` synchronously AND supports `await` (for endpoints that `await db.execute()`). This was an auto-fix applied in 17-09 to handle both sync and async call sites.
**Location:** `backend-hormonia/tests/conftest.py` — `SyncToAsyncSessionAdapter` class at line 759, overridden at line 818.

### Anti-Patterns to Avoid

- **Modifying Patient model to accept `**kwargs`:** Hides validation errors in production.
- **Modifying PatientCreate schema to exclude clinical fields:** Breaks the HTTP endpoint that successfully routes clinical fields into metadata.
- **Global `dependency_overrides.clear()` in wrong place:** The `finally` block in the `client` fixture already handles cleanup; the override must be set inside the fixture, not globally.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Finding valid Patient model columns | Introspect `Patient.__table__.columns` at runtime | Static `frozenset` constant | Static set is faster, explicit, and testable; runtime introspection adds complexity and can fail at import time |
| Async session bridging in tests | Custom async-compatible session factory | `SyncToAsyncSessionAdapter` already present in `tests/conftest.py` | Pattern already established in 17-09; critical conftest has the same pattern |

**Key insight:** The saga step filter problem is simpler than it looks. No migration, no schema change, no model change — just a keyword filter before `Patient(**filtered_dict)`.

## Common Pitfalls

### Pitfall 1: `Patient(**patient_dict)` with Pydantic-serialized extras

**What goes wrong:** `patient_data.dict(exclude_unset=True)` includes all set Pydantic schema fields. `PatientBase` defines `allergies`, `current_medications`, `comorbidities`, `blood_type`, `emergency_contact_name`, `emergency_contact_phone` as optional fields. When any of these are provided in the request body, they appear in the dict. SQLAlchemy declarative `__init__` calls `super().__init__(**kwargs)`, which rejects unknown keys with `TypeError`.
**Why it happens:** The endpoint's own handler routes clinical fields into metadata explicitly before any model construction. The saga step inlines the same construction but lacks the filter.
**How to avoid:** Always filter Pydantic dicts through a model allowlist before calling `Model(**dict)`.
**Warning signs:** `TypeError: 'X' is an invalid keyword argument for Y` in saga step logs; HTTP 422 response from an endpoint that should return 201.

### Pitfall 2: Coroutine not awaited in SyncToAsyncSessionAdapter

**What goes wrong:** If `execute()` returns a plain coroutine, endpoints that chain `.scalars()` synchronously on the return value get `'coroutine' object has no attribute 'scalars'`.
**Why it happens:** Some call sites call `result = await db.execute(stmt)` then `result.scalars()`, while others (sync-migrated code) call `result = self.db.execute(stmt)` then `result.scalars()`. A simple `async def execute()` returning a coroutine breaks the latter.
**How to avoid:** Use the `_AwaitableResultProxy` pattern already in place: the proxy forwards all attribute access to the sync `Result` synchronously AND implements `__await__` so it can be used with `await`. This was implemented in 17-09 as an auto-fix.
**Warning signs:** `RuntimeWarning: coroutine was never awaited` in test output; AttributeError on `.scalars()`.

### Pitfall 3: Sequential blocker discovery

**What goes wrong:** Fixing one test failure reveals a different first failure in the fail-fast gate, creating the appearance that the fix made things worse.
**Why it happens:** The suite runs sequentially under `-x`; pre-existing failures hidden behind earlier blockers surface only once the earlier blocker is resolved.
**How to avoid:** Trust deferred-items log. Each blocker documented in 17-06 through 17-09 was pre-existing and unrelated to Phase 17 split work. The split contract tests (9 tests) pass independently.
**Warning signs:** Each `python3 -m pytest -x` run reveals a new unrelated first failure in a different test file.

### Pitfall 4: Modifying split modules that already pass line-count contract tests

**What goes wrong:** Adding filtering logic to split modules could push them over 500 lines.
**Why it does not apply here:** The fix goes into `app/orchestration/saga_orchestrator/steps.py` (459 LOC currently), not into any of the flow split modules. Adding ~25 lines brings it to ~484 LOC — still under 500.
**Warning signs:** Would trigger `test_split_modules_stay_under_500_lines` or equivalent contract test failures.

## Code Examples

### Current `step_create_patient` Code with Blocker (steps.py:87-100)

```python
# CURRENT (broken for clinical-field payloads):
patient_dict = patient_data.dict(exclude_unset=True)
metadata = patient_dict.pop("metadata", {})

if doctor_id:
    patient_dict["doctor_id"] = doctor_id
if metadata:
    patient_dict["patient_data"] = metadata
if idempotency_key:
    patient_dict["idempotency_key"] = idempotency_key

patient = Patient(**patient_dict)  # FAILS if patient_dict has 'allergies', etc.
```

### Fixed `step_create_patient` Code (Plan 17-10 change)

```python
# _PATIENT_MODEL_FIELDS frozenset at module level (defined before SagaStepExecutor class)
_PATIENT_MODEL_FIELDS = frozenset({
    "doctor_id", "name", "birth_date", "treatment_type",
    "treatment_start_date", "flow_state", "current_day",
    "cpf_encrypted", "cpf_hash", "email_encrypted", "email_hash",
    "phone_encrypted", "phone_hash", "diagnosis", "treatment_phase",
    "doctor_notes", "patient_data", "idempotency_key",
    "deleted_at", "messaging_stopped_at",
    "cpf", "email", "phone", "timezone", "doctor_name", "enrollment_date",
})

# Inside step_create_patient (FIXED):
patient_dict = patient_data.dict(exclude_unset=True)
metadata = patient_dict.pop("metadata", {})

clinical_extras = {}
filtered_dict = {}
for key, value in patient_dict.items():
    if key in _PATIENT_MODEL_FIELDS:
        filtered_dict[key] = value
    else:
        clinical_extras[key] = value

if clinical_extras:
    metadata = metadata or {}
    metadata["clinical_info"] = clinical_extras

if doctor_id:
    filtered_dict["doctor_id"] = doctor_id
if metadata:
    filtered_dict["patient_data"] = metadata
if idempotency_key:
    filtered_dict["idempotency_key"] = idempotency_key

patient = Patient(**filtered_dict)  # Only valid kwargs; clinical extras in metadata
```

### Verification Command (Targeted)

```bash
cd backend-hormonia && python3 -m pytest tests/api/test_patients_endpoints.py::TestPatientCRUDEndpoints::test_create_patient_success -x --tb=short
```

### Full Fail-Fast Gate (After Fix)

```bash
cd backend-hormonia && python3 -m pytest -x --tb=short
```

### Split Contract Tests (9 tests, independent of fix)

```bash
cd backend-hormonia && python3 -m pytest \
  tests/unit/services/flow/test_flow_functions_split_contract.py \
  tests/unit/services/test_flow_core_split_contract.py \
  tests/unit/services/test_flow_management_split_contract.py \
  -x --tb=short
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `_flow_functions.py` (887 LOC monolith) | Shim + 3 split modules under 500 LOC each | Phase 17 plans 17-01/17-04 | SPLIT-05 satisfied |
| `flow_core.py` (882 LOC monolith) | Shim + 4 mixin modules under 500 LOC | Phase 17 plans 17-02/17-04 | SPLIT-06 satisfied |
| `flow_management.py` (694 LOC monolith) | Shim + 4 mixin modules under 500 LOC | Phase 17 plans 17-03/17-04 | SPLIT-07 satisfied |
| `get_async_db` not overridden in root test suite | `SyncToAsyncSessionAdapter` bridge + dependency override | Plan 17-09 | Unblocked patient create validation path |
| `Patient(**patient_dict)` with unfiltered Pydantic dict | `_PATIENT_MODEL_FIELDS` filter routes clinical extras to metadata | Plan 17-10 (pending) | Will unblock `test_create_patient_success` (422 → 201) |
| `UndefinedColumn` on `messaging_stopped_at` | Non-destructive fixture schema guard (`ALTER TABLE IF NOT EXISTS`) | Plan 17-04 | Unblocked critical test suite bootstrap |
| `notifications.notification_type` missing | Fixture schema guard additive column patch | Plan 17-07 | Unblocked notifications contract test |
| `audit_logs.valid_event_category` constraint mismatch | Fixture-time constraint rewrite (DROP + broadened re-create) | Plan 17-08 | Unblocked user activity API contract test |

**Deprecated/outdated:**
- `flow_core.py` as a monolith: now a compatibility shim, canonical code in `flow/core/`
- `flow_management.py` as a monolith: now a compatibility shim, canonical code in `flow/management/`
- `_flow_functions.py` as a monolith: now a compatibility shim, canonical code in `_flow_message_flow.py`, `_flow_response_flow.py`, `_flow_orchestration_utils.py`

## Open Questions

1. **Will any new first failure emerge after 17-10's fix?**
   - What we know: Plans 17-06 through 17-09 each closed one blocker and surfaced a new first failure. The deferred-items log documents the progression: `UndefinedColumn` → `422 vs 403` → `500 ResponseValidationError` → `UndefinedColumn notifications` → `audit_logs CheckViolation` → `422 vs 201 (async session)` → `422 vs 201 (saga payload)`.
   - What's unclear: Whether the saga payload fix is the last blocker or whether another pre-existing failure is hidden behind it.
   - Recommendation: Execute 17-10 Task 2 (full fail-fast rerun) and capture evidence. If a new blocker appears, log it in deferred-items as a distinct concern. SPLIT-05/06/07 structural requirements are already satisfied; any remaining test failures are pre-existing issues in other subsystems, not regressions from Phase 17 split work.

2. **Are any split module files approaching the 500-line ceiling?**
   - What we know: Current line counts from `wc -l`: `_flow_message_flow.py` 364, `_flow_response_flow.py` 242, `_flow_orchestration_utils.py` 325, `core/operations.py` 339, `core/transitions.py` 261, `core/template_binding.py` 75, `core/service.py` 28, `management/state_management.py` 297, `management/advancement.py` 196, `management/pause_resume.py` 289, `management/service.py` 48.
   - What's unclear: Whether Phase 17 fix work (17-10 changes only `steps.py`) could push any split module over 500 lines.
   - Recommendation: Not a concern — 17-10 touches only `steps.py` (459 LOC currently; ~484 after fix), which is not a split module and has no line-count constraint.

3. **Are the `TODO(async-migration)` markers in validation_service.py and sync_service.py a risk?**
   - What we know: Both files have `TODO(async-migration)` markers; the `SyncToAsyncSessionAdapter` in 17-09 bridges these sync `.execute()` calls so they work inside the test transaction.
   - What's unclear: Whether the adapter bridge is sufficient for all code paths exercised by `test_create_patient_success`.
   - Recommendation: The 17-09 deferred-items evidence shows the adapter now gets the patient-create execution into the saga step (past the validation), proving the adapter bridge works for those paths. The remaining 422 is from the saga step's unfiltered dict, not from the adapter.

## Sources

### Primary (HIGH confidence)

- Direct codebase inspection: `backend-hormonia/app/orchestration/saga_orchestrator/steps.py` lines 87-100 — exact failing code
- Direct codebase inspection: `backend-hormonia/app/models/patient.py` — Patient model columns and property setters
- Direct codebase inspection: `backend-hormonia/app/schemas/patient.py` — PatientBase clinical fields that cause blocker
- Direct codebase inspection: `backend-hormonia/tests/conftest.py` lines 759-818 — SyncToAsyncSessionAdapter and get_async_db override (already applied in 17-09)
- Direct codebase inspection: `backend-hormonia/app/services/flow/` split modules — all verified under 500 lines
- `.planning/phases/17-flow-core-splits/17-VERIFICATION.md` — authoritative 12/13 verification status
- `.planning/phases/17-flow-core-splits/deferred-items.md` — timestamped blocker progression evidence
- `.planning/phases/17-flow-core-splits/17-10-PLAN.md` — already-drafted fix plan for the saga payload blocker
- `.planning/phases/17-flow-core-splits/17-09-SUMMARY.md` — confirms 17-09 execution, adapter auto-fix, and blocker transition

### Secondary (MEDIUM confidence)

- SQLAlchemy declarative constructor behavior: confirmed by `TypeError` in test output ("invalid keyword argument for Patient") which is the standard SQLAlchemy error for unknown `__init__` kwargs.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified from actual codebase files
- Architecture: HIGH — verified from actual module line counts and import chains
- Pitfalls: HIGH — each pitfall was directly encountered and documented in deferred-items log during phase execution
- Fix prescription: HIGH — Plan 17-10 is already written with exact code to add

**Research date:** 2026-02-25
**Valid until:** This phase is nearly complete; research is valid for the duration of 17-10 execution only.
