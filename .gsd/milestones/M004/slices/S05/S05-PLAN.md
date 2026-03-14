# S05: Resíduo funcional de Firebase removido do runtime adjacente

**Goal:** Remove the remaining live Firebase semantics from the adjacent runtime so auth/session cache identity, audit/admin/docs output, and adjacent type surfaces align with the canonical cookie-backed contract without drifting into schema or migration cleanup.
**Demo:** The auth dependency files compile cleanly, Redis-backed session/cache/login/websocket flows no longer serialize or resolve staff identity through `firebase_uid`, audit/admin/docs surfaces expose only the canonical session contract, adjacent frontend types build without Firebase-shaped runtime fields, and the S01 residue guard/handoff reflect the reduced boundary honestly.

## Must-Haves

- The committed merge markers and syntax breakage in the auth dependency surface are removed before semantic proof runs.
- The live session/cache seam (`auth_session_cache.py`, `session_cache.py`, shared helpers, login payload writers) stops keying, listing, invalidating, or rehydrating staff sessions through `firebase_uid` in the official runtime path.
- Shared runtime adapters and websocket-adjacent consumers stop persisting `firebase_uid` as live session/cache metadata unless a passive schema passthrough is unavoidably retained outside the happy path.
- Audit/admin/docs runtime-adjacent surfaces stop reading, modeling, or advertising Firebase auth/session semantics as part of the official system.
- Adjacent frontend type/narrative surfaces stop treating Firebase as a live auth provider or canonical user field.
- The S01 residue verifier and handoff artifacts are republished so the post-S05 boundary is executable and honest.
- Active requirements advanced by this slice: R047 (owned), R049 (supported).

## Proof Level

- This slice proves: contract
- Real runtime required: no
- Human/UAT required: no

## Verification

