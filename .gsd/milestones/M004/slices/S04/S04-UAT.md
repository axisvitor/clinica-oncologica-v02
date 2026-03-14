# S04: Superfícies legadas de auth/sessão aposentadas — UAT

**Milestone:** M004
**Written:** 2026-03-14T16:31:44-03:00

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S04 proves a backend contract cut and route retirement boundary. The slice definition is satisfied by focused pytest plus the backend residue verifier, not by human browser interaction or a live assembled stack.

## Preconditions

- The repo is at the S04 tip on branch `gsd/M004/S04`.
- Backend dependencies are installed in `backend-hormonia/`.
- No local backend/frontend server needs to be running for this slice replay.
- The tester can run commands from the repo root.

## Smoke Test

Run:

`bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`

Expected: the output lists only the approved backend residue categories/files for `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query`, then ends with `RESULT: --check backend OK`.

## Test Cases

### 1. Official auth chokepoints stay cookie-only and reject legacy transport

1. Run:
   - `cd backend-hormonia`
   - `pytest -q tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py`
2. Inspect the output.
3. **Expected:** 18 tests pass. The canonical cookie-backed session flow remains green, login no longer emits `X-Session-ID`, header-only and session-as-Bearer HTTP requests fail with the explicit cookie-required/invalid-session surfaces, and websocket auth still uses `AUTH_WEBSOCKET_SESSION_INVALID` for rejected legacy transport and `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED` for lookup failures.

### 2. Helper consumers and acceptance proof no longer hide behind dual transport

1. Run:
   - `cd backend-hormonia`
   - `pytest -q tests/api/v2/test_localization.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/integration/test_auth_hard_cut_end_to_end.py`
2. Inspect the output.
3. **Expected:** 42 tests pass. Localization, password-change/hard-cut helpers, and the integrated auth flow all authenticate with cookie + CSRF only; header-only requests are rejected explicitly; and no test depends on sending both session cookie and `X-Session-ID` together.

### 3. Root `/session/*` is retired intentionally, not by drift

1. Run:
   - `cd backend-hormonia`
   - `pytest -q tests/auth/test_session_validation.py`
2. Inspect the output.
3. **Expected:** 5 tests pass. Representative `/session/*` routes, unknown subpaths, and requests carrying legacy headers/cookies all return HTTP 410 with the stable retirement code `AUTH_LEGACY_SESSION_ROUTE_RETIRED`, the retired path, and the canonical replacement prefix instead of 404 drift or legacy route behavior.

### 4. The backend residue boundary matches the post-S04 runtime honestly

1. From the repo root, run:
   - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
   - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
2. Inspect both outputs.
3. **Expected:** both commands pass. The backend report/check should no longer mention approved `root_legacy_session` or Firebase-narrative residue. They should list only the remaining approved backend categories: `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query`.

## Edge Cases

### Header-only auth must still fail when ambient cookies are absent

1. Run the Case 2 command pack.
2. **Expected:** the integrated hard-cut proof passes only because it clears the client cookie jar before the header-only probe. If a future regression leaves cookies in place, the probe stops being trustworthy even if the test command still looks right.

### Websocket invalid-session vs lookup-failure diagnostics must stay distinct

1. Run the Case 1 command pack.
2. **Expected:** tests still distinguish rejected legacy/invalid session attempts (`AUTH_WEBSOCKET_SESSION_INVALID`) from lookup exceptions (`AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED`). A collapse to one generic websocket auth failure is a regression on this slice boundary.

### Unknown `/session/*` paths must still tombstone

1. Run the Case 3 command pack.
2. **Expected:** even unknown or obviously dead subpaths under `/session/*` return the same 410 tombstone payload. A 404 here means the retirement surface drifted; a 2xx/401 with old semantics means the legacy router revived.

## Failure Signals

- Any failure in `tests/api/v2/test_auth_session_priority.py`, `tests/api/test_websocket_session_auth_contract.py`, or `tests/api/v2/test_auth_local_login.py` mentioning `X-Session-ID`, bearer session transport, websocket `session_id`, or missing canonical cookie behavior.
- Any failure in `tests/api/v2/test_localization.py`, `tests/api/v2/test_auth_hard_cut_cleanup.py`, or `tests/integration/test_auth_hard_cut_end_to_end.py` that passes only when cookie + header are both present.
- `tests/auth/test_session_validation.py` returning 404 or old `/session/*` behavior instead of HTTP 410 with `AUTH_LEGACY_SESSION_ROUTE_RETIRED`.
- `verify-runtime-residue.sh --report backend` or `--check backend` surfacing `root_legacy_session`, Firebase narrative residue, or any unexpected new backend category/file hit.

## Requirements Proved By This UAT

- R048 — Confirms the official staff auth/session runtime now uses one canonical cookie-backed contract and no longer officially accepts `/session/*`, `X-Session-ID`, session-as-Bearer, or websocket `session_id` fallback.
- R047 — Supports the broader no-Firebase runtime goal by shrinking the official backend auth/session boundary to the canonical contract and retiring the old transport surfaces explicitly.
- R049 — Supports the identity convergence goal by removing alternative transport paths that could bypass the canonical `user_id`-centered session flow.

## Not Proven By This UAT

- Full removal of backend/adjacent `firebase_uid` functional residue across cache, audit, adapters, and related seams; that belongs to S05.
- Assembled local stack proof with Firebase Auth envs blank across `/login`, `/dashboard`, `/admin`, and `/whatsapp`; that belongs to S06.
- Schema/Alembic cleanup and final migration-state convergence; that belongs to M005.

## Notes for Tester

- The backend pytest runs still emit the existing `pytest_asyncio` loop-scope deprecation warning. It is known and non-blocking for S04.
- A green backend residue report/check is expected to keep listing some approved `firebase_uid` and rejection/detection anchors after S04. That is acceptable here; only unexpected new residue or revived `root_legacy_session`/Firebase-narrative entries would fail the slice.
- If a header-only rejection assertion starts passing unexpectedly, check for leaked cookies in the test client before assuming the runtime contract reopened.
