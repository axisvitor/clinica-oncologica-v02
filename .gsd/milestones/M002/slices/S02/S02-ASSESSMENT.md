---
id: S02
parent: M002
milestone: M002
status: assessed
assessed_at: 2026-03-11T23:20:01-03:00
conclusion: roadmap_still_valid
---

# S02 Assessment — roadmap still holds

No roadmap rewrite is needed after S02.

S02 appears to have retired the migration/recovery risk it was meant to retire: the task evidence shows public `reset-request` / `reset-confirm`, shared password-reset orchestration, canonical `user_id` session revocation, and admin first-access / admin-triggered recovery all shipped with the planned focused pytest coverage green.

## Success-criterion coverage check

- Staff users can log in with email/password through the product’s own auth flow and reach protected dashboard/API surfaces without Firebase token exchange. → S03, S04
- Existing users regain access through reset/first-access email flows instead of manual account recreation. → S04
- Session continuity features such as remember-me, verify-session, logout, and protected-route auth keep working after the provider switch. → S03, S04
- Frontend dashboard and realtime auth no longer depend on Firebase SDK state or Firebase tokens. → S03, S04
- Firebase Auth runtime/config dependencies are removed or tombstoned, and integrated verification proves the assembled auth system works end to end. → S04

Coverage check passes: every success criterion still has at least one remaining owning slice.

## Why the remaining slices still make sense

Concrete remaining work still lines up with the existing S03/S04 split:

- `frontend-hormonia/src/app/providers/AuthContext.tsx` still bootstraps auth through `firebaseAuthLazy`, Firebase auth listeners, Firebase token refresh, and Firebase-backed WebSocket connection behavior.
- `frontend-hormonia/src/services/firebase-auth.ts` still performs Firebase sign-in before backend session creation.
- `frontend-hormonia/src/hooks/useMetricsWebSocket.ts` still fetches a Firebase token and sends it in the WebSocket URL.
- `frontend-hormonia/src/pages/medico/MedicoLogin.tsx` still reflects the old CRM/Firebase-oriented browser path.
- `frontend-hormonia/src/features/admin/UserCreateModal.tsx` and `frontend-hormonia/src/features/admin/UserEditModal.tsx` still use direct password / temporary-password UX, which matches the intentional T03 compatibility hold until frontend cutover.

That means:

- **S03** still correctly owns the browser-path cutover, including dashboard auth lifecycle, médico auth UX/restore behavior, realtime bootstrap, and consuming the new first-access/recovery backend contract instead of legacy Firebase or temporary-password assumptions.
- **S04** still correctly owns the hard cut, runtime/config cleanup, and integrated proof that the assembled system works end to end without Firebase Auth dependency.

No new evidence suggests reordering, merging, or splitting the remaining slices.

## Requirement coverage

Requirement coverage remains sound.

- S02 materially de-risked **R007**, **R008**, and **R009** at the backend contract level.
- The remaining active requirements still have credible owners: **R005/R006/R010** in S03+S04, **R011/R012** in S04, with **R008** still naturally completed by S03 consuming the new admin first-access contract in the frontend/admin UX.
- No requirement ownership or status changes are necessary for this reassessment.
