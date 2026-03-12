# Hormonia E2E Test Suite

This directory contains Playwright coverage for the frontend running against the real backend.

## Current auth model

Staff authentication is session-first. The browser flow covered here is:

1. Login with email + password
2. Restore the session after reload
3. Request password recovery
4. Confirm password reset
5. Change the password from the security settings page
6. Logout and revoke all sessions

The canonical acceptance proof for this flow is:

- `tests/e2e/auth/session-first-hard-cut.spec.ts`
- `.gsd/milestones/M002/slices/S04/S04-PROOF.md`

## Quick start

```bash
cd frontend-hormonia
npm install
npx playwright install
```

Start the local stack with the legacy browser/admin auth variables blank at process launch, then run:

```bash
npx playwright test tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts
```

## Required assumptions for the hard-cut proof

The session-first acceptance spec expects:

- frontend available at `http://localhost:5173`
- backend available at `http://localhost:8000`
- a seeded staff user with email/password fixtures
- a reset token generated for that same user before the test starts

The rerunnable seed, token-generation, and startup commands live in:

- `.gsd/milestones/M002/slices/S04/S04-PROOF.md`

## Useful commands

```bash
# List the hard-cut spec only
npx playwright test --list tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts

# Run the spec in headed mode
npx playwright test tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts --headed

# Open the latest HTML report
npx playwright show-report test-results/e2e-report
```

## Scope notes

- `tests/e2e/auth/session-first-hard-cut.spec.ts` is the operator-facing acceptance proof for staff auth.
- Older provider-specific staff-auth guidance has been retired; do not reintroduce it in this directory.
- When the hard-cut spec fails, inspect `S04-PROOF.md`, Playwright traces, and backend/frontend logs before changing selectors.
