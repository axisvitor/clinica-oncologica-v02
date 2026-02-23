---
phase: 06-async-hot-path-migration
plan: 02
subsystem: database
tags: [sqlalchemy, asyncsession, asyncpg, fastapi, flowcore, async-migration]

# Dependency graph
requires:
  - phase: 06-async-hot-path-migration
    provides: Research and infrastructure confirmation — AsyncSession, get_async_db, asyncpg already in place
provides:
  - FlowCore base class fully migrated to AsyncSession for all 7 annotated TODO(async-migration) sites
  - _commit_flow_state_with_lock converted to async def with await-based optimistic locking
  - flows router get_flow_service_dependency injects AsyncSession via get_async_db
  - EnhancedFlowEngine and FlowService receive AsyncSession for all hot-path methods
affects:
  - 06-async-hot-path-migration (plans 03, 04 — sequential_message_handler and quiz service follow same patterns)
  - Any code that calls FlowCore.enroll_patient, advance_patient_flow, pause_patient_flow, resume_patient_flow, get_flow_state, calculate_patient_day, health_check

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Inline repo queries pattern: replace self.repo.method() with await self.db.execute(select(Model).filter(...)) and result.scalar_one_or_none()"
    - "Dual-session DI pattern: AsyncSession for FlowCore/EnhancedFlowEngine hot paths, sync Session for legacy FlowManagementService ORM calls"
    - "Shared engine injection: EnhancedFlowEngine(async_db) passed to both FlowService and FlowManagementService to unify AsyncSession usage"

key-files:
  created: []
  modified:
    - backend-hormonia/app/services/flow_core.py
    - backend-hormonia/app/services/flow_service.py
    - backend-hormonia/app/services/flow_management.py
    - backend-hormonia/app/services/enhanced_flow_engine.py
    - backend-hormonia/app/api/v2/routers/flows.py

key-decisions:
  - "Dual-session DI: async_db for FlowCore/EnhancedFlowEngine (non-blocking hot paths), sync db for FlowManagementService ORM calls (avoids MissingGreenlet on legacy query API)"
  - "Shared EnhancedFlowEngine(async_db) passed to both FlowService and FlowManagementService so FlowCore inherited async methods work via both callers"
  - "FlowManagementService.advance/pause/resume: replaced enhanced_flow_engine._commit_flow_state_with_lock() (now async) with direct self.db.commit() (sync) since FlowManagementService uses sync Session"
  - "EnhancedFlowEngine sync methods migrated: _get_flow_type_from_state made async, generate_flow_message repo calls inlined, process_patient_response repo calls inlined, _get_conversation_history and _get_recent_interactions converted to async select()"

patterns-established:
  - "Inline async queries: When a sync repo is used by an async hot-path method, inline the specific query as await self.db.execute(select(Model).filter(...)) with a comment # Inlined from RepoClass.method() for async compat"
  - "FlowService list/query methods: use select(Model).filter() + result.scalars().all() pattern with func.count() for totals"
  - "EnhancedFlowEngine process methods: all DB interactions must be async when engine uses AsyncSession"

requirements-completed: [ASYNC-02]

# Metrics
duration: 12min
completed: 2026-02-23
---

# Phase 6 Plan 02: Flow Core Async Migration Summary

**FlowCore migrated to AsyncSession — 7 TODO(async-migration) sites resolved, optimistic locking made async, flows router injects AsyncSession with dual-session DI pattern to preserve sync FlowManagementService ORM calls**

## Performance

- **Duration:** 12 min
- **Started:** 2026-02-23T00:55:37Z
- **Completed:** 2026-02-23T01:07:10Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- All 7 `TODO(async-migration)` annotations in `flow_core.py` resolved — sync `Session.query()` calls replaced with `await self.db.execute(select(...))`
- `_commit_flow_state_with_lock` converted from sync `def` to `async def` with awaited query and commit, preserving full optimistic locking logic
- `get_flow_service_dependency` in flows router now injects `AsyncSession` via `get_async_db` into `FlowService` and `EnhancedFlowEngine`, while keeping sync `Session` for `FlowManagementService` repo calls
- `EnhancedFlowEngine` async-safe: `process_patient_response`, `generate_flow_message`, `_get_flow_type_from_state`, `_get_conversation_history`, `_get_recent_interactions` all converted to use async select queries
- `FlowService.get_patient_flow_history` and `list_templates` converted from sync `.query()` to async `select()` with `func.count()` for totals

## Task Commits

Each task was committed atomically:

1. **Task 1: Convert FlowCore to AsyncSession** - `48923d96` (feat)
2. **Task 2: Update flows router dependency to inject AsyncSession** - `f275cd00` (feat)

