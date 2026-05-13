---
id: T03
parent: S01
milestone: M014
key_files:
  - backend-hormonia/app/core/security.py
  - backend-hormonia/app/services/password_reset_service.py
  - backend-hormonia/app/api/v2/routers/auth.py
  - backend-hormonia/app/core/redis_manager/utils.py
  - backend-hormonia/tests/conftest.py
  - backend-hormonia/tests/integration/test_password_reset_migration_flow.py
  - backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py
key_decisions:
  - Captured MEM068: password reset replay hardening consumes only hashed JTIs via SET NX EX before mutation; cache uncertainty fails closed and duplicate JTI returns stable 409 without sensitive material.
duration: 
verification_result: passed
completed_at: 2026-05-13T06:56:21.460Z
blocker_discovered: false
---

# T03: Made password reset JWTs single-use by consuming hashed JTIs with Redis SET NX EX before credential or session side effects.

**Made password reset JWTs single-use by consuming hashed JTIs with Redis SET NX EX before credential or session side effects.**

## What Happened

Added a backwards-compatible password reset claims verifier in `app.core.security`: the existing `verify_password_reset_token()` still returns the email, while `verify_password_reset_token_claims()` returns validated `sub`, `jti`, and `exp` for replay control and rejects missing JTI as an invalid token. Updated `PasswordResetService.confirm_password_reset()` to validate password strength and token claims, resolve the user, then atomically consume a SHA-256 hashed JTI cache key with `SET NX EX` before updating `hashed_password`, migration flags, lockout state, DB sessions, Redis sessions, or auth failed-attempt state. Replay now returns stable `AUTH_RESET_TOKEN_REPLAYED` with 409; missing/expired/malformed JTI remains `AUTH_RESET_TOKEN_INVALID_OR_EXPIRED`; missing/unsupported/unavailable cache consumption fails closed with `AUTH_PASSWORD_RESET_SERVICE_UNAVAILABLE` before mutation. Added PHI/secret-safe endpoint diagnostics for reset-confirm failures using request_id, outcome/error/status, and token-consumption reason only. Updated test cache doubles to honor `nx=True` and added M014/S01 replay tests covering first success, replay denial, no extra revocation, missing JTI, malformed/expired token, cache exception, weak password, and direct service-level no-mutation assertions.

## Verification

Ran the focused replay test file after implementation and the required T03 verification command covering replay tests, existing password recovery API contracts, and the password reset migration integration flow. Final required suite passed with 16 tests in 3.06s. Earlier TDD red/green runs intentionally failed before implementation and while adjusting rollback-sensitive test assertions; final evidence below is the fresh passing verification.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py` | 0 | ✅ pass — 8 passed | 24848ms |
| 2 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py backend-hormonia/tests/api/v2/test_auth_password_recovery.py backend-hormonia/tests/integration/test_password_reset_migration_flow.py` | 0 | ✅ pass — 16 passed | 27154ms |

## Deviations

Extended supporting cache doubles in `tests/conftest.py` and null Redis helpers in `app/core/redis_manager/utils.py` to preserve Redis SET NX semantics in tests; added endpoint failure logging in `app/api/v2/routers/auth.py` to satisfy observability impact. These support the task contract but exceed the narrow expected-output file list.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/core/security.py`
- `backend-hormonia/app/services/password_reset_service.py`
- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/app/core/redis_manager/utils.py`
- `backend-hormonia/tests/conftest.py`
- `backend-hormonia/tests/integration/test_password_reset_migration_flow.py`
- `backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py`
