---
phase: 06-async-hot-path-migration
plan: 01
subsystem: database
tags: [asyncsession, sqlalchemy, fastapi, webhook, whatsapp, async-migration]

# Dependency graph
requires: []
provides:
  - "SequentialMessageHandler using AsyncSession for all DB operations"
  - "Webhook hot-path (evolution_webhook -> MessageWebhookHandler -> SequentialMessageHandler) is fully async end-to-end"
  - "Factory function get_sequential_message_handler accepts AsyncSession"
affects:
  - 06-async-hot-path-migration  # plans 02, 03 follow same pattern

# Tech tracking
tech-stack:
  added: []  # AsyncSession infrastructure already existed in database.py
  patterns:
    - "Inline async select() queries instead of calling sync repository methods from async context"
    - "async def _set_flow_progress() — convert sync helper to async when it calls await self.db.commit()"
    - "Route-level Depends(get_async_db) injects AsyncSession through the full handler chain"

key-files:
  created: []
  modified:
    - "backend-hormonia/app/services/flow/sequential_message_handler.py"
    - "backend-hormonia/app/integrations/whatsapp/api/webhooks.py"
    - "backend-hormonia/app/services/webhook/handlers/message_handler.py"
    - "backend-hormonia/app/services/response_processor/processor.py"
    - "backend-hormonia/app/agents/patient/flow_coordinator/coordinator.py"
    - "backend-hormonia/app/services/hive_mind_integration.py"

key-decisions:
  - "Inline FlowStateRepository.get_active_flow() as direct select() query in SequentialMessageHandler rather than converting the repository class — avoids breaking all 22 sync callers"
  - "Convert _set_flow_progress() from sync def to async def since it now calls await self.db.commit()"
  - "coordinator.py and hive_mind_integration.py keep sync SessionLocal() with comments — they are Hive-Mind agent initialization paths, not FastAPI hot paths; deferred to follow-up"
  - "webhooks.py: add Session import back alongside AsyncSession for other non-migrated handler signatures to avoid NameError"

patterns-established:
  - "Pattern: When a sync helper def contains await calls after async migration, convert it to async def and await all call sites"
  - "Pattern: Inline specific sync repo queries as select()-based await self.db.execute() rather than converting whole repository classes"
  - "Pattern: Route Depends(get_db) -> Depends(get_async_db) is the only change needed at the injection point; the session flows through db: Any chain"

requirements-completed:
  - ASYNC-01

# Metrics
duration: 65min
completed: 2026-02-22
---

# Phase 06 Plan 01: Async Hot-Path Migration — SequentialMessageHandler Summary

**AsyncSession migration of the WhatsApp webhook hot-path: all 12 sync DB sites in SequentialMessageHandler replaced with awaitable SQLAlchemy execute/commit, and FastAPI route injection switched from get_db to get_async_db**

## Performance

- **Duration:** ~65 min
- **Started:** 2026-02-22T22:55:00Z
- **Completed:** 2026-02-23T01:02:19Z
- **Tasks:** 2 of 2
- **Files modified:** 6

## Accomplishments

- All 12 `TODO(async-migration)` annotations in `sequential_message_handler.py` resolved — zero remain
- `SequentialMessageHandler.__init__` changed from `db: Session` to `db: AsyncSession`; all `self.db.query()` calls replaced with `await self.db.execute(select(...))`; all `self.db.commit()` calls are now `await self.db.commit()`
- The webhook handler chain (`evolution_webhook` -> `MessageWebhookHandler` -> `SequentialMessageHandler`) is now fully non-blocking: `Depends(get_db)` replaced with `Depends(get_async_db)` in both route handlers
- `FlowStateRepository.get_active_flow()` inlined as a direct `select(PatientFlowState)` query to avoid passing `AsyncSession` to a sync repository

## Task Commits

Each task was committed atomically:

