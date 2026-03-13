# S04 Cleanup Manifest

**Slice:** S04 — Dead-Code And Obsolete-Compatibility Cleanup
**Milestone:** M003
**Published:** 2026-03-13
**Status:** closed with proof

## Purpose

This manifest closes S04 with an auditable boundary:
- what dead residue was actually removed,
- what compatibility surfaces are intentionally still live,
- which proof commands must be reused before anyone broadens or reopens the cleanup.

The inputs for this manifest are:
- `.gsd/milestones/M003/slices/S04/tasks/T01-SUMMARY.md`
- `.gsd/milestones/M003/slices/S04/tasks/T02-SUMMARY.md`
- `.gsd/milestones/M003/slices/S04/S04-RESEARCH.md`
- the rerun proof commands recorded below
- direct code reads in `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/auth_role_dependencies.py`, `backend-hormonia/app/api/v2/routers/auth.py`, and `backend-hormonia/app/routers/auth_session.py`

## Removed Frontend Residue

| Surface | Removed state | Why removal was safe | Proof that now guards it |
|---|---|---|---|
| `frontend-hormonia/src/lib/api.ts` | Deleted outright | Exact repo-local imports were already zero and the stable public client seam remains `frontend-hormonia/src/lib/api-client.ts` | `tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts`, the focused frontend integration pack, `npm run typecheck`, and `npm run build` |
| `frontend-hormonia/src/lib/types/api.ts` | Deleted outright | The last proof-only import was migrated to canonical owners in `frontend-hormonia/src/lib/api-client/types.ts` and `frontend-hormonia/src/types/shared` before deletion | `tests/unit/types-validation.test.ts`, `tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts`, `npm run typecheck`, and `npm run build` |
| `frontend-hormonia/src/hooks/use-quiz-session.ts` | Deleted outright | No surviving callers remained; live quiz ownership stays with `frontend-hormonia/src/features/monthly-quiz/hooks/useMonthlyQuiz.ts`, `frontend-hormonia/src/lib/api-client/quiz.ts`, and `frontend-hormonia/src/lib/api-client/monthly-quiz.ts` | `tests/monthly-quiz/useMonthlyQuiz.spec.tsx`, the focused frontend integration pack, `npm run typecheck`, and `npm run build` |

### Frontend boundary note

S04 does **not** keep tombstone shims for these paths. The executable boundary is negative:
- the deleted files must stay absent, and
- the focused proof must stay off the legacy compat barrel.

That is why `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` is part of the acceptance surface.

## Removed Backend Auth Residue

| Surface | Removed state | Why removal was safe | Proof that now guards it |
|---|---|---|---|
| `verify_firebase_token` | Removed from the public auth dependency/export surface; absent from `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/__init__.py`, and the legacy helper home used by the old façade | There are no runtime app imports of the symbol. The remaining repo mentions are residual docs/tests/artifacts only, and `/api/v2/auth/firebase/verify` is already tombstoned by hard-cut coverage | `backend-hormonia/tests/unit/test_auth_dependency_module_split.py`, `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py`, and the aligned websocket/session proof pack |
| `get_doctor_user` | Removed from the public auth dependency/export surface | No runtime callers remain on the public surface; canonical role gating is exercised through the current session/user helpers instead | `backend-hormonia/tests/unit/test_auth_dependency_module_split.py`, `backend-hormonia/tests/auth/test_session_role_enforcement.py`, and `backend-hormonia/tests/security/test_rbac_authorization.py` |
| `get_current_user_websocket` | Removed from the public auth dependency/export surface and absent from the legacy helper surface that used to host websocket compatibility wrappers | The authoritative websocket contract is session-first / jwt-only. Legacy `firebase` and `auto` auth types are now explicitly unsupported instead of silently patched back in for tests | `backend-hormonia/tests/unit/test_auth_dependency_module_split.py`, `backend-hormonia/tests/services/websocket/test_connection_manager.py`, and `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` |

### Backend boundary note

S04 does **not** restore removed wrappers just because stale tests used to patch them. The executable rule is:
- the removed names stay absent from the public dependency surface, and
- the websocket/auth proof must assert current behavior (`jwt` / `session`) plus explicit rejection of retired legacy auth modes (`firebase` / `auto`).

## Retained Compatibility Islands

These are **intentional retained surfaces**, not ambiguous leftovers.

