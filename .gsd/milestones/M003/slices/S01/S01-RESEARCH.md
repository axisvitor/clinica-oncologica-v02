# M003/S01 — Research

**Date:** 2026-03-12

## Summary

This slice **owns R035 (evidence-based dead-code removal)** and **supports R039 (strong proof for structural cleanup)**. The repo evidence matches the roadmap: the highest-value cleanup seams are still `backend-hormonia/app/dependencies/auth_dependencies.py` (**1579 lines**) and the frontend `api-client` / type surface centered on `frontend-hormonia/src/lib/api-client/index.ts` (**1304 lines**), `frontend-hormonia/src/lib/api-client/types.ts` (**1159 lines**), and `frontend-hormonia/src/types/api.ts` (**900 lines**). The right move is still backend auth/session first, frontend client/type second, then deletion only after proof. Starting with deletion would be reckless because both seams still sit behind large caller/import blast radii.

Backend auth/session is not just “one big dependency file”. `auth_dependencies.py` mixes session resolution, Redis session/cache logic, DB fallback, Firebase compatibility, RBAC, websocket auth, and generic cache helpers, while `app/api/v2/routers/auth.py` and the still-live legacy writer `app/routers/auth_session.py` both constrain what the reader side may safely drop. The live contract is split: **mapping-style session dict** callers sit behind **202** `Depends(get_current_user_from_session)` call sites plus **7** `Depends(get_current_user_object_from_session)` adapters, while **`User`-returning** callers sit behind **60** `Depends(get_current_user)` call sites and **68** `Depends(get_admin_user)` call sites. Those are not interchangeable seams. The dict contract still carries derived `permissions`, still drives `request.state.user_id`, `request.state.user_role`, and `request.state.session_id`, and is still surrounded by **9** hardcoded `session_id` cookie alias reads plus a `roles` wrapper that still rehydrates via `firebase_uid`.

Frontend drift is similarly real. The stable public client seam is **not** `src/lib/api-client/index.ts` directly; it is `frontend-hormonia/src/lib/api-client.ts`, which already acts as the compatibility façade for **104** internal imports. The ownership modules sit behind it: `frontend-hormonia/src/lib/api-client/index.ts` owns the client implementation surface, `frontend-hormonia/src/lib/api-client/types.ts` owns the transport/shared DTO bag for **34** direct imports, and `frontend-hormonia/src/types/api.ts` stays the app-facing/UI façade for **50** imports. The remaining legacy aliases are much colder: `frontend-hormonia/src/lib/types/api.ts` has **1** app consumer left (`src/hooks/usePatients.ts`) plus a validation test, `frontend-hormonia/src/lib/api.ts` has **0** exact repo-local imports, and `src/hooks/use-quiz-session.ts` shows no repo-local callers beyond itself. There are still **10 same-named exported declarations** duplicated between `src/types/api.ts` and `src/lib/api-client/types.ts`, so S03 has to preserve the façades while narrowing ownership and S04 can only delete aliases after grep/type/build proof.

## Recommendation

Treat S01 as the boundary-setting slice for the rest of M003:

1. **S02: split backend auth/session around the current contract, not around aesthetics.**
   - Preserve `get_current_user_from_session()` as the mapping-style session dict seam first.
   - Preserve `get_current_user_object_from_session()` / `get_current_user()` as the `User`-shape seam second; they are adapters, not interchangeable with the dict surface.
   - Keep `request.state.session_id`, `request.state.user_id`, and `request.state.user_role` intact while moving internals.
   - Normalize canonical writer/reader alignment before deleting fallback logic or literal `session_id` compatibility reads.
   - Treat `admin`, `reports`, `enhanced_reports`, and `roles` wrappers as constraints to carry forward, not cleanup collateral.

2. **S03: split frontend client/type surface behind the existing façades.**
   - Keep `@/lib/api-client` as the public client entrypoint.
   - Keep `@/lib/api-client/types` and `@/types/api` stable while clarifying which module actually owns which type family.
   - Move internal implementation/type ownership first; remove compatibility exports only after direct proof.