1. **Task 1: Convert SequentialMessageHandler to AsyncSession** - `a09e63c7` (feat)
2. **Task 2: Update FastAPI-path callers to pass AsyncSession** - `e3572778` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `backend-hormonia/app/services/flow/sequential_message_handler.py` — Full AsyncSession migration: type hint, 12 TODO sites, _set_flow_progress() converted to async def, factory function updated
- `backend-hormonia/app/integrations/whatsapp/api/webhooks.py` — Route handlers use `Depends(get_async_db)`, `AsyncSession` type hints on hot-path functions; `Session` import preserved for non-migrated handlers
- `backend-hormonia/app/services/webhook/handlers/message_handler.py` — Docstring updated to note AsyncSession context; no logic change needed (db: Any)
- `backend-hormonia/app/services/response_processor/processor.py` — Docstring note; no logic change needed (db: Any, inherits AsyncSession via chain)
- `backend-hormonia/app/agents/patient/flow_coordinator/coordinator.py` — Comment added: Hive-Mind agent path uses sync Session, needs follow-up
- `backend-hormonia/app/services/hive_mind_integration.py` — Comment added: agent framework uses sync Session, needs follow-up

## Decisions Made

- Inlined `FlowStateRepository.get_active_flow()` as a direct `select(PatientFlowState)` query in `_get_or_create_flow_state()` rather than converting the whole repository class. This is the lowest-risk approach — the repository has many other sync callers outside this phase scope.
- `_set_flow_progress()` was originally a sync `def` that directly called `self.db.commit()`. After the migration, it needed `await self.db.commit()`. Converted it to `async def` and added `await` to all 12 call sites throughout the class.
- `coordinator.py` and `hive_mind_integration.py` both use `SessionLocal()` (sync) in agent framework initialization — these are not FastAPI request-path callers and are documented with comments for a follow-up migration task rather than changed now.
- When `Session` import was removed from `webhooks.py`, six other handler signatures (`handle_message_update`, `handle_send_message`, etc.) caused `NameError: name 'Session' is not defined`. Added `Session` import back alongside `AsyncSession` to fix this without expanding scope.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _set_flow_progress() converted from sync def to async def**
- **Found during:** Task 1 (Convert SequentialMessageHandler to AsyncSession)
- **Issue:** The plan specified converting `self.db.commit()` to `await self.db.commit()` inside `_set_flow_progress()`, but the method was a sync `def` — `await` is not valid inside a sync function
- **Fix:** Changed `def _set_flow_progress(...)` to `async def _set_flow_progress(...)` and added `await` to all 12 call sites within the class
- **Files modified:** `backend-hormonia/app/services/flow/sequential_message_handler.py`
- **Verification:** All 12 `await self._set_flow_progress(...)` confirmed via grep; import check passes
- **Committed in:** `a09e63c7` (Task 1 commit)

**2. [Rule 3 - Blocking] Session import re-added to webhooks.py after removal caused NameError**
- **Found during:** Task 2 (Update FastAPI-path callers)
- **Issue:** Replacing `Session` import with `AsyncSession` only caused `NameError: name 'Session'` at 6 non-migrated handler function signatures at module level
- **Fix:** Added `from sqlalchemy.orm import Session` back alongside `AsyncSession` so out-of-scope handlers keep their existing type hints
- **Files modified:** `backend-hormonia/app/integrations/whatsapp/api/webhooks.py`
- **Verification:** `python3 -c "from app.integrations.whatsapp.api.webhooks import evolution_webhook; print('import OK')"` passes
- **Committed in:** `e3572778` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug fix: sync→async def conversion, 1 blocking: missing import)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered

None beyond the two auto-fixed deviations above.

## User Setup Required

None - no external service configuration required. AsyncSession infrastructure (`asyncpg`, `get_async_db`) was already installed and configured in `database.py`.

## Next Phase Readiness

- Plan 06-01 complete: `sequential_message_handler.py` hot-path is fully async
- Plan 06-02 (`flow_core.py`, 7 TODOs) and 06-03 (`enhanced_quiz_service.py`, 8 TODOs) can proceed with the same patterns established here
- The `coordinator.py` / `hive_mind_integration.py` Hive-Mind agent paths still use sync `Session` — documented with comments for a follow-up task outside this phase

---
*Phase: 06-async-hot-path-migration*
*Completed: 2026-02-22*
