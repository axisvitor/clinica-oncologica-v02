---
phase: 09-observability
plan: 03
subsystem: websocket
tags: [websocket, redis, pubsub, cross-instance, broadcast]

# Dependency graph
requires:
  - phase: 09-observability
    provides: WebSocket connection manager with broadcast_to_all_authenticated, broadcast_to_patient_room, broadcast_to_user API
provides:
  - Correct cross-instance WebSocket message delivery via RedisPubSubManager
  - Fixed handler method calls matching UnifiedWebSocketConnectionManager API
  - No AttributeError on incoming pub/sub messages
affects: [websocket, multi-instance, horizontal-scaling]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Use UnifiedWebSocketConnectionManager.broadcast_to_all_authenticated() for global broadcast — not broadcast()"
    - "Use UnifiedWebSocketConnectionManager.broadcast_to_patient_room() for room messages — not broadcast_to_room()"
    - "Use UnifiedWebSocketConnectionManager.broadcast_to_user() for user messages — not manual connection iteration"

key-files:
  created: []
  modified:
    - backend-hormonia/app/services/redis_pubsub_manager.py

key-decisions:
  - "Replace manual user connection iteration (conn_data.get()) with broadcast_to_user() — ConnectionInfo is a dataclass, not a dict; .get() raises AttributeError at runtime"
  - "broadcast_to_all_authenticated() is the correct name (not broadcast()) because it only sends to authenticated connections, which is the intended semantics for WebSocket pub/sub"
  - "No public API of UnifiedWebSocketConnectionManager was changed — only fixed the callers in RedisPubSubManager"

patterns-established:
  - "When adding cross-instance pub/sub delivery, always verify method names against the actual connection manager API before wiring"

requirements-completed: [OBS-03]

# Metrics
duration: 5min
completed: 2026-02-23
---

# Phase 9 Plan 03: RedisPubSubManager Method Name Fix Summary

**Fixed three broken cross-instance WebSocket delivery methods in RedisPubSubManager to call correct UnifiedWebSocketConnectionManager API, eliminating silent AttributeError in multi-instance deployments**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-23T13:27:18Z
- **Completed:** 2026-02-23T13:32:00Z
- **Tasks:** 1 of 1
- **Files modified:** 1

## Accomplishments
- Fixed `_handle_broadcast()`: `broadcast()` -> `broadcast_to_all_authenticated()`
- Fixed `_handle_room_message()`: `broadcast_to_room()` -> `broadcast_to_patient_room()`
- Fixed `_handle_user_message()`: replaced 8-line manual connection iteration + `send_personal_message()` with single `broadcast_to_user()` call
- Echo prevention (instance_id check) confirmed intact and untouched
- All publish methods confirmed unchanged

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix three broken method calls in RedisPubSubManager handler methods** - `6be2fcce` (fix)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `backend-hormonia/app/services/redis_pubsub_manager.py` - Corrected three handler method calls to match UnifiedWebSocketConnectionManager API; removed broken manual connection iteration pattern

## Decisions Made
- Replace manual user connection iteration (using `conn_data.get("user_id")`) with `broadcast_to_user()` — `ConnectionInfo` is a dataclass, not a dict; `.get()` raises `AttributeError` at runtime
- `broadcast_to_all_authenticated()` is the correct name because it only sends to authenticated connections, matching the intended semantics
- No public API of `UnifiedWebSocketConnectionManager` was changed — only the callers in `RedisPubSubManager`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `python` command not found in WSL environment; used `python3` for import verification. Import succeeded without issues.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Cross-instance WebSocket message delivery is now correct; multi-instance deployments can rely on pub/sub broadcasting without AttributeError
- The WebSocket pub/sub blocker noted in STATE.md (Phase 9 research flag) is resolved
- Ready for any remaining Phase 09 observability plans

---
*Phase: 09-observability*
*Completed: 2026-02-23*
