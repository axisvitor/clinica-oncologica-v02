---
id: S04
parent: M003
milestone: M003
provides:
  - Removed the strongest proven-dead frontend compatibility residue, pinned the already-pruned backend auth dependency surface with negative contract coverage, and published an explicit manifest for the compatibility islands that remain live.
requires:
  - slice: S02
    provides: Narrowed backend auth/session seams and focused session-first backend verification.
  - slice: S03
    provides: Narrowed frontend api-client/type seams and focused session-first frontend verification.
affects:
  - S05
  - frontend-hormonia
  - backend-hormonia
key_files:
  - .gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md
  - .gsd/milestones/M003/slices/S04/S04-SUMMARY.md
  - .gsd/milestones/M003/slices/S04/S04-UAT.md
  - .gsd/milestones/M003/slices/S01/verify-evidence-map.sh
  - frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts
  - backend-hormonia/tests/unit/test_auth_dependency_module_split.py
key_decisions:
  - Delete proven-dead frontend compat files outright after migrating the last test-only import, and pin the absence with a negative contract test instead of leaving tombstones.
  - Do not reintroduce removed backend auth wrappers for stale test compatibility; current-contract tests must assert export absence and explicit rejection of legacy websocket auth modes.
  - Treat the S01 evidence-map verifier as a living gate whose bookkeeping must move with intentional deletions.
patterns_established:
  - Close cleanup work with an explicit deleted-vs-retained manifest so future slices inherit a concrete boundary instead of rediscovering what is still live.
  - When runtime code is already pruned, convert stale tests into negative contract coverage rather than rebuilding obsolete compatibility shims.
observability_surfaces:
  - .gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md
  - frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts
  - backend-hormonia/tests/unit/test_auth_dependency_module_split.py
  - backend-hormonia/tests/services/websocket/test_connection_manager.py
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all
drill_down_paths:
  - .gsd/milestones/M003/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S04/tasks/T03-SUMMARY.md
duration: 2h50m across 3 tasks
verification_result: passed
completed_at: 2026-03-13T12:28:07-03:00
---

# S04: Dead-Code And Obsolete-Compatibility Cleanup

**S04 removed the strongest proven-dead compatibility residue, locked the narrowed backend auth surface in place with executable negative contracts, and closed with a manifest-backed proof gate for what still remains legacy-only.**

## What Happened

T01 removed the three strongest frontend dead-code candidates after migrating the last proof-only import onto canonical owners:
- `frontend-hormonia/src/lib/api.ts`
- `frontend-hormonia/src/lib/types/api.ts`
- `frontend-hormonia/src/hooks/use-quiz-session.ts`

That deletion was pinned by `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts`, which now fails on file resurrection or if focused proof drifts back toward the deleted type barrel.

T02 confirmed the backend runtime was already in the desired pruned state and fixed the real blocker: stale proof that still behaved as if removed Firebase/websocket helpers should exist. The slice kept `verify_firebase_token`, `get_doctor_user`, and `get_current_user_websocket` off the public auth dependency surface, turned split-contract tests into explicit absence checks, and rewrote websocket manager coverage so the current contract accepts only `jwt` / `session` while rejecting retired `firebase` / `auto` modes.

T03 converted that cleanup into a durable handoff. It published `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md`, refreshed the missing slice-close artifacts, updated the S01 evidence-map verifier and anchored metrics so intentional deletions register as zero-line tracked surfaces instead of stale failures, and reran the slice proof pack on the post-cleanup repo state.

The resulting cleanup boundary is now explicit:
- **Deleted:** the dead frontend alias/type/hook files and the already-pruned backend auth export residue.
- **Retained on purpose:** `backend-hormonia/app/routers/auth_session.py`, `firebase_uid` fallback behavior, and bearer-token fallback behavior.

## Verification

Passed on final rerun:
- `cd frontend-hormonia && npm run test -- tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts tests/unit/types-validation.test.ts tests/monthly-quiz/useMonthlyQuiz.spec.tsx`
  - 3 files / 21 tests green
