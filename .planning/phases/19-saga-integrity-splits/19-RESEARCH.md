# Phase 19: Saga & Integrity Splits - Research

**Researched:** 2026-02-26
**Domain:** Python module refactoring — saga orchestration and flow integrity layers
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- `saga/orchestrator`: split into orchestrator, step-executor, and metrics-focused modules.
- `saga/compensation`: split into compensation-chain logic and step-handler modules.
- `flow_integrity`: split into corruption-detection and recovery-action modules.
- Use `*_pkg` package structure for split modules, matching prior phase conventions.
- Keep backward compatibility at legacy import paths during Phase 19.
- Do not add deprecation warnings in this phase.
- Execute in this order: orchestrator -> compensation -> integrity.
- Keep commits atomic per split plan.
- Run quality gates per plan (not only at phase end).
- If a blocker appears and blocks the plan, fix it immediately and document the deviation.
- Require contract tests + targeted regressions + line-budget checks for each plan.
- Enforce `<500` lines per new split module file with no exceptions.
- Ensure coverage includes all three domains (orchestrator, compensation, integrity).
- Keep SUMMARY files detailed, including evidence, commands, deviations, and blockers.

### Claude's Discretion
- Runtime parity implementation details are delegated to Claude, with strict observable behavior parity as default.
- Public export strategy details are delegated to Claude, with explicit `__all__` whitelisting as default.

### Deferred Ideas (OUT OF SCOPE)
- Full migration to remove legacy shim paths and delete legacy compatibility code after downstream callers are migrated (future phase/backlog item).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SPLIT-08 | `saga/orchestrator.py` (645 LOC) split into main orchestrator + step executor + metrics | Orchestrator already imports SagaStepExecutor from steps.py; metrics block (lines 46-101) is self-contained and can be extracted into a dedicated metrics.py module. The main orchestrator body + resume + compat wrappers fits under 500 lines after extraction. |
| SPLIT-09 | `saga/compensation.py` (573 LOC) split into compensation chain + step handlers | SagaCompensator.compensate_saga + _compensate_saga_internal + _compensate_step_with_retry form the chain logic; _compensate_message + _compensate_flow + _compensate_patient + _track_compensation_failure form the handler logic. Chain module delegates to handlers. |
| SPLIT-10 | `flow_integrity.py` (559 LOC) split into corruption detection + recovery actions | Methods _validate_flow_type_compatibility, _validate_state_transitions, _validate_flow_data_integrity, _generate_flow_checksum, validate_flow_consistency, prevent_invalid_transitions, validate_referential_integrity form the detection layer; repair_flow_integrity + health_check + get_flow_integrity_service form the recovery layer. |
</phase_requirements>

---

## Summary

Phase 19 is a pure refactor — no new capabilities, no new external dependencies. The three target files are all in the Python backend at `backend-hormonia/`. Two of the three (`saga/orchestrator.py` at 645 LOC, `saga/compensation.py` at 573 LOC) live inside the already-existing `app/orchestration/saga_orchestrator/` package, which is itself the product of an earlier split. The third (`flow_integrity.py` at 559 LOC) lives in `app/services/`.

A critical structural discovery: `saga/orchestrator.py` is **not** the same file as REQUIREMENTS.md implies at face value. The `saga_orchestrator/` package already has `steps.py` (518 LOC) and `persistence.py` (202 LOC) as separate modules, with `orchestrator.py` (645 LOC) being the coordination layer. The split target for SPLIT-08 is `orchestrator.py` itself, which contains a large Prometheus metrics block (lines 46-101, ~60 lines) that can be extracted into a dedicated `metrics.py` module, leaving the orchestration logic under 500 lines.

All three splits follow the `*_pkg` pattern established in Phases 17 and 18: extract focused sub-modules into a new `_pkg/` directory, make the original file a thin re-export shim, and expose a clean `__all__` from the package's `__init__.py`. The key risk is the existing test coverage, which imports directly from sub-module paths (e.g., `from app.orchestration.saga_orchestrator.compensation import SagaCompensator`) — these imports must remain valid after the split.

