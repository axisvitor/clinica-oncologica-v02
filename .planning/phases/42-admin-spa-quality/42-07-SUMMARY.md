---
phase: 42-admin-spa-quality
plan: 07
subsystem: testing
tags: [knip, dependencies, typescript, vite, eslint]
requires:
  - phase: 42-admin-spa-quality
    provides: dependency hygiene baseline and verification gap list
provides:
  - Removed five knip-flagged unused dependencies from admin SPA
  - Restored green lint/typecheck/build after dependency pruning
  - Produced lockfile aligned to final dependency graph
affects: [phase-42-verification, admin-spa-quality]
tech-stack:
  added: []
  patterns: [native ui fallbacks, fetch-based API client]
key-files:
  created: [.planning/phases/42-admin-spa-quality/42-07-SUMMARY.md]
  modified:
    - frontend-hormonia/package.json
    - frontend-hormonia/package-lock.json
    - frontend-hormonia/src/components/ui/radio-group.tsx
    - frontend-hormonia/src/components/ui/slider.tsx
    - frontend-hormonia/src/components/ui/toggle.tsx
    - frontend-hormonia/src/lib/api-client/enhanced-analytics.ts
    - frontend-hormonia/src/utils/bootstrap.ts
key-decisions:
  - "Removed all five flagged dependencies instead of preserving dead-path imports."
  - "Replaced axios/Radix-dependent code paths with local implementations to keep gates green post-prune."
patterns-established:
  - "Dependency hygiene: remove unused packages first, then repair direct compile/runtime coupling."
requirements-completed: [ADMIN-01, ADMIN-02, ADMIN-03, ADMIN-04, ADMIN-05, ADMIN-06, ADMIN-07, ADMIN-08]
duration: 25 min
completed: 2026-03-04
---

# Phase 42 Plan 07: Dependency gap closure Summary

**Admin SPA dependency hygiene is closed by removing the five remaining knip-unused packages and keeping frontend quality gates green with targeted compatibility fixes.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-03-04T19:13:28Z
- **Completed:** 2026-03-04T19:38:40Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Removed `@radix-ui/react-radio-group`, `@radix-ui/react-slider`, `@radix-ui/react-toggle`, `axios`, and `web-vitals` from admin SPA dependencies.
- Verified `eslint`, `tsc --noEmit`, and `vite build` remain green after dependency pruning.
- Re-ran knip dependency audit and confirmed there are no remaining `Unused dependencies` findings.

## Task Commits

Each task was committed atomically:

1. **Task 1: Resolve the five unresolved knip dependency findings** - `62199919` (chore)
2. **Task 2: Run full post-cleanup quality gates and confirm lockfile consistency** - `6d3a8d7b` (fix)

## Files Created/Modified

- `frontend-hormonia/package.json` - Removed five unused dependencies from the runtime dependency graph.
- `frontend-hormonia/package-lock.json` - Synced lockfile with the pruned dependency set.
- `frontend-hormonia/src/components/ui/radio-group.tsx` - Replaced Radix dependency with local radio-group implementation.
- `frontend-hormonia/src/components/ui/slider.tsx` - Replaced Radix slider wrapper with native range-based slider component.
- `frontend-hormonia/src/components/ui/toggle.tsx` - Replaced Radix toggle with local pressed-state button implementation.
- `frontend-hormonia/src/lib/api-client/enhanced-analytics.ts` - Replaced axios transport with fetch-based HTTP client.
- `frontend-hormonia/src/utils/bootstrap.ts` - Removed `web-vitals` dynamic import usage.

## Decisions Made

- Removed all five flagged dependencies instead of keeping packages tied to dead-path imports.
- Preserved app behavior by implementing local UI/API alternatives rather than re-adding removed dependencies.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Dependency removal broke TypeScript compilation**

- **Found during:** Task 2 (post-cleanup quality gates)
- **Issue:** Existing files still imported removed Radix/axios/web-vitals modules, causing `tsc` failures.
- **Fix:** Replaced affected UI/API/bootstrap paths with dependency-free local implementations.
- **Files modified:** `frontend-hormonia/src/components/ui/radio-group.tsx`, `frontend-hormonia/src/components/ui/slider.tsx`, `frontend-hormonia/src/components/ui/toggle.tsx`, `frontend-hormonia/src/lib/api-client/enhanced-analytics.ts`, `frontend-hormonia/src/utils/bootstrap.ts`
- **Verification:** `npx eslint . --max-warnings 0 && npx tsc --noEmit && npm run build` passes.
- **Committed in:** `6d3a8d7b`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Auto-fix was required to keep quality gates green after dependency pruning; no scope creep outside impacted dependency paths.

## Issues Encountered

- `knip --dependencies` still reports pre-existing `Unlisted dependencies` and `Unresolved imports` in test paths unrelated to this plan's dependency-removal gap.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ADMIN-07 dependency gap is closable from the unused-dependency perspective.
- Plan output is ready for verification/state closeout with known pre-existing knip test-path noise documented.

---

_Phase: 42-admin-spa-quality_
_Completed: 2026-03-04_

## Self-Check: PASSED

- FOUND: `.planning/phases/42-admin-spa-quality/42-07-SUMMARY.md`
- FOUND: `62199919`
- FOUND: `6d3a8d7b`
