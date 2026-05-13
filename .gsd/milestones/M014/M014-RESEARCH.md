# M014 — Research: Hardening Médio e Proof Gaps

**Date:** 2026-05-13

## Summary

M014 should start by converting the R012/R013 backlog into an executable evidence matrix, then close the highest-risk externally reachable gaps first. The codebase already has strong M013-era patterns to reuse: canonical session dependencies, two-doctor/two-patient negative fixtures, private upload/report serving, WuzAPI HMAC/SSRF/idempotency services, public quiz signed state, and reviewer-facing matrix documentation. The main M014 risk is not lack of primitives; it is inconsistent wiring and proof drift across older subsystems.

The biggest current surprises are: `/api/v2/adk/run` is publicly callable and trusts payload-supplied `user_id`; CSRF middleware has broad exemptions for session-protected state-changing route prefixes; WuzAPI idempotency service can fail closed, but the WuzAPI router currently catches idempotency infrastructure errors and continues processing; the HTTP cache middleware treats only Bearer headers as authenticated, so session-cookie GETs can be cached under public headers; the quiz frontend persists answer/progress details in `localStorage`; and the async DB engine turns `sslmode=verify-*` into an SSL context with certificate verification disabled. These are good slice boundaries because each can be proven with controlled tests and side-effect sentries without live WuzAPI/Gemini or production data.

Recommended order: (1) ingress/replay/rate-limit contracts, (2) ADK auth/session ownership, (3) browser/PHI cache plus quiz frontend proof, (4) upload stored-XSS handling, (5) JWT/config posture proof and evidence matrix closure. This keeps externally reachable entry points first, then closes state/session ownership, then browser persistence and artifact-serving risks. RLS/DB TLS/deployment secrets should be treated as controlled configuration/posture proofs unless the user explicitly promotes production-like validation to M015/R014.

## Recommendation

Use a **test-first hardening + proof** approach. For each R012/R013 item, write a focused negative/positive contract test that proves the current behavior, then implement the smallest shared control needed, and finally record the command in `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md`. The matrix should explicitly classify every item as **closed**, **not applicable with evidence**, or **deferred with owner**; nothing from R012/R013 should disappear silently.

Reuse M013 patterns instead of new endpoint-local patches:

- Auth/session/role: `app.dependencies.auth_dependencies.get_current_user_from_session`, `get_current_user_object_from_session`, role helpers, and request-state identity.
- Ownership fixtures: `backend-hormonia/tests/api/v2/security_boundary_helpers.py` for two-doctor/two-patient negative proof.
- Private file/report serving: upload/report helpers from M013, never raw `StaticFiles` for private artifacts.
- PHI-safe diagnostics: generic HTTP errors plus structured extras containing IDs/status/reason only; no patient names, phones, prompts, quiz answers, tokens, cookies, private paths, provider bodies, or secrets.
- Evidence artifact shape: follow `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md` but map R012/R013 instead of F-01..F-11.

Avoid overbuilding M014 into R014. Do not require live providers, production WuzAPI/Gemini, real PHI, or broad production-like DB+queue harness. For DB TLS/RLS and deployment secrets, prove local/config contracts and document what was not runtime-validated.

## Implementation Landscape

### Key Files