3. **S04: use an evidence ledger, not cleanup instinct.**
   - Candidates exist, but several “ugly” paths are still live compatibility shims.
   - Deletions should happen only after call-site grep, focused tests, and type/build proof line up.

4. **Keep scope locked.**
   - `backend-hormonia/app/api/v2/routers/flows.py` (**1281 lines**) and `backend-hormonia/app/services/webhook/handlers/message_handler.py` (**1126 lines**) are still major hotspots, but they are not the first attack zone for M003. They should be guarded as adjacent sensitive surfaces, not pulled into S02/S03 unless a direct auth/client contract forces it.

## Ranked Hotspot Inventory

| Rank | Area | Files | Evidence | Why it matters now | Recommended slice |
|---|---|---|---|---|---|
| 1 | Backend auth/session seam | `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/routers/auth_session.py` | `auth_dependencies.py lines=1579`; `auth.py lines=1245`; `auth_session.py lines=731`; `Depends(get_current_user_from_session)=202`; `Depends(get_current_user_object_from_session)=7`; `Depends(get_current_user)=60`; `Depends(get_admin_user)=68`; `hardcoded_session_id_alias=9` | Highest maintenance risk and highest contract sensitivity; S02 has to preserve both the dict session seam and the `User` seam while canonical and legacy session writers both remain live | S02 |
| 2 | Frontend api-client/type surface | `frontend-hormonia/src/lib/api-client.ts`, `frontend-hormonia/src/lib/api-client/index.ts`, `frontend-hormonia/src/lib/api-client/types.ts`, `frontend-hormonia/src/types/api.ts`, `frontend-hormonia/src/lib/types/api.ts` | `api-client.ts lines=75 imports=104`; `index.ts lines=1304`; `types.ts lines=1159 imports=34`; `types/api.ts lines=900 imports=50`; `lib/types/api.ts lines=526 imports=1`; `duplicate_exports=10` | High churn risk across many screens; keep `@/lib/api-client` and `@/types/api` stable while moving ownership inside `src/lib/api-client/index.ts` / `types.ts` and retiring legacy aliases only after proof | S03 |
| 3 | Adjacent backend auth consumers | `backend-hormonia/app/api/v2/routers/admin/dependencies.py`, `backend-hormonia/app/api/v2/routers/reports.py`, `backend-hormonia/app/api/v2/routers/enhanced_reports.py`, `backend-hormonia/app/api/v2/routers/roles/dependencies.py` | `admin/dependencies.py lines=132`; `reports.py lines=787`; `enhanced_reports.py lines=764`; `roles/dependencies.py lines=65`; `hardcoded_session_id_alias=9`; wrapper drift is live | These files already fork the central contract via overrides, literal cookie aliases, mock/test branches, and `firebase_uid` rehydration. S02 must preserve them before simplifying them. | S02/S04 |
| 4 | Adjacent critical non-target hotspots | `backend-hormonia/app/api/v2/routers/flows.py`, `backend-hormonia/app/services/webhook/handlers/message_handler.py` | `flows.py lines=1281`; `message_handler.py lines=1126` | Sensitive surfaces that must not regress while cleanup happens elsewhere | S05 guardrails only |

### Backend verifier anchors

- `backend-hormonia/app/dependencies/auth_dependencies.py` — `lines=706`
- `backend-hormonia/app/api/v2/routers/auth.py` — `lines=1245`
- `backend-hormonia/app/routers/auth_session.py` — `lines=731`
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` — `lines=136`
- `backend-hormonia/app/api/v2/routers/reports.py` — `lines=787`
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py` — `lines=764`
- `backend-hormonia/app/api/v2/routers/roles/dependencies.py` — `lines=23`
- `backend-hormonia/app/api/v2/routers/flows.py` — `lines=1281`
- `backend-hormonia/app/services/webhook/handlers/message_handler.py` — `lines=1126`
- `Depends(get_current_user_from_session)=202`
- `Depends(get_current_user_object_from_session)=7`
- `Depends(get_current_user)=60`
- `Depends(get_admin_user)=68`
- `hardcoded_session_id_alias=9`

### Backend S02 contract boundary

