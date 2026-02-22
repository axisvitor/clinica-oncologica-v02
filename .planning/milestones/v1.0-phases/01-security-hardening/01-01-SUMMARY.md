---
phase: 01-security-hardening
plan: 01
subsystem: auth
tags: [fastapi, auth, session, redis, dependency-injection, monitoring]

# Dependency graph
requires: []
provides:
  - Monitoring router with canonical session-based auth on all protected endpoints
  - Read endpoints accessible to admin + doctor roles (get_current_active_user)
  - Admin mutation endpoints locked to admin role (get_admin_user)
  - Health and Prometheus endpoints remain unauthenticated for probes
affects: [02-lgpd-compliance, 03-hipaa-audit]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FastAPI dependency_overrides for test isolation (replaces module-level monkeypatching)"
    - "Role-split auth: get_current_active_user for reads, get_admin_user for mutations"

key-files:
  created: []
  modified:
    - backend-hormonia/app/api/v2/routers/enhanced_monitoring.py
    - backend-hormonia/tests/api/v2/test_enhanced_monitoring.py

key-decisions:
  - "Read monitoring endpoints (metrics, APM, DB, resources, business, anomalies, dashboard, alerts, performance) use get_current_active_user — both admin and doctor roles can view monitoring data"
  - "Admin-only endpoints are: GET /config, PUT /config, POST /export/grafana/query, POST /actions/* — these mutate state or expose raw query execution"
  - "/health/live, /health/ready, and /export/prometheus remain unauthenticated for Railway health probes and Prometheus scraping (OWASP standard: network-level protection)"
  - "Removed unused db=Depends(get_db) parameter from update_monitoring_config (db was only used by the deleted placeholder function)"

patterns-established:
  - "dependency_overrides pattern: app.dependency_overrides[get_admin_user] = lambda: mock_user in try/finally blocks for clean teardown"
  - "Auth split in router: import both get_admin_user and get_current_active_user from auth_dependencies, apply per endpoint type"

requirements-completed: [SEC-01]

# Metrics
duration: 5min
completed: 2026-02-22
---

# Phase 1 Plan 1: Replace Monitoring Placeholder Auth Summary

**Canonical session-based auth enforced on all monitoring endpoints by replacing raw DB query placeholder with get_admin_user/get_current_active_user from auth_dependencies.py**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-22T16:33:38Z
- **Completed:** 2026-02-22T16:38:57Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Deleted the local `get_admin_user` placeholder in enhanced_monitoring.py that returned the first admin user from DB with no token or session validation — the most immediate patient data exposure risk in Phase 1 scope
- Replaced with canonical `get_admin_user` and `get_current_active_user` from `auth_dependencies.py`, which validate Redis sessions (~2-5ms) before allowing access
- Applied role-based split: 18 read endpoints use `get_current_active_user` (admin + doctor), 6 mutation/config endpoints keep `get_admin_user` (admin only), 2 endpoints remain unauthenticated (`/health`, `/export/prometheus`)
- Updated all 66 monitoring tests from module-level `patch()` to FastAPI `dependency_overrides` pattern, with new `TestAuthenticationEnforcement` class verifying unauthenticated requests are rejected (401/403) and doctor role can access reads

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace placeholder get_admin_user with canonical auth imports** - `dd00b23c` (fix)
2. **Task 2: Update monitoring tests to use dependency_overrides** - `e08eb872` (feat)

**Plan metadata:** (recorded after state update)

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/enhanced_monitoring.py` - Deleted local placeholder auth function, added canonical imports, split endpoints by role requirement, removed unused imports (datetime, timezone, get_db, UserRole, RequestContext)
- `backend-hormonia/tests/api/v2/test_enhanced_monitoring.py` - Migrated all 60 existing tests to dependency_overrides, added doctor_user fixture, added 6 auth enforcement tests (total: 66 tests, all passing)

## Decisions Made

- Read monitoring endpoints allow both admin and doctor access per the CONTEXT.md decision — doctors need to see patient metrics and system alerts during clinical workflows
- Admin-only endpoints are mutation or raw query execution endpoints: `GET /config`, `PUT /config`, `POST /export/grafana/query`, and all `POST /actions/*`
- `/export/prometheus` stays unauthenticated — Prometheus scraping uses network-level protection (OWASP standard); app-level auth would break standard scraper configurations
- Removed the orphaned `db=Depends(get_db)` parameter from `update_monitoring_config` since it was only needed by the now-deleted placeholder function

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused `db=Depends(get_db)` from update_monitoring_config**
- **Found during:** Task 1 (replacing placeholder auth)
- **Issue:** After deleting the local `get_admin_user` that used `get_db`, the `update_monitoring_config` endpoint still had `db=Depends(get_db)` injected but never used in the function body. With `get_db` no longer imported, this would cause a `NameError` at runtime.
- **Fix:** Removed the `db=Depends(get_db)` parameter from `update_monitoring_config` signature. The function body never referenced `db`.
- **Files modified:** backend-hormonia/app/api/v2/routers/enhanced_monitoring.py
- **Verification:** Import search confirms no `get_db` reference remains in file
- **Committed in:** dd00b23c (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Auto-fix required for correctness — the orphaned `db=Depends(get_db)` parameter would cause a `NameError` at startup since `get_db` was no longer imported. No scope creep.

## Issues Encountered

None — plan executed cleanly. The canonical auth functions (`get_admin_user`, `get_current_active_user`) were already fully implemented in `auth_dependencies.py` with Redis session validation, making this a straightforward import replacement.

## User Setup Required

None - no external service configuration required. Auth dependencies use the existing Redis session infrastructure.

## Next Phase Readiness

- SEC-01 complete: monitoring endpoints no longer expose patient data to unauthenticated requests
- 66 tests passing with proper FastAPI dependency_overrides pattern established as project convention
- Ready for SEC-02 and SEC-03 (LGPD compliance and HIPAA audit trail hardening in parallel phases 2 and 3)

## Self-Check: PASSED

- FOUND: backend-hormonia/app/api/v2/routers/enhanced_monitoring.py
- FOUND: backend-hormonia/tests/api/v2/test_enhanced_monitoring.py
- FOUND: .planning/phases/01-security-hardening/01-01-SUMMARY.md
- FOUND: commit dd00b23c (Task 1 — fix: replace placeholder auth)
- FOUND: commit e08eb872 (Task 2 — feat: dependency_overrides tests)

---
*Phase: 01-security-hardening*
*Completed: 2026-02-22*
