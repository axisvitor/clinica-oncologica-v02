---
id: T02
parent: S01
milestone: M015
key_files:
  - backend-hormonia/app/core/database/async_engine.py
  - backend-hormonia/tests/core/test_async_engine_tls_config.py
key_decisions:
  - Treat `sslmode=require` as explicit TLS-encryption-only posture rather than certificate verification.
  - For verified async PostgreSQL TLS modes, fail closed unless `sslrootcert` is present and SSLContext construction succeeds.
  - Expose startup observability as sanitized TLS posture booleans/mode code, never full URLs, credentials, cert paths, or key material.
duration: 
verification_result: passed
completed_at: 2026-05-14T04:53:48.716Z
blocker_discovered: false
---

# T02: Fixed async PostgreSQL TLS configuration so FastAPI asyncpg startup participates in strict DB TLS posture with sanitized diagnostics.

**Fixed async PostgreSQL TLS configuration so FastAPI asyncpg startup participates in strict DB TLS posture with sanitized diagnostics.**

## What Happened

Added a testable async PostgreSQL connection preparation seam in `backend-hormonia/app/core/database/async_engine.py`. The helper converts `postgresql://`, `postgresql+psycopg://`, and `postgresql+psycopg2://` URLs to `postgresql+asyncpg://`, strips libpq SSL query parameters from the asyncpg URL, preserves non-SSL query parameters, and builds `connect_args` with an SSLContext matching the requested sslmode. `verify-full` now requires and loads `sslrootcert`, keeps hostname verification enabled, and uses `CERT_REQUIRED`; `verify-ca` requires CA material but disables hostname checks; `require` enables TLS with explicit encryption-only posture (`CERT_NONE`, hostname disabled); and `disable`/absent sslmode creates no SSL context. Optional client cert/key loading is supported without logging paths. Malformed URLs, unsupported sslmodes, missing CA for verified modes, unsupported TLS version hints, invalid client cert combinations, and SSLContext construction failures raise named `AsyncDatabaseConfigError` messages that avoid DSNs, passwords, cert paths, and private key material. Startup logging now reports only TLS posture booleans/mode class. Added focused tests in `backend-hormonia/tests/core/test_async_engine_tls_config.py`; the first red run failed on the missing helper/error type, then the implementation passed focused and required regression checks. A security review pass over the changed seam considered DB URL parsing, TLS downgrade/MITM posture, SSL file path handling, and log/error leakage; no remaining high/critical findings were identified in the modified scope.

## Verification

Verified the new helper behavior and regression baseline with pytest. Focused TLS helper tests passed (`9 passed`) covering verify-full with CA/client cert and stripped libpq params, verify-ca hostname behavior, require mode encryption-only posture, disabled mode, unsupported/missing sslmode failure, SSLContext construction sanitization, and log redaction. Required task verification passed (`14 passed`) including the existing M014 JWT/config posture tests. Full S01 runtime runner was not executed because T02 is an intermediate task and T03/T04 own the DB seam probe and closure gate.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && PYTHONPATH=. pytest tests/core/test_async_engine_tls_config.py -q` | 0 | ✅ pass (9 tests) | 21103ms |
| 2 | `cd backend-hormonia && PYTHONPATH=. pytest tests/core/test_async_engine_tls_config.py tests/security/test_m014_s05_jwt_config_posture.py -q` | 0 | ✅ pass (14 tests) | 21750ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/core/database/async_engine.py`
- `backend-hormonia/tests/core/test_async_engine_tls_config.py`
