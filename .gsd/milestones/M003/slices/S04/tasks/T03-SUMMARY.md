---
id: T03
parent: S04
milestone: M003
provides:
  - Published the S04 cleanup manifest, created the missing slice handoff artifacts, and closed the slice proof gate with a green evidence-map verifier plus recorded frontend/backend proof results.
key_files:
  - .gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md
  - .gsd/milestones/M003/slices/S04/S04-SUMMARY.md
  - .gsd/milestones/M003/slices/S04/S04-UAT.md
  - .gsd/milestones/M003/slices/S01/verify-evidence-map.sh
  - .gsd/milestones/M003/slices/S01/S01-RESEARCH.md
key_decisions:
  - Treat the S01 evidence-map verifier as a living slice gate and update its bookkeeping when S04 intentionally deletes tracked cleanup candidates.
  - Make `backend-hormonia/app/routers/auth_session.py`, `firebase_uid`, and the bearer-token fallback explicit retained surfaces in the manifest instead of leaving them as ambiguous leftovers.
patterns_established:
  - Final cleanup tasks should ship a deleted-vs-retained manifest plus exact proof commands/results so downstream work inherits a concrete regression checklist rather than reopening discovery.
observability_surfaces:
  - .gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all
  - focused frontend Vitest and backend Pytest cleanup suites
duration: 1h10m
verification_result: passed
completed_at: 2026-03-13T12:16:44-03:00
blocker_discovered: false
---

# T03: Publish the cleanup manifest and close the slice proof gate

**Published the S04 cleanup manifest, created the missing slice handoff pack, and closed the evidence-map gate on the post-cleanup repo state.**

## What Happened

I wrote `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md` as the slice-close ledger for S04. It explicitly separates:
- removed frontend residue (`frontend-hormonia/src/lib/api.ts`, `frontend-hormonia/src/lib/types/api.ts`, `frontend-hormonia/src/hooks/use-quiz-session.ts`),
- removed backend auth residue (`verify_firebase_token`, `get_doctor_user`, `get_current_user_websocket`), and
- retained compatibility islands (`backend-hormonia/app/routers/auth_session.py`, `firebase_uid`, and the bearer-token fallback).

I then wrote the missing slice handoff artifacts `.gsd/milestones/M003/slices/S04/S04-SUMMARY.md` and `.gsd/milestones/M003/slices/S04/S04-UAT.md` so future work can consume the cleanup boundary without rereading the entire slice history.

While closing the gate, I found that `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` still hard-read deleted S04 candidate files and still compared against stale anchored metrics. I updated the verifier to treat deleted tracked files as zero-line surfaces and synced the anchored counts in `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` so `--report all` / `--check all` now reflect the actual post-cleanup repo state instead of crashing on already-deleted files.

Finally, I reran the slice proof pack and recorded the exact command outcomes in the manifest and slice handoff docs.

## Verification

Passed:
- `cd frontend-hormonia && npm run test -- tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts tests/unit/types-validation.test.ts tests/monthly-quiz/useMonthlyQuiz.spec.tsx`
  - 3 files / 21 tests green
- `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
  - 4 files / 43 tests green
- `cd frontend-hormonia && npm run typecheck && npm run build`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`
- `python3 - <<'PY' ...` manifest coverage check from the task plan
  - printed `manifest covers removed residue and retained compatibility islands`

## Diagnostics

- Read `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md` first for the slice-close boundary.
- Re-run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all` for the post-cleanup metrics snapshot.
- Re-run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all` to confirm the living evidence-map gate still matches repo state.
- Re-run the focused frontend/backend proof commands recorded in the manifest to distinguish deleted-file resurrection from retained-island drift.

## Deviations

Updated the S01 evidence-map verifier and its anchored research metrics even though the T03 plan only named S04 artifacts explicitly. This was required to make the slice-level `--check all` proof gate reflect the intentional S04 deletions instead of failing on stale bookkeeping.

## Known Issues

- Frontend integration suites still emit the existing Node warning about `--localstorage-file` lacking a valid path; the focused proof remains green.
- Backend pytest still emits the existing `pytest_asyncio` deprecation warning about `asyncio_default_fixture_loop_scope` being unset.

## Files Created/Modified

- `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md` — published the deleted-vs-retained cleanup ledger, proof commands, and verifier snapshot for downstream reuse.
- `.gsd/milestones/M003/slices/S04/S04-SUMMARY.md` — created the real slice handoff summary for S04.
- `.gsd/milestones/M003/slices/S04/S04-UAT.md` — created the slice-close regression/UAT checklist.
- `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` — updated the verifier so deleted tracked files resolve as zero-line surfaces instead of causing a shell failure.
- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` — synced anchored metrics so the verifier matches the current repo.
- `.gsd/DECISIONS.md` — recorded the living evidence-map gate decision for downstream slices.
- `.gsd/milestones/M003/slices/S04/S04-PLAN.md` — marked T03 complete.
- `.gsd/STATE.md` — advanced state from the in-progress T03 action to the post-S04 handoff state.
