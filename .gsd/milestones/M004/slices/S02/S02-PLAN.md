# S02: Backend auth/sessão convergido para identidade canônica

**Goal:** Converge the backend auth/session substrate on one canonical `user_id`-first identity contract so login, verify-session, restore, logout, and adjacent official-runtime helpers no longer depend on `firebase_uid` in the happy path.
**Demo:** Focused backend proof passes while `backend-hormonia/app/dependencies/auth_session_cache.py`, `auth_session_contract.py`, `auth_session_shared.py`, `user_cache_shared.py`, and the public auth dependency surface all resolve canonical session identity through `id` / `user_id` first, keep request-state side effects stable, and leave `firebase_uid` only as an explicit compatibility fallback when canonical IDs are absent.

## Requirement Coverage

- Owned by this slice: **R048** — Auth/sessão converge para um contrato canônico único.
- Owned by this slice: **R049** — A identidade canônica deixa de depender de `firebase_uid` no runtime.
- Supported by this slice: **R047** — Firebase sai de vez do runtime oficial.
- Not claimed here: transport retirement for root `/session/*`, `X-Session-ID`, session-as-Bearer, and websocket query fallback stays for S03/S04; frontend cutover stays for S03.

## Must-Haves

- The canonical backend happy path for login, verify-session, restore, and logout stays on one `user_id`-centric session contract from route handlers through cache hydration, DB fallback, and request-state enrichment.  
  _Advances: R048, R049_
- `backend-hormonia/app/dependencies/auth_session_cache.py`, `auth_session_contract.py`, `auth_session_shared.py`, and `user_cache_shared.py` stop needing `firebase_uid` to resolve authenticated identity on the happy path; `firebase_uid` survives only as an explicit compatibility fallback when canonical IDs are missing.  
  _Advances: R049, supports R047_
- Adjacent official-runtime consumers that still depend on the shared helper family inherit the same canonical identity semantics without silent session-source precedence drift or override breakage.  
  _Advances: R048, R049_
- The slice closes with focused backend proof plus a shrunk S01 backend residue boundary, so later slices inherit an updated map of what legacy transport behavior still remains to be retired.  
  _Advances: R047, R048, R049_

## Proof Level

- This slice proves: integration
- Real runtime required: no
- Human/UAT required: no

## Verification

- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_local_login.py tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/integration/test_local_auth_core_flow.py`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`

## Observability / Diagnostics

- Runtime signals: `request.state.session_id` / `user_id` / `user_role` remain the canonical auth side effects; auth/session failures keep stable 401/403/503 surfaces plus existing safe diagnostics such as `request_id`, `debug_step`, and websocket auth error codes.
- Inspection surfaces: the focused pytest suites above, assertions over Redis/DB session hydration in the new tests, and `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` for the live backend residue map.
- Failure visibility: the proof must distinguish cache-hydration drift, shared-helper drift, request-state/override regressions, websocket/session lookup regressions, and stale residue bookkeeping instead of collapsing them into a generic auth failure.
- Redaction constraints: never log or assert on raw passwords, full session tokens, cookies, or other secret-bearing values; keep diagnostics to synthetic IDs, prefix-only session hints, and user-safe error metadata.

## Integration Closure

- Upstream surfaces consumed: `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/auth_session_contract.py`, `backend-hormonia/app/dependencies/auth_session_cache.py`, `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/api/v2/user_cache_shared.py`, `backend-hormonia/app/api/websockets.py`, `backend-hormonia/tests/api/v2/test_auth_local_login.py`, `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py`, `backend-hormonia/tests/api/v2/test_auth_session_priority.py`, `backend-hormonia/tests/api/test_websocket_session_auth_contract.py`, and `backend-hormonia/tests/integration/test_local_auth_core_flow.py`.
- New wiring introduced in this slice: the canonical and shared helper families converge on one `user_id`-first identity contract while preserving the current transport compatibility seams and request-state side effects.
- What remains before the milestone is truly usable end-to-end: S03 must cut the official frontend over to the canonical session contract, S04 must retire or tombstone the remaining legacy transport surfaces, S05 must remove adjacent Firebase runtime residue, and S06 must replay the assembled no-Firebase stack.

