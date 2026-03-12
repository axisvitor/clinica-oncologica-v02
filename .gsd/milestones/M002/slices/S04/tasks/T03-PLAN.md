---
estimated_steps: 5
estimated_files: 8
---

# T03: Make backend readiness, health, and public config honest without Firebase Auth

**Slice:** S04 — Hard Cut Cleanup And Integrated Proof
**Milestone:** M002

## Description

Remove the operational lie that staff authentication depends on Firebase configuration. After this task, backend readiness, health, initialization, validation, and public configuration surfaces must describe the real session-first staff-auth runtime and remain inspectable when Firebase admin/browser auth configuration is absent.

## Steps

1. Update `backend-hormonia/app/routers/health.py` so readiness and startup validation check database, Redis, and session-auth prerequisites without failing purely because Firebase Admin credentials are absent.
2. Update `backend-hormonia/app/api/v2/routers/system/health.py` and `helpers/health_checker.py` so system health reports staff-auth-relevant components truthfully and treats Firebase auth as optional/out-of-scope instead of a required component.
3. Update `backend-hormonia/app/api/v2/routers/system/validation.py`, `initialization.py`, and `dependencies/auth_dependencies.py` so configuration/init warnings no longer say auth “will not work” without Firebase and instead surface actionable session-auth diagnostics.
4. Update `backend-hormonia/app/api/v2/routers/system/config.py`, `helpers/config_builder.py`, and any affected schemas so the public config surface stops emitting `VITE_FIREBASE_*` and only publishes session-first/frontend-safe configuration.
5. Run the dedicated operational proof plus core auth/health regressions with Firebase auth env intentionally absent to confirm the system remains ready, inspectable, and honest.

## Must-Haves

- [ ] Missing Firebase Admin/browser auth config no longer makes staff-auth readiness fail or public config lie about required runtime settings.
- [ ] Health/validation/initialization output remains inspectable with stable component names and actionable messages.
- [ ] Auth dependency initialization logging no longer claims first-party auth is broken when Firebase is absent.
- [ ] No public system config payload exposes `VITE_FIREBASE_*` values for the staff-auth path.

## Verification

- `cd backend-hormonia && pytest tests/api/v2/test_system_auth_hard_cut_operational.py tests/api/v2/test_health.py tests/api/v2/test_auth_local_login.py -q`
- `env -u FIREBASE_ADMIN_PROJECT_ID -u FIREBASE_ADMIN_PRIVATE_KEY -u FIREBASE_ADMIN_CLIENT_EMAIL bash -lc 'cd backend-hormonia && pytest tests/api/v2/test_system_auth_hard_cut_operational.py -q'`

## Observability Impact

- Signals added/changed: Health/readiness/validation/init responses now expose session-auth-relevant component status instead of stale Firebase-required status.
- How a future agent inspects this: Query `/api/v2/health/ready`, `/api/v2/system/health`, `/api/v2/system/validate`, and `/api/v2/system/config`, then compare against the dedicated operational pytest suite.
- Failure state exposed: Missing database/Redis/session prerequisites and stale config/public-config regressions appear as named component failures or assertion diffs instead of generic “Firebase not configured” noise.

## Inputs

- `backend-hormonia/app/routers/health.py` and `backend-hormonia/app/api/v2/routers/system/*` — current operational surfaces that still model Firebase auth as required.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — currently emits misleading initialization logging when Firebase creds are absent.

## Expected Output

- Backend health/readiness/system routes report honest session-first staff-auth readiness without Firebase auth config.
- Public config/schema no longer emits Firebase-auth runtime knobs for the frontend.
- Operational diagnostics become specific enough that a future agent can localize auth boot failures quickly.
