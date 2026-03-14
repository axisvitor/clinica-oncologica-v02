# S05: Resíduo funcional de Firebase removido do runtime adjacente — UAT

**Milestone:** M004
**Written:** 2026-03-14T18:46:45-03:00

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S05 proves a contract cleanup across backend runtime-adjacent seams, adjacent frontend type surfaces, and the residue verifier boundary. The slice definition is satisfied by focused pytest/vitest/build/verifier replay rather than by manual browser work or a live assembled stack.

## Preconditions

- The repo is at the S05 tip on branch `gsd/M004/S05`.
- Backend dependencies are installed in `backend-hormonia/`.
- Frontend dependencies are installed in `frontend-hormonia/`.
- No local backend/frontend server needs to be running for this slice replay.
- Commands are run from the repo root unless a case says otherwise.

## Smoke Test

Run:

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`

Expected: the command ends with `RESULT: --check all OK`; the backend output lists only the reduced approved categories/files for passive `firebase_uid` compatibility or rejection bookkeeping, and `[frontend]` reports `no approved residue`.

## Test Cases

### 1. Core auth/session/cache identity stays on canonical `user_id`

1. Run:
   - `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py`
   - `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`
2. Inspect the output.
3. **Expected:** all commands pass. The dependency seam compiles cleanly, Redis session creation/listing/invalidation uses canonical `user_id`, shared restore/login/websocket-adjacent proof no longer requires or emits `firebase_uid`, `firebase_uid`-only session payloads are rejected, and websocket diagnostics stay on the pinned cookie-only contract.

### 2. Audit, admin, and routed docs stop advertising Firebase-era runtime semantics

1. Run:
   - `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py`
2. Inspect the output.
3. **Expected:** all tests pass. Audit extraction/persistence refreshes canonical `user_id` / `session_id`, admin audit responses and exports omit `firebase_uid` from top-level output and nested metadata, and routed docs/examples describe cookie-backed session handling instead of Firebase or `X-Session-ID` guidance.

### 3. Adjacent frontend type surfaces stay session-first and build cleanly

1. Run:
   - `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts`
   - `cd frontend-hormonia && npm run build`
2. Inspect the output.
3. **Expected:** the type-focused vitest pack passes and the production build completes. Canonical frontend user types no longer expose `firebase_uid`, RBAC/admin barrels no longer export provider-era enums, medico validation helpers use generic session/user context wording, and no stale import path breaks the build.

### 4. The published residue boundary matches the cleaned post-S05 runtime

1. Run:
   - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
   - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
2. Inspect both outputs.
3. **Expected:** both commands pass. The backend report/check should list only the surviving approved categories/files (`firebase_uid`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`) in their reduced post-S05 scopes, and the frontend section should still report no approved residue.

## Edge Cases

### `firebase_uid`-only runtime payloads must fail instead of silently rehydrating a session

1. Run the Case 1 backend pytest pack.
2. **Expected:** the shared auth/session proof still rejects `firebase_uid`-only payloads before any cache/DB fallback revives them as canonical runtime identity.

### Stale cached user payloads must be sanitized before they are emitted back to callers

1. Run the Case 1 backend pytest pack.
2. **Expected:** shared restore/login/websocket-adjacent tests still prove that stale cached payloads lose `firebase_uid` before they are returned as runtime auth state.

### Audit/admin exports must strip Firebase identity even when metadata still contains it historically

1. Run the Case 2 backend pytest pack.
2. **Expected:** focused audit/admin tests still prove that top-level output and nested `event_metadata` drop `firebase_uid`, rather than merely hiding it in one serializer layer.

### Frontend residue must stay at zero even if backend approved hotspots remain

1. Run the Case 4 verifier commands.
2. **Expected:** `[frontend]` continues to report `no approved residue`. Any new frontend hit is an immediate regression, even though the backend still has approved compatibility/rejection bookkeeping after S05.

## Failure Signals

- `py_compile` fails or backend auth/cache tests mention merge markers, `firebase_uid` in canonical session payloads, missing `user_id`, or reopened websocket/query/header transport behavior.
- Audit/admin/docs tests fail with `firebase_uid` appearing in runtime metadata/output, routed docs/examples mentioning Firebase or `X-Session-ID`, or missing canonical cookie/session guidance.
- Frontend vitest/build fails with `AuthProvider`, `firebase_uid`, or provider-era medico/RBAC types resurfacing in canonical barrels.
- `verify-runtime-residue.sh --report all` or `--check all` shows cleaned hotspots such as shared auth/cache/login/auth-user-adapter files returning to the allowlist, or any frontend residue reappearing.

## Requirements Proved By This UAT

- R049 — Confirms that runtime identity/cache/session and adjacent official surfaces now resolve through canonical `id` / `user_id` semantics rather than `firebase_uid`.
- R047 — Supports the broader no-Firebase runtime goal by proving the adjacent runtime no longer treats Firebase as part of the canonical auth/session/audit/docs/frontend story.

## Not Proven By This UAT

- Assembled local stack proof with Firebase Auth envs blank across `/login`, `/dashboard`, `/admin`, and `/whatsapp`; that belongs to S06.
- Physical schema/model/Alembic cleanup for Firebase-era fields and migrations; that belongs to M005.
- Final repo-wide dead-code purge beyond the scoped runtime-adjacent Firebase cleanup; that belongs to later work.

## Notes for Tester

- Backend pytest runs still emit the existing `pytest_asyncio` loop-scope deprecation warning. It is known and non-blocking for S05.
- A green verifier run after S05 is expected to keep listing a small approved backend residue set. Those hits are now passive compatibility/rejection bookkeeping only; cleaned shared-auth/Redis/auth-user-adapter hotspots should not come back.
- If a failure appears only in `verify-runtime-residue.sh --check all`, compare it against the focused proof packs before changing the allowlist. The guard should follow verified boundary changes, not mask them.
