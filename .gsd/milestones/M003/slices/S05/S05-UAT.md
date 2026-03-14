# S05: Integrated Proof And Structural Closeout — UAT

**Milestone:** M003
**Written:** 2026-03-13T14:15:57-03:00
**Status:** partial / red closeout — structural gate and direct compat proof are partially green, but legacy `/session/logout` is still blocking final acceptance.

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S05 acceptance depends on both the replayed structural gate from T01 and the assembled local-stack runtime proof from T02/T03. This artifact records both, and it leaves the unresolved runtime blocker explicit instead of implying end-to-end closure.

## Preconditions

Local assembled stack used for the runtime proof:

### Backend

```bash
cd backend-hormonia && \
  FIREBASE_ADMIN_PROJECT_ID='' \
  FIREBASE_ADMIN_CLIENT_EMAIL='' \
  FIREBASE_ADMIN_PRIVATE_KEY='' \
  WHATSAPP_WUZAPI_TOKEN='<redacted-local-mock>' \
  WHATSAPP_WUZAPI_USE_MOCK='true' \
  uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend-hormonia && \
  VITE_API_URL='http://localhost:8000' \
  VITE_API_BASE_URL='http://localhost:8000' \
  VITE_WS_BASE_URL='ws://localhost:8000/ws' \
  VITE_FIREBASE_API_KEY='' \
  VITE_FIREBASE_PROJECT_ID='' \
  VITE_FIREBASE_APP_ID='' \
  VITE_FIREBASE_AUTH_DOMAIN='' \
  npm run dev -- --host 0.0.0.0 --port 5173
```

Replay-safe local proof artifacts:
- `/tmp/gsd-s05-t02-proof.env` — masked seeded-user contract
- `/tmp/gsd-s05-runtime-proof.json` — sanitized direct compat results
- `/tmp/gsd-s05-browser-bootstrap` — browser bootstrap helper that avoids printing credentials

Runtime truth checks that stayed green:
- `http://localhost:8000/health/ready`
  - `status=ready`
  - dependencies included `database`, `redis`, `session_auth`
  - no `firebase` dependency present
- `http://localhost:8000/api/v2/system/config`
  - returned current public config keys without Firebase config residue

## Smoke Test

Quick acceptance checkpoint for this slice:
1. Replay the focused structural gate from T01.
2. Prove canonical login + canonical verify + Bearer fallback + invalid legacy `session/validate` on the assembled stack.
3. Prove live legacy `session/logout` and then finish `/admin`, `/dashboard`, and `/whatsapp` browser smoke.

Current result:
- Steps 1 and 2 are green.
- Step 3 is red at `DELETE /session/logout`, so the routed browser smoke was not claimed green afterward.

## Test Cases

### 1. Structural closeout gate stays green on the S05 branch

1. Run:
   - `cd frontend-hormonia && npm run test -- tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts tests/unit/types-validation.test.ts tests/monthly-quiz/useMonthlyQuiz.spec.tsx`
   - `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
   - `cd frontend-hormonia && npm run typecheck && npm run build`
   - `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py tests/integration/test_auth_hard_cut_end_to_end.py`
   - `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`
   - `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`
2. Confirm all commands pass.
3. **Expected:** the S04 cleanup boundary is still green before any runtime claim is made.

### 2. Canonical auth/session and Bearer fallback still work on the assembled backend

1. Use the seeded proof user from `/tmp/gsd-s05-t02-proof.env`.
2. Run direct assembled-stack probes against:
   - `POST /api/v2/auth/login`
   - cookie-backed `GET /api/v2/auth/verify-session`
   - `GET /api/v2/auth/verify-session` with `Authorization: Bearer <session_id>`
   - `GET /api/v2/users/me` with `Authorization: Bearer <session_id>`
3. **Expected:** all four return `200` on the local no-Firebase stack.

Captured result:
- `POST /api/v2/auth/login` → `200`
- cookie-backed `GET /api/v2/auth/verify-session` → `200`
- `Authorization: Bearer <session_id>` on `GET /api/v2/auth/verify-session` → `200`
- `Authorization: Bearer <session_id>` on `GET /api/v2/users/me` → `200`

### 3. Retained legacy compat checks stay within the documented contract

1. Send invalid session input to `GET /session/validate`.
2. Send a live session created by canonical login to `DELETE /session/logout`.
3. Check the same live session again with `GET /session/validate`.
4. **Expected:** invalid `session/validate` returns `200` with `valid:false`, and live `session/logout` returns a clean success response that revokes the session.

Captured result:
- invalid `GET /session/validate` → `200` with `valid:false`
- live `DELETE /session/logout` → `422`
- follow-up `GET /session/validate` on that same session → `200` with `valid:false`

Exact live `DELETE /session/logout` response body captured in T03:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["query", "token"],
      "msg": "Field required",
      "input": null
    }
  ],
  "error": "VALIDATION_ERROR",
  "message": "Input validation failed",
  "details": {
    "errors": [
      {
        "field": "query.token",
        "message": "Field required",
        "type": "missing",
        "details": null
      }
    ]
  },
  "request_id": null,
  "timestamp": "2026-03-13T14:12:19.838161-03:00"
}
```