- `backend-hormonia/app/middleware/csrf.py` — double-submit CSRF implementation. Important findings: safe-method handling exists, but `EXEMPT_PATHS` includes session-protected state-changing prefixes such as `/api/v2/messages`, `/api/v2/enhanced-messages`, `/api/v2/flows`, `/api/v2/auth/logout`, and password reset endpoints. M014 should narrow exemptions to truly public/provider-auth routes and keep cookie-session writes protected.
- `backend-hormonia/tests/auth/test_csrf_middleware.py` — large CSRF suite. Some current tests encode the broad exemption behavior, so M014 must update tests to the new contract rather than preserving unsafe exemptions.
- `backend-hormonia/app/api/v2/routers/auth.py` — login/session/password reset/logout endpoints. Password reset request is enumeration-safe at the response level, but confirm uses stateless JWT reset tokens and no observed jti/used-token or `last_password_change` replay check. Logout and profile/password writes are good CSRF proof targets.
- `backend-hormonia/app/services/password_reset_service.py` and `backend-hormonia/app/core/security.py` — reset token creation/verification and credential update/session revocation. Add one-time/replay rejection here, not in only the route, so first-access/admin reset flows share the control.
- `backend-hormonia/tests/integration/test_password_reset_migration_flow.py` — existing reset migration/session revocation proof. Extend with reset-token replay and side-effect sentry tests.
- `backend-hormonia/app/integrations/wuzapi/webhook.py` — WuzAPI webhook entry point. It validates HMAC and calls `AtomicWebhookIdempotency`, but catches idempotency failures and continues. M014 should make idempotency infrastructure failure fail closed before `_handle_message` side effects.
- `backend-hormonia/app/services/webhook/idempotency.py` — Redis SET NX EX idempotency primitive. The service mostly has the desired atomic behavior, but DB fallback has a last-resort fail-open branch; router behavior is the bigger immediate contradiction.
- `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py` — currently includes `test_idempotency_fail_open`; M014 should invert/replace this with fail-closed proof plus duplicate side-effect sentries.
- `backend-hormonia/app/middleware/distributed_rate_limiter.py` and `backend-hormonia/app/middleware/rate_limit_core.py` — distributed rate-limit middleware. `_get_client_identifier` trusts `X-Forwarded-For` unconditionally; define a trusted-proxy contract before testing. Core limiter has `fail_open=True` by default, which may be acceptable for availability but should be explicitly classified.
- `backend-hormonia/app/utils/rate_limiter.py` — SlowAPI limiter used on auth/public endpoints. It uses `get_remote_address`, disables itself in tests, and has custom Redis DB selection. M014 rate-limit proof should choose whether to test this layer, `RateLimitMiddleware`, or both.
- `backend-hormonia/app/api/v2/routers/adk.py` — current ADK endpoint has no `Depends(...)` auth guard, builds `user_id` from request payload or default, and allows session resume/close/cancel by supplied IDs.
- `backend-hormonia/app/ai/adk/session_store.py` and `backend-hormonia/app/ai/adk/runtime.py` — ADK session/invocation metadata has `user_id` on sessions/invocations, but session resolution currently checks tool/status/size rather than owner. Add owner checks in store/runtime and route-level authenticated user resolution.
- `backend-hormonia/tests/api/v2/test_adk.py` — existing ADK lifecycle/normalization tests. Extend for anonymous denial, payload `user_id` ignored, foreign session resume/close/cancel denial, expired/closed session denial, and PHI-safe error/log assertions.
- `backend-hormonia/app/middleware/cache_middleware.py` — HTTP response cache. It caches GET responses, marks them `Cache-Control: public`, and identifies authentication only by `Authorization: Bearer`, not session cookies. It also does cache lookup before downstream auth can set `request.state.user_id`. Prefer a sensitive-route no-store/denylist or allowlist cache model for PHI endpoints.
- `frontend-hormonia/src/lib/react-query/queryClient.ts` and `frontend-hormonia/src/lib/react-query/persistentCache.ts` — dashboard React Query IndexedDB persister persists the whole client state by default for seven days. Add a sensitive query filter or disable persistence for PHI query prefixes (`patients`, `messages`, `reports`, `alerts`, `flows`, clinical/AI summaries, auth/session), with tests proving skipped persistence.
- `frontend-hormonia/src/lib/query-keys.ts` — central query-key registry. Good place to define/derive sensitive query prefixes for persistence filtering and invalidation proof.
- `quiz-mensal-interface/lib/quiz-progress-storage.ts` and `quiz-mensal-interface/hooks/quiz/useQuizState.ts` — quiz progress stores `answers`, `otherTexts`, `patientName`, `templateName`, and session-keyed data in localStorage for seven days. This conflicts with PHI client-cache hardening. M014 should either remove answer/name persistence or store only non-PHI progress metadata with a short TTL.
- `quiz-mensal-interface/lib/api-client.ts` and `quiz-mensal-interface/hooks/use-quiz-session.ts` — public quiz frontend already uses RAM-only CSRF and HttpOnly cookies. Keep this pattern; add proof that malformed backend payloads and token/XSS attempts fail safely.
- `quiz-mensal-interface/tests/security/*` and `quiz-mensal-interface/tests/unit/*` — quiz frontend lane exists, but it does not yet prove localStorage excludes saved answers/names or that the new backend public quiz contract is complete. Extend rather than creating an entirely new harness.
- `backend-hormonia/app/api/v2/routers/upload/config.py`, `handlers.py`, `storage.py`, `validators.py`, `security.py` — upload subsystem already separates public/private roots and gates private downloads. Stored-XSS proof needs to cover malicious HTML/SVG/script payloads and response headers. Current allowed MIME list excludes `text/html`/`image/svg+xml`, but `.html` uploaded as `text/plain` or risky public text files should be explicitly handled.
- `backend-hormonia/app/services/file_security.py` — scans `.html`, `.htm`, `.svg` only when file extension reaches this layer and only for selected script patterns. Consider blocking active-content extensions outright or forcing attachment/nosniff on all download paths.
- `backend-hormonia/tests/api/v2/test_private_upload_serving.py` — M013 private-serving tests. Extend for stored-XSS rejection/safe download headers and public-upload active-content denial.
- `backend-hormonia/app/core/token_blacklist.py` and `backend-hormonia/tests/core/test_token_blacklist.py` — Redis token blacklist manager exists and has unit tests, but first-party auth is session-first and `app.utils.security.verify_token` does not appear to consult this manager. M014 should decide whether JWT revocation is applicable to live staff auth or only legacy token utilities.
- `backend-hormonia/app/dependencies/auth_session_contract.py` — canonical session auth ignores Authorization/X-Session-ID and requires session cookie. This is useful evidence if JWT revocation is classified as not-applicable to official staff auth.
- `backend-hormonia/app/core/database/async_engine.py` — async DB URL conversion strips `sslmode=require/verify-ca/verify-full` and creates an SSL context with hostname/certificate verification disabled. This is a concrete DB TLS posture issue for M014 config proof.
- `backend-hormonia/app/core/database_config.py` and `backend-hormonia/app/database.py` — sync engine connect args do not visibly enforce DB TLS; add/test configuration checks here if M014 covers DB TLS.
- `backend-hormonia/alembic/versions/6f8c2d4a9b10_enable_rls_sensitive_tables.py` — RLS migration exists for sensitive tables, but policy is `USING (true) WITH CHECK (true)` for current_user. Treat as table-level hardening/posture, not row ownership isolation, unless explicitly re-scoped.
- `backend-hormonia/app/api/v2/routers/system/validation.py`, `backend-hormonia/app/utils/key_validation/*`, `.gitignore` — deployment secret/config proof. `.env`, Firebase admin JSON, and `config_dump.json` are gitignored/untracked locally; `.env.example` is tracked. Add evidence without reading or printing secret values.