- `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`
- `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py`
- `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts`
- `cd frontend-hormonia && npm run build`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`

## Observability / Diagnostics

- Runtime signals: auth dependency syntax stays py-compile clean, session payload/unit proof distinguishes canonical `user_id` storage from stale `firebase_uid` metadata, audit/admin/docs proof exposes canonical session fields and operator guidance, and the S01 residue report shows any surviving approved hotspots by category.
- Inspection surfaces: the focused pytest packs above, the frontend type/build checks, and `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all` for the live residue inventory.
- Failure visibility: the proof must tell us whether a regression is in core Redis session identity, shared login/websocket payload writing, audit/admin/docs serialization, or adjacent frontend type drift instead of collapsing everything into one grep failure.
- Redaction constraints: do not log or assert on real credentials, cookies, or PHI; diagnostics may expose stable error codes, synthetic session identifiers, canonical user IDs, and redacted audit metadata only.

## Integration Closure

- Upstream surfaces consumed: the S02 canonical helper seams, the S04 cookie-only auth/session contract, `backend-hormonia/app/core/redis_manager/session_cache.py`, `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/api/v2/user_cache_shared.py`, `backend-hormonia/app/services/audit/audit_service.py`, `backend-hormonia/app/api/v2/routers/docs/data_providers.py`, and the adjacent frontend type surfaces under `frontend-hormonia/src/types/**`.
- New wiring introduced in this slice: one canonical `user_id`-only session/cache payload path reused by Redis session storage, shared auth/cache adapters, login-written payloads, audit/admin serializers, and routed operator docs/type surfaces.
- What remains before the milestone is truly usable end-to-end: S06 still owns the assembled no-Firebase stack proof, and M005 still owns schema/migration cleanup for Firebase columns, enums, and historical structural residue.

## Tasks

- [x] **T01: Restore auth dependency hygiene and canonicalize the core Redis session contract** `est:1h15m`
  - Why: The merge-marker blocker makes every later assertion suspect, and the deepest remaining runtime dependency still lives in the main auth-session helper plus Redis session cache contract.
  - Files: `backend-hormonia/app/dependencies/auth_session_contract.py`, `backend-hormonia/app/dependencies/auth_session_cache.py`, `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/__init__.py`, `backend-hormonia/app/core/redis_manager/session_cache.py`, `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py`, `backend-hormonia/tests/unit/test_session_cache.py`
  - Do: Remove committed merge markers while preserving the S04 cookie-only transport contract; then narrow session creation, rehydration, listing, and bulk invalidation in the core Redis/session helper seam to canonical `id` / `user_id`, keeping any leftover `firebase_uid` strictly out of the live identity pivot.
  - Verify: `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py && cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py`
  - Done when: the dependency files compile cleanly and the core Redis session contract no longer needs `firebase_uid` to store, read, or bulk-invalidate staff sessions.
- [x] **T02: Remove `firebase_uid` from shared auth/cache adapters and login-written session payloads** `est:1h15m`
  - Why: S02 fixed lookup priority, but shared helpers, login payload writers, and adapter seams still keep Firebase alive in runtime metadata that adjacent consumers inherit.
  - Files: `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/api/v2/user_cache_shared.py`, `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/dependencies/auth_user_adapter.py`, `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py`, `backend-hormonia/tests/api/v2/test_auth_local_login.py`, `backend-hormonia/tests/api/test_websocket_session_auth_contract.py`
  - Do: Stop serializing `firebase_uid` into session/cache payloads from local login and shared user adapters, align shared helper rehydration and websocket-adjacent cache usage to canonical `user_id` payloads only, and preserve the S04 cookie-only transport plus stable websocket auth diagnostics while doing it.
  - Verify: `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`
  - Done when: canonical login, restore, and websocket proof passes without `firebase_uid` being written or required in live session/cache payloads.
- [x] **T03: Converge audit, admin, and operator docs surfaces on the canonical runtime** `est:1h15m`
  - Why: After the core auth cleanup, Firebase still survives in audit context, admin serializers, and live operator docs guidance; that keeps R047 false even if login itself is clean.
  - Files: `backend-hormonia/app/middleware/hipaa_audit_middleware.py`, `backend-hormonia/app/services/audit/audit_service.py`, `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py`, `backend-hormonia/app/schemas/v2/admin_extensions.py`, `backend-hormonia/app/api/v2/routers/docs/data_providers.py`, `backend-hormonia/tests/services/audit/test_audit_service.py`, `backend-hormonia/tests/api/v2/test_admin_extensions.py`, `backend-hormonia/tests/api/v2/test_docs.py`
  - Do: Remove runtime reads/writes of `request.state.firebase_uid` and Firebase-shaped audit/admin serialization where canonical `user_id` already exists; update routed docs guidance from Firebase/`X-Session-ID` language to cookie-backed session semantics; and prove that audit output, admin audit responses, and docs examples now describe the post-S04 contract without touching M005 schema/migration debt.
  - Verify: `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py`
  - Done when: audit/admin/docs proof passes with canonical `user_id`-first runtime semantics and no official operator guidance still treating Firebase or `X-Session-ID` as live.
- [x] **T04: Remove Firebase-shaped adjacent frontend type residue** `est:45m`
  - Why: The official frontend runtime is already clean, but shared user/RBAC/medico types still describe Firebase as live and can reintroduce drift through imports or stale narrative.
  - Files: `frontend-hormonia/src/types/api.ts`, `frontend-hormonia/src/types/rbac.ts`, `frontend-hormonia/src/types/medico.ts`, `frontend-hormonia/src/lib/api-client/__tests__/normalizers.test.ts`, `frontend-hormonia/tests/unit/types/admin-types.test.ts`, `frontend-hormonia/tests/unit/types/type-consistency.test.ts`
  - Do: Narrow adjacent frontend/shared types so canonical user/session surfaces no longer expose `firebase_uid` or `AuthProvider.FIREBASE` as official runtime semantics; rewrite lingering Firebase-claims narrative in medico/RBAC types without breaking current imports or the S03-normalized user shape.
  - Verify: `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts && npm run build`
  - Done when: type-focused proof and the production build pass with adjacent frontend auth/user types free of Firebase-shaped canonical residue.
- [x] **T05: Republish the post-S05 residue boundary and slice handoff** `est:45m`
  - Why: S05 is only durable if the verifier and handoff artifacts describe the new backend/frontend boundary honestly; S01 will not infer docs/type cleanup or reduced approved hotspots on its own.
  - Files: `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`, `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`, `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md`, `.gsd/milestones/M004/slices/S01/S01-UAT.md`
  - Do: Rerun the residue report after T01–T04, remove or relabel approved Firebase hotspots that no longer belong in the runtime boundary, and republish the S01 handoff narrative so the verifier story matches the focused S05 proof while clearly leaving schema/migration debt to M005 and assembled-stack proof to S06.
  - Verify: `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
  - Done when: the S01 report/check are green with no stale approved hotspots and the handoff artifacts explicitly describe the post-S05 residue boundary.

## Files Likely Touched

- `backend-hormonia/app/dependencies/auth_session_contract.py`
- `backend-hormonia/app/dependencies/auth_session_cache.py`
- `backend-hormonia/app/dependencies/auth_dependencies.py`
- `backend-hormonia/app/dependencies/__init__.py`
- `backend-hormonia/app/core/redis_manager/session_cache.py`
- `backend-hormonia/app/api/v2/auth_session_shared.py`
- `backend-hormonia/app/api/v2/user_cache_shared.py`
- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/app/dependencies/auth_user_adapter.py`
- `backend-hormonia/app/middleware/hipaa_audit_middleware.py`
- `backend-hormonia/app/services/audit/audit_service.py`
- `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py`
- `backend-hormonia/app/schemas/v2/admin_extensions.py`
- `backend-hormonia/app/api/v2/routers/docs/data_providers.py`
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py`
- `backend-hormonia/tests/unit/test_session_cache.py`
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py`
- `backend-hormonia/tests/api/v2/test_auth_local_login.py`
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py`
- `backend-hormonia/tests/services/audit/test_audit_service.py`
- `backend-hormonia/tests/api/v2/test_admin_extensions.py`
- `backend-hormonia/tests/api/v2/test_docs.py`
- `frontend-hormonia/src/types/api.ts`
- `frontend-hormonia/src/types/rbac.ts`
- `frontend-hormonia/src/types/medico.ts`
- `frontend-hormonia/src/lib/api-client/__tests__/normalizers.test.ts`
- `frontend-hormonia/tests/unit/types/admin-types.test.ts`
- `frontend-hormonia/tests/unit/types/type-consistency.test.ts`
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md`
- `.gsd/milestones/M004/slices/S01/S01-UAT.md`
