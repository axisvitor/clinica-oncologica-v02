# Phase 23: Service Migration - Research

**Researched:** 2026-02-27
**Domain:** FastAPI + SQLAlchemy AsyncSession service-layer migration (API/Celery coexistence)
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
### Caller compatibility contract
- Preserve existing service method behavior and external call expectations during migration.
- Avoid breaking argument names/order and returned data shapes at existing call sites.
- If async adaptation requires helper methods, keep compatibility wrappers so current callers continue to work.

### API and Celery coexistence policy
- Shared services invoked from API context become async-capable and accept `AsyncSession` via DI constructor pattern.
- Services exclusively used by Celery remain sync and continue using `Session`.
- For dual-use services, keep explicit async paths for API calls and sync-compatible paths for Celery workers; do not use event-loop bridging hacks in worker code.

### Error semantics and behavior parity
- Preserve current business validation behavior and error meanings while migrating DB access.
- Keep exception categories/messages stable unless a change is required to correct incorrect behavior.
- Prioritize behavior parity over style-only refactors in this phase.

### Rollout and acceptance strictness
- Migrate by service group (patient, quiz, analytics, communication, auth/session, infrastructure, `flow_monitoring_pkg`) with automated checks after each group.
- Consider each group complete only when API-context usage is non-blocking and group-level automated checks pass.
- End phase with cross-group verification focused on zero `MissingGreenlet` regressions in migrated service paths.

### Claude's Discretion
- Exact method naming for async/sync adapters and wrappers.
- Internal query refactor shape (`db.execute(select(...))` helper patterns) as long as behavior parity is preserved.
- Test file organization and fixture reuse strategy.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SVC-01 | Patient services (`sync_service.py`, `validation_service.py`) support async callers via AsyncSession | Dual-session adapter pattern, `select()`/`await execute()` rewrite map, parity test pattern from Phase 22 async tests |
| SVC-02 | Quiz services (`quiz_service.py`, `quiz_templates.py`, `quiz_engine.py`, `enhanced_quiz_service.py`) migrated to async DB operations | Explicit API-async vs Celery-sync path split; remove async methods that still call sync `.query()`; dependency factory split |
| SVC-03 | Analytics services (`flow_analytics.py`, `metrics_collector.py`, `enhanced_analytics_service.py`) migrated to async DB operations | Async query conventions + no implicit IO guidance; prioritize API-exposed services first; preserve output contracts |
| SVC-04 | Communication services (`unified_whatsapp_service.py`, `dispatcher.py`) support async callers where invoked from API context | Keep async-first API paths, preserve sync worker compatibility, avoid worker loop-bridging hacks |
| SVC-05 | Auth/session services (`firebase_user_sync_service.py`, `session_service.py`) support async callers | Replace sync ORM calls in async methods; keep role/security semantics stable; validate auth contract parity |
| SVC-06 | Infrastructure services (`consent_service.py`, `audit_service.py`, `cache/flow_template_cache.py`) support async callers where invoked from API context | Migrate API-invoked DB operations to async-safe patterns; keep Celery-only infra sync where applicable |
| SVC-07 | Flow monitoring service (`flow_monitoring_pkg/`) mixin hierarchy accepts AsyncSession | Apply mixed-session hierarchy pattern similar to `flow_dashboard_pkg`; prevent sync query calls in async-exposed paths |
</phase_requirements>

## Summary

Phase 23 should be planned as a targeted service-layer conversion, not a broad architecture rewrite. The codebase already has the Phase 21 foundation (`get_async_db`, async engine/session factory, `DualSessionMixin`) and Phase 22 proven patterns (async-safe `select/execute`, contract-preserving tests, concurrent safety checks). The planning focus is sequencing service groups so API-reachable services become non-blocking while Celery-only services remain sync.

The highest risk is hidden sync ORM calls inside async methods (`db.query(...)`, sync `commit/refresh/execute` inside `async def`) and implicit lazy-load IO under `AsyncSession` (officially tied to `MissingGreenlet`). This is already visible in Phase 23 target files (`patient/sync_service.py`, `patient/validation_service.py`, `firebase_user_sync_service.py`, several analytics and monitoring services). Plan tasks around eliminating these patterns incrementally per service group and proving parity after each group.

A second planning risk is boundary confusion: some services are dual-use (API + Celery), others are effectively worker-only. User decisions lock this policy: dual-use services need explicit async API paths plus sync-compatible worker paths, and worker code must not rely on event-loop bridging tricks. Keep migration localized to service internals and DI wiring, preserving caller signatures and response/error contracts.

