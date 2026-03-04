---
phase: 42-admin-spa-quality
plan: 01
subsystem: ui
tags: [react, typescript, wuzapi, api-client, admin-spa]
requires:
  - phase: 39-wuzapi-migration
    provides: WuzAPI backend endpoints and Evolution tombstone
provides:
  - Evolution env/type references removed from active admin SPA contracts
  - Hive Mind API client trimmed to health and agents.list only
  - ADMIN-03 audit confirming no duplicated /whatsapp endpoint calls across client layers
affects: [42-02, 42-03, 42-04, admin-dashboard]
tech-stack:
  added: []
  patterns: ["Frontend API clients must map only to live backend routes", "Remove tombstoned provider references from runtime/env/types"]
key-files:
  created: []
  modified:
    - frontend-hormonia/src/lib/env-validator.ts
    - frontend-hormonia/src/types/api-wave2.ts
    - frontend-hormonia/src/types/system-stats.ts
    - frontend-hormonia/src/lib/api-client/hive-mind.ts
key-decisions:
  - "Kept Hive Mind client surface to /health and /agents only to avoid guaranteed 404s from dead routes."
  - "Documented ADMIN-03 as two distinct endpoint families (/whatsapp/* in WhatsAppService vs /hive-mind/* in apiClient), so no dedup action was required."
patterns-established:
  - "API contract hardening: remove frontend method/type surfaces when backend endpoints do not exist."
  - "Provider tombstone consistency: remove stale env keys and service-status fields after migration."
requirements-completed: [ADMIN-01, ADMIN-02, ADMIN-03]
duration: 22 min
completed: 2026-03-04
---

# Phase 42 Plan 01: Evolution Cleanup and Hive Mind API Alignment Summary

**Admin SPA now reflects post-WuzAPI reality by removing lingering Evolution contracts and keeping Hive Mind client calls on the two backend routes that actually exist.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-03-04T13:00:36Z
- **Completed:** 2026-03-04T13:23:18Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Removed remaining `VITE_ENABLE_EVOLUTION` and `VITE_EVOLUTION_API_URL` validation surfaces from runtime env validation.
- Removed `evolution_api` from admin system service-status TypeScript contracts in both Wave2 and system-stats type modules.
- Trimmed `hive-mind.ts` to only `health()` and `agents.list()` with dead type/method cleanup matching live backend routes.
- Completed ADMIN-03 audit: `WhatsAppService.ts` uses `/api/v2/whatsapp/*` while `apiClient` modules do not call WhatsApp endpoints; no duplicate endpoint calls found.

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove Evolution dead code + duplicate API audit** - `742f709b` (fix)
2. **Task 2: Trim hive-mind.ts to real endpoints** - `1ab4a067` (fix)

## Files Created/Modified
- `frontend-hormonia/src/lib/env-validator.ts` - Removed Evolution validation keys and kept Demo-only validation section.
- `frontend-hormonia/src/types/api-wave2.ts` - Removed stale `ServiceStatusMetrics.evolution_api` field.
- `frontend-hormonia/src/types/system-stats.ts` - Removed stale `ServiceStatusMetrics.evolution_api` field.
- `frontend-hormonia/src/lib/api-client/hive-mind.ts` - Removed six dead response types and all dead API methods; retained `health` + `agents.list`.

## Decisions Made
- Kept hive-mind frontend API surface strictly aligned to existing backend endpoints (`/api/v2/hive-mind/health`, `/api/v2/hive-mind/agents`).
- Treated ADMIN-03 duplicate concern as architectural-layer duplication (two HTTP clients) rather than endpoint duplication because endpoint families are distinct.

## Deviations from Plan

None - plan executed exactly as written.

## Authentication Gates

None.

## Issues Encountered
- `eslint` reports 5 pre-existing warnings in unrelated metrics chart/websocket files; no errors and no scope expansion applied.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Ready for `42-02-PLAN.md` (TanStack Query migration for Hive Mind components).
- API/client contract cleanup in this plan reduces noise for upcoming Prettier and knip passes.

---
*Phase: 42-admin-spa-quality*
*Completed: 2026-03-04*

## Self-Check: PASSED

- Found summary file: `.planning/phases/42-admin-spa-quality/42-01-SUMMARY.md`
- Found task commit: `742f709b`
- Found task commit: `1ab4a067`
