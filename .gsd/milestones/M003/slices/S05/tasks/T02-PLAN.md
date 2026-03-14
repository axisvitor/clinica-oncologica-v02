---
estimated_steps: 5
estimated_files: 6
---

# T02: Prove assembled runtime continuity on the local stack

**Slice:** S05 — Integrated Proof And Structural Closeout
**Milestone:** M003

## Description

Replay the real staff-auth/browser/runtime path on the current routed surfaces instead of trusting stale admin-era e2e coverage. This task stands up the no-Firebase local stack, keeps WuzAPI mocked so the WhatsApp route exercises a real status surface, re-proves the retained compatibility islands, and captures browser/runtime evidence for `/admin`, `/dashboard`, and `/whatsapp` on the actual assembled app.

## Steps

1. Start the backend and frontend from the M002 no-Firebase proof recipe, keeping the frontend on `npm run dev` at port 5173 and enabling mocked WuzAPI so `/whatsapp` can load meaningful status data.
2. Prepare the seeded staff user/session fixture needed for session-first login and for direct compatibility checks against `/session/*` and bearer fallback.
3. Re-prove retained compatibility behavior directly: invalid `/session/validate`, live-session `/session/logout`, and canonical auth acceptance of `Authorization: Bearer <session_id>`.
4. Run `tests/e2e/auth/session-first-hard-cut.spec.ts` on Chromium only when the seeded-user contract is available; if it is not, record the explicit fixture reason for skipping instead of widening scope.
5. Use browser-tool assertions plus network/console diagnostics to smoke `/admin`, `/dashboard`, and `/whatsapp`, then write the outcome and any skips/blockers into `T02-SUMMARY.md` and `S05-UAT.md`.

## Must-Haves

- [ ] Current session-first routes are proven on the assembled local stack, not only by focused suites.
- [ ] Retained compatibility islands (`/session/*`, bearer fallback) are re-proven or explicitly bounded with evidence and a concrete reason.

## Verification

- `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `cd frontend-hormonia && npx playwright test tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts --project=chromium` when the seeded-user fixture contract is available
- Browser assertions and network checks captured in `S05-UAT.md` for `/admin` → `/login` → intended route, successful `/api/v2/dashboard/main`, successful `/api/v2/monitoring/wuzapi/session/status`, `/session/validate` invalid-session `200` + `valid:false`, `/session/logout` revocation, and bearer session fallback acceptance.

## Observability Impact

- Signals added/changed: no new runtime signals; this task consumes existing verifier output, backend/frontend readiness logs, browser console/network logs, and auth/session HTTP responses, then records them in slice artifacts.
- How a future agent inspects this: replay the local-stack start commands from the M002 proof recipe, read `S05-UAT.md`, and inspect the recorded network requests and compat-response bodies before reopening refactor scope.
- Failure state exposed: redirect drift, route-level request failures, missing mocked-infrastructure status, invalid compat-response semantics, and seeded-fixture unavailability are all surfaced explicitly in the task summary/UAT instead of hiding behind a generic smoke failure.

## Inputs

- `.gsd/milestones/M002/slices/S04/S04-PROOF.md` — reusable local-stack startup recipe and seeded-user contract for no-Firebase staff auth.
- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts` — canonical real-browser auth acceptance aligned to the current session-first contract.
- `backend-hormonia/tests/auth/test_session_validation.py` — retained `/session/*` compatibility contract.
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` — backend end-to-end auth/session contract, including the canonical auth path that still needs bearer-fallback proof.

## Expected Output

- `.gsd/milestones/M003/slices/S05/tasks/T02-SUMMARY.md` — exact local-stack commands, compat checks, browser assertions, skip reasons, and blocker diagnostics.
- `.gsd/milestones/M003/slices/S05/S05-UAT.md` — assembled proof log for `/admin`, `/dashboard`, `/whatsapp`, `/session/*`, and bearer fallback on the current routed runtime.
