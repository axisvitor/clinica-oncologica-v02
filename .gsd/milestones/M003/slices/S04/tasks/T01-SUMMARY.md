---
id: T01
parent: S04
milestone: M003
provides:
  - Deleted the dead frontend compatibility alias/type/hook files, migrated the last test-only compat import to canonical shared/transport owners, and added a contract test that turns file resurrection or legacy-import drift into named failures.
key_files:
  - frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts
  - frontend-hormonia/tests/unit/types-validation.test.ts
  - frontend-hormonia/src/lib/api.ts
  - frontend-hormonia/src/lib/types/api.ts
  - frontend-hormonia/src/hooks/use-quiz-session.ts
key_decisions:
  - The cleanup boundary is now pinned by a negative contract: the deleted compat files must stay absent, while `tests/unit/types-validation.test.ts` validates canonical ownership through `src/lib/api-client/types` and `src/types/shared` instead of keeping the legacy barrel alive for tests.
patterns_established:
  - When a compat surface is proven dead, migrate the last proof import to the canonical owner first, then delete the files outright and add a contract test that fails on resurrection instead of preserving a tombstone shim.
observability_surfaces:
  - `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts`, the focused frontend Vitest proof pack, `npm run typecheck`, and `npm run build`.
duration: 40m
verification_result: passed
completed_at: 2026-03-13T11:43:30-03:00
blocker_discovered: false
---

# T01: Delete dead frontend compatibility files and pin the new boundary

**Deleted the dead frontend compat files, moved the last type-validation proof to canonical owners, and added a contract test that catches resurrection or legacy-import drift immediately.**

## What Happened

I added `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` as the new boundary proof for S04. It asserts that `src/lib/api.ts`, `src/lib/types/api.ts`, and `src/hooks/use-quiz-session.ts` stay deleted and that `tests/unit/types-validation.test.ts` no longer imports the legacy compat barrel.

I then rewrote `frontend-hormonia/tests/unit/types-validation.test.ts` so it validates the same core app/transport/realtime shapes through canonical owners instead of `src/lib/types/api.ts`. The migrated proof now uses `src/lib/api-client/types` for transport DTO coverage and `src/types/shared` for the shared response/error shapes that previously came from the compat layer.

With the last test-only dependency removed, I deleted `frontend-hormonia/src/lib/api.ts`, `frontend-hormonia/src/lib/types/api.ts`, and `frontend-hormonia/src/hooks/use-quiz-session.ts` outright without leaving aliases or tombstones behind.

## Verification

Passed:
- `cd frontend-hormonia && npm run test -- tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts tests/unit/types-validation.test.ts tests/monthly-quiz/useMonthlyQuiz.spec.tsx tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- `cd frontend-hormonia && npm run typecheck && npm run build`

Slice-level checks also run for status tracking:
- Failed: `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py`
  - current red state is outside T01 scope: `tests/services/websocket/test_connection_manager.py` still patches `app.services.websocket.connection_manager.verify_firebase_token`, which no longer exists
- Failed: `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`
  - current red state is expected until later slice work updates verifier/manifests: the script still references `frontend-hormonia/src/lib/types/api.ts`, which T01 deleted by design

## Diagnostics

- Re-run `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` to detect deleted-file resurrection or a reintroduced `lib/types/api` import in the focused proof.
- Re-run the focused frontend Vitest command from the task plan to inspect auth/client/realtime/monthly-quiz behavior after the cleanup.
- Use `npm run typecheck` and `npm run build` in `frontend-hormonia/` to confirm the deletion remains compile- and build-safe.

## Deviations

- None.

## Known Issues

- The backend websocket connection-manager proof still expects a patchable `verify_firebase_token` symbol and remains red until T02 narrows the backend auth dependency surface/tests.
- The slice evidence-map verifier still points at the deleted frontend compat file and remains red until the later S04 documentation/verifier cleanup lands.

## Files Created/Modified

- `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` — added the executable boundary proof that the dead compat files stay deleted and the focused type-validation proof stays off the legacy barrel.
- `frontend-hormonia/tests/unit/types-validation.test.ts` — migrated the last test-only compat import to canonical transport/shared owners while preserving the core type-shape assertions.
- `frontend-hormonia/src/lib/api.ts` — deleted the dead API alias file.
- `frontend-hormonia/src/lib/types/api.ts` — deleted the dead compat type barrel.
- `frontend-hormonia/src/hooks/use-quiz-session.ts` — deleted the dead legacy quiz-session hook.
