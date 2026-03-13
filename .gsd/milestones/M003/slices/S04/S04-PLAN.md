# S04: Dead-Code And Obsolete-Compatibility Cleanup

**Goal:** Remove the strongest proven-dead frontend and backend compatibility residue left after S02/S03, while explicitly documenting the legacy auth/session islands that are still live so the main runtime path becomes clearer without visible contract drift.
**Demo:** Focused cleanup proof passes while `frontend-hormonia/src/lib/api.ts`, `frontend-hormonia/src/lib/types/api.ts`, and `frontend-hormonia/src/hooks/use-quiz-session.ts` are deleted, `backend-hormonia/app/dependencies/auth_dependencies.py` / `backend-hormonia/app/dependencies/__init__.py` no longer export `verify_firebase_token`, `get_doctor_user`, or `get_current_user_websocket`, and a dedicated S04 manifest records why `backend-hormonia/app/routers/auth_session.py` plus the remaining `firebase_uid` / bearer-token fallbacks stay isolated instead of being deleted.

## Requirement Coverage

- Owned by this slice: **R036** — remove obsolete compatibility layers when deadness is proven, and explicitly isolate the compat islands that are still live.
- Supported by this slice: **R034** — preserve the S02/S03 hotspot-size win by pruning residue instead of letting dead compatibility stay on the new seams.
- Supported by this slice: **R035** — every deletion is tied to the S01/S04 evidence and focused proof, while still-live compat paths are documented instead of guessed dead.
- Supported by this slice: **R037** — keep auth/session/client/quiz visible behavior stable while narrowing the internal cleanup surface.
- Supported by this slice: **R038** — leave a clearer canonical-vs-legacy map for future maintainers.
- Supported by this slice: **R039** — close the cleanup with focused backend/frontend verification plus the evidence-map gate.

## Decomposition Rationale

Start with the frontend deletions because they are the strongest evidence-backed dead paths and the lowest-risk size win. Follow with backend auth export pruning because it touches a more sensitive contract surface, but the remaining work is still narrow and well-covered by the refreshed session-first proof pack. Finish with an explicit cleanup manifest and verifier rerun so S05 inherits a narrowed compatibility map instead of reopening discovery.

## Must-Haves

- The proven-dead frontend alias/type/hook files are deleted after migrating the last test-only compat import, and current auth/client/monthly-quiz proof still passes.
  _Covers: R035, R036, R037_
- The dead backend auth dependency exports and their no-longer-used legacy helper implementations are removed from the public dependency surface without regressing the current session-first auth/websocket/rbac proof.
  _Covers: R035, R036, R037_
- S04 leaves an explicit cleanup manifest that distinguishes removed residue from retained compatibility islands (`auth_session.py`, `firebase_uid` fallback, bearer-token fallback) and ties each decision to proof.
  _Covers: R036, R038, R039_

## Proof Level

- This slice proves: integration
- Real runtime required: no
- Human/UAT required: no

## Verification

- `cd frontend-hormonia && npm run test -- tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts tests/unit/types-validation.test.ts tests/monthly-quiz/useMonthlyQuiz.spec.tsx`
- `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- `cd frontend-hormonia && npm run typecheck && npm run build`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`

## Observability / Diagnostics

- Runtime signals: cleanup regressions surface through named import-boundary contract failures, auth dependency surface tests, session-first auth/websocket/rbac suites, and the evidence-map verifier.
- Inspection surfaces: the focused Vitest/Pytest commands above, `npm run typecheck`, `npm run build`, `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`, and the S04 cleanup manifest.
- Failure visibility: future regressions should identify either a reintroduced deleted file/export, a broken canonical auth/session path, or a legacy-island boundary that drifted without documentation.
- Redaction constraints: keep proof limited to source paths, public export names, and user-safe auth/client diagnostics; do not print secrets, cookies, or patient payloads.

## Integration Closure

- Upstream surfaces consumed: `frontend-hormonia/src/lib/api-client.ts`, `frontend-hormonia/src/lib/api-client/index.ts`, `frontend-hormonia/src/lib/api-client/types.ts`, `frontend-hormonia/src/features/monthly-quiz/hooks/useMonthlyQuiz.ts`, `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/auth_legacy_firebase.py`, `backend-hormonia/app/dependencies/auth_role_dependencies.py`, `backend-hormonia/app/routers/auth_session.py`, and the S01 evidence-map verifier.
- New wiring introduced in this slice: no new runtime entrypoints; the slice narrows imports/exports, deletes dead files, and adds an explicit cleanup manifest for what remains legacy-only.
- What remains before the milestone is truly usable end-to-end: S05 still needs the integrated backend/frontend/dashboard/admin smoke that proves the assembled system still behaves correctly after S02–S04.

## Tasks

