---
id: T03
parent: S01
milestone: M015
key_files:
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/docker-compose.yml
  - scripts/security/m015-runtime/db_seam.py
  - scripts/security/m015-runtime/redaction.py
  - scripts/security/m015-runtime/tests/test_runner_contract.py
  - tests/core/test_async_engine_tls_config.py
  - tests/security/test_m014_s05_jwt_config_posture.py
key_decisions:
  - Use the backend image for `db-probe` so the probe exercises the same Python dependencies, Alembic graph, and network boundary as the FastAPI runtime.
  - Fail closed on durable evidence redaction hits and remove green summaries if redaction validation fails.
  - Root-level verification shims import canonical backend tests rather than duplicating test logic.
duration: 
verification_result: mixed
completed_at: 2026-05-14T05:26:53.661Z
blocker_discovered: true
---

# T03: Added the M015 DB seam probe, redaction guard, Compose wiring, and root-path test shims; exact unit gate now passes, while full runtime verification stops at a migration URL option failure that needs continuation.

**Added the M015 DB seam probe, redaction guard, Compose wiring, and root-path test shims; exact unit gate now passes, while full runtime verification stops at a migration URL option failure that needs continuation.**

## What Happened

Implemented the DB seam substrate requested by T03 in tracked files: `scripts/security/m015-runtime/db_seam.py` now runs inside the backend image and is structured to wait for verify-full PostgreSQL TLS, run Alembic as `hormonia_app`, verify FastAPI health/readiness through the app runtime, collect pg_stat_ssl/catalog/RLS evidence, prove app-role insert plus denied-role RLS blocking, and write redaction-validated JSON/Markdown artifacts. Added `scripts/security/m015-runtime/redaction.py` with durable evidence denylist validation for credentialed URLs, private keys, auth/cookie headers, Firebase/service-account material, CPF/email/phone patterns, raw `/mnt/c` paths, cert mount paths, and raw patient/provider payload markers. Updated `scripts/security/m015-runtime/docker-compose.yml` so `db-probe` uses the backend image, mounts the probe/redaction helpers, inherits backend runtime env, and writes artifacts to `backend-hormonia/docs/reports/security/m015`. Updated the runner to generate a correlation-aware probe env, run the DB seam probe after readiness, record sanitized probe logs, update teardown status in evidence, sanitize cert/host paths, use Dragonfly's current `--dbnum=16` flag, and generate HASH_SALT with mixed-character URL-safe entropy so production validation allows the synthetic runtime. Added root-level test shims for the gate's expected paths (`tests/core/test_async_engine_tls_config.py` and `tests/security/test_m014_s05_jwt_config_posture.py`) because the canonical tests live under `backend-hormonia/tests/...`; the shims set the same minimal safe test defaults normally supplied by backend `conftest.py`.

Runtime progress was real: after fixing Dragonfly and HASH_SALT, the full runner successfully completed setup, cert generation, Compose startup, Postgres verify-full TLS readiness, Dragonfly readiness, FastAPI `/health`, worker liveness, and probe TLS connection. The remaining failure is in the migration phase: Alembic/psycopg rejects the generated connection URL option `sslminversion` (`invalid connection option "sslminversion"`). The likely next fix is to remove that libpq-incompatible URL key for Alembic/psycopg or replace it with the supported libpq option while preserving TLS protocol verification via `pg_stat_ssl`. Per hard-timeout recovery, I stopped further debugging and recorded this explicit continuation state instead of continuing to explore.

## Verification

Fresh verification performed: static compile plus runner contract/redaction tests passed; the exact gate that previously failed because `tests/core/test_async_engine_tls_config.py` was missing now passes (`14 passed`). Full slice runtime verification was attempted three times. First failed at Compose because Dragonfly latest rejects `--num_dbs`; fixed to `--dbnum`. Second failed because API production validation rejected hex-only HASH_SALT; fixed to URL-safe entropy. Third reached the DB seam probe and failed in the migrations phase because psycopg/Alembic rejected `sslminversion` in the generated database URL. Sanitized failure evidence is available at `scripts/security/m015-runtime/evidence/m015-20260514T052400Z-1154737/db-probe.log`. No green DB evidence artifacts were written because the redaction/evidence phase is intentionally after successful migrations/TLS/RLS proof.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m py_compile scripts/security/m015-runtime/redaction.py scripts/security/m015-runtime/db_seam.py tests/core/test_async_engine_tls_config.py tests/security/test_m014_s05_jwt_config_posture.py && python3 -m unittest scripts/security/m015-runtime/tests/test_runner_contract.py` | 0 | ✅ pass | 368ms |
| 2 | `PYTHONPATH=. pytest tests/core/test_async_engine_tls_config.py tests/security/test_m014_s05_jwt_config_posture.py -q` | 0 | ✅ pass (14 passed, 10 warnings) | 3727ms |
| 3 | `./scripts/security/verify-m015-runtime-security.sh --seam db` | 1 | ❌ fail (initial Compose failure: Dragonfly latest rejected --num_dbs; fixed to --dbnum) | 146434ms |
| 4 | `./scripts/security/verify-m015-runtime-security.sh --seam db` | 1 | ❌ fail (API startup rejected hex-only HASH_SALT; fixed to URL-safe entropy) | 183038ms |
| 5 | `./scripts/security/verify-m015-runtime-security.sh --seam db` | 1 | ❌ fail (current blocker: migrations phase rejects psycopg option sslminversion) | 72796ms |

## Deviations

Hard-timeout recovery required stopping before full runtime verification was green. As a result, the DB seam implementation is in place and partial runtime phases passed, but the final runtime demo is not yet complete.

## Known Issues

Full runtime verification `./scripts/security/verify-m015-runtime-security.sh --seam db` currently fails at phase `migrations` with failure_class `migration_failure`: psycopg/Alembic reports `invalid connection option "sslminversion"`. Evidence/summary artifacts are not produced until this is fixed and the probe reaches the evidence phase.

## Files Created/Modified

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `scripts/security/m015-runtime/db_seam.py`
- `scripts/security/m015-runtime/redaction.py`
- `scripts/security/m015-runtime/tests/test_runner_contract.py`
- `tests/core/test_async_engine_tls_config.py`
- `tests/security/test_m014_s05_jwt_config_posture.py`
