# S01: Evidence Map And Cleanup Guardrails — UAT

**Milestone:** M003
**Written:** 2026-03-12

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: this slice proves a repo-derived evidence contract and handoff pack, not runtime behavior. The verifier and markdown artifacts are the shipped surface.

## Preconditions

1. Run from the repo root.
2. `bash`, `rg`, `wc`, and `python3` must be available.
3. The slice artifacts must exist: `S01-RESEARCH.md`, `S01-SUMMARY.md`, `S01-UAT.md`, and `verify-evidence-map.sh`.
4. The reviewer should treat `verify-evidence-map.sh --report all` as the first source of truth and the markdown as valid only when the verifier agrees.

## Smoke Test

1. Run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`.
2. Confirm the output lists backend and frontend hotspot metrics plus `handoff.summary.open_scaffold_items=0` and `handoff.uat.open_scaffold_items=0`.
3. Run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`.
4. Confirm the command exits zero and names no missing sections, no drifting anchors, and no open scaffold items.

## Test Cases

### 1. Backend scope evidence

1. Run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report backend`.
2. Run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend`.
3. Read the backend sections in `S01-RESEARCH.md` and `S01-SUMMARY.md`.
4. **Expected:** the report and the markdown agree on hotspot sizes, caller counts, explicit non-candidates, wrapper constraints, and the exact backend verification commands.

### 2. Frontend scope evidence

1. Run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report frontend`.
2. Run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend`.
3. Read the frontend sections in `S01-RESEARCH.md` and `S01-SUMMARY.md`.
4. **Expected:** the report and the markdown agree on façade import counts, duplicate-export counts, legacy alias counts, candidate proof gates, and the distinction between public façades, internal ownership modules, and legacy aliases.

### 3. Slice-close handoff pack

1. Run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`.
2. Run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`.
3. Read `S01-SUMMARY.md` sections `Next Slice Execution Order`, `Backend Handoff`, `Frontend Handoff`, `Deletion Proof Queue`, `Exact Verification Commands`, and `Reviewer Focus`.
4. **Expected:** the slice-close artifacts are complete, contain no scaffold residue, and are sufficient for S02–S05 without reopening repo-wide discovery.

## Edge Cases

### Drifted counts after repo changes

1. Change a tracked hotspot file, import graph, or deletion-candidate reference.
2. Re-run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`.
3. Re-run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`.
4. **Expected:** the report reflects the new counts immediately and `--check` names the drifting file, symbol, or missing section until the markdown is reconciled.

### Missing artifact or heading

1. Remove or rename one of the required sections or files.
2. Re-run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`.
3. **Expected:** the verifier exits non-zero and names the missing file or heading directly.

### Incomplete handoff pack

1. Reintroduce an unchecked scaffold item or delete one of the required command blocks from `S01-SUMMARY.md` or `S01-UAT.md`.
2. Re-run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`.
3. **Expected:** the verifier fails loudly on the open scaffold item or missing command instead of silently accepting a partial handoff.

## Failure Signals

- `verify-evidence-map.sh` exits non-zero because it cannot find `S01-RESEARCH.md`, `S01-SUMMARY.md`, or `S01-UAT.md`.
- The report or check output shows a mismatch for hotspot line counts, caller/import blast radius, duplicate export names, or candidate-reference counts.
- `--check all` reports open scaffold items in the summary/UAT after the slice is claimed complete.
- The summary/UAT omit the exact backend, frontend, or slice-close command pack that downstream slices inherit.
- Output includes anything beyond repo paths, static counts, symbol names, and verification commands.

## Requirements Proved By This UAT

- R035 — cleanup remains evidence-based because the verifier re-derives hotspot and candidate signals from the live repo and fails when the markdown drifts.
- R039 — structural cleanup handoff is strong enough to reuse because the summary/UAT now encode the exact attack order, non-candidates, proof queue, and verification commands.

## Not Proven By This UAT

- Runtime auth behavior, browser UX, or end-to-end flows.
- That any deletion candidate is truly dead; this slice only proves the queued commands needed before deletion.
- That S02–S05 stay green after future refactors; those slices must still run the preserved suites.

## Notes for Tester

Use the verifier first and the prose second. If the report and the markdown disagree, the report wins until the artifact is updated. If a candidate looks dead but the proof queue for that candidate has not been executed yet, treat it as blocked rather than safe to remove.

## Reviewer Checklist

1. Does `S01-SUMMARY.md` keep the execution order as backend contract split, frontend ownership split, deletion proof, then integrated smoke?
2. Do the backend handoff sections still protect the mapping-style session dict contract, the `User` adapter contract, and the request-state side effects?
3. Do the frontend handoff sections still protect `@/lib/api-client` and `@/types/api` while treating `src/lib/api-client/index.ts` and `src/lib/api-client/types.ts` as internal ownership modules and `src/lib/api.ts` / `src/lib/types/api.ts` as proof-blocked legacy aliases?
4. Does every cleanup candidate still name concrete grep plus targeted test plus type/build proof instead of prose-only suspicion?
5. Do the exact commands below still match `S01-RESEARCH.md`, `S01-SUMMARY.md`, and `verify-evidence-map.sh`?

Backend regression commands:
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report backend`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend`
- `cd backend-hormonia && pytest tests/auth/test_session_validation.py tests/auth/test_user_conversion.py tests/api/v2/test_auth_session_priority.py`
- `cd backend-hormonia && pytest tests/auth/test_user_conversion.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py`
- `cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py`
- `cd backend-hormonia && pytest tests/api/v2/test_admin.py tests/api/v2/test_dashboard.py tests/api/test_admin_contracts.py`
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py`

Frontend regression commands:
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report frontend`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend`
- `cd frontend-hormonia && npm run typecheck && npm run test -- tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts`
- `cd frontend-hormonia && npm run test -- tests/integration/auth/session-first-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx`
- `cd frontend-hormonia && npm run test -- tests/integration/admin-auth-flow.test.tsx tests/components/dashboard/QuickStats.test.tsx`

Slice-close commands:
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`
- `cd frontend-hormonia && npx playwright test tests/e2e/auth/login.spec.ts tests/e2e/admin-dashboard-complete.spec.ts tests/e2e/websocket.spec.ts tests/e2e/test_whatsapp_integration_e2e.spec.ts`
