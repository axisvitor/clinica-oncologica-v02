# S05: Integrated Proof And Structural Closeout — UAT

**Milestone:** M003
**Written:** 2026-03-13T22:17:00-03:00
**Status:** passed — structural gate, assembled auth/session/logout proof, seeded-user Chromium acceptance, and routed `/dashboard` / `/admin` / `/whatsapp` smoke are green on the current branch.

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S05 closes only when the cleanup boundary stays green, the assembled no-Firebase runtime still honors the retained auth/session contract, and the affected routed surfaces render successfully in-browser. This artifact captures all three.

## Preconditions

Local assembled stack used for the final replay:

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
- `/tmp/gsd-s05-runtime-proof.json` — earlier sanitized compat results
- `/tmp/gsd-s05-browser-bootstrap` — browser/bootstrap helper that avoids printing credentials
- `.gsd/milestones/M003/M003-VERIFY.json` — authoritative final verification artifact for the milestone closeout

Runtime truth checks:
- `http://localhost:8000/health/ready`
  - `status=ready`
  - dependencies included `database`, `redis`, `session_auth`
  - no `firebase` dependency present
- `http://localhost:8000/api/v2/system/config`
  - returned current public config keys without Firebase config residue

## Smoke Test

Quick acceptance checkpoint for this slice:
1. Replay the focused structural gate from T01.
2. Prove canonical login + canonical verify + Bearer fallback + legacy `/session/logout` on the assembled stack.
3. Prove the seeded-user browser acceptance spec and routed `/dashboard`, `/admin`, and `/whatsapp` smoke.

Current result:
- Steps 1, 2, and 3 are green.

## Test Cases

### 1. Structural closeout gate stays green on the S05 branch

Run:
- `cd frontend-hormonia && npm run test -- tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts tests/unit/types-validation.test.ts tests/monthly-quiz/useMonthlyQuiz.spec.tsx`
- `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- `cd frontend-hormonia && npm run typecheck && npm run build`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`

Expected:
- all commands pass
- the cleanup boundary remains green before runtime claims are made

Captured result:
- passed

### 2. Canonical auth/session and Bearer fallback still work on the assembled backend

Run direct assembled-stack probes against:
- `POST /api/v2/auth/login`
- cookie-backed `GET /api/v2/auth/verify-session`
- `GET /api/v2/auth/verify-session` with `Authorization: Bearer <session_id>`
- `GET /api/v2/users/me` with `Authorization: Bearer <session_id>`

Expected:
- all return `200` on the local no-Firebase stack

Captured result:
- `POST /api/v2/auth/login` → `200`
- cookie-backed `GET /api/v2/auth/verify-session` → `200`
- `Authorization: Bearer <session_id>` on `GET /api/v2/auth/verify-session` → `200`
- `Authorization: Bearer <session_id>` on `GET /api/v2/users/me` → `200`

### 3. Retained legacy compat checks stay within the documented contract

Run:
1. Send invalid session input to `GET /session/validate`.
2. Send a live session created by canonical login to `DELETE /session/logout` with CSRF token.
3. Check the same live session again with `GET /session/validate`.

Expected:
- invalid `session/validate` returns `200` with `valid:false`
- live `session/logout` returns a clean success response
- the same session is invalid afterward

Captured result:
- invalid `GET /session/validate` → `200` with `valid:false`
- live `DELETE /session/logout` → `200` with `success=true`, `sessions_deleted=1`, `message="Session logged out successfully"`
- follow-up `GET /session/validate` on that same session → `200` with `valid:false`

### 4. Seeded-user browser acceptance proves the no-Firebase staff-auth contract end to end

Run:

```bash
cd frontend-hormonia && \
  source /tmp/gsd-s05-browser-bootstrap \
  ./node_modules/.bin/playwright test tests/e2e/auth/session-first-hard-cut.spec.ts \
    --config tests/e2e/playwright.config.e2e.ts \
    --project=chromium
```

Expected:
- one Chromium spec passes covering config truth, login, restore, reset, password rotation, logout, and logout-all

Captured result:
- passed (`1 passed`)

### 5. Routed browser entrypoints render successfully on the live frontend

Target entrypoints:
- `/dashboard`
- `/admin`
- `/whatsapp`

Expected:
1. login reaches `/dashboard`
2. `/admin` renders authenticated admin root
3. `/whatsapp` renders the WhatsApp integration surface

Captured result:
- `/dashboard` → heading `Dashboard`
- `/admin` → heading `Admin Dashboard`
- `/whatsapp` → heading `WhatsApp Integration`
- recorded in `.gsd/milestones/M003/M003-VERIFY.json`

## Edge Cases

### Invalid legacy session validation

Expected:
- `GET /session/validate` with invalid session input returns `200` with `valid:false`

Captured result:
- passed exactly as expected

### Conditional Playwright acceptance

Expected:
- use the seeded-user contract only when available locally and keep it masked from repo artifacts

Captured result:
- seeded-user contract was available locally
- Chromium acceptance ran and passed using the masked bootstrap helper

## Failure Signals

- `DELETE /session/logout` stops returning a clean success response
- `GET /session/validate` stops returning `200` with `valid:false` for invalid sessions
- `Authorization: Bearer <session_id>` stops working on canonical auth/session paths
- seeded-user Chromium acceptance fails on login/restore/reset/logout flows
- `/dashboard`, `/admin`, or `/whatsapp` stops rendering its expected routed surface
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all` fails

## Requirements Proved By This UAT

- R037 — visible contracts stayed stable across auth/session/logout and the routed dashboard/admin/WhatsApp surfaces
- R038 — the cleanup is safer to maintain because the narrowed seams are backed by replayable current-state proof
- R039 — milestone closeout rests on focused suites plus direct runtime and browser smoke evidence

## Not Proven By This UAT

- anything beyond the targeted M003 surfaces; this UAT is structural-cleanup acceptance, not a full product regression sweep

## Notes for Tester

- Use `.gsd/milestones/M003/M003-VERIFY.json` as the current authoritative closeout artifact; it supersedes the earlier red S05 handoff.
- The routed browser smoke still logs non-blocking `TaskHealthIndicator` queue-status fetch errors plus the usual unauthenticated restore 401 before login. Those did not block milestone closure because the target routes rendered and the auth/session contract stayed green.
- If a future branch reopens `auth_session.py`, the first replay should be: `verify-evidence-map.sh --check all`, the direct assembled auth/logout probe, then the seeded-user Chromium spec.
