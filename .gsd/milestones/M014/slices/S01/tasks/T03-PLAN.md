---
estimated_steps: 21
estimated_files: 5
skills_used: []
---

# T03: Make password reset tokens single-use and replay-safe

---
estimated_steps: 8
estimated_files: 5
skills_used:
  - api-design
  - tdd
  - verify-before-complete
---

Why: Password reset JWTs already carry a `jti`, but `PasswordResetService.confirm_password_reset` only validates signature/expiration and can accept the same token repeatedly until expiration. S01 must deny replay before a second password change or session revocation side effect.

Files: `backend-hormonia/app/core/security.py`, `backend-hormonia/app/services/password_reset_service.py`, password recovery tests and new S01 replay tests.

Do:
1. Add a backwards-compatible helper in `app.core.security` that verifies password-reset JWTs and returns redacted claims needed by the service (`sub`, `jti`, `exp`) while preserving the existing `verify_password_reset_token()` email-return contract.
2. In `PasswordResetService.confirm_password_reset`, validate password/token, resolve the user, then atomically consume the token JTI using Redis/cache `SET NX EX` (store only a hash of the JTI or a non-secret key, never the raw token).
3. If the JTI is already consumed, raise a stable `PasswordResetFailure` before updating `hashed_password`, `last_password_change`, auth provider, lockout state or sessions. Prefer a 409 replay/conflict or the existing generic invalid-token diagnostic if preserving response compatibility; in all cases avoid email/token in the response.
4. If the token-consumption backend is unavailable or cannot guarantee atomicity, fail closed with service-unavailable before user mutation.
5. Update test doubles such as recovery Redis fixtures to support the atomic set contract.
6. Add `backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py` proving first confirm succeeds, second confirm with same token fails, and the second request does not change the password or enqueue/revoke extra sessions.

Failure Modes (Q5): Redis/cache unavailable denies with 503 before mutation; duplicate JTI denies with 409/400-class stable diagnostic before mutation; malformed/expired/missing JTI returns invalid token diagnostics.

Load Profile (Q6): One atomic cache write per reset confirm; 10x reset attempts should be bounded by auth rate limiting from T01 and avoid DB mutation on replay.

Negative Tests (Q7): reused valid token, token missing `jti`, expired token, malformed token, cache `set` exception, weak password must not consume token.

Done when: reset tokens are single-use in controlled tests, existing password migration flow still works once with CSRF, and no test response/log includes token, email, password, cookie or reset link.

## Inputs

- ``backend-hormonia/app/core/security.py``
- ``backend-hormonia/app/services/password_reset_service.py``
- ``backend-hormonia/app/api/v2/routers/auth.py``
- ``backend-hormonia/tests/api/v2/test_auth_password_recovery.py``
- ``backend-hormonia/tests/integration/test_password_reset_migration_flow.py``

## Expected Output

- ``backend-hormonia/app/core/security.py``
- ``backend-hormonia/app/services/password_reset_service.py``
- ``backend-hormonia/tests/api/v2/test_auth_password_recovery.py``
- ``backend-hormonia/tests/integration/test_password_reset_migration_flow.py``
- ``backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py``

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py backend-hormonia/tests/api/v2/test_auth_password_recovery.py backend-hormonia/tests/integration/test_password_reset_migration_flow.py

## Observability Impact

Password reset diagnostics should record outcome class, request_id and token-consumption reason only. They must not log raw token, JTI, reset URL, email address, password, session cookie or PHI.