### Build Order

1. **Inventory/evidence matrix skeleton first.** Create `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md` with one row per R012/R013 item and initial status `open`. This prevents scope loss.
2. **Ingress/replay first.** CSRF exemptions, reset replay, WuzAPI replay/idempotency, duplicate-oracle behavior, and XFF/rate-limit identity are externally reachable and can share side-effect sentry patterns.
3. **ADK auth/session ownership second.** `/api/v2/adk/run` is a clean, small surface with obvious missing auth and session-owner checks. Closing it early reduces AI/PHI exposure risk.
4. **Browser/PHI cache and quiz frontend third.** Backend no-store behavior and frontend persistence filtering must align; quiz localStorage changes should be proven in the same slice so patient answers/names do not remain in browser storage.
5. **Upload stored-XSS fourth.** M013 already made private serving safe; M014 can focus on active-content rejection or forced-download headers without reworking storage.
6. **JWT/config posture and final matrix last.** JWT revocation, RLS, DB TLS, deployment secrets, and duplicate-oracle leftovers need classification and proof, but some may be not-applicable/config-only. Finish with integrated backend/frontend commands and matrix validation.

## Boundary Contracts That Matter

### CSRF / session-cookie writes

State-changing requests authenticated by browser cookies should require a valid CSRF header+cookie pair unless they are truly public/provider routes protected by a different mechanism (e.g., WuzAPI HMAC). `Authorization`/`X-API-Key` bypass can remain for non-cookie machine clients, but custom session headers must not bypass CSRF.

Proof should show denial before route side effects for missing header, missing cookie, invalid signature, mismatch, expired token, and unsafe exempt-prefix attempts. Positive proof should cover login/CSRF bootstrap and legitimate quiz/frontend flows.

