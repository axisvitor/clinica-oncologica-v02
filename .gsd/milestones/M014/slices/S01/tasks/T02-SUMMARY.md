---
id: T02
parent: S01
milestone: M014
key_files:
  - backend-hormonia/app/middleware/csrf.py
  - backend-hormonia/tests/auth/test_csrf_middleware.py
  - backend-hormonia/tests/api/v2/test_auth_password_recovery.py
  - backend-hormonia/tests/integration/test_password_reset_migration_flow.py
  - backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py
key_decisions:
  - Captured MEM067: CSRF exemptions stay narrow, and Authorization/X-API-Key header bypass is explicit-only for true non-cookie token-auth ingress.
duration: 
verification_result: passed
completed_at: 2026-05-13T06:33:06.380Z
blocker_discovered: false
---

# T02: Contracted CSRF exemptions to non-session ingress and proved session-backed mutations fail closed before route side effects.

**Contracted CSRF exemptions to non-session ingress and proved session-backed mutations fail closed before route side effects.**

## What Happened

Narrowed `CSRFMiddleware` exemptions to safe methods, token endpoints, docs/health, provider webhooks, public/static ingress, and tokenized public quiz APIs. Removed the broad session-backed exemptions for messages, enhanced messages, flows, auth login/register/refresh/logout, and password reset endpoints, and changed the Authorization/X-API-Key bypass to an explicit empty allowlist so headers alone cannot skip CSRF on cookie/session-backed mutations. Reworked CSRF denial handling to emit PHI-safe structured diagnostics with event_type, reason, method/path, optional safe request_id, and hashed client identity, without token/cookie/header/body values. Updated password recovery and password-reset migration tests to fetch the real CSRF token endpoint for legitimate browser-style reset, confirm, and login requests. Added a focused S01 security proof file with dependency/endpoint sentinels showing missing header, invalid header, missing cookie, invalid cookie, mismatch, expired token, and Authorization-header attempts return 403 before route dependency/body execution, while valid double-submit and provider webhook fixture paths still pass.

## Verification

Ran the required focused CSRF/password-recovery pytest suite after the final wrap-up rerun: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py backend-hormonia/tests/auth/test_csrf_middleware.py backend-hormonia/tests/api/v2/test_auth_password_recovery.py` passed with 109 tests. Also ran the impacted password reset migration integration file because its CSRF helper was updated; it passed with 2 tests.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py backend-hormonia/tests/auth/test_csrf_middleware.py backend-hormonia/tests/api/v2/test_auth_password_recovery.py` | 0 | ✅ pass — 109 passed in 3.28s | 27287ms |
| 2 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integration/test_password_reset_migration_flow.py` | 0 | ✅ pass — 2 passed in 1.73s | 25758ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/middleware/csrf.py`
- `backend-hormonia/tests/auth/test_csrf_middleware.py`
- `backend-hormonia/tests/api/v2/test_auth_password_recovery.py`
- `backend-hormonia/tests/integration/test_password_reset_migration_flow.py`
- `backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py`