- `get_current_user_from_session()` returns **mapping-style session dicts**, not `User` objects. The preserved surface includes at least `id`, `email`, `role`, `is_active`, derived `permissions`, optional `firebase_uid`, and the side effects `request.state.session_id`, `request.state.user_id`, and `request.state.user_role`.
- `get_current_user_object_from_session()` strips non-model keys like `permissions`, maps `user_id -> id`, normalizes timestamps/role values, and produces a `User` object. `get_current_user()` prefers the session path whenever cookie/header session state exists and only falls back to bearer-token Firebase validation when that session path is absent.
- `app/api/v2/routers/auth.py::_create_canonical_session_cache_entry()` and `auth_dependencies.py::_session_payload_to_user_data()` share the canonical session envelope: `user_id` plus metadata keys `session_id`, `email`, `full_name`, `role`, `is_active`, `created_at`, `updated_at`, `last_login`, `remember_me`, and `max_age_seconds`. `firebase_uid` remains compatibility data, not the canonical happy-path key.
- The request-state side effects are live contract, not incidental implementation. `backend-hormonia/app/utils/request_context.py`, `backend-hormonia/app/api/v2/routers/admin/activity.py`, `backend-hormonia/app/middleware/hipaa_audit_middleware.py`, `backend-hormonia/app/middleware/lgpd_middleware.py`, cache/rate-limit middleware, and monitoring readers all depend on those injected values continuing to exist.

### Backend wrapper drift constraints

- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` already diverges from the center via dependency overrides, test-environment fallback, and literal `request.cookies.get("session_id")` handling.
- `backend-hormonia/app/api/v2/routers/reports.py` manually re-wraps `get_current_user_from_session()` and hardcodes `Cookie(None, alias="session_id")` instead of using `settings.SESSION_COOKIE_NAME`.
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py` repeats the wrapper, also hardcodes `alias="session_id"`, and adds `Mock` / timed `get_redis_cache()` branches.
- `backend-hormonia/app/api/v2/routers/roles/dependencies.py` expects mapping-style `current_user` data and still rehydrates through `firebase_uid`; it is a direct constraint on any attempt to delete `firebase_uid` compatibility early.

### Frontend verifier anchors

- `frontend-hormonia/src/lib/api-client.ts` — `lines=75`, `imports=104`
- `frontend-hormonia/src/lib/api-client/index.ts` — `lines=1304`
- `frontend-hormonia/src/lib/api-client/types.ts` — `lines=1159`, `imports=34`
- `frontend-hormonia/src/types/api.ts` — `lines=900`, `imports=50`
- `frontend-hormonia/src/lib/types/api.ts` — `lines=526`, `imports=1`
- `duplicate_exports` — `count=10`, `names=AIChatResponse, AIRecommendation, AlertType, BulkMessageRequest, GenerateReportRequest, Message, MessageType, QuizResponse, Report, SendMessageRequest`

### Frontend S03 contract boundary

- `@/lib/api-client` is the stable public client façade. It must keep exporting `apiClient`, the default export, `ApiClient`, `ApiError`, and the curated auth/patient/quiz/analytics types that existing callers import today.
- `frontend-hormonia/src/lib/api-client/index.ts` and `frontend-hormonia/src/lib/api-client/types.ts` are **internal ownership modules**, not the public seam. S03 should split implementation and transport DTOs here while leaving the public façades stable.
- `@/types/api` is the app-facing/UI façade. It already adapts transport types into UI shapes and helpers such as `frontend-hormonia/src/lib/ai-adapters.ts`; narrowing ownership here is safer than forcing every UI caller onto raw transport DTOs.
- `frontend-hormonia/src/lib/types/api.ts` and `frontend-hormonia/src/lib/api.ts` are **legacy compatibility aliases**. They may be migrated, tombstoned, or deleted only after exact-import proof shows no surviving callers.

## Cleanup Guardrail Matrix

