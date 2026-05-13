---
estimated_steps: 21
estimated_files: 4
skills_used: []
---

# T02: Contract CSRF exemptions to non-session ingress only

---
estimated_steps: 7
estimated_files: 5
skills_used:
  - api-design
  - tdd
  - verify-before-complete
---

Why: `CSRFMiddleware.EXEMPT_PATHS` currently exempts broad session-protected/state-changing surfaces (`/api/v2/messages`, `/api/v2/enhanced-messages`, `/api/v2/flows`) and password reset endpoints. S01 requires browser/session state changes to reject missing or invalid CSRF before route dependencies, DB writes, queues, or provider calls.

Files: `backend-hormonia/app/middleware/csrf.py`, existing CSRF/password recovery tests, and a focused S01 CSRF proof file.

Do:
1. Narrow CSRF exemptions to safe methods, token endpoint, docs/health, intentional provider webhooks protected by HMAC/idempotency, and explicitly public non-cookie APIs.
2. Remove broad exemptions for authenticated/session-protected mutating APIs and password reset submit endpoints; keep Authorization/X-API-Key bypass limited to true token-auth paths.
3. Ensure missing header, invalid header token, missing cookie, invalid cookie, and mismatch return 403 without invoking endpoint side effects.
4. Update password recovery/API tests to fetch/include CSRF tokens for legitimate browser-style reset requests and confirms.
5. Add `backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py` with an endpoint side-effect sentinel proving denials happen before route body/dependency execution.
6. Keep webhook paths exempt from CSRF because T04 covers them with HMAC/timestamp/idempotency, not browser cookies.

Failure Modes (Q5): Missing/invalid CSRF denies with 403; absent CSRF secret in production remains startup failure; malformed tokens are rejected without logging token values.

Load Profile (Q6): CSRF validation is CPU-only HMAC and constant-time compare; 10x denied traffic should not reach DB or queue.

Negative Tests (Q7): no header, no cookie, invalid signature, expired token, mismatch, cookie-session mutating endpoint without Authorization, and valid double-submit fixture.

Done when: CSRF middleware tests prove the contracted exemptions and legitimate fixture tests include CSRF, while missing/invalid tokens deny before side effects.

## Inputs

- ``backend-hormonia/app/middleware/csrf.py``
- ``backend-hormonia/app/middleware/csrf_tokens.py``
- ``backend-hormonia/app/api/v2/routers/auth.py``
- ``backend-hormonia/tests/auth/test_csrf_middleware.py``
- ``backend-hormonia/tests/api/v2/test_auth_password_recovery.py``
- ``backend-hormonia/tests/integration/test_password_reset_migration_flow.py``

## Expected Output

- ``backend-hormonia/app/middleware/csrf.py``
- ``backend-hormonia/tests/auth/test_csrf_middleware.py``
- ``backend-hormonia/tests/api/v2/test_auth_password_recovery.py``
- ``backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py``

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py backend-hormonia/tests/auth/test_csrf_middleware.py backend-hormonia/tests/api/v2/test_auth_password_recovery.py

## Observability Impact

CSRF denial logs should include method/path/reason and request identifier only. They must not include CSRF token values, cookies, Authorization headers, request bodies, emails, phone numbers or PHI.
