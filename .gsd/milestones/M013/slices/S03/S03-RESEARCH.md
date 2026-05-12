# S03 Research: Quiz Link/Session Boundary

**Depth:** Deep research. This slice spans authenticated ownership checks, signed public quiz tokens, stateful cookie compatibility endpoints, and DB-backed link/session invariants.

## Summary

S03 owns the still-open quiz requirements:

- **R004:** quiz link/status/history/active-link endpoints must enforce patient ownership.
- **R005:** public quiz access/submit must bind token, session, patient, expiration, and link state.
- **R010/R011 support:** reuse S02 two-doctor/two-patient negative fixtures and keep denial diagnostics ID/reason-only with no PHI, tokens, or secrets.

The vulnerable surfaces are concentrated under `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/` and mounted at `/api/v2/quiz-extensions`.

Key findings:

1. **Authenticated quiz link operations are authenticated but not ownership-scoped.** `crud.py` protects routes with `_get_current_user_simple`, but `POST /links/`, `GET /patients/{patient_id}/status`, `GET /patients/{patient_id}/history`, and `GET /links/active/` do not call `load_patient_with_access` or otherwise filter by assigned doctor. `GET /links/active/` currently returns active sessions for all patients, including `patient_name`.
2. **Public token verification is signature-only, not link/session-state verification.** `public.py::_decode_quiz_token()` verifies the JWT signature/expiry, but public access/submit routes do not require the decoded token to match `QuizSession.patient_id`, `QuizSession.quiz_template_id`, stored `session_metadata.token_hash`, `link_status`, or `expiration_date`.
3. **Compatibility cookie endpoints trust raw `quiz_session_id`.** `POST /access` sets only an HttpOnly `quiz_session_id` cookie. `GET /session/active` and `POST /submit` accept that raw UUID without a signed/opaque state proof. A forged/stolen session UUID is therefore enough to read the public quiz payload or submit responses while the session status is `started`.
4. **Current public routes create or use invalid/ambiguous session states.** `public.py` uses `in_progress`/`pending` in some paths, while `QuizSession.status` only accepts `started`, `completed`, `cancelled`, `expired`. `crud.py` also checks `status.in_(['started', 'active'])`, but `active` is link metadata, not a valid session status.
5. **Existing reusable ingredients are present.** S02’s `load_patient_with_access` helper should cover authenticated patient ownership. `TokenManager` already generates/verifies JWTs and hashes tokens. Link metadata already stores `token_hash`, `expires_at`, `link_status`, `short_code`, and `access_count`. `router_registry.py`’s `/q/{code}` resolver has a useful link-status/expiration pattern.

## Recommendation

Implement a small shared public quiz authorization seam plus route-level ownership checks:

1. **Authenticated ownership:** in `monthly_quiz_operations/crud.py`, call `load_patient_with_access(db, patient_id, current_user)` before creating links or reading patient status/history. For active links/dashboard-style list surfaces, filter SQL by `Patient.doctor_id == current_user.id` for doctors and allow admins to see all.
2. **Public token/session validator:** add a helper in `public.py` or a small sibling module (for example `monthly_quiz_operations/public_security.py`) that:
   - verifies the JWT via `TokenManager.verify_token()`;
   - parses `patient_id`, `quiz_template_id`, `session_id`, `type`, and `exp` as required fields;
   - loads the `QuizSession` by `session_id` **and** requires `session.patient_id == token.patient_id` and `session.quiz_template_id == token.quiz_template_id`;
   - requires `session.status == 'started'`, not expired, not completed/cancelled/expired;
   - requires `session_metadata.link_status == 'active'` and `session_metadata.token_hash == TokenManager.hash_token(token)` (or accepted previous-token hash only if the project deliberately enables a grace-period policy);
   - uses the earliest of JWT `exp`, `session.expiration_date`, and `session_metadata.expires_at` as the effective expiration;
   - returns generic 401/403/404 responses and logs only safe IDs plus `reason`.
