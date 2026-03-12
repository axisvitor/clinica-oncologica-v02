---
estimated_steps: 4
estimated_files: 7
---

# T04: Ship reset and first-access UX plus physician login route alignment

**Slice:** S03 — Frontend And Realtime Cutover
**Milestone:** M002

## Description

Turn the cutover into real product behavior by replacing the forgot-password placeholder with routed recovery screens and making the legacy physician entrypoint compatible with the canonical email-first auth surface instead of CRM/Firebase assumptions.

## Steps

1. Update `frontend-hormonia/src/pages/LoginPage.tsx` so “Esqueci minha senha” navigates to a real reset-request screen instead of opening the current support-email placeholder.
2. Add `frontend-hormonia/src/pages/auth/PasswordResetRequestPage.tsx` and `frontend-hormonia/src/pages/auth/PasswordResetConfirmPage.tsx`, wired to the S02 reset APIs with accessible form validation, generic success messaging, and actionable token-expired / invalid-token failure states.
3. Extend `frontend-hormonia/src/app/routes/routeConfig.ts` and `frontend-hormonia/src/app/routes/routeDefinitions.tsx`, and convert `frontend-hormonia/src/pages/medico/MedicoLogin.tsx` / `frontend-hormonia/src/app/routes/MedicoRoutes.tsx` into a compatibility entrypoint that lands on the canonical email-first login flow instead of CRM-only validation.
4. Run the recovery/route cutover suite and targeted login-page coverage until the browser surface offers real reset / first-access behavior and the physician entrypoint is coherent.

## Must-Haves

- [ ] The forgot-password path uses `reset-request` and `reset-confirm` endpoints, not support-email instructions or Firebase reset helpers.
- [ ] Recovery success messaging stays generic enough not to leak account-existence information, while error states remain actionable and inspectable.
- [ ] `/medico/login` no longer validates CRM-only identifiers or relies on Firebase-era copy/behavior.
- [ ] The routed public surface includes real password reset pages so admin-created first-access users have an actual browser path back into the product.

## Verification

- `cd frontend-hormonia && npx vitest run tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/unit/pages/LoginPage.comprehensive.test.tsx`
- Confirm the suite no longer sees the support-email placeholder or CRM-only physician login validation on the cutover path.

## Observability Impact

- Signals added/changed: Recovery UX now surfaces backend reset success/failure states explicitly instead of hiding them behind a static help message.
- How a future agent inspects this: Navigate the reset routes in the test harness or inspect the routed alert/form state in the focused integration suite.
- Failure state exposed: Expired token, invalid token, and request failure states become visible at the UI boundary rather than collapsing into “contact support.”

## Inputs

- `frontend-hormonia/tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx` — failing proof for reset UX and physician route alignment.
- `frontend-hormonia/src/pages/LoginPage.tsx` / `frontend-hormonia/src/pages/medico/MedicoLogin.tsx` — current placeholder and drifted doctor entrypoint surfaces to replace.

## Expected Output

- `frontend-hormonia/src/pages/LoginPage.tsx` — login page wired to real recovery navigation.
- `frontend-hormonia/src/pages/auth/PasswordResetRequestPage.tsx` and `frontend-hormonia/src/pages/auth/PasswordResetConfirmPage.tsx` — routed first-access / reset UX.
- `frontend-hormonia/src/app/routes/routeConfig.ts` and `frontend-hormonia/src/app/routes/routeDefinitions.tsx` — public route wiring for the recovery screens.
- `frontend-hormonia/src/pages/medico/MedicoLogin.tsx` / `frontend-hormonia/src/app/routes/MedicoRoutes.tsx` — compatibility physician entrypoint aligned to email-first auth.
