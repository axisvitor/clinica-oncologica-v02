---
phase: 43-quiz-interface-quality
plan: 02
subsystem: testing
tags: [jest, msw, react-testing-library, quiz]
requires:
  - phase: 43-01
    provides: Quiz lint/test baseline and dependency modernization entrypoint
provides:
  - Quiz test dependencies upgraded to MSW v2 with CSS module mapper support
  - MSW handlers migrated from rest/ctx to http/HttpResponse
  - Jest runtime compatibility layer for MSW v2 in jsdom-based suites
affects: [43-03, 43-04, quiz-quality-gates]
tech-stack:
  added: [identity-obj-proxy, undici]
  patterns: [MSW v2 handler conventions, Jest polyfill bootstrap for node interceptors]
key-files:
  created: [quiz-mensal-interface/tests/polyfills.ts]
  modified: [quiz-mensal-interface/package.json, quiz-mensal-interface/package-lock.json, quiz-mensal-interface/tests/mocks/handlers.ts, quiz-mensal-interface/tests/setup.ts, quiz-mensal-interface/tests/quiz-other-option.test.tsx]
key-decisions:
  - Keep Jest on jsdom but force node export conditions to resolve MSW v2 node entrypoints.
  - Add explicit runtime polyfills in test setup instead of downgrading MSW.
patterns-established:
  - "MSW handlers in quiz tests must use http/HttpResponse only"
  - "Load polyfills before importing msw/node server in Jest setup"
requirements-completed: [QUIZ-04, QUIZ-05]
duration: 71 min
completed: 2026-03-05
---

# Phase 43 Plan 02: MSW v2 Quiz Test Migration Summary

**Quiz test infrastructure now runs on MSW v2 with stable Jest/jsdom interoperability, preserving token and failure-path quiz coverage.**

## Performance

- **Duration:** 71 min
- **Started:** 2026-03-05T00:06:30Z
- **Completed:** 2026-03-05T01:18:13Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added missing `identity-obj-proxy` dependency and upgraded `msw` to v2 in quiz test stack.
- Migrated all quiz MSW handlers from `rest/ctx` to `http/HttpResponse` with equivalent scenarios.
- Restored green targeted suites by adding deterministic MSW/Jest polyfills and preserving existing UI assertions.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add missing test dependency and upgrade MSW to v2** - `bf600599` (chore)
2. **Task 2: Migrate MSW handlers/setup from v1 rest/ctx API to v2 http/HttpResponse API** - `7bc1a9c7` (feat)

## Files Created/Modified

- `quiz-mensal-interface/package.json` - Updated devDependencies and Jest resolver/export conditions for MSW v2.
- `quiz-mensal-interface/package-lock.json` - Locked dependency graph after MSW v2 and undici additions.
- `quiz-mensal-interface/tests/mocks/handlers.ts` - Rewrote handlers to `http.*` + `HttpResponse` conventions.
- `quiz-mensal-interface/tests/setup.ts` - Ensured polyfills load before MSW server lifecycle hooks.
- `quiz-mensal-interface/tests/polyfills.ts` - Added node/jsdom runtime globals needed by MSW v2 interceptors.
- `quiz-mensal-interface/tests/quiz-other-option.test.tsx` - Mocked toast hook to avoid cross-package React hook context conflict.

## Decisions Made

- Kept `listen/resetHandlers/close` lifecycle semantics unchanged while migrating only handler API surface.
- Added `testEnvironmentOptions.customExportConditions` for node-compatible package export resolution under jsdom.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Jest could not resolve `msw/node` with default jsdom export conditions**

- **Found during:** Task 2 (MSW v2 migration verification)
- **Issue:** Targeted suites failed before execution due module resolution mismatch.
- **Fix:** Added `testEnvironmentOptions.customExportConditions` in Jest config (`package.json`).
- **Files modified:** `quiz-mensal-interface/package.json`
- **Verification:** `npm test -- --runInBand --forceExit tests/unit/quiz-interface.test.tsx tests/quiz-other-option.test.tsx`
- **Committed in:** `7bc1a9c7`

**2. [Rule 3 - Blocking] Missing runtime globals (`Response`, streams, channels) for MSW v2 interceptors**

- **Found during:** Task 2 (post-resolution test run)
- **Issue:** Jest/jsdom environment lacked required node web APIs.
- **Fix:** Added `tests/polyfills.ts`, loaded it before server import in setup, and added `undici` for fetch primitives.
- **Files modified:** `quiz-mensal-interface/tests/polyfills.ts`, `quiz-mensal-interface/tests/setup.ts`, `quiz-mensal-interface/package.json`, `quiz-mensal-interface/package-lock.json`
- **Verification:** `npm test -- --runInBand --forceExit tests/unit/quiz-interface.test.tsx tests/quiz-other-option.test.tsx`
- **Committed in:** `7bc1a9c7`

**3. [Rule 3 - Blocking] Invalid hook call in quiz other-option suite via external toast store import path**

- **Found during:** Task 2 targeted verification
- **Issue:** `tests/quiz-other-option.test.tsx` executed real `useToast` hook chain crossing package boundaries, causing React context mismatch.
- **Fix:** Added local Jest mock for `@/hooks/use-toast` in that suite.
- **Files modified:** `quiz-mensal-interface/tests/quiz-other-option.test.tsx`
- **Verification:** `npm test -- --runInBand --forceExit tests/unit/quiz-interface.test.tsx tests/quiz-other-option.test.tsx`
- **Committed in:** `7bc1a9c7`

---

**Total deviations:** 3 auto-fixed (3 blocking)
**Impact on plan:** All fixes were required to complete planned migration and keep verification green without scope creep.

## Issues Encountered

- Jest run without `--forceExit` stayed open after passing due lingering async handles; verification repeated with `--forceExit` and passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Quiz test stack now uses supported MSW v2 APIs and can be extended in follow-up plans without legacy rest/ctx constraints.
- Remaining Phase 43 plans can rely on this baseline for additional quality-gate automation.

---

_Phase: 43-quiz-interface-quality_
_Completed: 2026-03-05_

## Self-Check: PASSED

- Found `.planning/phases/43-quiz-interface-quality/43-02-SUMMARY.md`.
- Found task commits `bf600599` and `7bc1a9c7`.