3. **Signed/opaque session state for cookie compatibility:** keep `/access` usable for the frontend, but after validating the access token set a second HttpOnly cookie such as `quiz_session_state` containing signed state (`type='quiz_session_state'`, `session_id`, `patient_id`, `quiz_template_id`, expiry, and optionally current token hash/JTI). Then require this state cookie on `/session/active`, `/submit`, and ideally `/logout`. Raw `quiz_session_id` alone must fail.
4. **Do not create public sessions from unbound public access/submit.** Link creation is the session creation boundary. Public access/submit should only load and validate an existing link/session. This avoids fallback behavior that silently accepts a valid token with missing/bad session state.
5. **Remove token-prefix diagnostics from touched quiz denial paths.** `TokenManager.verify_token()` currently logs `extra={'token_prefix': token[:10]}` for invalid/expired tokens, and some audit/metrics helpers use `token_prefix`. S03 should avoid passing token prefixes and should consider replacing these warnings with reason-only or non-reversible event IDs if caplog tests cover public denial diagnostics.

## Implementation Landscape

### Authenticated operations (`crud.py`)

Target file: `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/crud.py`.

Relevant routes:

- `POST /api/v2/quiz-extensions/links/` (`create_quiz_link`): currently verifies only the template and creates/reuses a session for `link_data.patient_id`. Add patient ownership before any session creation or token generation.
- `GET /api/v2/quiz-extensions/patients/{patient_id}/status` (`get_patient_quiz_status`): add `load_patient_with_access` before querying sessions.
- `GET /api/v2/quiz-extensions/patients/{patient_id}/history`: delegates to status, so securing status covers it.
- `GET /api/v2/quiz-extensions/links/active/`: currently lists all started/active sessions and returns patient names. Restrict doctors to own patients with a `QuizSession -> Patient` ownership join/filter; admins see all.
- Adjacent optional hardening: `GET /api/v2/quiz-extensions/stats/dashboard/` aggregates all sessions for every doctor. It is less PHI-heavy than active links but is in the same dashboard family; consider doctor filtering if task budget allows.

Use S02 helper: `from app.api.v2.patients_shared_helpers import load_patient_with_access`.

### Public access and submit (`public.py`)

Target file: `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py`.

Relevant routes:

- `GET /api/v2/quiz-extensions/monthly/public/current?token=...`: signed token is checked, but DB session binding/link state is not.
- `POST /api/v2/quiz-extensions/monthly/public/{quiz_id}/submit`: signed token is checked and URL quiz mismatch is checked, but session status/link state/token hash/patient binding are not. If `session_id` exists, it uses that session without validating status or ownership.
- `POST /api/v2/quiz-extensions/access`: frontend compatibility entrypoint. Should validate full link/session state and set both `quiz_session_id` and signed/opaque `quiz_session_state` cookies.
- `GET /api/v2/quiz-extensions/session/active`: currently accepts raw `quiz_session_id` cookie only. Must require signed/opaque state.
- `POST /api/v2/quiz-extensions/submit`: currently accepts raw `quiz_session_id` cookie only and writes `QuizResponse`. Must require signed/opaque state.
- `POST /api/v2/quiz-extensions/logout`: currently can cancel any `started` session named by raw cookie. Treat as part of the same boundary: clear cookies always, but only mutate/cancel a session when signed state validates.

Useful existing code/patterns:

- `TokenManager.generate_token(..., session_id=..., token_type='quiz_access')`, `verify_token()`, `hash_token()` in `backend-hormonia/app/domain/quizzes/session/token_manager.py`.
- `QuizSession.is_expired` and `set_expiration_date()` in `backend-hormonia/app/models/quiz.py`.
- `QuizLinkStatus` enum in `backend-hormonia/app/schemas/monthly_quiz.py` (`active`, `expired`, `used`, `cancelled`).
- `/q/{code}` resolver in `backend-hormonia/app/core/router_registry.py` already checks session terminal states, metadata `link_status`, metadata/session expiry, updates token hash/access counters, and redirects to a tokenized URL.
- `backend-hormonia/app/domain/quizzes/security/token_rotation.py` is not integrated, but its `submit_quiz_response_with_rotation` shows the right lookup invariant: match `session_id`, `patient_id`, `quiz_template_id`, then token hash.

### Tests and fixtures

Good fixture base:

- `backend-hormonia/tests/api/v2/security_boundary_helpers.py` creates two doctors, admin, patient A/B, and auth dependency overrides.
- Extend it or create local S03 helpers for a `QuizTemplate`, one `QuizSession` per patient, and a function to mint/store matching `TokenManager` tokens in `session.session_metadata`.

