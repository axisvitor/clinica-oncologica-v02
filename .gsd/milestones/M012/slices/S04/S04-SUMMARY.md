---
id: S04
parent: M012
milestone: M012
provides:
  - Replayable verification script `verify-m012.sh` proving all 11 M012 Definition of Done items
  - Audit artifact `.gsd/milestones/M012/M012-VERIFY.json` with phase-level verification status
  - Milestone-level closure evidence across S01–S03 backend, pipeline, cache, skip, and frontend editor surfaces
requires:
  - slice: S01
    provides: migration, model, schemas, GET/PUT override API, cache invalidation path
  - slice: S02
    provides: override injection in `_get_day_config`, shared Redis cache key, skip logic in on-demand and batch paths
  - slice: S03
    provides: PatientDetailPage override editor UI, typed React Query hook, frontend build proof
affects: []
key_files:
  - verify-m012.sh
  - .gsd/milestones/M012/M012-VERIFY.json
key_decisions:
  - Final milestone verification is replayable and file-backed instead of relying on one-off terminal output
patterns_established:
  - verify script follows grouped PASS/FAIL phase pattern used by prior milestone verifiers
  - Phase audit persisted as JSON so milestone closure can be inspected without rerunning the build immediately
observability_surfaces:
  - `bash verify-m012.sh` stdout with 11 grouped checks and summary exit code
  - `.gsd/milestones/M012/M012-VERIFY.json` phase audit for ast.parse, structure, cache, skip, and frontend build checks
  - Requirement proof chain across S01–S03 summaries plus verifier phases

duration: 8m
verification_result: passed
completed_at: 2026-03-17
---

# S04: Verificação integrada

**Created a replayable milestone verifier that consolidates S01–S03 into one proof artifact: backend syntax, migration/API structure, override/cache/skip wiring, frontend editor wiring, TypeScript compile, and production build all pass.**

## What Happened

Built `verify-m012.sh` at the repo root as the terminal proof for M012. The script checks all milestone deliverables across 11 grouped phases:

1. `ast.parse` on all 9 backend Python files touched by M012
2. Migration structure (`patient_flow_overrides` + correct `down_revision`)
3. GET merge path with `source: "global" | "override"`
4. PUT save path with Redis invalidation pattern
5. `_get_day_config` override-first lookup and override cache key usage
6. Skip handling in both pipeline surfaces
7. Override immutability via separate table + merge-at-read
8. PatientDetailPage wiring for `PatientFlowOverrideEditor` and `Personalizar Fluxo`
9. Future-day restriction via `current_flow_day`, `editable`, and disabled UI gating
10. `npx tsc --noEmit`
11. `npx vite build`

The script exits non-zero on any failed group and succeeded with 11/11 passing. The run was persisted to `.gsd/milestones/M012/M012-VERIFY.json`, giving the milestone a stable audit artifact instead of ephemeral terminal output.

## Verification

- `bash verify-m012.sh` → ✅ exit 0, 11/11 groups passed
- `.gsd/milestones/M012/M012-VERIFY.json` exists and records all phases with `"status": "passed"`
- Frontend closure confirmed by `npx tsc --noEmit` and `npx vite build`
- Backend closure confirmed by `ast.parse` plus structure checks for migration, API, cache invalidation, override-first lookup, and skip logic

## Requirements Advanced

- none

## Requirements Validated

- R104 — override persistence table structure verified in migration and model proof chain
- R105 — merged GET + saving PUT path verified in schema/router/verifier checks
- R108 — PatientDetailPage override editor wiring and future-day gating verified
- R109 — fixed override immutability verified via separate table + merge-at-read

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- No functional deviations. Verification stayed structural/build-based rather than live-runtime because the slice plan explicitly scoped S04 to replayable static proof.

## Known Limitations

- The verifier proves assembled structure and build health, not live HTTP request replay against a running stack.
- JSON audit captures phase summaries but not raw command stdout for every group.

## Follow-ups

- none — this is the terminal slice for M012

## Files Created/Modified

- `verify-m012.sh` — replayable milestone verifier with 11 grouped checks and non-zero failure exit
- `.gsd/milestones/M012/M012-VERIFY.json` — phase-level audit artifact for the verification run

## Forward Intelligence

### What the next unit should know
- `verify-m012.sh` is the canonical re-entry point if any M012 regression is suspected.
- The script covers S01 persistence/API, S02 pipeline/cache/skip, and S03 frontend editor/build proof in one place.

### What's fragile
- The verifier relies on structural patterns (`grep` + `ast.parse`) rather than runtime requests, so contract drift that preserves those patterns could still require deeper replay later.
- Frontend build module counts may drift slightly over time; success should be judged by exit code, not exact transformed-module totals.

### Authoritative diagnostics
- `bash verify-m012.sh`
- `.gsd/milestones/M012/M012-VERIFY.json`

### What assumptions changed
- No assumptions changed. The slice closed exactly as planned: verification-only, terminal, replayable.