| Surface | Guardrail that must remain true | Why it exists | Verification command(s) |
|---|---|---|---|
| Backend session dict contract | `get_current_user_from_session()` must keep returning mapping-style user data with at least `id`, `email`, `role`, `is_active`, `permissions`, optional `firebase_uid`, and must keep setting `request.state.user_id`, `request.state.user_role`, `request.state.session_id` | 202 direct dict callers still assume mapping access; request-context/audit/middleware readers depend on the request-state side effects; auth-adjacent frontend/admin code still reads `user.permissions` | `cd backend-hormonia && pytest tests/auth/test_session_validation.py tests/auth/test_user_conversion.py tests/api/v2/test_auth_session_priority.py` |
| Backend `User` contract | `get_current_user_object_from_session()` must keep stripping non-model keys (`permissions`, `cached_at`), mapping `user_id -> id`, normalizing timestamps/role, and `get_current_user()` must keep preferring the session path before bearer-token fallback | 7 direct adapters plus 60 `Depends(get_current_user)` callers and 68 `Depends(get_admin_user)` callers rely on `User` semantics rather than mapping semantics | `cd backend-hormonia && pytest tests/auth/test_user_conversion.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py` |
| Canonical session writer/reader alignment | `api/v2/routers/auth.py::_create_canonical_session_cache_entry()` must keep writing `user_id` plus metadata keys `session_id`, `email`, `full_name`, `role`, `is_active`, `created_at`, `updated_at`, `last_login`, `remember_me`, and `max_age_seconds`; `auth_dependencies.py::_session_payload_to_user_data()` / fallback logic must keep reading them | Writer/reader drift would break login → restore → logout, and `app/routers/auth_session.py` still writes/reads a thinner legacy shape so fallback logic cannot disappear early | `cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_session_priority.py` |
| Admin/dashboard auth continuity | Admin/dashboard surfaces must still authenticate through the preserved session contracts across `admin/dependencies.py`, `reports.py`, `enhanced_reports.py`, and `roles/dependencies.py` before any wrapper simplification | These wrappers already diverge via dependency overrides, literal `session_id` cookie handling, mock/test branches, and `firebase_uid` rehydration | `cd backend-hormonia && pytest tests/api/v2/test_admin.py tests/api/v2/test_dashboard.py tests/api/test_admin_contracts.py` |
| Websocket/auth adjacency | Session-first websocket proof must remain green while the legacy Firebase-only websocket dependency is only isolated, not removed | `get_current_user_websocket()` is likely obsolete, but websocket/login surfaces are operationally sensitive and auth-adjacent | `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py` |
| Frontend public client façade | `@/lib/api-client` must remain the only public client entrypoint; `src/lib/api-client/index.ts` can move underneath it, but the façade must keep exporting `apiClient`, the default export, `ApiClient`, `ApiError`, and the curated type surface | 104 internal imports hit this façade directly, so import-path churn here would turn S03 into a repo-wide sweep | `cd frontend-hormonia && npm run typecheck && npm run test -- tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts` |
| Frontend type ownership split | `@/lib/api-client/types` and `@/types/api` must stay stable façades while ownership is narrowed behind them; adapters like `src/lib/ai-adapters.ts` must keep transport/UI differences explicit | 34 transport-type imports and 50 app-facing imports already split the surface; collapsing them in one move would create silent DTO drift | `cd frontend-hormonia && npm run typecheck && npm run test -- tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts` |
| Frontend auth/session/client behavior | Session-first auth, restore, and initialization surfaces must not drift while client internals are split | M002 proved these routes; S03 must preserve them | `cd frontend-hormonia && npm run test -- tests/integration/auth/session-first-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx` |
| Frontend admin/dashboard surfaces | Admin/dashboard consumers must survive the client/type refactor without import-path or DTO drift | They are high-visibility consumers of the same shared surface | `cd frontend-hormonia && npm run test -- tests/integration/admin-auth-flow.test.tsx tests/components/dashboard/QuickStats.test.tsx` |
| Full-stack smoke before milestone close | Critical visible loops still work: login, dashboard/admin, websocket, WhatsApp-adjacent flow surfaces | R037/R039 require proof stronger than cleaner files | `cd frontend-hormonia && npx playwright test tests/e2e/auth/login.spec.ts tests/e2e/admin-dashboard-complete.spec.ts tests/e2e/websocket.spec.ts tests/e2e/test_whatsapp_integration_e2e.spec.ts` |

