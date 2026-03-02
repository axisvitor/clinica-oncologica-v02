---
phase: 33-new-provider-foundation
plan: 03
subsystem: api
tags: [wuzapi, redis, circuit-breaker, testing, mock]
requires:
  - phase: 33-01
    provides: WuzAPI client foundation and retry policy
provides:
  - Redis circuit breaker protection around WuzAPI HTTP execution
  - MockWuzAPIClient drop-in test double with in-memory message capture
  - Env-driven get_wuzapi_client factory and exports for real/mock selection
affects: [phase-34-webhook-adapter, phase-36-idempotent-sender]
tech-stack:
  added: []
  patterns: [redis circuit breaker call-wrapper, env-based client factory, async mock client]
key-files:
  created:
    - backend-hormonia/app/integrations/wuzapi/mock.py
    - backend-hormonia/tests/integrations/wuzapi/test_wuzapi_mock.py
  modified:
    - backend-hormonia/app/integrations/wuzapi/client.py
    - backend-hormonia/app/integrations/wuzapi/__init__.py
    - backend-hormonia/tests/integrations/wuzapi/test_wuzapi_client.py
key-decisions:
  - "Use RedisCircuitBreaker.call() around _do_request so open-circuit rejects before HTTP execution."
  - "Use WHATSAPP_WUZAPI_USE_MOCK=true as the single switch for mock activation via package factory."
patterns-established:
  - "WuzAPI client resilience: rate limiter first, then circuit breaker, then request execution"
  - "Mock client mirrors public interface and returns realistic provider-shaped payloads"
requirements-completed: [CLI-04, CLI-05]
duration: 10m
completed: 2026-03-02
---

# Phase 33 Plan 03: New Provider Foundation Summary

**Redis-backed circuit breaker now shields WuzAPI request execution while a drop-in mock client and env factory enable deterministic testing without outbound HTTP.**

## Performance

- **Duration:** 10m
- **Started:** 2026-03-02T00:46:08Z
- **Completed:** 2026-03-02T00:57:05Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Integrated `RedisCircuitBreaker(name="wuzapi")` with thresholds 5/60/3 directly into `WuzAPIClient` request flow.
- Added `MockWuzAPIClient` with `send_text`, `send_media`, `connect`, `disconnect`, async context manager support, and in-memory sent message tracking.
- Added `get_wuzapi_client()` in package exports to switch between real and mock clients via `WHATSAPP_WUZAPI_USE_MOCK`.
- Added 10 dedicated mock/factory tests and verified the full WuzAPI integration test suite passes.

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire RedisCircuitBreaker into WuzAPIClient** - `1f9d4ac2` (feat)
2. **Task 2 (TDD RED): Add failing tests for mock and factory behavior** - `be06f614` (test)
3. **Task 2 (TDD GREEN): Implement mock client and env factory** - `3c8b3b50` (feat)
4. **Task 2 deviation fix: stabilize pre-existing client tests under shared breaker state** - `660fe773` (fix)

## Files Created/Modified

- `backend-hormonia/app/integrations/wuzapi/client.py` - Circuit breaker wiring around request execution.
- `backend-hormonia/app/integrations/wuzapi/mock.py` - Mock client with realistic responses and in-memory message log.
- `backend-hormonia/app/integrations/wuzapi/__init__.py` - Factory function and export surface updates.
- `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_mock.py` - 10 behavior tests for mock client/factory/circuit-breaker key.
- `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_client.py` - Test isolation fix to avoid cross-test Redis circuit leakage.

## Decisions Made

- Kept the backoff decorator on `_make_request` and moved HTTP logic into `_do_request` so circuit-breaker wrapping remains explicit and reusable.
- Factory selection uses only `WHATSAPP_WUZAPI_USE_MOCK` (string `"true"`, case-insensitive) to minimize configuration ambiguity.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed cross-test failure caused by shared Redis breaker state**
- **Found during:** Plan verification (`python3 -m pytest tests/integrations/wuzapi/ -x -q`)
- **Issue:** Existing `test_wuzapi_client.py` accumulated failures in shared Redis state (`name="wuzapi"`), opening the circuit and breaking later assertions.
- **Fix:** Updated test helper to force in-memory breaker mode and reset state for each test client.
- **Files modified:** `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_client.py`
- **Verification:** `python3 -m pytest tests/integrations/wuzapi/ -x -q`
- **Committed in:** `660fe773`

---

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** Necessary for deterministic test execution after introducing a globally keyed Redis circuit breaker; no scope creep.

## Issues Encountered

- `python` binary was unavailable in environment; switched verification commands to `python3`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- WuzAPI client now has resilience and test-double infrastructure required for downstream webhook parsing and idempotent message sender migration work.
- No new blockers introduced.

---
*Phase: 33-new-provider-foundation*
*Completed: 2026-03-02*

## Self-Check: PASSED

- FOUND: `.planning/phases/33-new-provider-foundation/33-03-SUMMARY.md`
- FOUND: `1f9d4ac2`
- FOUND: `be06f614`
- FOUND: `3c8b3b50`
- FOUND: `660fe773`