### Reset replay and duplicate oracle

Password reset should keep generic responses for request initiation and should reject replayed/old confirm tokens after first successful use. A robust lightweight contract is: reset JWT must contain `jti/iat`, and confirm rejects tokens whose `iat` is not newer than `user.last_password_change` or whose `jti` is already consumed. The side-effect sentry is password hash/session revocation count unchanged on replay.

The exact “duplicate oracle” surface is still ambiguous in current docs. Likely candidates are patient creation/validation duplicate CPF/phone/email messages or auth/account existence flows. Start by proving current API responses for duplicates and unknown accounts, then either genericize the externally visible response or document admin-only applicability.

### WuzAPI replay/idempotency

Webhook HMAC must run before JSON processing side effects, and idempotency acquisition must run before `_handle_message`/`_handle_receipt`. Duplicates should return a safe duplicate response without creating messages/flow responses. Idempotency infrastructure failure should fail closed for M014 unless an explicit availability exception is documented; current router behavior appears fail-open even though the service has fail-closed paths.

### X-Forwarded-For / rate-limit identity

Do not trust `X-Forwarded-For` from arbitrary clients. Define `TRUSTED_PROXY_IPS`/trusted CIDRs and only use the leftmost untrusted client IP when the immediate peer is trusted. If no trusted proxy is present, use `request.client.host` and ignore spoofed headers. Tests should include spoofed XFF from untrusted peer, trusted proxy chain, malformed header, localhost whitelist bypass disabled, and 429 header assertions.

### ADK auth and session ownership

ADK route should require canonical session auth and should derive `user_id` from the authenticated user, not from payload. ADK session/invocation resume/close/cancel should require stored `payload.user_id == current_user.id` (admin exception only if intentionally allowed). Denials should not echo prompts, patient context, tool outputs, or session state.

### PHI cache / browser persistence

Backend PHI responses should be `Cache-Control: no-store, private` (or not cached by middleware at all) unless explicitly classified non-PHI. Frontend persistent React Query should be allowlist-based or filter sensitive prefixes. Quiz frontend should not persist patient names, answers, free text, or other-option text in `localStorage`; if progress is retained, persist only a non-PHI cursor with short TTL and clear on completion/logout/session error.

### Upload stored-XSS

Reject active content (`.html`, `.htm`, `.svg`, script-bearing text/CSV if rendered inline) or serve every download with `Content-Disposition: attachment` plus `X-Content-Type-Options: nosniff` under auth. Public uploads must not accept active content that `StaticFiles` can render in the browser. Private downloads can safely use attachment names like `upload-{id}{safe_suffix}`.

### JWT revocation multi-worker

The official staff auth path is session-first and rejects bearer-only legacy transports. If JWT access tokens are no longer accepted for staff auth, M014 can classify JWT revocation as not-applicable to the live auth path with proof: bearer-only request fails, cookie session revocation works across DB/cache, and `TokenBlacklistManager` unit tests cover legacy utility behavior. If any live endpoint still trusts JWT directly, wire `TokenBlacklistManager.is_blacklisted` into token verification and add Redis-backed multi-instance tests.

### RLS / DB TLS / deployment secrets

RLS and DB TLS are posture/config contracts under M014, not live exploitation proof. RLS migration exists but uses permissive policies, so do not claim row ownership isolation from it. DB TLS needs a stronger config contract: production URLs should require TLS and `verify-full`/CA verification where feasible; async engine should not downgrade `sslmode=verify-*` to `CERT_NONE`. Deployment-secret proof should use git/config checks that avoid printing secrets.

## Requirement Assessment

