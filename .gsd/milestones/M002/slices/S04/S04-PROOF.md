# S04 Proof — Hard Cut Cleanup And Integrated Proof

## Scope

This artifact records the final T05 cleanup and verification work for the session-first hard cut.

Source of truth for the slice:

- `.gsd/milestones/M002/slices/S04/S04-PLAN.md`
- `.gsd/milestones/M002/slices/S04/tasks/T05-PLAN.md`

## What T05 changed

Repository-facing Firebase-auth staff-login guidance was removed or rewritten toward the session-first proof surface.

Updated guidance/proof files:

- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts`
- `frontend-hormonia/tests/e2e/playwright.config.e2e.ts`
- `frontend-hormonia/tests/e2e/README.md`
- `frontend-hormonia/tests/e2e/SETUP_INSTRUCTIONS.md`
- `docs/frontend/guides/api/API_GUIDE.md`
- `docs/frontend/guides/configuration/ENVIRONMENT_GUIDE.md`
- `docs/frontend/guides/deployment/DEPLOYMENT_GUIDE.md`
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`

## Local-stack assumptions used for proof

### Backend launch

The backend was started with Firebase staff-auth env vars intentionally blank, while also setting a local WuzAPI token/mock flag because that startup validation is unrelated to staff auth but required for the process to boot.

```bash
cd backend-hormonia && \
  FIREBASE_ADMIN_PROJECT_ID='' \
  FIREBASE_ADMIN_CLIENT_EMAIL='' \
  FIREBASE_ADMIN_PRIVATE_KEY='' \
  WHATSAPP_WUZAPI_TOKEN='local-proof-token' \
  WHATSAPP_WUZAPI_USE_MOCK='true' \
  uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend launch

The frontend was started against the local backend/websocket endpoints with Firebase browser-auth vars blank.

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

### E2E seeded user contract

Do **not** persist plaintext passwords or reset tokens in repo artifacts. For replay, export fresh values per run and seed/update the user in the local database before executing the browser proof.

Required env vars for the Playwright proof:

```bash
export E2E_SESSION_FIRST_EMAIL='session-first-proof@example.com'
export E2E_SESSION_FIRST_PASSWORD='<set-per-run>'
export E2E_SESSION_FIRST_ROTATED_PASSWORD='<set-per-run>'
export E2E_SESSION_FIRST_RESET_TOKEN='<generated-per-run>'
```

A one-off helper can seed the user and emit a fresh reset token using:

- `backend-hormonia/app.database.SessionLocal`
- `backend-hormonia/app.models.user.User`
- `backend-hormonia/app.utils.security.get_password_hash`
- `backend-hormonia/app.core.security.create_password_reset_token`

## Verification results

### Static residue guard

```bash
bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh
```

Result: **PASS**

Observed output:

```text
verify-no-firebase-auth.sh: session-first staff-auth hotspots are free of Firebase-auth residue.
```

### Frontend focused vitest suites

```bash
cd frontend-hormonia && \
  npx vitest run \
    tests/integration/auth/session-first-cutover.test.tsx \
    tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx \
    tests/integration/realtime/session-websocket-cutover.test.ts \
    tests/integration/initialization/session-auth-operational-surfaces.test.tsx \
    tests/integration/auth/hard-cut-cleanup-proof.test.tsx
```

Result: **PASS** (`5 files, 18 tests`)

### Frontend production build

```bash
cd frontend-hormonia && npm run build
```

Result: **PASS**

### Backend focused pytest suites

```bash
cd backend-hormonia && \
  pytest \
    tests/api/test_websocket_session_auth_contract.py \
    tests/api/v2/test_auth_local_login.py \
    tests/api/v2/test_auth_password_recovery.py \
    tests/api/v2/test_auth_hard_cut_cleanup.py \
    tests/api/v2/test_system_auth_hard_cut_operational.py \
    tests/integration/test_local_auth_core_flow.py \
    tests/integration/test_password_reset_migration_flow.py \
    tests/integration/test_auth_hard_cut_end_to_end.py -q