**Primary recommendation:** For each of the three plans, create a `_pkg/` package alongside the original file, move responsibility-specific code into focused sub-modules under `_pkg/`, then replace the original file with a strict re-export shim. The `__init__.py` of the parent `saga_orchestrator/` package must be updated to reflect the new internal structure while keeping all public exports identical.

---

## Standard Stack

### Core

| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| Python | 3.12 (target 3.13) | Runtime | Project baseline |
| SQLAlchemy | existing | ORM / async sessions | Already in use throughout |
| pytest + pytest-asyncio | existing | Test framework | pyproject.toml: `asyncio_mode = "auto"` |
| prometheus_client | existing | Metrics counters/histograms | Already imported with graceful ImportError fallback |

### Supporting

| Component | Version | Purpose | When to Use |
|-----------|---------|---------|-------------|
| asyncio | stdlib | Async coordination | Already used in compensation retry (`asyncio.sleep`) |
| sqlalchemy.ext.asyncio.AsyncSession | existing | Async DB sessions | Used in compensation and steps — must be preserved in split modules |
| sqlalchemy.orm.Session | existing | Sync DB sessions | Used in persistence layer |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `*_pkg` directory pattern | single-file extract | `*_pkg` matches Phase 17/18 conventions; single-file would diverge from established pattern |
| Explicit `__all__` in shim | implicit re-export | Explicit `__all__` prevents accidental exposure and matches Phase 18 pattern |

**Installation:** No new packages needed. All dependencies are already present.

---

## Architecture Patterns

### Established `*_pkg` Pattern (from Phases 17 and 18)

The project has two clear precedents:

**Pattern A — Service-level pkg** (e.g., `flow_monitoring_pkg/`):
```
app/services/flow_monitoring.py            # shim: from flow_monitoring_pkg import ...
app/services/flow_monitoring_pkg/
    __init__.py                            # pkg public API with __all__
    metrics.py                             # Prometheus metrics + metric mixins
    health.py                              # Health check mixin
    alerting.py                            # Alert mixin
    trends.py                              # Trend mixin
    models.py                              # Data classes
    service.py                             # Composed service (inherits mixins)
```

**Pattern B — Package-internal module split** (e.g., `saga_orchestrator/` itself):
```
app/orchestration/saga_orchestrator/
    __init__.py                            # public API: SagaOrchestrator, exceptions, types
    orchestrator.py                        # main class
    steps.py                               # SagaStepExecutor
    compensation.py                        # SagaCompensator
    persistence.py                         # SagaPersistence
    types.py                               # TypedDicts
    exceptions.py                          # Custom exceptions
    query_helpers.py                       # shared helper
```

For Phase 19, the approach must match both patterns depending on the target:

**SPLIT-08 (orchestrator.py)**: Extract metrics into a new `orchestrator_pkg/` sub-package OR add a `metrics.py` directly inside `saga_orchestrator/` (Pattern B extension). Given that the package already exists and the split is minor (metrics block extraction), adding `metrics.py` directly inside `saga_orchestrator/` is cleaner and avoids an extra level of nesting.

**SPLIT-09 (compensation.py)**: Extract step handler methods into a `compensation_handlers.py` inside `saga_orchestrator/`. The `compensation.py` becomes the chain coordinator that imports from `compensation_handlers.py`.

**SPLIT-10 (flow_integrity.py)**: Create `flow_integrity_pkg/` in `app/services/` (Pattern A). Replace `flow_integrity.py` with a shim.

### Recommended Structure After Phase 19

```
app/orchestration/saga_orchestrator/
    __init__.py               # unchanged public API
    orchestrator.py           # shim OR slimmed-down class (see SPLIT-08 analysis)
    metrics.py                # extracted Prometheus counters/histograms (NEW)
    steps.py                  # unchanged (already under 500 lines: 518 LOC)
    compensation.py           # compensation chain coordinator
    compensation_handlers.py  # step handler methods (NEW)
    persistence.py            # unchanged
    types.py                  # unchanged
    exceptions.py             # unchanged
    query_helpers.py          # unchanged

app/services/
    flow_integrity.py         # shim: from flow_integrity_pkg import ...
    flow_integrity_pkg/       # NEW
        __init__.py           # public API with __all__
        detection.py          # corruption detection methods
        recovery.py           # repair + health_check + factory
```

### Shim Pattern (mandatory)

