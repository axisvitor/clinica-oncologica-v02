---
id: T03
parent: S04
milestone: M002
provides:
  - Backend operational status surfaces now report session-first staff-auth readiness without requiring Firebase Admin/browser auth config, and public config no longer emits VITE_FIREBASE_* values.
key_files:
  - backend-hormonia/app/routers/health.py
  - backend-hormonia/app/api/v2/routers/system/health.py
  - backend-hormonia/app/api/v2/routers/system/helpers/health_checker.py
  - backend-hormonia/app/api/v2/routers/system/validation.py
  - backend-hormonia/app/api/v2/routers/system/initialization.py
  - backend-hormonia/app/api/v2/routers/system/config.py
  - backend-hormonia/app/api/v2/routers/system/helpers/config_builder.py
  - backend-hormonia/app/dependencies/auth_dependencies.py
  - backend-hormonia/app/schemas/v2/system.py
key_decisions:
  - Expose staff-auth operational truth through a stable `session_auth` component instead of treating Firebase as a required readiness/health dependency.
  - Filter legacy firebase-hosting and Firebase public-auth config out of `/api/v2/system/config` so the public payload stays honest for the shipped session-first runtime.
patterns_established:
  - Readiness/validation/init checks should distinguish critical session prerequisites (secret key, session cookie contract, HttpOnly) from optional diagnostics (CSRF secret warning, Redis degradation, external APIs).
  - Public config should publish only frontend-safe session-first runtime knobs and may redact legacy hosting/auth residues even if old env values still exist elsewhere in deployment settings.
observability_surfaces:
  - /health/ready
  - /health/startup
  - /api/v2/system/health
  - /api/v2/system/validate
  - /api/v2/system/initialize
  - /api/v2/system/config
  - backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py
  - structured auth dependency initialization logs
duration: 1h20m
verification_result: passed
completed_at: 2026-03-12T13:56:01-03:00
blocker_discovered: false
---

# T03: Make backend readiness, health, and public config honest without Firebase Auth

**Reframed backend operational/auth surfaces around session-first staff auth, removed public Firebase config publication, and kept no-Firebase startup diagnostics inspectable instead of falsely reporting auth as broken.**

## What Happened

I completed the backend honesty cut for the operational surfaces covered by T03.

The top-level health router now treats staff auth as a session-first concern: `/health/ready` checks database, Redis, and a named `session_auth` prerequisite group instead of failing because Firebase Admin credentials are absent. `/health/startup` likewise validates session-auth-relevant settings (`DATABASE_URL`, `SECURITY_SECRET_KEY`, `SESSION_COOKIE_NAME`, `SESSION_ENABLE_COOKIE_HTTPONLY`) and records CSRF secret presence as an inspectable optional diagnostic instead of a Firebase requirement.

The admin system health surface now reports `database`, `redis`, `session_auth`, and `external_apis`. The new `session_auth` component exposes stable metadata such as cookie mode and CSRF configuration state, while only marking the component unhealthy for actual session contract breakage and degraded for production CSRF gaps.

`/api/v2/system/validate` and `/api/v2/system/initialize` were updated so they no longer warn that Firebase auth is required. They now emit actionable session-first messages, especially around CSRF and cookie hardening, while preserving inspectable warning/error arrays.

`/api/v2/system/config` and the system schema/helpers were updated to stop publishing `VITE_FIREBASE_*` values. The public payload now exposes only API/WebSocket/session-first-safe frontend settings, and it filters legacy Firebase-hosting origins out of the published CORS list so the hard-cut operational proof stays honest even if old deployment settings still contain those domains.

Finally, `app/dependencies/auth_dependencies.py` no longer logs that authentication “will not work” when Firebase Admin credentials are absent. It now logs Firebase compatibility as optional and explicitly states that session-first staff authentication remains available.

## Verification

Task-plan verification passed:

- `cd backend-hormonia && pytest tests/api/v2/test_system_auth_hard_cut_operational.py tests/api/v2/test_health.py tests/api/v2/test_auth_local_login.py -q`
  - Result: **passed**