```

Result: **PASS**

Note: the integrated backend proof was updated so `logout-all` is exercised **after re-login**, because the shipped first-party password-change behavior revokes the current session immediately.

### Local runtime truth checks

#### Readiness

```bash
curl http://localhost:8000/health/ready
```

Observed:

- `status=ready`
- dependencies included `database`, `redis`, `session_auth`
- no `firebase` dependency present

#### Public config

```bash
curl http://localhost:8000/api/v2/system/config
```

Observed:

- payload contained `VITE_API_BASE_URL`, `VITE_API_URL`, `VITE_WS_BASE_URL`, `VITE_ENVIRONMENT`, etc.
- `firebase` did **not** appear anywhere in the JSON payload

### Playwright test discovery

The e2e config had to use `testDir: '.'` because the config file itself lives under `tests/e2e/`; with the previous nested `./tests/e2e` value, the T05 acceptance command discovered zero tests.

```bash
cd frontend-hormonia && \
  npx playwright test --list --config tests/e2e/playwright.config.e2e.ts
```

Result: **PASS** for discovery.

The session-first hard-cut spec is now discoverable at:

- `auth/session-first-hard-cut.spec.ts`

### Playwright browser acceptance

Command used:

```bash
cd frontend-hormonia && \
  E2E_BASE_URL='http://localhost:5173' \
  E2E_SESSION_FIRST_EMAIL="$E2E_SESSION_FIRST_EMAIL" \
  E2E_SESSION_FIRST_PASSWORD="$E2E_SESSION_FIRST_PASSWORD" \
  E2E_SESSION_FIRST_ROTATED_PASSWORD="$E2E_SESSION_FIRST_ROTATED_PASSWORD" \
  E2E_SESSION_FIRST_RESET_TOKEN="$E2E_SESSION_FIRST_RESET_TOKEN" \
  VITE_FIREBASE_API_KEY='' \
  VITE_FIREBASE_PROJECT_ID='' \
  VITE_FIREBASE_APP_ID='' \
  VITE_FIREBASE_AUTH_DOMAIN='' \
  FIREBASE_ADMIN_PROJECT_ID='' \
  FIREBASE_ADMIN_CLIENT_EMAIL='' \
  npx playwright test auth/session-first-hard-cut.spec.ts \
    --config tests/e2e/playwright.config.e2e.ts \
    --project=chromium
```

Result: **FAIL**

Current failure state:

- the spec reaches the login page and submits credentials
- the page remains on `/login` instead of transitioning to `/dashboard`
- a direct backend login probe against `POST /api/v2/auth/login` returns `200 OK` with a valid `session_id` and admin user payload on the same local stack

This means the remaining red signal is in the real browser acceptance path, not the backend auth contract itself.

## Most useful diagnostics when replaying

### Browser artifacts

Inspect the latest Playwright failure artifacts under:

- `frontend-hormonia/test-results/`
- specifically the generated directory for `auth-session-first-hard-cut...`

Useful files there:

- `test-failed-1.png`
- `video.webm`
- `error-context.md`

### Backend runtime probes

Use these first when auth or readiness looks wrong:

```bash
curl http://localhost:8000/health/ready
curl http://localhost:8000/api/v2/system/config
curl -H 'Content-Type: application/json' \
  -X POST http://localhost:8000/api/v2/auth/login \
  --data '{"email":"<seeded-email>","password":"<seeded-password>","remember_me":true}'
```

### Hotspots to inspect for the remaining browser failure

- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts`
- `frontend-hormonia/src/app/providers/AuthContext.tsx`
- `frontend-hormonia/src/features/auth/ProtectedRoute.tsx`
- `frontend-hormonia/src/lib/api-client/auth.ts`
- `frontend-hormonia/src/lib/api-client/core.ts`

### Background-process logs used during proof

- backend process label: `s04-backend-no-firebase`
- frontend process label: `s04-frontend-no-firebase`

## Summary

What is green:

- static residue cleanup
- repository-facing Firebase-auth guidance cleanup
- frontend focused auth/runtime proof suites
- frontend production build
- backend focused auth/runtime proof suites
- local-stack readiness/config truth checks without Firebase staff-auth env vars
- Playwright spec discovery and reproducible local-stack execution notes

What is still red:

- the final real-browser acceptance path remains blocked because the Playwright login attempt does not advance from `/login` to `/dashboard`, even though the backend login endpoint succeeds directly on the same stack