**Primary recommendation:** Use a per-group "API-async first, Celery-sync preserved" migration template: adapt session typing + query execution path + parity tests, then verify zero `MissingGreenlet` in that group before moving on.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | `>=2.0.45,<2.1.0` | ORM + async/session model | Official async patterns use `AsyncSession` + `select()`/`execute()` and explicitly address `MissingGreenlet` pitfalls |
| FastAPI | `>=0.128.0,<0.200.0` | API DI + request lifecycle | Existing project DI uses FastAPI dependencies; async/sync dependency functions are first-class and composable |
| asyncpg | `>=0.30.0,<0.31.0` | Async PostgreSQL driver | Required backend for async engine URL (`postgresql+asyncpg://`) already implemented in project async engine |
| psycopg (v3) | `>=3.2.13,<3.3.0` | Sync PostgreSQL driver for worker/session paths | Preserves Celery sync paths and existing sync SQLAlchemy Session behavior |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | `>=8.1.0,<9.0.0` | Test runner | Group-level regression checks after each service migration slice |
| pytest-asyncio | `>=0.23.0,<0.24.0` | Async test execution | Validate async service methods and ensure no sync query regressions in async paths |
| redis (redis-py asyncio) | `>=6.4.0,<7.0.0` | Session/cache integration in service layer | Where migrated services combine DB + Redis behavior in API async context |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SQLAlchemy `select()/execute()` for async paths | Keep legacy `.query()` in async methods | Causes implicit/sync IO risk (`MissingGreenlet`) in API async context |
| Explicit dual paths (async API + sync Celery) | Single bridged path via async/sync adapters in worker | Violates locked coexistence policy; increases runtime coupling and debugging complexity |
| Incremental service-group migration | Big-bang migration across all services | Faster in theory, but high regression surface and weak rollback isolation |

**Installation:**
```bash
pip install -r backend-hormonia/requirements.txt
```

## Architecture Patterns

### Recommended Project Structure
```
backend-hormonia/app/
├── core/database/            # Async engine + DualSessionMixin primitives
├── dependencies/             # Async DI factories (API) and sync factories (Celery/shared)
├── services/                 # Migrated service internals, dual-path adapters
└── tasks/                    # Celery worker entrypoints (sync Session remains valid)
```

### Pattern 1: Dual-Session Service Contract
**What:** Service constructor accepts `Session | AsyncSession`; internal DB access goes through adapter helpers (or explicit branch helpers), not ad-hoc mixed calls.
**When to use:** Service is used by both API routes and Celery tasks.
**Example:**
```python
# Source: backend-hormonia/app/core/database/dual_session.py
class DualSessionMixin:
    db: Session | AsyncSession

    @property
    def is_async(self) -> bool:
        return isinstance(self.db, AsyncSession)

    def _execute(self, stmt, **kwargs):
        return self.db.execute(stmt, **kwargs)
```

### Pattern 2: Async API Dependency, Sync Worker Dependency
**What:** Keep async factories in `dependencies/*_services.py` using `Depends(get_async_db)`; keep sync factories in `service_dependencies.py` for worker-safe paths.
**When to use:** Any service reachable from API request scope.
**Example:**
```python
# Source: backend-hormonia/app/dependencies/flow_services.py
async def get_async_flow_analytics_service(
    db: AsyncSession = Depends(get_async_db),
) -> FlowAnalyticsService:
    return FlowAnalyticsService(db)
```

### Pattern 3: Async Query Rewrite (No Implicit IO)
**What:** Replace sync ORM query chains in async paths with `select(...)` + `await db.execute(...)` + `result.scalars()/all()`.
**When to use:** Any `async def` service method touching DB.
**Example:**
```python
# Source: backend-hormonia/app/services/flow_alerts.py
stmt = select(PatientFlowState).where(...)
inconsistent = (await self.db.execute(stmt)).scalars().all()
```

### Pattern 4: Behavior-Parity Regression Guard
**What:** Tests assert async path works and explicitly fail if sync query path is used.
**When to use:** Every migrated service group before marking complete.
**Example:**
```python
# Source: backend-hormonia/tests/unit/services/test_data_integrity_monitoring_async.py
db.query = Mock(side_effect=AssertionError("sync db.query should not be used"))
db.execute = AsyncMock()
```

### Anti-Patterns to Avoid
- **Async method with sync ORM calls:** `async def` plus `self.db.query(...)` or non-awaited DB operations causes blocking/`MissingGreenlet` risk.
- **Worker event-loop bridging as default path:** using `run_sync`/adapters to hide wrong session type in Celery violates locked coexistence policy.
- **Signature refactors during migration:** changing public method args/return shapes in the same PR obscures parity regressions.
- **Cross-group migration in one task:** weakens rollback and verification clarity.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Session type routing | Custom ad-hoc `if async` logic per method | `DualSessionMixin` + explicit async/sync service paths | Reduces duplicate branching and migration drift |
| Async ORM compatibility | Homemade wrappers around lazy loads | SQLAlchemy async guidance: eager load / explicit `await execute(select(...))` | Officially avoids implicit IO / `MissingGreenlet` traps |
| API dependency wiring | Manual service construction in routers everywhere | FastAPI dependency factories (`Depends(get_async_db)` for API) | Keeps boundary explicit and testable |
| Cache + template retrieval | New custom cache layer in migration | Existing `FlowTemplateCacheService` | Already handles TTL, invalidation, warmup, metrics |

**Key insight:** The project already has the migration primitives; Phase 23 success comes from disciplined application and verification, not new infrastructure.

## Common Pitfalls

