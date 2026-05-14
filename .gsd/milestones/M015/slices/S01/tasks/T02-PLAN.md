---
estimated_steps: 14
estimated_files: 2
skills_used:
  - tdd
  - verify-before-complete
  - security-review
---

# T02: Fix async PostgreSQL TLS handling for strict runtime participation

Why: The DB proof must include the actual FastAPI async DB path, not only an external psycopg probe. Current `app/core/database/async_engine.py` strips `sslmode=require/verify*` and builds an asyncpg SSL context with hostname verification disabled and `CERT_NONE`, so S01 must fix this before claiming runtime TLS posture.

Expected executor skills_used frontmatter: `tdd`, `verify-before-complete`, `security-review`.
Estimated scope: about 7 steps / 2 files.

Do:
1. Extract a testable helper from `backend-hormonia/app/core/database/async_engine.py` that converts sync PostgreSQL URLs to asyncpg URLs and returns sanitized async URL plus `connect_args`.
2. Preserve non-SSL query parameters that asyncpg supports, but remove libpq-only SSL query parameters from the async URL after converting them into an `ssl.SSLContext`.
3. Implement strict semantics: `sslmode=verify-full` loads `sslrootcert`, sets `CERT_REQUIRED`, and keeps hostname checking enabled; `sslmode=verify-ca` loads CA material with hostname checking disabled; `sslmode=require` enables TLS without silently pretending certificate verification happened; `sslmode=disable` creates no SSL context.
4. Support optional `sslcert`/`sslkey` client cert loading when present, but never log paths or secret material beyond boolean posture flags.
5. Ensure malformed SSL paths, unsupported SSL modes, or context construction failures fail closed during engine initialization with a named, sanitized error.
6. Keep existing URL scheme replacements for `postgresql://`, `postgresql+psycopg://`, and `postgresql+psycopg2://`.
7. Add focused tests in `backend-hormonia/tests/core/test_async_engine_tls_config.py` covering verify-full with CA, verify-ca hostname behavior, require mode, disabled mode, malformed sslmode, query stripping, and no DSN/secret leakage.

Failure Modes (Q5): missing CA for verify-full -> sanitized initialization failure; unsupported sslmode -> sanitized failure; malformed URL -> sanitized failure; asyncpg rejects leftover libpq params -> unit test catches before runtime.

Load Profile (Q6): one SSL context per engine process; per-operation cost unchanged after startup. At 10x processes, DB connection pools/cert file access break before helper CPU cost.

Negative Tests (Q7): wrong sslmode, missing sslrootcert for verify-full, leftover `sslmode`/`sslrootcert` in asyncpg URL, and logs/errors containing passwords are all rejected.

## Inputs

- `backend-hormonia/app/core/database/async_engine.py`
- `backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py`

## Expected Output

- `backend-hormonia/app/core/database/async_engine.py`
- `backend-hormonia/tests/core/test_async_engine_tls_config.py`

## Verification

cd backend-hormonia && PYTHONPATH=. pytest tests/core/test_async_engine_tls_config.py tests/security/test_m014_s05_jwt_config_posture.py -q

## Observability Impact

Async engine startup logs should expose only TLS posture booleans/mode class, never full URLs, passwords, cert contents, or private paths. Failures become named initialization errors instead of ambiguous asyncpg connection errors.