Interpretation for the handoff:
- the retained `/session/logout` island is not green
- the live failure shape points at request/dependency transport mismatch (`query.token`) rather than a vague runtime crash
- the same session becoming invalid by the next `session/validate` call means response contract and side effect are currently out of sync

### 4. Routed browser entrypoints

Target routed entrypoints for final acceptance:
- `/admin`
- `/dashboard`
- `/whatsapp`

Expected routed proof once the compat blocker is fixed:
1. `/admin` redirects to `/login` when unauthenticated.
2. Successful login returns to the intended route.
3. `/dashboard` completes a successful `/api/v2/dashboard/main` fetch without fatal render error state.
4. `/admin` authenticated root renders for the staff user.
5. `/whatsapp` completes a successful `/api/v2/monitoring/wuzapi/session/status` fetch on mocked WuzAPI.

Current result:
- not claimed green in this closeout
- these checks were left pending after the retained legacy `/session/logout` blocker turned the slice red

## Edge Cases

### Invalid legacy session validation

1. Call `GET /session/validate` with invalid session input.
2. **Expected:** `200` with `valid:false` rather than a canonical auth-style `401`.

Captured result:
- passed exactly as expected

### Conditional Playwright acceptance

1. Seeded-user contract availability was checked first.
2. The seeded-user contract was available locally, so fixture availability was **not** the reason the Playwright pass stopped.
3. **Expected:** only run the Chromium Playwright pass once the retained compatibility proof ahead of it is clean enough to make the browser result meaningful.

Captured result:
- `cd frontend-hormonia && npx playwright test tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts --project=chromium` was intentionally not claimed green in the final closeout because the slice stopped after the actionable live `/session/logout` blocker was isolated.

## Failure Signals

- `DELETE /session/logout` returns `422` with missing `query.token`
- `GET /session/validate` stops returning `200` with `valid:false` for invalid sessions
- `Authorization: Bearer <session_id>` stops working on canonical auth/session paths
- `/admin` does not redirect through `/login` correctly
- `/api/v2/dashboard/main` fails or the dashboard falls into fatal render error state
- `/api/v2/monitoring/wuzapi/session/status` fails on `/whatsapp`

## Requirements Proved By This UAT

- none fully — this UAT advances `R037`, `R038`, and `R039`, but it does not close them because legacy `/session/logout` is still red and the routed `/admin`, `/dashboard`, and `/whatsapp` smoke is still pending.

## Not Proven By This UAT

- clean live revocation behavior for legacy `/session/logout`
- final browser/runtime proof for `/admin`, `/dashboard`, and `/whatsapp`
- the seeded-user Chromium Playwright acceptance path as a green closeout signal
- milestone closure for `R037`, `R038`, and `R039`

## Notes for Tester

- Treat `.gsd/milestones/M003/slices/S05/S05-SUMMARY.md` and this UAT as the authoritative closeout pair for S05.
- `S05` can stay marked complete in `.gsd/milestones/M003/M003-ROADMAP.md` as a truthful red handoff, but do not move `R037`, `R038`, `R039` in `.gsd/REQUIREMENTS.md` until legacy `/session/logout` is explained or fixed and the routed `/admin`, `/dashboard`, `/whatsapp` smoke is rerun.
- The most direct next replay is: fix or rebind the legacy `/session/logout` CSRF contract, rerun the direct compat probes, then run the pending browser/Playwright proof.
