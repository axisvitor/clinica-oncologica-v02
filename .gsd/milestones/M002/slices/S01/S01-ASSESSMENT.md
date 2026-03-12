---
date: 2026-03-11
triggering_slice: M002/S01
verdict: no-change
---

# Reassessment: M002/S01

## Success-Criterion Coverage Check

- Staff users can log in with email/password through the product’s own auth flow and reach protected dashboard/API surfaces without Firebase token exchange. → S03, S04
- Existing users regain access through reset/first-access email flows instead of manual account recreation. → S02, S04
- Session continuity features such as remember-me, verify-session, logout, and protected-route auth keep working after the provider switch. → S03, S04
- Frontend dashboard and realtime auth no longer depend on Firebase SDK state or Firebase tokens. → S03, S04
- Firebase Auth runtime/config dependencies are removed or tombstoned, and integrated verification proves the assembled auth system works end to end. → S04

Coverage check: pass.

## Changes Made

No changes.

S01 retired the backend identity-contract risk it was supposed to retire: first-party email/password login now issues the canonical DB + Redis + HttpOnly session, `verify-session` / `logout` / protected-route auth work on canonical `user_id`, and focused verification is green. The remaining slices still line up with the unfinished work exactly where expected:

- S02 still owns reset/first-access, email recovery, and admin-created-account activation/migration.
- S03 still owns browser-path cutover for dashboard + médico auth, remember-me/session restore, realtime bootstrap, and moving consumers onto the canonical `/api/v2/users/*` surface.
- S04 still owns Firebase Auth runtime/config removal or tombstoning plus the final integrated proof.

No new risk from S01 justifies reordering, merging, or splitting the remaining slices. The boundary map remains credible; the only practical nuance is that `/api/v2/auth/*` profile routes are now explicitly temporary compatibility aliases, which is already consistent with the planned S03 cutover and S04 cleanup.

## Requirement Coverage Impact

None.

Requirement coverage remains sound after S01:

- R005 and R006 now have backend proof from S01, while S03 and S04 still provide the remaining browser/session-continuity and integrated-proof coverage.
- R007, R008, and R009 remain credibly owned by S02.
- R010 remains credibly owned by S03.
- R011 remains credibly owned by S04.
- R012 remains soundly covered across S02-S04, with S01 improving the backend diagnostic baseline without changing ownership.

## Decision References

- "M002 uses a hard cut for staff authentication: Firebase Auth must leave the shipped runtime state instead of remaining as a long-lived compatibility mode."
- "M002 preserves the Redis + HttpOnly cookie session architecture and replaces only the identity provider, avoiding a simultaneous shift to JWT-only auth."
- "M002 keeps account provisioning admin-driven and migrates existing users through reset/first-access email flows instead of manual recreation."
- "M002/S01 makes Redis session payloads user-id-centric; `firebase_uid` becomes compatibility data rather than the canonical happy-path auth key."
- "M002/S01 exposes canonical authenticated-user routes under /api/v2/users/* and keeps /api/v2/auth/* as a hidden legacy alias so downstream frontend cutover can move without breaking current callers immediately."