- [x] **T01: Delete dead frontend compatibility files and pin the new boundary** `est:1h30m`
  - Why: The frontend candidates are the strongest proven-dead residue in scope, and deleting them first retires real compatibility sludge with the smallest blast radius.
  - Files: `frontend-hormonia/src/lib/api.ts`, `frontend-hormonia/src/lib/types/api.ts`, `frontend-hormonia/src/hooks/use-quiz-session.ts`, `frontend-hormonia/tests/unit/types-validation.test.ts`, `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts`, `frontend-hormonia/tests/monthly-quiz/useMonthlyQuiz.spec.tsx`
  - Do: Add a focused cleanup contract test that makes the deleted compat files and their last test-only import boundary explicit; migrate `tests/unit/types-validation.test.ts` onto canonical types; delete the zero-import alias files and dead quiz hook without replacing them with fresh shims; and rerun the focused frontend auth/client/monthly-quiz proof plus typecheck/build.
  - Verify: `cd frontend-hormonia && npm run test -- tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts tests/unit/types-validation.test.ts tests/monthly-quiz/useMonthlyQuiz.spec.tsx tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts && npm run typecheck && npm run build`
  - Done when: The three proven-dead frontend files are gone, no focused frontend proof still imports the legacy type barrel, and the current auth/client/monthly-quiz verification pack remains green.
- [x] **T02: Prune dead backend auth dependency exports and legacy helper residue** `est:1h40m`
  - Why: The backend public dependency surface still exposes wrappers with no runtime callers, which keeps the auth/session seam blurrier than the post-S02 structure actually is.
  - Files: `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/__init__.py`, `backend-hormonia/app/dependencies/auth_legacy_firebase.py`, `backend-hormonia/tests/unit/test_auth_dependency_module_split.py`, `backend-hormonia/tests/services/websocket/test_connection_manager.py`, `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py`
  - Do: Remove `verify_firebase_token`, `get_doctor_user`, and `get_current_user_websocket` from the public auth dependency/export surface; prune matching dead implementations in `auth_legacy_firebase.py` if no internal callers remain; update the split-contract coverage to assert the narrowed surface; and make any directly-blocking Firebase-era websocket residue explicit (updated or skipped) instead of silently pinning removed symbols as if they were still authoritative runtime behavior.
  - Verify: `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py`
  - Done when: The dead wrappers/helpers are no longer exported from the backend auth dependency surface, stale Firebase-only tests stop blocking symbol removal implicitly, and the focused backend session-first proof pack stays green.
- [x] **T03: Publish the cleanup manifest and close the slice proof gate** `est:50m`
  - Why: S04 is only complete if the deletions and the remaining live compatibility islands are explicit enough that S05 can reuse them as guardrails instead of rediscovering them.
  - Files: `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md`, `.gsd/milestones/M003/slices/S04/S04-SUMMARY.md`, `.gsd/milestones/M003/slices/S04/S04-UAT.md`
  - Do: Write a dedicated cleanup manifest that lists removed frontend residue, removed backend auth residue, and the retained compatibility islands with rationale; record the exact proof commands/results that justify each decision; then rerun the evidence-map verifier and final slice proof so the documentation reflects real post-cleanup state rather than plan-time intent.
  - Verify: `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all && python3 - <<'PY'
from pathlib import Path
manifest = Path('.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md').read_text()
required = [
    'frontend-hormonia/src/lib/api.ts',
    'frontend-hormonia/src/lib/types/api.ts',
    'frontend-hormonia/src/hooks/use-quiz-session.ts',
    'verify_firebase_token',
    'get_doctor_user',
    'get_current_user_websocket',
    'backend-hormonia/app/routers/auth_session.py',
    'firebase_uid',
    'bearer-token fallback',
]
missing = [item for item in required if item not in manifest]
if missing:
    raise SystemExit(f'manifest missing required cleanup entries: {missing}')
print('manifest covers removed residue and retained compatibility islands')
PY`
  - Done when: The manifest/summary/UAT artifacts clearly distinguish deleted vs retained compatibility surfaces, the verifier is green against the post-cleanup repo state, and S05 can consume the resulting checklist without reopening scope.

## Files Likely Touched

- `frontend-hormonia/src/lib/api.ts`
- `frontend-hormonia/src/lib/types/api.ts`
- `frontend-hormonia/src/hooks/use-quiz-session.ts`
- `frontend-hormonia/tests/unit/types-validation.test.ts`
- `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts`
- `backend-hormonia/app/dependencies/auth_dependencies.py`
- `backend-hormonia/app/dependencies/__init__.py`
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py`
- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py`
- `backend-hormonia/tests/services/websocket/test_connection_manager.py`
- `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md`
- `.gsd/milestones/M003/slices/S04/S04-SUMMARY.md`
- `.gsd/milestones/M003/slices/S04/S04-UAT.md`