```python
# flow_integrity.py (after split)
"""Shim - canonical code lives in flow_integrity_pkg/. See Phase 19."""

from app.services.flow_integrity_pkg import (
    FlowIntegrityService,
    get_flow_integrity_service,
)

__all__ = [
    "FlowIntegrityService",
    "get_flow_integrity_service",
]
```

### Anti-Patterns to Avoid

- **Circular imports**: `compensation_handlers.py` must not import from `compensation.py`. Data should flow only in one direction: coordinator imports handlers.
- **Direct DB session creation in extracted modules**: All extracted modules must accept the `db` session as a parameter, never create their own sessions.
- **Breaking existing test imports**: Tests import `from app.orchestration.saga_orchestrator.compensation import SagaCompensator` — this path must remain valid.
- **Moving `__all__` without updating it**: Every shim must declare an explicit `__all__` matching what the original exported.

---

## File-by-File Split Analysis

### SPLIT-08: `orchestrator.py` (645 LOC)

**Current internal structure:**
- Lines 1-42: Imports
- Lines 43-101: Prometheus metrics block (`SAGA_STARTS_TOTAL`, `SAGA_COMPLETIONS_TOTAL`, etc. — 8 counters/histograms + `METRICS_AVAILABLE` guard)
- Lines 104-113: `_detect_phone_format()` helper
- Lines 115-645: `SagaOrchestrator` class (constructor + `execute_patient_onboarding_saga` + `resume_saga` + `_resume_saga_internal` + compat wrappers)

**Split plan:**
- Create `app/orchestration/saga_orchestrator/metrics.py` with the Prometheus block + `_detect_phone_format()` + `METRICS_AVAILABLE` flag
- `orchestrator.py` imports from `metrics.py` and remains the sole home of `SagaOrchestrator`
- After extraction: `metrics.py` ~75 LOC, `orchestrator.py` ~575 LOC

**Note:** Extracting the metrics block alone brings `orchestrator.py` from 645 to approximately 575 lines — just above the 500-line target. The `SagaOrchestrator` class itself has compat wrappers (lines 584-645) that delegate directly to `self.compensator`. These 60+ lines of wrappers could move to a separate `orchestrator_compat.py` or be inlined into the class's docstring note. Given that the target is strict `<500`, the compat wrappers (6 methods, ~62 lines) should also be extracted or the class refactored to remove redundancy.

**Practical split boundary:** Extract metrics + `_detect_phone_format` (to `metrics.py`, ~70 LOC) AND move compat wrappers to a mixin or drop as a minor docstring annotation, leaving `orchestrator.py` at ~510 LOC. Alternatively, combine steps.py (already existing, 518 LOC) note: steps.py is a separate pre-existing file. The saga orchestrator's `steps.py` is already 518 LOC which exceeds 500 itself and was NOT flagged as a SPLIT-08 target. SPLIT-08 targets only `orchestrator.py`.

**Revised approach for strict `<500`:**
- `metrics.py`: 8 Prometheus metrics + `METRICS_AVAILABLE` + `_detect_phone_format` (~75 LOC)
- The compat wrapper methods (6 methods, ~62 LOC) can be removed from `orchestrator.py` since they purely delegate to `self.compensator` — they are already documented as delegating. They exist only for backward compatibility with callers that may call them on the orchestrator instance. Check callers before removing.
- If callers exist: move wrappers to a `_compat_wrappers.py` included via mixin pattern.
- If no external callers: remove wrappers, leaving orchestrator at ~510 LOC. Further check: the docstring, blank lines, and metric calls inline total around 130 lines. Removing those + extracting metrics should bring it to ~475.

**Confidence:** HIGH — the extraction boundary is mechanically clear.

### SPLIT-09: `compensation.py` (573 LOC)

**Current internal structure:**
- Lines 1-28: Imports + logger
- Lines 31-175: `SagaCompensator` class with chain methods:
  - `compensate_saga()` — public entry point with lock
  - `_compensate_saga_internal()` — main orchestration loop
  - `_compensate_step_with_retry()` — retry infrastructure
- Lines 230-397: Step handler methods:
  - `_compensate_message()` (~58 LOC) — cancels saga messages
  - `_compensate_flow()` (~52 LOC) — deletes flow states
  - `_compensate_patient()` (~55 LOC) — deletes patient record