- `env -u FIREBASE_ADMIN_PROJECT_ID -u FIREBASE_ADMIN_PRIVATE_KEY -u FIREBASE_ADMIN_CLIENT_EMAIL bash -lc 'cd backend-hormonia && pytest tests/api/v2/test_system_auth_hard_cut_operational.py -q'`
  - Result: **passed**

Additional slice-level spot check:

- `bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`
  - Result: **fails as expected outside T03 scope** on remaining T04/T05 residue (`/api/v2/auth/firebase/verify`, Firebase password-change/debug seams, and docs/e2e guidance). The backend operational-firebase-requirement/public-config portion is no longer the failing part.

## Diagnostics

Future agents can inspect this task through:

- `backend-hormonia/app/routers/health.py` for top-level readiness/startup truthfulness
- `backend-hormonia/app/api/v2/routers/system/health.py`
- `backend-hormonia/app/api/v2/routers/system/helpers/health_checker.py`
- `backend-hormonia/app/api/v2/routers/system/validation.py`
- `backend-hormonia/app/api/v2/routers/system/initialization.py`
- `backend-hormonia/app/api/v2/routers/system/config.py`
- `backend-hormonia/app/dependencies/auth_dependencies.py`
- `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py`

Most useful runtime checks:

- `GET /health/ready` → should show `session_auth` and no `firebase`
- `GET /api/v2/system/health` → should show `session_auth` component metadata
- `POST /api/v2/system/validate` → should warn about CSRF/cookie posture, not Firebase auth absence
- `POST /api/v2/system/initialize` → should initialize `session_auth`, not `firebase`
- `GET /api/v2/system/config` → should contain no `VITE_FIREBASE_*` keys and no Firebase-auth guidance

## Deviations

- I also updated `backend-hormonia/app/api/v2/routers/system/metrics.py` and `backend-hormonia/app/schemas/v2/system.py` so related system-info metadata reflects `session_auth` naming instead of a stale `firebase_auth` feature flag. This was not explicitly called out in the task file list, but it keeps the adjacent system observability surface aligned with the T03 honesty cut.

## Known Issues

- `bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh` is still red because T04/T05 work remains: `/api/v2/auth/firebase/verify`, Firebase-backed password-change/debug paths, and Firebase-focused docs/e2e guidance are still present.
- Slice-final proof commands (full backend slice suite, frontend slice suite, build, and Playwright no-Firebase acceptance) were not rerun here; T03 completed its own required verification, and the remaining slice-wide gate belongs to later tasks.

## Files Created/Modified

- `backend-hormonia/app/routers/health.py` — replaced Firebase readiness/startup checks with session-auth prerequisites and optional CSRF diagnostics.
- `backend-hormonia/app/api/v2/routers/system/health.py` — switched component reporting from `firebase` to `session_auth` and updated cache key scope.
- `backend-hormonia/app/api/v2/routers/system/helpers/health_checker.py` — implemented honest `session_auth` component health evaluation.
- `backend-hormonia/app/api/v2/routers/system/validation.py` — removed Firebase-required warnings and added session-auth/cookie/CSRF guidance.
- `backend-hormonia/app/api/v2/routers/system/initialization.py` — initializes `session_auth` instead of `firebase` and records actionable missing prerequisites.
- `backend-hormonia/app/api/v2/routers/system/config.py` — removed Firebase public config publication and filtered public CORS output for session-first honesty.
- `backend-hormonia/app/api/v2/routers/system/helpers/config_builder.py` — removed Firebase public-config builder and tightened safe-env filtering.
- `backend-hormonia/app/api/v2/routers/system/helpers/__init__.py` — dropped exported Firebase public-config helper aliases.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — changed Firebase init logging to optional compatibility language instead of “auth will not work”.
- `backend-hormonia/app/schemas/v2/system.py` — aligned public/system schemas and examples with `session_auth` naming and no public Firebase config.
- `backend-hormonia/app/api/v2/routers/system/metrics.py` — renamed adjacent system-info feature metadata to `session_auth`.
- `.gsd/DECISIONS.md` — recorded the session-auth operational-surface/public-config decision for downstream tasks.