Existing tests likely needing updates:

- `backend-hormonia/tests/api/v2/test_monthly_quiz_compatibility.py` currently expects `GET /api/v2/quiz-extensions/session/active` to succeed with only a raw `quiz_session_id` cookie. S03 should update this to first call `/access`, capture the new state cookie, then recover; add a negative raw-cookie-only test.
- `backend-hormonia/tests/api/critical/test_quiz_submit.py` uses old base64 fake tokens and weak status assertions. Prefer a new focused S03 security suite with real `TokenManager` tokens instead of extending the weak integration assertions.

## Natural Seams / Suggested Task Split

1. **T01 — Authenticated quiz ownership boundary**
   - Files: `crud.py`, `tests/api/v2/test_quiz_link_session_boundary.py` (new or extended), maybe `security_boundary_helpers.py`.
   - Scope: create link/status/history/active links; assert Doctor A cannot touch/list Doctor B patient links; assigned doctor/admin still work.

2. **T02 — Public link/session validator**
   - Files: `public.py` or new `public_security.py`, tests for token hash, patient/session/template binding, expiration, cancelled/revoked link state.
   - Scope: token-based `/monthly/public/current` and `/monthly/public/{quiz_id}/submit` fail closed for mismatches and still accept a valid fixture.

3. **T03 — Signed session-state cookie compatibility**
   - Files: `public.py`, `test_monthly_quiz_compatibility.py`, focused S03 tests.
   - Scope: `/access` sets signed/opaque state; `/session/active`, `/submit`, and `/logout` reject raw/forged `quiz_session_id` alone and accept the state minted by `/access`.

4. **T04 — Denial diagnostics and closeout proof**
   - Files: token/log callsites if needed; focused tests using `caplog`/response-body checks.
   - Scope: denial responses/logs exclude patient names, phones, response values, tokens, cookie values, and secrets; run the focused/full S03 proof.

## First Proof

Highest-risk first failing test: prove raw cookie submission is no longer enough.

Recommended test shape in `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`:

1. Create two-doctor/two-patient fixture.
2. Create a published monthly quiz template and a `started` session for Patient B with a known question.
3. Without a valid access token/state cookie, set only `quiz_session_id=<patient_b_session_id>` on the client.
4. As an unauthenticated/public caller, POST `/api/v2/quiz-extensions/submit` with a response.
5. Expected after fix: 401/403 and no `QuizResponse` row; response/log body excludes Patient B name/phone, answer text, token/cookie values.

This proof blocks the most direct F-05 class: a forged/stolen raw session UUID driving public submit.

## Verification Plan

Focused commands from repository root (cwd-restricted equivalent; add or adjust paths after tests are written):

```bash
PYTHONPATH=backend-hormonia pytest \
  backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py \
  backend-hormonia/tests/api/v2/test_monthly_quiz_compatibility.py \
  backend-hormonia/tests/api/v2/test_phase25_messages_quiz_async.py \
  backend-hormonia/tests/test_quiz_session_expiration.py \
  -q
```

If the executor uses the backend directory as cwd, equivalent historical project command is:

```bash
cd backend-hormonia && pytest \
  tests/api/v2/test_quiz_link_session_boundary.py \
  tests/api/v2/test_monthly_quiz_compatibility.py \
  tests/api/v2/test_phase25_messages_quiz_async.py \
  tests/test_quiz_session_expiration.py \
  -q
```

Specific assertions to include:

- Doctor A `POST /api/v2/quiz-extensions/links/` for Patient B returns 403 and creates no session/token.
- Doctor A `GET /api/v2/quiz-extensions/patients/{patient_b}/status` and `/history` return 403 and do not leak patient name/session IDs.
- Doctor A `GET /api/v2/quiz-extensions/links/active/` excludes Patient B, Patient B name, phone, session ID, and token/link values; admin sees both.
- Token with mismatched URL quiz ID returns 401 (already partly present; keep real signed token).
- Token whose `session_id` belongs to another patient/template returns 401/403.
- Token whose hash is not equal to stored `session_metadata.token_hash` returns 401/403.
- Expired `session.expiration_date`, expired metadata `expires_at`, expired JWT `exp`, `link_status in {'cancelled','revoked','expired'}`, and terminal session statuses reject before response writes.
- Raw `quiz_session_id` cookie alone fails for `/session/active`, `/submit`, and no longer cancels foreign sessions via `/logout`.
- Valid fixture flow: create link or create matching session+token metadata; `/access` succeeds, sets state cookie, `/session/active` succeeds with both cookies, `/submit` stores one response, final question completes session.
- Denial diagnostics contain safe IDs/reason only; no patient names/phones, response text, tokens, cookies, or secrets.