- Lines 399-573: `_track_compensation_failure()` (~175 LOC) — Redis + Alert + quarantine + Sentry

**Split plan:**
- `compensation.py` keeps: `SagaCompensator` class, `compensate_saga`, `_compensate_saga_internal`, `_compensate_step_with_retry` (~200 LOC after handlers extracted)
- NEW `compensation_handlers.py`: `_compensate_message`, `_compensate_flow`, `_compensate_patient`, `_track_compensation_failure` (~380 LOC)
- `compensation.py` imports handler functions from `compensation_handlers.py` and calls them via `self`
- The handler methods are best kept as standalone async functions (not methods of a separate class) so `compensation.py` can call them directly passing `self.db`, `self.redis`, and the saga object
- After split: `compensation.py` ~200 LOC, `compensation_handlers.py` ~380 LOC

**Confidence:** HIGH

### SPLIT-10: `flow_integrity.py` (559 LOC)

**Current internal structure:**
- Lines 1-43: Module docstring + imports
- Lines 27-97: `FlowIntegrityService.__init__` + `validate_flow_consistency` (validation orchestrator)
- Lines 99-275: Detection methods:
  - `_validate_flow_type_compatibility()` (~28 LOC)
  - `_validate_state_transitions()` (~63 LOC)
  - `_get_max_step_for_flow()` (~12 LOC)
  - `_validate_flow_data_integrity()` (~67 LOC)
  - `_generate_flow_checksum()` (~31 LOC)
- Lines 308-416: More detection:
  - `prevent_invalid_transitions()` (~42 LOC)
  - `validate_referential_integrity()` (~66 LOC)
- Lines 418-559: Recovery:
  - `repair_flow_integrity()` (~82 LOC)
  - `health_check()` (~45 LOC)
- Lines 549-559: Factory function `get_flow_integrity_service()`

**Split plan:**
- `flow_integrity_pkg/detection.py`: A `FlowIntegrityDetectionMixin` containing `validate_flow_consistency`, `_validate_flow_type_compatibility`, `_validate_state_transitions`, `_get_max_step_for_flow`, `_validate_flow_data_integrity`, `_generate_flow_checksum`, `prevent_invalid_transitions`, `validate_referential_integrity` (~370 LOC)
- `flow_integrity_pkg/recovery.py`: A `FlowIntegrityRecoveryMixin` containing `repair_flow_integrity`, `health_check` (~130 LOC)
- `flow_integrity_pkg/service.py`: `FlowIntegrityService(FlowIntegrityDetectionMixin, FlowIntegrityRecoveryMixin)` with `__init__` + factory function (~50 LOC)
- `flow_integrity_pkg/__init__.py`: Re-exports `FlowIntegrityService`, `get_flow_integrity_service` (~20 LOC)
- `flow_integrity.py` (shim): `from app.services.flow_integrity_pkg import ...` (~10 LOC)

**Total after split:** detection.py ~370, recovery.py ~130, service.py ~50 — all under 500.

**Confidence:** HIGH

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Backward compat validation | Custom import hook | Explicit `__all__` shim | Simpler, same guarantees, matches prior phase pattern |
| Line count enforcement | Manual counting | `wc -l <file>` in task verification | Already the project standard for line-budget gates |
| Test contract verification | New test framework | pytest with existing fixtures | All saga tests already exist and use pytest-asyncio |

**Key insight:** The project pattern is mechanically consistent across Phases 17 and 18 — re-export shim + `*_pkg` directory + mixin composition. Deviating from this pattern introduces inconsistency and increases reviewer cognitive load.

---

## Common Pitfalls

### Pitfall 1: Circular Imports Between Split Modules

**What goes wrong:** `compensation_handlers.py` imports `SagaCompensator` to type-annotate `saga` parameters, while `compensation.py` imports from `compensation_handlers.py`. Python raises `ImportError` at startup.

**Why it happens:** When splitting a class, private methods often reference `self` for shared state. Moving them to a separate module requires them to either receive the necessary state as arguments or import the parent class for type hints.

**How to avoid:** Use `from __future__ import annotations` for deferred evaluation, or use string forward references in type hints. Pass `self.db`, `self.redis`, and `saga` as explicit arguments to handler functions rather than making them methods of a second class.