## Files Created/Modified
- `backend-hormonia/app/services/flow_core.py` - Added AsyncSession/select/text imports; converted all 7 TODO sites and _commit_flow_state_with_lock to async; removed all 7 TODO comments
- `backend-hormonia/app/api/v2/routers/flows.py` - Added get_async_db and AsyncSession imports; updated get_flow_service_dependency with dual async_db/db parameters
- `backend-hormonia/app/services/flow_service.py` - Added select/func imports; converted get_patient_flow_history and list_templates to async select() queries
- `backend-hormonia/app/services/flow_management.py` - Added optional flow_engine kwarg to constructor; replaced _commit_flow_state_with_lock calls with direct sync self.db.commit()
- `backend-hormonia/app/services/enhanced_flow_engine.py` - Added select import; converted process_patient_response, generate_flow_message, _get_flow_type_from_state (now async), _get_conversation_history, _get_recent_interactions to async select queries; fixed self.db.commit() -> await self.db.commit()

## Decisions Made
- **Dual-session DI pattern**: `async_db` (AsyncSession) for FlowCore/EnhancedFlowEngine hot paths, sync `db` for FlowManagementService and FlowStateRepository. This avoids MissingGreenlet on legacy `.query()` ORM calls while still making the 7 annotated hot paths non-blocking.
- **Shared EnhancedFlowEngine(async_db)**: single engine instance passed to both FlowService and FlowManagementService so FlowCore inherited methods (enroll_patient, calculate_patient_day, etc.) work correctly from both callers.
- **FlowManagementService sync commit**: Since FlowManagementService uses sync Session, replaced calls to the now-async `_commit_flow_state_with_lock` with direct `self.db.commit()` inline, preserving version increment logic.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FlowManagementService called _commit_flow_state_with_lock without await after it was made async**
- **Found during:** Task 2 (flows router dependency update)
- **Issue:** FlowManagementService.advance_patient_flow, pause_patient_flow, and resume_patient_flow all called `self.enhanced_flow_engine._commit_flow_state_with_lock()` without await. After Task 1 made this method async, these would silently not commit.
- **Fix:** Replaced the three `_commit_flow_state_with_lock` calls in FlowManagementService with direct `flow_state.version = expected_version + 1; self.db.commit()` (sync), since FlowManagementService keeps sync Session
- **Files modified:** backend-hormonia/app/services/flow_management.py
- **Verification:** Import check passes; sync commit preserved with version increment
- **Committed in:** f275cd00 (Task 2 commit)

**2. [Rule 1 - Bug] EnhancedFlowEngine had sync self.db.query() and self.db.commit() calls that would fail with AsyncSession**
- **Found during:** Task 2 (tracing full call chain from flows router)
- **Issue:** EnhancedFlowEngine receives async_db in the dependency factory, but its own methods (process_patient_response, generate_flow_message, _get_flow_type_from_state, _get_conversation_history, _get_recent_interactions) used sync self.db.query() and self.db.commit()
- **Fix:** Converted all sync DB calls in EnhancedFlowEngine to await self.db.execute(select(...)) pattern; made _get_flow_type_from_state async; updated its call site to await; changed self.db.commit() to await self.db.commit()
- **Files modified:** backend-hormonia/app/services/enhanced_flow_engine.py
- **Verification:** Import check passes; all sync DB calls replaced
- **Committed in:** f275cd00 (Task 2 commit)

**3. [Rule 1 - Bug] FlowService.get_patient_flow_history and list_templates used sync self.db.query() on AsyncSession**
- **Found during:** Task 2 (FlowService receives async_db but has own sync DB methods)
- **Issue:** FlowService inherits FlowCore and receives async_db, but its own get_patient_flow_history and list_templates methods used self.db.query() which is unsupported on AsyncSession
- **Fix:** Converted both methods to use select(Model) with await self.db.execute() and func.count() for totals
- **Files modified:** backend-hormonia/app/services/flow_service.py
- **Verification:** Import check passes; select() + result.scalars().all() pattern applied consistently
- **Committed in:** f275cd00 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — bugs caused by passing AsyncSession to classes that still had sync DB calls)
**Impact on plan:** All three auto-fixes were necessary for correctness. The plan underestimated the cascade of sync DB calls in EnhancedFlowEngine and FlowService's own methods. The dual-session DI approach was the minimal correct solution that keeps FlowManagementService's legacy sync ORM calls working while making the 7 FlowCore hot paths non-blocking.

## Issues Encountered
- FlowManagementService creates its own EnhancedFlowEngine(db) internally. Solution: accept optional flow_engine kwarg in constructor, injecting the async_db-backed engine from the DI factory. This ensures FlowCore async methods work when called via FlowManagementService.
- The plan's scope was the 7 FlowCore annotations, but passing AsyncSession cascaded into EnhancedFlowEngine's non-annotated methods and FlowService's own query methods. All were fixed as Rule 1 bugs.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- FlowCore async migration complete (ASYNC-02 satisfied)
- Same inline-repo-query pattern applies to Plan 03 (sequential_message_handler, 12 TODOs) and Plan 04 (enhanced_quiz_service, 8 TODOs)
- No blockers for next plan

---
*Phase: 06-async-hot-path-migration*
*Completed: 2026-02-23*