## Risks / Watch-outs

- **Status mismatch is real.** Do not introduce more `in_progress`, `pending`, or `active` session statuses unless the model/migration is intentionally changed. Use `started` for active sessions and `session_metadata.link_status` for link activity.
- **Do not let compatibility preserve the vulnerability.** Updating `test_monthly_quiz_compatibility.py` is expected; raw cookie recovery should become negative unless the signed/opaque state cookie is also present.
- **JSONB `.astext` and SQLite tests.** Existing code uses JSONB `.astext` for short-code lookups. If focused tests run on SQLite and fail around JSON operators, prefer cross-dialect Python filtering for small test-scoped lookups or isolate the JSONB query behind an adapter.
- **Token prefix logging conflicts with R011.** Existing quiz audit/metrics modules still contain `token_prefix` patterns. S03 should at least avoid new usage and may need to remove `TokenManager` token-prefix warnings if caplog-based denial tests include invalid/expired token paths.
- **Public aggregate results are probably out of S03 scope.** `GET /monthly/public/{quiz_id}/results` returns aggregate data without auth. It should remain low priority unless findings explicitly require token-protecting aggregate results.

## Skill Discovery

Installed skills directly relevant to approach: `api-design`, `security-review`, `observability`, `verify-before-complete`, and project `react-best-practices` if frontend cookie handling is touched. No extra skill was installed.

`npx skills find` results for core technologies:

- FastAPI: promising optional skills include `npx skills add wshobson/agents@fastapi-templates` (16.7K installs), `npx skills add mindrally/skills@fastapi-python` (8.5K installs), `npx skills add jeffallan/claude-skills@fastapi-expert` (2.9K installs).
- SQLAlchemy: promising optional skills include `npx skills add bobmatnyc/claude-mpm-skills@sqlalchemy-orm` (871 installs), `npx skills add wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` (791 installs), `npx skills add cfircoo/claude-code-toolkit@sqlalchemy-postgres` (220 installs).
- PyJWT: no matching skill found.

## Sources Consulted

- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/crud.py`
- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py`
- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/_shared.py`
- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/__init__.py`
- `backend-hormonia/app/api/v2/router.py`
- `backend-hormonia/app/api/v2/_quiz_shared.py`
- `backend-hormonia/app/api/v2/patients_shared_helpers.py`
- `backend-hormonia/app/domain/quizzes/session/token_manager.py`
- `backend-hormonia/app/domain/quizzes/session/factory.py`
- `backend-hormonia/app/domain/quizzes/operations/link_ops.py`
- `backend-hormonia/app/domain/quizzes/queries/status.py`
- `backend-hormonia/app/domain/quizzes/security/token_rotation.py`
- `backend-hormonia/app/core/router_registry.py`
- `backend-hormonia/app/models/quiz.py`
- `backend-hormonia/app/schemas/monthly_quiz.py`
- `backend-hormonia/app/schemas/v2/quiz_extensions.py`
- `backend-hormonia/tests/api/v2/security_boundary_helpers.py`
- `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py`
- `backend-hormonia/tests/api/v2/test_monthly_quiz_compatibility.py`
- `backend-hormonia/tests/api/v2/test_phase25_messages_quiz_async.py`
- `backend-hormonia/tests/test_quiz_session_expiration.py`
- GSD exec scans: `7194c9e9-ccd3-4e2c-a794-ec6b2d2b9e71`, `ac6da52a-7d97-4fb8-8fdd-9a35398205d3`, `90165893-1768-45f4-9252-12632936d713`, `a3cbe740-ed3a-451e-931a-199be1aa9caf`, `64c56439-a5c3-4d60-b7b1-e862567e6f13`, `55d62c3d-52c5-4848-9056-fc96b4781585`.