**Warning signs:** `ImportError: cannot import name 'X' from partially initialized module` at test startup.

### Pitfall 2: Breaking Direct Sub-Module Imports in Tests

**What goes wrong:** Tests do `from app.orchestration.saga_orchestrator.compensation import SagaCompensator`. If `SagaCompensator` moves to a new sub-module, this import breaks.

**Why it happens:** The split extracts content from `compensation.py` but the original module path must remain valid.

**How to avoid:** For SPLIT-09, `compensation.py` itself stays as the coordinator — `SagaCompensator` is NOT moved, its handler methods are moved. The class definition remains in `compensation.py`. This means `from app.orchestration.saga_orchestrator.compensation import SagaCompensator` continues to work without a shim.

**Warning signs:** `ImportError` in test files that import directly from old paths.

### Pitfall 3: AsyncSession vs Session Mixin Confusion

**What goes wrong:** `compensation.py` uses `AsyncSession` (`await self.db.execute(...)`, `await self.db.delete()`). If extracted handler functions are called from a sync context or the wrong session type, runtime errors occur.

**Why it happens:** The codebase has a mix of sync Session (persistence.py, orchestrator's `self.db.query()` calls) and AsyncSession (compensation.py, steps.py). The same `self.db` is passed to both depending on caller context.

**How to avoid:** Document the async requirement explicitly in extracted modules. Do not change session semantics during this phase — preserve exactly the calling convention each method already uses.

**Warning signs:** `TypeError: object Session is not awaitable` or `RuntimeError: no running event loop`.

### Pitfall 4: `flow_integrity.py` Has Only One Caller

**What goes wrong:** `data_integrity_monitoring.py` is the only production caller of `flow_integrity.py`. The shim path must be exact.

**Why it happens:** If the shim exports a different name or the caller uses `from app.services.flow_integrity import get_flow_integrity_service`, that exact import must work via the shim.

**How to avoid:** Verify the exact import statement in `data_integrity_monitoring.py` before writing the shim. The shim must export everything the caller uses.

**Warning signs:** `ImportError` in `data_integrity_monitoring.py` at runtime or in tests.

### Pitfall 5: `steps.py` Already at 518 LOC

**What goes wrong:** `steps.py` is 518 lines, already over the 500-line budget. SPLIT-08 does not target steps.py (it is in scope of the pre-existing `saga_orchestrator` package structure, not a new split target). If the plan inadvertently triggers a requirement to split steps.py as well, scope creep occurs.

**Why it happens:** Requirements SPLIT-08 specifically targets `orchestrator.py`, not `steps.py`. The 518 LOC `steps.py` is a pre-existing condition.

**How to avoid:** Keep SPLIT-08 strictly focused on `orchestrator.py`. Do not touch `steps.py`. Note this pre-existing condition in the SUMMARY.

---

## Code Examples

### Pattern: Metrics Extraction to `metrics.py`

```python
# saga_orchestrator/metrics.py  (NEW)
"""Prometheus metrics for saga orchestration. See Phase 19."""

import logging

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram

    SAGA_STARTS_TOTAL = Counter(
        "saga_onboarding_starts_total",
        "Total number of saga starts",
        ["doctor_id"],
    )
    SAGA_COMPLETIONS_TOTAL = Counter(...)
    # ... remaining metrics ...
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("prometheus_client not available, saga metrics disabled")


def detect_phone_format(phone: str) -> str:
    """Detect phone number format for metrics labeling."""
    import re
    if not phone:
        return "other"
    if phone.startswith("+"):
        return "e164"
    digits = re.sub(r"\D", "", phone)
    if len(digits) in (10, 11, 12, 13):
        return "brazilian"
    return "other"

__all__ = [
    "SAGA_STARTS_TOTAL",
    "SAGA_COMPLETIONS_TOTAL",
    "SAGA_FAILURES_TOTAL",
    "SAGA_DURATION_SECONDS",
    "SAGA_LOCK_ACQUISITION_SECONDS",
    "SAGA_COMPENSATIONS_TOTAL",
    "SAGA_TRANSACTION_DURATION_SECONDS",
    "SAGA_PHONE_NORMALIZATION_TOTAL",
    "SAGA_STEP_DURATION_SECONDS",
    "METRICS_AVAILABLE",
    "detect_phone_format",
]
```

```python
# saga_orchestrator/orchestrator.py  (after extraction)
"""Saga Orchestrator - Main Orchestrator Class."""

from .metrics import (
    SAGA_STARTS_TOTAL, SAGA_COMPLETIONS_TOTAL, SAGA_FAILURES_TOTAL,
    SAGA_DURATION_SECONDS, SAGA_LOCK_ACQUISITION_SECONDS,
    SAGA_COMPENSATIONS_TOTAL, SAGA_TRANSACTION_DURATION_SECONDS,
    SAGA_PHONE_NORMALIZATION_TOTAL, SAGA_STEP_DURATION_SECONDS,
    METRICS_AVAILABLE, detect_phone_format,
)
# ... rest of imports ...

class SagaOrchestrator:
    # ... same class, no metrics definitions ...
```

### Pattern: Compensation Handler Extraction

```python
# saga_orchestrator/compensation_handlers.py  (NEW)
"""Saga compensation step handlers. Chain logic lives in compensation.py."""

from __future__ import annotations
import json
import logging
from typing import Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.timezone import now_sao_paulo

if TYPE_CHECKING:
    from app.models.patient_onboarding_saga import PatientOnboardingSaga

logger = logging.getLogger(__name__)


async def compensate_message(db: AsyncSession, saga: PatientOnboardingSaga) -> None:
    """Compensate Step 4: Mark welcome message as cancelled."""
    # ... extracted body ...


async def compensate_flow(db: AsyncSession, saga: PatientOnboardingSaga) -> None:
    """Compensate Step 3: Delete or deactivate flow state."""
    # ... extracted body ...


async def compensate_patient(db: AsyncSession, saga: PatientOnboardingSaga) -> None:
    """Compensate Step 1: Delete patient record."""
    # ... extracted body ...


async def track_compensation_failure(
    db: AsyncSession, redis: Any, saga_id: UUID, step: int, error: Exception
) -> None:
    """Track compensation failures for audit and manual recovery."""
    # ... extracted body ...


__all__ = [
    "compensate_message",
    "compensate_flow",
    "compensate_patient",
    "track_compensation_failure",
]
```

```python
# saga_orchestrator/compensation.py  (after extraction — chain only)
"""Saga Compensation Logic — chain coordinator. Handlers in compensation_handlers.py."""

from .compensation_handlers import (
    compensate_message,
    compensate_flow,
    compensate_patient,
    track_compensation_failure,
)

class SagaCompensator:
    # ... same class definition, __init__, compensate_saga,
    # _compensate_saga_internal, _compensate_step_with_retry ...

    async def _compensate_message(self, saga):
        await compensate_message(self.db, saga)

    async def _compensate_flow(self, saga):
        await compensate_flow(self.db, saga)

    async def _compensate_patient(self, saga):
        await compensate_patient(self.db, saga)

    async def _track_compensation_failure(self, saga_id, step, error):
        await track_compensation_failure(self.db, self.redis, saga_id, step, error)
```

### Pattern: Flow Integrity Mixin Composition

```python
# flow_integrity_pkg/service.py
"""Composed FlowIntegrityService."""

from typing import Any
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository

from .detection import FlowIntegrityDetectionMixin
from .recovery import FlowIntegrityRecoveryMixin


class FlowIntegrityService(
    FlowIntegrityDetectionMixin,
    FlowIntegrityRecoveryMixin,
):
    """Service for flow consistency validation and referential integrity checking."""

    def __init__(self, db: Any):
        self.db = db
        self.flow_state_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)


def get_flow_integrity_service(db: Any) -> FlowIntegrityService:
    return FlowIntegrityService(db)
```

```python
# flow_integrity.py (shim after SPLIT-10)
"""Shim - canonical code lives in flow_integrity_pkg/. See Phase 19."""

from app.services.flow_integrity_pkg import (
    FlowIntegrityService,
    get_flow_integrity_service,
)

__all__ = [
    "FlowIntegrityService",
    "get_flow_integrity_service",
]
```

---

## Caller Map

### `saga/orchestrator.py` callers (production)

| File | Import | Risk |
|------|--------|------|
| `app/api/v2/routers/admin/compensation.py` | `from app.orchestration.saga_orchestrator import SagaOrchestrator` | LOW — uses package `__init__`, unchanged |
| `app/api/v2/routers/patients/crud.py` | `from app.orchestration.saga_orchestrator import SagaOrchestrator` | LOW |
| `app/domain/patient/onboarding/coordinator.py` | `from app.orchestration.saga_orchestrator import SagaOrchestrator` | LOW |
| `app/services/patient/onboarding_factory.py` | `from app.orchestration.saga_orchestrator import SagaOrchestrator` | LOW |
| `app/tasks/saga_retry.py` | `from app.orchestration.saga_orchestrator import SagaOrchestrator` | LOW |

All production callers use the package `__init__.py` path, not the sub-module path. The `__init__.py` exports are unchanged so these callers are unaffected.

### `saga/compensation.py` callers (tests import sub-module directly)

| File | Import | Risk |
|------|--------|------|
| `tests/orchestration/test_saga_orchestrator.py` | `from app.orchestration.saga_orchestrator.compensation import SagaCompensator` | MEDIUM — must stay valid |
| `tests/services/test_saga_compensation.py` | `from app.orchestration.saga_orchestrator.compensation import SagaCompensator` | MEDIUM |
| `tests/services/test_saga_compensation.py` | `from app.orchestration.saga_orchestrator import SagaCompensationError` | LOW — via __init__ |

**Mitigation:** Keep `SagaCompensator` class in `compensation.py`. Do not move the class itself — only extract the handler method bodies to `compensation_handlers.py`.

### `flow_integrity.py` callers (production)

| File | Import | Risk |
|------|--------|------|
| `app/services/data_integrity_monitoring.py` | `from app.services.flow_integrity import FlowIntegrityService` (inferred from grep) | MEDIUM — must verify exact import |

**Action for plan:** Before writing shim, grep `data_integrity_monitoring.py` for exact import form to ensure shim covers it.

---

## Validation Architecture

> `workflow.nyquist_validation` is not present in `.planning/config.json` — this section is included because tests are already available and contract validation is required by CONTEXT.md decisions.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 + pytest-asyncio |
| Config file | `backend-hormonia/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd backend-hormonia && python -m pytest tests/orchestration/test_saga_orchestrator.py tests/services/test_saga_compensation.py -x -q` |
| Full suite command | `cd backend-hormonia && python -m pytest -x --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SPLIT-08 | Metrics extracted; orchestrator.py < 500 LOC; `SagaOrchestrator` importable from original paths | unit + line-budget | `python -m pytest tests/orchestration/test_saga_orchestrator.py -x -q && wc -l app/orchestration/saga_orchestrator/orchestrator.py` | ✅ |
| SPLIT-08 | Prometheus metrics available (or gracefully absent) after extraction | unit | `python -m pytest tests/orchestration/test_saga_orchestrator.py -k "metric" -x -q` | ✅ (covered by existing tests) |
| SPLIT-09 | `SagaCompensator` importable from `saga_orchestrator.compensation`; compensation.py < 500 LOC | unit + line-budget | `python -m pytest tests/services/test_saga_compensation.py -x -q && wc -l app/orchestration/saga_orchestrator/compensation.py` | ✅ |
| SPLIT-09 | Compensation step handlers (`_compensate_message`, `_compensate_flow`, `_compensate_patient`) behave identically after extraction | unit regression | `python -m pytest tests/services/test_saga_compensation.py -x -q` | ✅ |
| SPLIT-10 | `FlowIntegrityService` importable from original `app.services.flow_integrity` path; flow_integrity_pkg modules < 500 LOC | unit + line-budget | `python -c "from app.services.flow_integrity import FlowIntegrityService; print('OK')"` | Partial — no dedicated flow_integrity test file found |
| SPLIT-10 | `data_integrity_monitoring.py` continues to import without error after shim applied | smoke import | `cd backend-hormonia && python -c "from app.services.data_integrity_monitoring import DataIntegrityMonitoringService; print('OK')"` | ❌ Wave 0 gap |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/orchestration/ tests/services/test_saga_compensation.py -x -q`
- **Per wave merge (per plan):** Full saga + compensation test suite + line-budget check + shim import verification
- **Phase gate:** `python -m pytest -x --tb=short` before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/services/test_flow_integrity.py` — no dedicated test file for `FlowIntegrityService` found. Need to add a minimal smoke test covering: (1) `FlowIntegrityService` importable from shim path; (2) `get_flow_integrity_service(db)` returns an instance; (3) `validate_flow_consistency` and `repair_flow_integrity` callable.
- [ ] Import smoke test for `data_integrity_monitoring.py` — verify it imports cleanly after shim applied.

---

## Open Questions

1. **Does `orchestrator.py` reach strictly < 500 lines after extracting only the metrics block?**
   - What we know: Metrics block is ~60 LOC; compat wrappers are ~62 LOC; imports are ~40 LOC; remaining class body is ~480 LOC
   - What's unclear: Whether the compat wrapper methods have any production callers that call them directly on a `SagaOrchestrator` instance (not via `self.compensator`)
   - Recommendation: Grep for `._compensate_saga(`, `._compensate_flow(`, `._compensate_patient(`, `._compensate_message(`, `._track_compensation_failure(` called on a `SagaOrchestrator` instance before deciding whether to remove or keep compat wrappers. If no callers: remove compat wrappers from `orchestrator.py` (they already delegate entirely to `self.compensator`). This brings `orchestrator.py` to ~515 LOC after metrics extraction, then the compat wrapper removal brings it to ~453 LOC — safely under 500.

2. **Exact import form in `data_integrity_monitoring.py` for `flow_integrity`**
   - What we know: `data_integrity_monitoring.py` is the only production caller found by grep
   - What's unclear: Whether it imports `FlowIntegrityService`, `get_flow_integrity_service`, or both
   - Recommendation: Read `data_integrity_monitoring.py` at plan time and match shim exports exactly

3. **`steps.py` at 518 LOC — pre-existing out-of-budget file**
   - What we know: `steps.py` is 518 lines, 18 lines over the 500-line budget. It predates Phase 19 and is not in the SPLIT-08 target.
   - What's unclear: Whether the verifier will flag this as a Phase 19 gap
   - Recommendation: Document in SUMMARY as pre-existing condition, explicitly out of scope for Phase 19. The verifier should only check the three files targeted by SPLIT-08/09/10.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Monolithic service files | `*_pkg` directory with focused sub-modules + legacy shim | Phase 17-18 | Consistent pattern now established; Phase 19 follows exactly |
| Direct class method ownership of all logic | Mixin-composed service classes | Phase 17-18 | Enables fine-grained testing and < 500 LOC enforcement |
| Single Prometheus metrics block inline | Dedicated `metrics.py` module | Phase 19 (new) | Metrics can be tested and updated independently |

---

## Sources

### Primary (HIGH confidence)

- Direct file inspection — `orchestrator.py` (645 LOC), `compensation.py` (573 LOC), `flow_integrity.py` (559 LOC) — read in full during research
- Direct inspection of Phase 17/18 `*_pkg` pattern implementations: `flow_monitoring_pkg/`, `enhanced_flow_engine_pkg/`, `flow_dashboard_pkg/`
- `pyproject.toml` — pytest configuration and asyncio_mode settings
- `tests/orchestration/test_saga_orchestrator.py`, `tests/services/test_saga_compensation.py` — existing test coverage confirmed

### Secondary (MEDIUM confidence)

- `STATE.md` — phase history and decisions recorded for Phases 17-18 confirming shim pattern and explicit `__all__` as mandatory
- `CONTEXT.md` — user decisions confirmed `*_pkg` pattern and `<500` LOC enforcement

### Tertiary (LOW confidence)

- None — all findings are from direct codebase inspection.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — same stack as Phases 17/18, no new dependencies
- Architecture: HIGH — `*_pkg` pattern fully documented with two prior implementations
- Pitfalls: HIGH — circular imports and AsyncSession mixing are confirmed risks based on existing code structure
- Line-count projections: MEDIUM — estimated after reading file structure; exact counts require mechanical extraction

**Research date:** 2026-02-26
**Valid until:** 2026-03-28 (stable codebase, no fast-moving dependencies)