| Requirement item | Current research assessment | Suggested M014 disposition |
|---|---|---|
| ADK auth | Real current gap: route has no auth dependency and trusts payload user_id. | Implement and prove. |
| ADK session ownership | Real current gap: session store tracks user_id but resume/close/cancel checks tool/status, not owner. | Implement and prove. |
| CSRF | Partial implementation; exemptions are too broad for session-cookie writes. | Narrow exemptions and prove. |
| reset replay | Likely real gap: reset tokens are stateless JWTs with `jti`, but no observed used-token/iat replay guard. | Implement and prove. |
| webhook replay | Primitive exists; router fail-open behavior conflicts with fail-closed milestone strategy. | Fix router contract and prove. |
| X-Forwarded-For/rate-limit | Real trust-model gap: `X-Forwarded-For` is trusted unconditionally in middleware. | Define trusted proxy model and prove. |
| PHI client cache | Real backend and frontend gaps: session-cookie HTTP cache and IndexedDB/localStorage persistence. | Implement targeted no-store/filtering and prove. |
| upload stored-XSS | Partially mitigated by MIME allowlist and private serving, but no direct malicious HTML/SVG/script proof. | Add reject/attachment/nosniff proof. |
| JWT revocation multi-worker | Ambiguous because canonical staff auth is session-first. Redis blacklist exists but is not wired into utility verifier. | Decide applicability; prove N/A or wire manager. |
| RLS | Migration exists but permissive `USING true` policy means it is posture hardening, not isolation. | Static/config proof only unless re-scoped. |
| DB TLS | Real config/code posture issue in async engine; sync path unclear. | Unit/config proof; no live TLS claim. |
| deployment secrets | `.env`/admin JSON/config dump are gitignored and untracked; validation utilities exist. | Evidence-only/config validation; do not print secret values. |
| duplicate oracle | Exact surface unclear. Patient duplicate validation and auth reset are likely candidates. | Validate first, then close or document N/A. |
| quiz frontend lane | Tests exist, but not enough for PHI storage/new backend contract. | Extend tests; align with cache slice. |

## Proposed Slice Boundaries

### Slice A — Ingress, Replay, and Rate-Limit Identity

Scope: CSRF exemptions, reset replay, WuzAPI replay/idempotency, duplicate-oracle validation, and XFF/trusted proxy semantics.

Likely tests:

- `backend-hormonia/tests/auth/test_csrf_middleware.py` updates for protected session-cookie POST/PUT/DELETE routes.
- New focused route tests such as `backend-hormonia/tests/api/v2/test_m014_csrf_ingress_contracts.py` with side-effect sentries.
- Extend `backend-hormonia/tests/integration/test_password_reset_migration_flow.py` for reset replay.
- Replace/extend `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py::test_idempotency_fail_open` with fail-closed and duplicate no-side-effect tests.
- New `backend-hormonia/tests/middleware/test_rate_limit_trusted_proxy.py` for XFF semantics.

### Slice B — ADK Auth and Session Ownership

Scope: route auth, authenticated user derivation, owner checks in ADK session/invocation operations, PHI-safe denials.

Likely files: `app/api/v2/routers/adk.py`, `app/schemas/v2/adk.py`, `app/ai/adk/session_store.py`, `app/ai/adk/runtime.py`, `tests/api/v2/test_adk.py`.

### Slice C — PHI Cache and Quiz Frontend Persistence

Scope: backend HTTP no-store/skip cache for PHI endpoints, React Query persistence filtering, quiz localStorage hardening, frontend tests.

Likely files: `app/middleware/cache_middleware.py`, `app/core/middleware_setup.py`, `frontend-hormonia/src/lib/react-query/*`, `frontend-hormonia/src/lib/query-keys.ts`, `quiz-mensal-interface/lib/quiz-progress-storage.ts`, `quiz-mensal-interface/hooks/quiz/useQuizState.ts`, quiz/frontend unit tests.

### Slice D — Upload Stored-XSS Proof

Scope: reject active-content uploads or force safe attachment/nosniff serving; public static active-content denial; private download headers.

Likely files: upload validators/security/handlers plus `tests/api/v2/test_private_upload_serving.py` or new `test_upload_stored_xss.py`.

### Slice E — JWT, RLS/DB TLS, Deployment Secrets, Final Matrix

Scope: classify JWT revocation applicability, add DB TLS config tests, RLS migration/static proof, tracked-secret proof, final evidence matrix and integrated command.

Likely files: `app/core/token_blacklist.py`, `app/utils/security.py` if JWT is live, `app/core/database/async_engine.py`, `app/core/database_config.py`, `app/api/v2/routers/system/validation.py`, Alembic migration tests, docs matrix.

## Verification Strategy

Use controlled pytest/Jest/Vitest commands and keep providers mocked. Suggested final evidence classes:

