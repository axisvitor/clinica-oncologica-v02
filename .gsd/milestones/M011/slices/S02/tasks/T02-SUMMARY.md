---
id: T02
parent: S02
milestone: M011
provides:
  - S02 terminal verification: tsc, vite build, and grep audit all green
  - Pre-existing TS errors in e2e playwright config fixed (bracket notation for process.env)
key_files:
  - frontend-hormonia/tests/e2e/playwright.config.e2e.ts
  - frontend-hormonia/dist/index.html
key_decisions: []
patterns_established:
  - "queryPresets.realtime in queryClient.ts is an allowed low-threshold preset for monitoring hooks"
  - "useOptimizedQuery.helpers.ts and ProductionProvider.tsx are dead code — not imported anywhere"
observability_surfaces:
  - "rg 'staleTime|refetchInterval' across frontend-hormonia/src/ is the canonical audit command"
  - "tsc --noEmit exit code 0 confirms no type regressions from T01 edits"
  - "vite build producing dist/ confirms compilable output"
duration: 12m
verification_result: passed
completed_at: 2026-03-17
blocker_discovered: false
---

# T02: Install dependencies and verify build — S02 terminal verification all green

**Verified S02 request-discipline changes: npm ci + tsc --noEmit + vite build all exit 0, grep audit confirms no staleTime < 60s or refetchInterval < 120s outside monitoring hooks**

## What Happened

1. **npm ci** — installed 542 packages successfully (47s).
2. **tsc --noEmit** — initially found 6 pre-existing errors in `tests/e2e/playwright.config.e2e.ts` caused by `process.env.CI` dot notation with `noPropertyAccessFromIndexSignature: true`. Fixed by switching to `process.env['CI']` bracket notation. Second run: exit 0, zero errors.
3. **vite build** — 4741 modules transformed, clean production build in 73s. Output in `dist/`.
4. **Grep audit** — four separate audits (staleTime expression pattern, refetchInterval expression pattern, staleTime numeric literals, refetchInterval numeric literals) all returned empty outside monitoring exclusions.

Two files with sub-threshold values were identified and verified as non-issues:
- `queryClient.ts` `queryPresets.realtime` — explicitly a monitoring/real-time preset (allowed)
- `useOptimizedQuery.helpers.ts` — 30s staleTime fallback but dead code (zero imports)
- `ProductionProvider.tsx` — 1s dev staleTime but dead code (zero imports)

## Verification

| Check | Result |
|-------|--------|
| `npm ci` | ✅ 542 packages, exit 0 |
| `tsc --noEmit` | ✅ exit 0, zero errors |
| `vite build` | ✅ exit 0, 4741 modules, dist/ produced |
| staleTime < 60s grep (expression) | ✅ empty (no violations) |
| refetchInterval < 120s grep (expression) | ✅ empty (no violations) |
| staleTime < 60000 grep (numeric) | ✅ empty (no violations) |
| refetchInterval < 120000 grep (numeric) | ✅ empty (no violations) |
| Slice diagnostic check | ✅ all values above threshold outside monitoring exclusions |

## Diagnostics

- Run `rg "staleTime|refetchInterval" --type ts --type-add 'tsx:*.tsx' --type tsx frontend-hormonia/src/` to audit all values
- Exclude monitoring with: `| grep -v features/system | grep -v features/monitoring | grep -v hive-mind | grep -v ClinicalMonitoring | grep -v AdminMonitoringTab | grep -v hooks/api/useSystemStats | grep -v features/whatsapp`
- `queryPresets.realtime` in `queryClient.ts` is the only allowed sub-threshold preset definition
- Dead code files (`useOptimizedQuery.helpers.ts`, `ProductionProvider.tsx`) contain sub-threshold fallbacks but are never imported

## Deviations

- Fixed 6 pre-existing TS errors in `tests/e2e/playwright.config.e2e.ts` — `process.env.CI` → `process.env['CI']` (bracket notation required by `noPropertyAccessFromIndexSignature: true`). These errors pre-date T01 changes and were blocking `tsc --noEmit`.

## Known Issues

- `useOptimizedQuery.helpers.ts` has a 30s staleTime fallback — dead code today but should be cleaned up if reactivated.
- `ProductionProvider.tsx` has 1s dev-mode staleTime — also dead code, same cleanup note.
- 5 npm vulnerabilities (2 moderate, 3 high) — pre-existing, not related to S02 changes.

## Files Created/Modified

- `frontend-hormonia/tests/e2e/playwright.config.e2e.ts` — fixed process.env bracket notation for TS compliance
- `.gsd/milestones/M011/slices/S02/tasks/T02-PLAN.md` — added Observability Impact section (pre-flight fix)
