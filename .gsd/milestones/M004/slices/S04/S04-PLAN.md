# S04: Superfícies legadas de auth/sessão aposentadas

**Goal:** Retire the remaining backend-owned legacy auth/session transport from the official runtime so staff auth/session flows are cookie-backed only, `/session/*` is intentionally dead, and the residue guard matches that tighter boundary.
**Demo:** The backend official auth/session path rejects `X-Session-ID`, `Authorization: Bearer <session_id>`, websocket `session_id` query fallback, and root `/session/*` while canonical cookie-backed login/verify/logout/restore behavior still passes under focused and acceptance proof.

## Must-Haves

- The two live resolver stacks (`auth_session_contract.py` and `auth_session_shared.py`) stop accepting `X-Session-ID`, session-as-Bearer, and websocket query `session_id` as official staff session transport.
- Canonical `/api/v2/auth/*` and websocket auth keep the cookie-backed session contract working without reviving legacy debug headers or transport fallbacks.
- Remaining in-scope backend helper/consumer surfaces that still require or advertise `X-Session-ID`/Bearer session transport are migrated to the canonical dependency surface or explicitly rejected.
- Root `/session/*` is retired intentionally with explicit tombstone/rejection behavior, not by accidental 404 drift.
- The S01 residue verifier and its handoff artifacts are republished so the post-S04 backend boundary is executable and honest.
- Active requirements advanced by this slice: R047, R048, R049.

## Proof Level

- This slice proves: contract
- Real runtime required: no
- Human/UAT required: no

## Verification

- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_localization.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`

## Observability / Diagnostics

- Runtime signals: explicit 401/410 rejection bodies for retired auth/session transport, stable websocket auth error codes `AUTH_WEBSOCKET_SESSION_INVALID` and `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED`, and unchanged canonical `request.state.session_id` / `user_id` side effects on cookie-backed flows.
- Inspection surfaces: the focused pytest files above plus `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` for the live residue inventory.
- Failure visibility: focused tests must distinguish “canonical cookie flow still works” from “legacy transport is now rejected,” and `/session/*` retirement must expose a deterministic tombstone/rejection status instead of a generic missing-route failure.
- Redaction constraints: do not log or assert on raw secret material; auth diagnostics may expose stable error codes, request-scoped state, and synthetic session identifiers only.

## Integration Closure

- Upstream surfaces consumed: `backend-hormonia/app/dependencies/auth_session_contract.py`, `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/api/websockets.py`, `backend-hormonia/app/api/v2/routers/localization.py`, helper dependencies under `backend-hormonia/app/api/v2/**`, and the S01 residue guard.
- New wiring introduced in this slice: central retirement wiring for root `/session/*` plus cookie-only dependency usage across remaining in-scope backend helper surfaces.
- What remains before the milestone is truly usable end-to-end: S05 still owns adjacent `firebase_uid`/Firebase narrative cleanup outside this transport boundary, and S06 still owns the assembled no-Firebase stack proof.

## Tasks

- [x] **T01: Hard-cut legacy session transport at the auth chokepoints** `est:1h15m`
  - Why: Both resolver stacks and the canonical auth/websocket extractors must be cut together or legacy transport will survive through an alternate path.
  - Files: `backend-hormonia/app/dependencies/auth_session_contract.py`, `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/api/websockets.py`, `backend-hormonia/tests/api/v2/test_auth_session_priority.py`, `backend-hormonia/tests/api/test_websocket_session_auth_contract.py`, `backend-hormonia/tests/api/v2/test_auth_local_login.py`
  - Do: Make cookie-backed session state the only accepted staff session transport in the resolver/request-extractor layer; remove `X-Session-ID` response emission and session-as-Bearer lookup from canonical auth routes; reject websocket header/query fallback while preserving stable websocket auth diagnostics and canonical login/verify/logout payloads.
  - Verify: `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py`
  - Done when: cookie-backed auth still passes through the official path, header/bearer/query fallback is rejected in focused proof, and websocket failures still emit the pinned diagnostic codes.
- [ ] **T02: Converge remaining helper consumers and acceptance proof on the cookie-only contract** `est:1h30m`
  - Why: After the chokepoint cut, direct helper consumers and dual-transport fixtures can still keep the legacy contract alive or hide regressions, especially in `localization.py` and shared helper wrappers.
  - Files: `backend-hormonia/app/api/v2/routers/localization.py`, `backend-hormonia/app/api/v2/templates_shared.py`, `backend-hormonia/app/api/v2/routers/tasks/dependencies.py`, `backend-hormonia/app/api/v2/routers/admin/dependencies.py`, `backend-hormonia/app/api/v2/messages/helpers.py`, `backend-hormonia/tests/api/v2/test_localization.py`, `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py`, `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`
  - Do: Migrate in-scope helper surfaces to reuse the canonical cookie-backed session dependency instead of parsing `X-Session-ID`/Bearer transport locally; sweep any remaining S01-approved helper wrappers still advertising legacy transport in reports/patients/quiz shared surfaces if they survive the first pass; narrow fixtures and acceptance tests to cookie + CSRF only so the suite proves the real post-cut contract.
  - Verify: `cd backend-hormonia && pytest -q tests/api/v2/test_localization.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/integration/test_auth_hard_cut_end_to_end.py`
  - Done when: localization and the remaining in-scope helper/acceptance surfaces no longer depend on `X-Session-ID`/Bearer session transport, and the acceptance pack stays green without dual-transport crutches.
- [ ] **T03: Tombstone `/session/*` and republish the backend residue boundary** `est:1h`
  - Why: S04 is only complete when the legacy root island is intentionally dead and the S01 verifier/docs agree with the new boundary; otherwise the cut is ambiguous and easy to regress.
  - Files: `backend-hormonia/app/routers/auth_session.py`, `backend-hormonia/app/core/router_registry.py`, `backend-hormonia/tests/auth/test_session_validation.py`, `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`, `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`, `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md`, `.gsd/milestones/M004/slices/S01/S01-UAT.md`
  - Do: Replace the mounted root `/session/*` compatibility island with explicit tombstones/rejections instead of silent disappearance; preserve deterministic retirement diagnostics under test; then republish the S01 allowlist and handoff docs so removed anchors disappear or are reclassified honestly alongside the slice proof.
  - Verify: `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
  - Done when: `/session/*` retirement behavior is explicit and tested, and the backend residue report/check match the reduced post-S04 boundary with no stale approved legacy anchors.

## Files Likely Touched

- `backend-hormonia/app/dependencies/auth_session_contract.py`
- `backend-hormonia/app/api/v2/auth_session_shared.py`
- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/app/api/websockets.py`
- `backend-hormonia/app/api/v2/routers/localization.py`
- `backend-hormonia/app/api/v2/templates_shared.py`
- `backend-hormonia/app/api/v2/routers/tasks/dependencies.py`
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py`
- `backend-hormonia/app/api/v2/messages/helpers.py`
- `backend-hormonia/app/api/v2/routers/reports.py`
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
- `backend-hormonia/app/api/v2/patients_utils.py`
- `backend-hormonia/app/api/v2/routers/patients/base.py`
- `backend-hormonia/app/api/v2/_quiz_shared.py`
- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/_shared.py`
- `backend-hormonia/app/routers/auth_session.py`
- `backend-hormonia/app/core/router_registry.py`
- `backend-hormonia/tests/api/v2/test_auth_session_priority.py`
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py`
- `backend-hormonia/tests/api/v2/test_auth_local_login.py`
- `backend-hormonia/tests/api/v2/test_localization.py`
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py`
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`
- `backend-hormonia/tests/auth/test_session_validation.py`
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md`
- `.gsd/milestones/M004/slices/S01/S01-UAT.md`