- `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
  - 4 files / 43 tests green
- `cd frontend-hormonia && npm run typecheck && npm run build`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`
  - ended with `RESULT: --report all OK`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`
  - ended with `RESULT: --check all OK`
- manifest coverage script from the slice plan
  - printed `manifest covers removed residue and retained compatibility islands`

Observed non-blocking diagnostics during verification:
- frontend integration suites still emit the existing Node warning about `--localstorage-file` lacking a valid path
- backend pytest still emits the existing `pytest_asyncio` fixture loop-scope deprecation warning

## Requirements Advanced

- R034 — preserved the S02/S03 hotspot-size win by deleting dead residue instead of letting compatibility scaffolding regrow around the new seams.
- R037 — kept auth/client/quiz/websocket visible behavior stable while narrowing the internal cleanup surface through focused proof.
- R038 — left a clearer canonical-vs-legacy ownership map through the manifest, negative contract tests, and retained-island documentation.
- R039 — closed the slice on focused frontend/backend verification plus the living evidence-map gate rather than on structural diffs alone.

## Requirements Validated

- R035 — S01’s evidence map and S04’s deletions, manifest, and green proof pack demonstrate that dead-code removal stayed evidence-based instead of taste-based.
- R036 — proven-dead compatibility files/exports were removed and the still-live compatibility islands were explicitly isolated away from the main runtime path.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- Updated `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` and the anchored metrics in `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` even though T03 nominally targeted S04 artifacts; the slice gate had to reflect post-cleanup deletions instead of failing on stale bookkeeping.
- Aligned `backend-hormonia/tests/validation/test_vulnerability_scenarios.py` with the tombstoned Firebase verify route so a latent stale patch would not re-break later broader verification.

## Known Limitations

- `backend-hormonia/app/routers/auth_session.py`, `firebase_uid`, and bearer-token fallback behavior are still live compatibility islands; S04 documents and bounds them, but does not remove them.
- S05 still needs the assembled cross-surface smoke for backend/frontend/dashboard/admin continuity after S02–S04.
- The existing Node `--localstorage-file` warning and `pytest_asyncio` deprecation warning remain non-blocking but unresolved.

## Follow-ups

- Use `S04-CLEANUP-MANIFEST.md` as the primary checklist for S05 integrated proof.
- If a future slice wants to remove `auth_session.py`, `firebase_uid`, or bearer-token fallback behavior, it must replace the retained-island rationale with new proof instead of assuming those paths are already dead.

## Files Created/Modified

- `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` — added the executable boundary that fails on deleted-file resurrection or legacy type-barrel drift.
- `frontend-hormonia/tests/unit/types-validation.test.ts` — moved the last test-only compat import onto canonical owners.
- `frontend-hormonia/src/lib/api.ts` — deleted the dead API alias file.
- `frontend-hormonia/src/lib/types/api.ts` — deleted the dead compat type barrel.
- `frontend-hormonia/src/hooks/use-quiz-session.ts` — deleted the dead legacy quiz-session hook.
- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` — pinned the narrowed auth dependency surface with negative contract checks.
- `backend-hormonia/tests/services/websocket/test_connection_manager.py` — updated websocket proof to accept `jwt` / `session` and reject `firebase` / `auto`.
- `backend-hormonia/tests/validation/test_vulnerability_scenarios.py` — aligned the stale Firebase verify expectation with the tombstoned route.
- `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md` — published the deleted-vs-retained cleanup ledger and recorded the exact proof commands.
- `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` — taught the verifier to treat deleted tracked files as zero-line surfaces.
- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` — synced anchored counts so the living verifier matches the post-S04 repo.
- `.gsd/milestones/M003/slices/S04/S04-SUMMARY.md` — compressed the task results into the slice handoff.
- `.gsd/milestones/M003/slices/S04/S04-UAT.md` — published the slice-close regression/UAT checklist.

## Forward Intelligence

### What the next slice should know
- `S04-CLEANUP-MANIFEST.md` is the authoritative deleted-vs-retained boundary for M003; use it as the starting checklist for any integrated smoke or future cleanup.

### What's fragile
- `backend-hormonia/app/routers/auth_session.py`, `firebase_uid`, and bearer-token fallback behavior — they are intentionally retained but still easy to misclassify as dead if someone reasons only from the main session-first happy path.

### Authoritative diagnostics
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all` and `--check all` — they now reflect post-cleanup reality and are the fastest way to detect deleted-file resurrection or bookkeeping drift.
- `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` and `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` — these are the sharpest contract checks for the cleanup boundary itself.

### What assumptions changed
- We assumed S04 still needed runtime-side backend wrapper deletions; in practice the runtime was already pruned and the real remaining work was stale proof plus stale verifier bookkeeping.
