# Phase 21: Async Foundation - Context

**Gathered:** 2026-02-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the DI infrastructure for async database operations: async session factory (`get_async_db`), dual-mode session support (`DualSessionMixin`), async service factory functions in `dependencies/`, and Celery isolation guards. This foundation enables all subsequent phases (22-27) to migrate services and routers to AsyncSession without breaking Celery worker paths.

Requirements: FOUND-01, FOUND-02, FOUND-03, FOUND-04.

</domain>

<decisions>
## Implementation Decisions

### Dual-mode session pattern
- Constructor injection: `Service.__init__(self, db: Session | AsyncSession)` — caller passes the right type
- Internal dispatch via `isinstance(self.db, AsyncSession)` checks
- Shared `DualSessionMixin` provides helper methods (`_execute()`, `_commit()`, `_get()`) that handle isinstance branching internally — services call `self._execute(stmt)` and don't care about sync/async
- Mixin location: `app/core/database/dual_session.py`

### get_async_db lifecycle
- Standalone `get_async_db` dependency alongside existing `get_db` — no replacement, no magic detection
- Routers switch one-by-one from `get_db` to `get_async_db` in later phases
- Async engine and session factory in `app/core/database/async_engine.py` (new file, separate from sync config)
- Driver: `asyncpg` (add to dependencies)
- Connection pooling: sensible defaults (pool_size=5, max_overflow=10, pool_pre_ping=True), tuning deferred to later

### Factory function design
- Organized one file per domain: `dependencies/patient_services.py`, `dependencies/flow_services.py`, etc.
- FastAPI `Depends()`-compatible async generators: `async def get_patient_service(db: AsyncSession = Depends(get_async_db)) -> PatientService`
- Flat injection only — each factory injects DB session, no nested `Depends()` chains
- Foundation scope: create the pattern + 2-3 example factories for critical services. Later phases (22-27) create their own factories as they migrate each service

### Celery isolation strategy
- Convention: Celery tasks always use sync `get_db()` — no changes to existing task code
- CI lint guard: `scripts/check_async_isolation.py` scans task files for `get_async_db` or `AsyncSession` imports and fails the build (follows existing `check_agent_run_calls.py` pattern)
- Runtime guard: `get_async_db` raises `RuntimeError` if called from non-async context (belt-and-suspenders defense in depth)
- Celery tasks calling shared dual-mode services pass sync `Session` — `DualSessionMixin` handles it

### Claude's Discretion
- Exact DualSessionMixin method signatures and helper API
- Which 2-3 services get example factories in this phase
- asyncpg connection string format adaptation
- Test fixtures for async session testing
- Pool default values (can adjust from suggested 5/10 if deployment target warrants)

</decisions>

<specifics>
## Specific Ideas

- CI guard pattern already exists: `scripts/check_agent_run_calls.py` blocks direct agent.run() — new `check_async_isolation.py` follows same pattern
- DualSessionMixin is similar to existing mixin patterns in the codebase (e.g., audit mixin)
- get_async_db must be request-scoped (FastAPI async generator with yield) matching get_db lifecycle

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 21-async-foundation*
*Context gathered: 2026-02-26*