## Tasks

- [x] **T01: Add failing canonical-identity proof for backend auth helpers** `est:1h`
  - Why: The visible `/api/v2/auth/*` routes are already close to the target; the real risk is hidden helper drift, so the slice starts by pinning the helper-layer contract in executable form before code moves.
  - Files: `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py`, `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py`, `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py`
  - Do: Add new unit/API tests that pin canonical embedded-user hydration, DB fallback by `user_id`, mapping-style session payloads, `request.state.session_id` / `user_id` / `user_role`, shared-helper behavior for adjacent V2 consumers, websocket/session lookup expectations, and explicit `firebase_uid` fallback only when canonical IDs are absent; extend the override contract test where needed and run the new proof red-first against the current helper drift.
  - Verify: `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py`
  - Done when: the new tests exist, assert the intended canonical helper contract, and fail for current helper dual-identity behavior rather than fixture/setup noise.
- [x] **T02: Converge session/cache/shared helpers on user_id-first identity** `est:2h`
  - Why: S02 only lands if the canonical and shared helper families stop deriving authenticated identity from `firebase_uid` on the happy path while the route contract and compatibility transports remain stable.
  - Files: `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/auth_session_contract.py`, `backend-hormonia/app/dependencies/auth_session_cache.py`, `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/api/v2/user_cache_shared.py`, `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py`, `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py`
  - Do: Update the canonical and shared helper seams so embedded canonical session data and DB/cache rehydration resolve identity by `id` / `user_id` first, keep mapping-style payloads and request-state enrichment stable, preserve the current accepted session transports and precedence deliberately, and leave `firebase_uid` only as a quarantined compatibility fallback when canonical IDs are missing.
  - Verify: `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py tests/integration/test_local_auth_core_flow.py`
  - Done when: the helper-layer proof and existing backend auth/session/websocket flow suites are green, official-runtime helpers no longer need `firebase_uid` on the happy path, and no transport-precedence or override regression appears.
- [x] **T03: Shrink the backend residue boundary and publish the S02 handoff** `est:1h`
  - Why: S02 is only durable if the S01 backend residue guard shrinks with the code and the slice leaves a precise handoff for S03/S04 about which legacy transport seams still remain on purpose.
  - Files: `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`, `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`, `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md`, `.gsd/milestones/M004/slices/S01/S01-UAT.md`, `.gsd/milestones/M004/slices/S02/S02-SUMMARY.md`, `.gsd/milestones/M004/slices/S02/S02-UAT.md`
  - Do: Re-run the backend residue report after the helper convergence, update the S01 allowlist and handoff artifacts for any removed or moved backend hotspots, then write S02 summary/UAT artifacts that name the converged backend contract, the remaining explicit transport compatibility seams, and the exact proof commands later slices inherit.
  - Verify: `(cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py tests/integration/test_local_auth_core_flow.py) && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
  - Done when: backend `firebase_uid` residue is reduced to explicit compatibility-only hotspots, S01 and S02 artifacts all describe the same remaining boundary, and the focused backend proof pack plus backend residue guard are green.

## Files Likely Touched

- `backend-hormonia/app/dependencies/auth_dependencies.py`
- `backend-hormonia/app/dependencies/auth_session_contract.py`
- `backend-hormonia/app/dependencies/auth_session_cache.py`
- `backend-hormonia/app/api/v2/auth_session_shared.py`
- `backend-hormonia/app/api/v2/user_cache_shared.py`
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py`
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py`
- `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py`
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`
- `.gsd/milestones/M004/slices/S02/S02-SUMMARY.md`
- `.gsd/milestones/M004/slices/S02/S02-UAT.md`