### Pitfall 1: Hidden Sync DB Calls in Async Methods
**What goes wrong:** Method is `async`, but internals still call sync `query()/commit()/execute()` patterns.
**Why it happens:** Partial migration (type hint changed, internals not converted).
**How to avoid:** For every async-exposed service method, enforce `select()` + awaited execution path.
**Warning signs:** `TODO(async-migration)` markers and `db.query(` in target files.

### Pitfall 2: Implicit Lazy Loading Under AsyncSession
**What goes wrong:** Attribute access triggers IO outside awaited context, raising `MissingGreenlet`.
**Why it happens:** ORM lazy load/expired attributes in async call path.
**How to avoid:** Prefer explicit eager loading and explicit async query execution; set/keep `expire_on_commit=False` for async sessions.
**Warning signs:** Exceptions mentioning `greenlet_spawn` or lazy-load access during API calls.

### Pitfall 3: Dual-Use Service Boundary Drift
**What goes wrong:** Service works for API but breaks Celery (or vice versa).
**Why it happens:** Single-path refactor ignores coexistence contract.
**How to avoid:** Maintain explicit async API path and sync-compatible worker path, with parity wrappers where needed.
**Warning signs:** Worker failures after API migration slice; new coupling to async-only dependencies in tasks.

### Pitfall 4: Contract Regression During Refactor
**What goes wrong:** Changed errors, payload shapes, or side effects.
**Why it happens:** Style/cleanup changes bundled with session migration.
**How to avoid:** Keep migration PRs narrow; assert pre/post behavior in unit/integration tests.
**Warning signs:** Endpoint snapshot diffs without intentional requirement changes.

## Code Examples

Verified patterns from official docs and in-repo implementation:

### Async ORM query execution
```python
# Source: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
stmt = select(User).where(User.id == user_id)
result = await async_session.execute(stmt)
user = result.scalar_one_or_none()
```

### API dependency injection for async service
```python
# Source: backend-hormonia/app/dependencies/patient_services.py
async def get_async_data_integrity_service(
    db: AsyncSession = Depends(get_async_db),
) -> DataIntegrityMonitoringService:
    return DataIntegrityMonitoringService(db)
```

### Regression guard against sync query path
```python
# Source: backend-hormonia/tests/unit/services/test_flow_dashboard_async.py
class _QueueAsyncSession:
    async def execute(self, statement):
        ...
    def query(self, *args, **kwargs):
        raise AssertionError("sync db.query should not be used")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ORM `.query()` in async-reachable methods | `select()` + awaited `execute()` | SQLAlchemy 2.x async best-practice era; applied in project Phases 21-22 | Removes sync-in-async blocking patterns and reduces `MissingGreenlet` risk |
| Sync-only service DI in API paths | Async dependency factories per domain | Project Phase 21 | Makes API session boundary explicit and testable |
| Ad-hoc mixed session handling | Standardized dual-session mixin + parity helpers | Project Phase 21 onward | Consistent migration surface for shared API/Celery services |

**Deprecated/outdated:**
- Legacy assumption that `async def` method is safe even with sync ORM internals.
- Implicit lazy-loading reliance in API async paths without explicit loading strategy.

## Open Questions

1. **Exact API vs Celery call-site ownership per target service**
   - What we know: Several target services are used in both API and tasks.
   - What's unclear: Complete per-method call-site map for all SVC-01..SVC-07 files.
   - Recommendation: Add a Wave-0 call-site inventory task per service group before code changes.

2. **`flow_monitoring_pkg` API exposure depth in this phase**
   - What we know: Monitoring service is used heavily from tasks, with sync query usage across mixins.
   - What's unclear: Which methods are API-reachable now vs only background-invoked.
   - Recommendation: Migrate API-invoked methods first; keep confirmed Celery-only paths sync per locked policy.

## Sources

### Primary (HIGH confidence)
- SQLAlchemy asyncio docs - https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html (AsyncSession concurrency, implicit IO prevention, `expire_on_commit=False` guidance; release banner 2.0.47 dated 2026-02-24)
- SQLAlchemy MissingGreenlet docs - https://docs.sqlalchemy.org/en/20/errors.html#missinggreenlet (cause tied to implicit IO/lazy loading in async contexts)
- Project constraints and requirements: `.planning/phases/23-service-migration/23-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`
- Project implementation patterns: `backend-hormonia/app/core/database/async_engine.py`, `backend-hormonia/app/core/database/dual_session.py`, `backend-hormonia/app/dependencies/flow_services.py`, `backend-hormonia/app/dependencies/patient_services.py`

### Secondary (MEDIUM confidence)
- FastAPI dependency docs - https://fastapi.tiangolo.com/tutorial/dependencies/ (DI behavior and async/def interoperability)
- SQLAlchemy ORM select/query guide - https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html (2.x query style framing)

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - versions and patterns come from project requirements + official SQLAlchemy/FastAPI docs
- Architecture: MEDIUM - strong repo evidence, but some service call-site boundaries still need explicit inventory
- Pitfalls: HIGH - directly evidenced by current target files and official MissingGreenlet guidance

**Research date:** 2026-02-27
**Valid until:** 2026-03-29