## Deletion Candidate Ledger

| Candidate | Current evidence | Current recommendation | Proof required before removal or isolation | Likely slice |
|---|---|---|---|---|
| `backend-hormonia/app/dependencies/auth_dependencies.py::verify_firebase_token` | `repo_refs=6`; current refs are the definition, tests/docs, and websocket-connection-manager patch points — no router hit surfaced by app scan | Strong dead-code suspect, but do not delete inside S02 | `rg -n "verify_firebase_token" backend-hormonia/app backend-hormonia/tests backend-hormonia/docs`<br>`cd backend-hormonia && pytest tests/auth/test_session_validation.py tests/auth/test_user_conversion.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_hard_cut_cleanup.py` | S04 |
| `backend-hormonia/app/dependencies/auth_dependencies.py::get_doctor_user` | `repo_refs=3`; still consistent with definition + package re-export residue rather than live callers | Likely removable or isolatable later | `rg -n "get_doctor_user" backend-hormonia/app backend-hormonia/tests`<br>`cd backend-hormonia && pytest tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py` | S04 |
| `backend-hormonia/app/dependencies/auth_dependencies.py::get_current_user_websocket` | `repo_refs=3`; still consistent with definition + package re-export residue | Likely obsolete after session-first websocket cutover, but higher risk than `get_doctor_user` | `rg -n "get_current_user_websocket" backend-hormonia/app backend-hormonia/tests`<br>`cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py`<br>`cd frontend-hormonia && npm run test -- tests/integration/realtime/session-websocket-cutover.test.ts` | S04 |
| Legacy Firebase-only branches inside `get_current_user()` | Still live code, not proven dead; bearer-token path, token cache, and `firebase_uid`-based lookups remain present | **Do not remove in S02**; isolate first if possible | `rg -n "firebase_uid|verify_token|get_cached_token|get_cached_user" backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/api/v2/routers/roles/dependencies.py backend-hormonia/app/routers/auth_session.py`<br>`cd backend-hormonia && pytest tests/auth/test_user_conversion.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py tests/api/test_websocket_session_auth_contract.py` | S04 |
| `backend-hormonia/app/routers/auth_session.py` compatibility behavior | `lines=731`; `validate_session` / `logout_session` still read `firebase_uid`, rebuild `permissions`, and operate on a thinner legacy session payload than the canonical v2 auth path | Not a deletion target yet | `rg -n "validate_session|logout_session|firebase_uid|permissions" backend-hormonia/app/routers/auth_session.py backend-hormonia/app/api/v2/routers/auth.py`<br>`cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_session_priority.py` | S04+ |
| `frontend-hormonia/src/lib/api.ts` | `lines=4`; `internal_imports=0`; no exact repo-local imports surfaced outside the alias file | Strong alias-cleanup suspect | `rg -n "['\"](@/lib/api|\.\./lib/api|\.\./\.\./lib/api|\.\./\.\./\.\./lib/api)['\"]" frontend-hormonia/src frontend-hormonia/tests`<br>`cd frontend-hormonia && npm run typecheck && npm run test -- tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts`<br>`cd frontend-hormonia && npm run build` | S04 |
| `frontend-hormonia/src/lib/types/api.ts` | `lines=526`; `internal_imports=1` (`src/hooks/usePatients.ts`); validation coverage still imports the alias directly | Migrate the last app caller, then remove or tombstone | `rg -n "@/lib/types/api|\.\./lib/types/api|\.\./\.\./src/lib/types/api" frontend-hormonia/src frontend-hormonia/tests`<br>`cd frontend-hormonia && npm run test -- src/hooks/__tests__/usePatients.test.ts tests/hooks/usePatientImport.test.ts`<br>`cd frontend-hormonia && npm run typecheck && npm run build` | S04 |
| `frontend-hormonia/src/hooks/use-quiz-session.ts` | `lines=476`; `rg -n "use-quiz-session|useQuizSession" frontend-hormonia/src frontend-hormonia/tests` only surfaces the file itself today | Suspicious public-quiz residue, but do not delete blindly | `rg -n "use-quiz-session|useQuizSession" frontend-hormonia/src frontend-hormonia/tests`<br>`cd frontend-hormonia && npm run test -- tests/monthly-quiz/useMonthlyQuiz.spec.tsx tests/unit/pages/QuestionariosPage.test.tsx`<br>`cd frontend-hormonia && npx playwright test tests/e2e/quiz-submission-flow.spec.ts tests/e2e/quiz-complete-flow.spec.ts` | S04 |
| Duplicate `RiskAssessmentRequest` declarations inside `frontend-hormonia/src/lib/api-client/types.ts` | `direct_declarations=2`; both declarations currently live in the transport type bag, independent of the 10-name cross-façade overlap | Safe cleanup candidate after type proof | `rg -n "export (interface|type) RiskAssessmentRequest\\b" frontend-hormonia/src/lib/api-client/types.ts frontend-hormonia/src/types/api.ts`<br>`cd frontend-hormonia && npm run test -- tests/hooks/api/usePhysicianRiskAssessments.test.tsx tests/integration/api-client.test.ts`<br>`cd frontend-hormonia && npm run typecheck` | S03/S04 |