| Retained surface | Why it is still live | Evidence tying the decision to code/proof | What S05 must still smoke |
|---|---|---|---|
| `backend-hormonia/app/routers/auth_session.py` | This router is still mounted and still owns the legacy `/session/*` surface. It remains a real runtime compatibility island, not dead code. | The evidence-map report still shows `backend.auth_session.lines=731`. Code reads show `create_session`, `validate_session`, `logout_session`, `logout_all_sessions`, and active-session handlers still operate on the legacy session payload and still read/write `firebase_uid` plus permission-shaped session data. `backend-hormonia/tests/auth/test_session_validation.py` remains part of the slice proof pack. | Re-smoke login/restore/logout behavior, plus the still-mounted `/session/*` compatibility endpoints, before anyone tries to delete or hard-cut the router. |
| `firebase_uid` compatibility fallback | Canonical `id` / `user_id` is authoritative now, but `firebase_uid` still has live compatibility reads and writes. | `backend-hormonia/app/dependencies/auth_role_dependencies.py` loads by canonical `id` / `user_id` first and falls back to `firebase_uid` only when canonical IDs are absent. `backend-hormonia/app/api/v2/routers/auth.py` still persists `user_payload["firebase_uid"] = user.firebase_uid`. `backend-hormonia/app/routers/auth_session.py` still restores, caches, and invalidates through `firebase_uid`. | Re-smoke admin/session rehydration and legacy session restore/logout paths before removing `firebase_uid` from the contract. |
| `bearer-token fallback` | Staff auth is session-first, but a legacy bearer path still exists when no session cookie or `X-Session-ID` is present. | `backend-hormonia/app/dependencies/auth_dependencies.py::get_current_user()` tries session cookie/header first and only then delegates to `auth_legacy_firebase.authenticate_legacy_bearer_user(...)`. `backend-hormonia/app/api/v2/routers/auth.py::_get_session_id_from_request()` also still accepts `Authorization: Bearer ...` as a compatibility extraction path. | Re-smoke the canonical cookie/session happy path and at least one legacy bearer caller or explicit non-use proof before deleting the bearer-token fallback. |

## Exact Proof Commands And Outcomes

These are the commands S05 should reuse instead of reopening discovery.

1. `cd frontend-hormonia && npm run test -- tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts tests/unit/types-validation.test.ts tests/monthly-quiz/useMonthlyQuiz.spec.tsx`
   - **Outcome:** passed
   - **Detail:** 3 test files, 21 tests green.

2. `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
   - **Outcome:** passed
   - **Detail:** 4 test files, 43 tests green. The existing Node warning about `--localstorage-file` lacking a valid path still appears, but the proof remains green.

3. `cd frontend-hormonia && npm run typecheck && npm run build`
   - **Outcome:** passed
   - **Detail:** TypeScript completed cleanly and the production Vite build completed successfully after the compat deletions.

4. `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py`
   - **Outcome:** passed
   - **Detail:** suite completed green at 100%. The existing `pytest_asyncio` deprecation warning about `asyncio_default_fixture_loop_scope` remains non-blocking.

5. `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`
   - **Outcome:** passed (`RESULT: --report all OK`)

6. `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`
   - **Outcome:** passed (`RESULT: --check all OK`)

## Evidence-Map Report Snapshot

The post-cleanup verifier snapshot that closed the slice:

```text
[backend]
  - backend.auth_dependencies.lines=675
  - backend.auth_router.lines=1245
  - backend.auth_session.lines=731
  - backend.admin_dependencies.lines=136
  - backend.reports.lines=787
  - backend.enhanced_reports.lines=764
  - backend.roles_dependencies.lines=23
  - backend.flows.lines=1281
  - backend.message_handler.lines=1126
  - backend.depends.get_current_user_from_session=202
  - backend.depends.get_current_user_object_from_session=7
  - backend.depends.get_current_user=60
  - backend.depends.get_admin_user=68
  - backend.hardcoded_session_id_alias=9
  - backend.candidate.verify_firebase_token.repo_refs=4
  - backend.candidate.get_doctor_user.repo_refs=1
  - backend.candidate.get_current_user_websocket.repo_refs=2

[frontend]
  - frontend.api_client_facade.lines=75
  - frontend.api_client_facade.imports=103
  - frontend.api_client_index.lines=223
  - frontend.api_client_types.lines=26
  - frontend.api_client_types.imports=34
  - frontend.types_api.lines=900
  - frontend.types_api.imports=50
  - frontend.legacy_types.lines=0
  - frontend.legacy_types.imports=0
  - frontend.legacy_api.lines=0
  - frontend.legacy_api.imports=0
  - frontend.use_quiz_session.lines=0
  - frontend.duplicate_exports.count=0
  - frontend.risk_assessment_request.direct_declarations=0
  - frontend.duplicate_exports.names=

[handoff]
  - handoff.summary.open_scaffold_items=0
  - handoff.uat.open_scaffold_items=0

RESULT: --report all OK
```

## Regression Checklist For S05

S05 should treat the following as the inherited cleanup gate:
- The three deleted frontend paths stay absent:
  - `frontend-hormonia/src/lib/api.ts`
  - `frontend-hormonia/src/lib/types/api.ts`
  - `frontend-hormonia/src/hooks/use-quiz-session.ts`
- The removed backend auth residues stay absent from the public surface:
  - `verify_firebase_token`
  - `get_doctor_user`
  - `get_current_user_websocket`
- The retained islands stay explicitly documented and intentionally live:
  - `backend-hormonia/app/routers/auth_session.py`
  - `firebase_uid`
  - `bearer-token fallback`
- The six proof commands above remain green.

If any of those conditions drift, treat it as a real cleanup-boundary regression, not as harmless documentation staleness.