```bash
cd backend-hormonia && pytest \
  tests/auth/test_csrf_middleware.py \
  tests/integration/test_password_reset_migration_flow.py \
  tests/integrations/wuzapi/test_wuzapi_webhook.py \
  tests/api/v2/test_adk.py \
  tests/api/v2/test_private_upload_serving.py \
  tests/core/test_token_blacklist.py \
  tests/middleware/test_rate_limit_trusted_proxy.py \
  tests/config/test_m014_security_posture.py \
  -q
```

```bash
cd frontend-hormonia && npm test -- --run <new-cache-persistence-tests>
cd frontend-hormonia && npm run typecheck
```

```bash
cd quiz-mensal-interface && npm test -- tests/unit/quiz-progress-storage.test.ts tests/unit/api-client.boundary.test.tsx tests/security/session-security.test.tsx
cd quiz-mensal-interface && npm run lint
```

Final matrix validation should assert that all R012/R013 named items appear, each has a status, each closed item has at least one command/evidence ID, and no unsafe sentinel strings appear in the matrix.

## Known Failure Modes Shaping Ordering

- **Proof preserving unsafe behavior:** Existing tests encode risky behavior (`test_idempotency_fail_open`, CSRF exempt session routes). Planners must allow test updates, not just implementation.
- **Middleware ordering/caching:** Cache lookup runs before endpoint auth can set request identity. Avoid trying to key session-cookie caches by request state before auth; no-store/allowlist is safer.
- **Session-first vs JWT ambiguity:** M014 should not spend a full slice wiring JWT revocation if bearer JWTs are no longer accepted by official staff auth. First prove live auth paths.
- **PHI logs while testing failures:** ADK prompts, quiz answers, patient names, and filesystem paths can easily leak through assertion messages/log extras. Tests should use sentinel strings and assert absence.
- **DB TLS overclaim:** Unit/config proof cannot prove production TLS. Matrix language must say “configuration contract validated,” not “production TLS verified.”
- **RLS overclaim:** Existing RLS migration is not row ownership isolation; do not represent it as a substitute for app-level ownership helpers.

## Candidate Requirements / Advisory Additions

These should be surfaced to the user/planner rather than silently expanding scope:

1. Define a trusted proxy model for rate limiting: explicit trusted proxy CIDRs, behavior for malformed XFF, and whether to ignore or reject spoofed headers.
2. Define a sensitive query-key classification for dashboard persistence and a non-PHI progress contract for quiz localStorage.
3. Decide whether ADK is staff-only or admin-only. If staff-only, doctors can run only owner-bound sessions/context; if admin-only, route guard can be simpler but less useful.
4. Decide whether legacy JWT access tokens are a supported auth surface. If not, classify JWT revocation multi-worker as N/A with proof of bearer-only denial.
5. Decide how strict DB TLS should be in local/dev versus production. Strong recommendation: production config validation should require TLS and avoid certificate verification downgrade.

## Skill Discovery

Installed skills relevant to later implementation/review: `react-best-practices` for React/Next.js cache changes, `api-design` for boundary contract shaping, `observability` for PHI-safe diagnostics, `security-review` for pre-closeout threat review, `test`/`verify-before-complete` for evidence discipline. No external skills were installed during this research. The local codebase already contains enough FastAPI/pytest/Next.js patterns for planning; if the user wants extra specialist guidance later, a FastAPI/security skill lookup could be run before implementation.

## Research Evidence Notes

Local research used `gsd_exec` scans instead of noisy raw output. Useful run IDs:

- `e243b156-faae-452a-83c2-92b65423d189` — broad relevant security surface scan.
- `b368bb8e-2d1b-46cb-970f-3e7765e1a016` — repo commands and relevant test layout.
- `e7cc0fea-d5dc-4ffa-8c02-ac4eeb7df941` — target file symbol/excerpt summary.
- `1533f00c-69e8-41cf-b47d-5c0d5e23cda6` — webhook idempotency/current tests summary.
- `0a94b84c-a7e3-4244-a3c6-5ccff906b949` — cache middleware usage and PHI cache clues.
- `d90870f8-8bb9-4f0f-a956-535097bbcf68` — quiz frontend files/test lane summary.
- `5923516b-fd4c-403d-8e56-befa3b245925` — deployment-secret gitignore/tracked-file proof without printing secrets.
- `c8da1eb7-84d7-44a6-9771-aed33cc0b462` — DB TLS/RLS config inventory.