### Backend candidate verifier anchors

- `verify_firebase_token` — `repo_refs=14`
- `get_doctor_user` — `repo_refs=5`
- `get_current_user_websocket` — `repo_refs=9`

### Frontend candidate verifier anchors

- `frontend-hormonia/src/lib/api.ts` — `lines=4`, `internal_imports=0`
- `frontend-hormonia/src/lib/types/api.ts` — `internal_imports=1`
- `frontend-hormonia/src/hooks/use-quiz-session.ts` — `lines=476`
- `RiskAssessmentRequest` — `direct_declarations=2`

## Explicit Non-Candidates

- `backend_session_permissions_field` — `status=keep`; live backend/frontend auth-adjacent readers still exist, so this stays in the contract until those readers move.
- `backend_firebase_uid_compatibility` — `status=keep`; `backend-hormonia/app/api/v2/routers/roles/dependencies.py`, `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/routers/auth_session.py`, and Redis compatibility adapters still read/write `firebase_uid`, so S02 may isolate it but must not delete it.
- `frontend_api_client_facade` — `status=keep`, `internal_imports=104`; `frontend-hormonia/src/lib/api-client.ts` is the public compatibility seam and is not a cleanup target while the façade is still this hot.
- `frontend_types_api_facade` — `status=keep`, `internal_imports=50`; `frontend-hormonia/src/types/api.ts` is still an app-facing façade, so narrowing ownership comes before deleting or collapsing it.

## Downstream Verification Commands

### Backend commands

- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report backend`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend`
- `cd backend-hormonia && pytest tests/auth/test_session_validation.py tests/auth/test_user_conversion.py tests/api/v2/test_auth_session_priority.py`
- `cd backend-hormonia && pytest tests/auth/test_user_conversion.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py`
- `cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py`
- `cd backend-hormonia && pytest tests/api/v2/test_admin.py tests/api/v2/test_dashboard.py tests/api/test_admin_contracts.py`
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py`

### Frontend commands

- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report frontend`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend`
- `cd frontend-hormonia && npm run typecheck && npm run test -- tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts`
- `cd frontend-hormonia && npm run test -- tests/integration/auth/session-first-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx`
- `cd frontend-hormonia && npm run test -- tests/integration/admin-auth-flow.test.tsx tests/components/dashboard/QuickStats.test.tsx`

### Slice-close commands

- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`
- `cd frontend-hormonia && npx playwright test tests/e2e/auth/login.spec.ts tests/e2e/admin-dashboard-complete.spec.ts tests/e2e/websocket.spec.ts tests/e2e/test_whatsapp_integration_e2e.spec.ts`

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Canonical backend session payload | `backend-hormonia/app/api/v2/routers/auth.py::_create_canonical_session_cache_entry()` + `backend-hormonia/app/dependencies/auth_dependencies.py::get_current_user_from_session()` | The writer/reader pair already defines the real session envelope; splitting around it is safer than inventing a new contract mid-refactor |
| Stable frontend client import seam | `frontend-hormonia/src/lib/api-client.ts` | This is already the compatibility façade used by 104 imports; keep it stable while changing internals underneath |
| UI-vs-transport AI shape conversion | `frontend-hormonia/src/lib/ai-adapters.ts` | It is the clearest existing adapter seam between `@/lib/api-client/types` and `@/types/api`; use this pattern rather than collapsing unlike types by hand |

