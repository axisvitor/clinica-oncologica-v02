# E2E Test Setup Instructions

## Session-first local-stack proof

The auth acceptance path in this repository runs on the local frontend + backend stack with first-party session auth only.

### 1. Install tooling

```bash
cd frontend-hormonia
npm install
npx playwright install
```

### 2. Start the backend

Use the backend environment already required for local development, but launch the process with the removed staff-auth provider variables blanked so the runtime proves the hard cut.

The exact shell command used for the slice proof is recorded in:

- `.gsd/milestones/M002/slices/S04/S04-PROOF.md`

### 3. Start the frontend

Run the frontend dev server against the local backend and local websocket endpoint.

The proof uses the same startup contract documented in `S04-PROOF.md` so the browser talks to the local backend instead of any remote environment.

### 4. Seed the proof user and generate a reset token

Before running the Playwright auth acceptance, make sure the proof user exists and export a fresh reset token for that user.

The exact seed and token commands are captured in:

- `.gsd/milestones/M002/slices/S04/S04-PROOF.md`

### 5. Run the acceptance spec

```bash
cd frontend-hormonia
npx playwright test tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts
```

## What the hard-cut spec verifies

- public system config does not advertise retired browser-auth settings
- login works with email + password
- reload restores the active session
- password reset request stays generic
- reset-confirm accepts a real token
- in-app password change revokes the active session and returns to login
- UI logout works
- logout-all revokes the remaining browser session
- no provider-era `/auth/firebase/verify` network traffic is emitted during the flow

## Failure checklist

If the spec fails, inspect in this order:

1. `bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`
2. `.gsd/milestones/M002/slices/S04/S04-PROOF.md`
3. Playwright trace / HTML report in `frontend-hormonia/test-results/`
4. backend `uvicorn` logs
5. frontend Vite logs