## Existing Code and Patterns

- `backend-hormonia/app/dependencies/auth_dependencies.py` — central auth/session hotspot; the internal split should follow its real responsibility clusters: session resolution, cache/DB rehydration, dict→`User` adaptation, legacy Firebase auth, role wrappers, websocket auth.
- `backend-hormonia/app/api/v2/routers/auth.py` — canonical session writer and the best source of truth for the Redis session payload fields that later readers must preserve.
- `backend-hormonia/app/routers/auth_session.py` — still-live legacy session writer/reader that proves thinner `firebase_uid`-centric compatibility behavior has not died yet.
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` — important warning pattern: wrapper logic already depends on dependency overrides, test bypasses, and hardcoded cookie handling. Refactors must preserve behavior before simplifying it.
- `backend-hormonia/app/api/v2/routers/reports.py` — concrete example of wrapper drift: it re-wraps `get_current_user_from_session()` manually and hardcodes `alias="session_id"` instead of using `settings.SESSION_COOKIE_NAME`.
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py` — same wrapper drift pattern plus extra mock/timed-cache branches, so it should not be assumed equivalent to the central dependency.
- `backend-hormonia/app/api/v2/routers/roles/dependencies.py` — mapping-style admin auth wrapper that still depends on `firebase_uid` for DB rehydration.
- `frontend-hormonia/src/lib/api-client.ts` — the public façade to preserve. Internal module split can change, but this entrypoint should remain stable.
- `frontend-hormonia/src/types/api.ts` — aggregate app-facing type façade. It already re-exports many transport types, which means it is a façade, not a clean source-of-truth module.
- `frontend-hormonia/src/lib/api-client/types.ts` — transport/shared DTO bag. This is where flow/alert/report/admin/quiz DTO ownership already lives, even though some same-named shapes are duplicated elsewhere.
- `frontend-hormonia/src/lib/types/api.ts` — legacy compatibility layer with explicit comments telling new code not to use it. Good cleanup target after the last consumer moves.
- `frontend-hormonia/src/lib/ai-adapters.ts` — good model for explicit seam ownership when transport and UI types differ.

## Constraints

- `backend-hormonia/app/dependencies/auth_dependencies.py` currently fronts **202** `Depends(get_current_user_from_session)` usages, **7** `Depends(get_current_user_object_from_session)` adapters, **60** `Depends(get_current_user)` usages, and **68** `Depends(get_admin_user)` usages. That is too much blast radius for contract drift.
- The backend auth seam has two live return-shape contracts: mapping-style session dicts and `User` objects. Treating them as interchangeable will break callers.
- The backend contract includes side effects, not just return values: `request.state.session_id`, `request.state.user_id`, and `request.state.user_role` are read elsewhere.
- Wrapper drift already exists: at least **9** hardcoded `session_id` cookie alias accesses remain under backend auth-adjacent code.
- `backend-hormonia/app/routers/auth_session.py` still writes and reads a thinner legacy session payload than the canonical v2 auth route. This is why central fallback logic still exists.
- `backend-hormonia/app/api/v2/routers/roles/dependencies.py` still relies on `firebase_uid` lookup from mapping-style session data, so `firebase_uid` is not a backend cleanup candidate yet.
- `frontend-hormonia/src/lib/api-client.ts` is the stable façade for **104** internal imports; `@/lib/api-client/types` has **34** imports; `@/types/api` has **50** imports; `@/lib/types/api` still has **1** internal import. Any S03 plan must preserve these façades before cleanup.
- There are **10** same-named direct exported declarations duplicated between `frontend-hormonia/src/types/api.ts` and `frontend-hormonia/src/lib/api-client/types.ts`: `AIChatResponse`, `AIRecommendation`, `AlertType`, `BulkMessageRequest`, `GenerateReportRequest`, `Message`, `MessageType`, `QuizResponse`, `Report`, `SendMessageRequest`.
- `frontend-hormonia/src/lib/api.ts` currently has **0** internal imports, but that is only repo-local evidence. Removal still needs build/type/export proof.

## Common Pitfalls

- **Confusing ugly compatibility with dead compatibility** — `auth_dependencies.py` and the frontend type surface both contain residue, but several branches still exist to bridge live drift (`firebase_uid`, thin session payloads, façade imports). Require grep + focused tests before deleting.
- **Refactoring only the implementation and forgetting the façades** — the safe seam is `@/lib/api-client`, not `src/lib/api-client/index.ts` directly. The same applies to backend wrapper dependencies that already sit between callers and the core function.
- **Swapping dict-returning and `User`-returning auth dependencies as if they were equivalent** — they are not. Some routes expect `.role`/`.id`, others expect mapping access and injected `permissions`.
- **Deleting session fallback logic before harmonizing session writers** — the v2 auth router and legacy auth-session writer do not emit the same payload completeness today.
- **Trying to unify all frontend types at once** — M003 should narrow ownership in the targeted seam, not turn into a repo-wide type redesign.

## Open Risks

- `backend-hormonia/app/api/v2/routers/admin/dependencies.py`, `reports.py`, and `enhanced_reports.py` are already local forks of session-auth wiring; central refactor work can pass while these wrappers still drift unless they are explicitly checked.
- `backend-hormonia/app/api/v2/routers/roles/dependencies.py` still depends on `firebase_uid`, so removing that field from the internal contract early would be a hidden auth regression.
- `backend-hormonia/app/routers/auth_session.py` still proves a thinner legacy session contract is live; removing fallback behavior before that route is retired or rewired would be a login/restore regression.
- The frontend has real same-name type collisions (`Report`, `MessageType`, `AIChatResponse`, etc.). A naive “dedupe” can silently change UI expectations.
- `frontend-hormonia/src/hooks/use-quiz-session.ts` looks like orphaned legacy code, but deleting it without proving route reachability could break a dormant/public quiz path.
- Because the next slices touch both backend and frontend auth-related seams, S05 must explicitly replay critical login/admin/dashboard/websocket/WhatsApp-adjacent smoke instead of trusting unit suites alone.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `wshobson/agents@fastapi-templates` | available via `npx skills add wshobson/agents@fastapi-templates` |
| React | `vercel-labs/agent-skills@vercel-react-best-practices` | available via `npx skills add vercel-labs/agent-skills@vercel-react-best-practices` |
| Frontend UI work | installed `frontend-design` skill | installed, but not directly relevant to this structural research slice |

## Sources

- The backend auth/session hotspot size, mixed responsibilities, and session-side effects came from `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/api/v2/routers/auth.py`, and `backend-hormonia/app/routers/auth_session.py`.
- The admin/report/enhanced-report wrapper drift and hardcoded cookie alias evidence came from `backend-hormonia/app/api/v2/routers/admin/dependencies.py`, `backend-hormonia/app/api/v2/routers/reports.py`, and `backend-hormonia/app/api/v2/routers/enhanced_reports.py`.
- The `firebase_uid`-dependent backend constraint came from `backend-hormonia/app/api/v2/routers/roles/dependencies.py` and the cache/auth compatibility helpers it still depends on.
- The frontend façade and alias evidence came from `frontend-hormonia/src/lib/api-client.ts`, `frontend-hormonia/src/lib/api.ts`, and `frontend-hormonia/src/lib/types/api.ts`.
- The frontend seam split, duplicate-type ownership, and adapter pattern evidence came from `frontend-hormonia/src/lib/api-client/index.ts`, `frontend-hormonia/src/lib/api-client/types.ts`, `frontend-hormonia/src/types/api.ts`, and `frontend-hormonia/src/lib/ai-adapters.ts`.
- The hotspot ranking and import/call-site counts came from repo-local `rg`/line-count scans across `backend-hormonia/app/**` and `frontend-hormonia/src/**`.
- Skill suggestions came from `npx skills find "FastAPI"` and `npx skills find "React"`.
