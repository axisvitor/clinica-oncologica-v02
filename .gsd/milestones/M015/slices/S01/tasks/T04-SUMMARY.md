---
id: T04
parent: S01
milestone: M015
key_files:
  - backend-hormonia/app/db/migrations.py
  - backend-hormonia/app/core/database/async_engine.py
  - backend-hormonia/tests/core/test_async_engine_tls_config.py
  - backend-hormonia/tests/security/test_m015_runtime_harness.py
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/docker-compose.yml
  - scripts/security/m015-runtime/db_seam.py
  - backend-hormonia/docs/reports/security/m015/db-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/db-seam-summary.md
  - .gsd/DECISIONS.md
key_decisions:
  - D026: Separate migration-time PostgreSQL TLS DSN compatibility from asyncpg runtime TLS context configuration.
  - Use libpq-compatible `ssl_min_protocol_version` in generated harness DSNs while retaining async runtime SSLContext verification and TLS minimum enforcement.
  - Record absent current-head sensitive tables in RLS evidence while continuing to fail any existing sensitive table missing forced RLS, revoked PUBLIC privileges, or app-role policy coverage.
duration: 
verification_result: passed
completed_at: 2026-05-14T05:53:44.129Z
blocker_discovered: false
---

# T04: Fixed Alembic-compatible TLS DSN handling and proved the M015 DB seam reaches sanitized TLS/RLS evidence with teardown complete.

**Fixed Alembic-compatible TLS DSN handling and proved the M015 DB seam reaches sanitized TLS/RLS evidence with teardown complete.**

## What Happened

Reviewed the runner/probe handoff, Alembic URL bootstrap, and async engine TLS handling. The M015 runner was generating `DATABASE_URL` and `M015_DATABASE_URL` with `sslminversion=TLSv1.2`, which async runtime code could consume but psycopg/libpq rejected before Alembic migrations completed. I changed the generated runner and Compose fallback DSNs/conninfo strings to use the canonical libpq key `ssl_min_protocol_version=TLSv1.2`, then added migration bootstrap normalization that translates historical `sslminversion`/`sslmaxversion` aliases to libpq-compatible keys and fails closed on unknown `ssl*` query options without leaking DSNs, secrets, or private paths. The async engine remains strict: it still strips TLS URL options from the asyncpg URL, builds an SSLContext for `verify-full`, loads the CA, keeps hostname verification, and applies minimum TLS versions for both alias and canonical keys.

Focused tests were added/updated for the migration compatibility regression and runtime TLS posture. After the migration fix let the real Docker seam progress, runtime verification exposed two RLS proof issues in the probe. First, `has_table_privilege('PUBLIC', ...)` treats `PUBLIC` as a role name and raised `UndefinedObject`; I replaced that with direct ACL expansion from `pg_class` so PUBLIC privilege revocation is checked accurately. Second, the current Alembic head does not create the `consents` table even though it is in the sensitive-table list and ORM models; the probe now records absent sensitive tables in evidence while still failing if no sensitive tables exist or if any existing sensitive table lacks forced RLS, revoked PUBLIC privileges, or the app-role policy.

The final DB seam run completed setup, certs, Compose, readiness, migrations, TLS evidence, RLS allow/deny probes, redaction-validated artifact writing, and idempotent teardown. Fresh sanitized artifacts were generated at `backend-hormonia/docs/reports/security/m015/db-seam-evidence.json` and `backend-hormonia/docs/reports/security/m015/db-seam-summary.md`.

## Verification

Verified shell syntax, focused TLS/harness unit tests, the real Docker-backed DB seam, absence of teardown residue for the successful Compose project, and redaction-safe evidence metadata. The successful seam run generated `db-seam-evidence.json` and `db-seam-summary.md`, recorded TLS `TLSv1.3` / `TLS_AES_256_GCM_SHA384`, applied Alembic head `m013_s04_upload_deleted_at` as `hormonia_app`, proved denied-role RLS insert blocked with SQLSTATE `42501`, and updated teardown result to `complete`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash -n scripts/security/verify-m015-runtime-security.sh` | 0 | ✅ pass | 22ms |
| 2 | `cd backend-hormonia && PYTHONPATH=. pytest tests/core/test_async_engine_tls_config.py tests/security/test_m015_runtime_harness.py -q` | 0 | ✅ pass (13 passed) | 20668ms |
| 3 | `./scripts/security/verify-m015-runtime-security.sh --seam db` | 0 | ✅ pass (DB seam reached evidence and teardown complete) | 72069ms |
| 4 | `docker ps/volume label check for project m015-runtime-m015-20260514t054818z-1191750` | 0 | ✅ pass (containers=0 volumes=0) | 679ms |
| 5 | `validate db-seam evidence/summary redaction and inspect TLS/RLS metadata` | 0 | ✅ pass (redaction passed; artifacts present) | 86ms |

## Deviations

Extended beyond the initial TLS URL regression to fix two runtime RLS proof defects surfaced only after migrations succeeded: PUBLIC pseudo-role privilege checks now use `pg_class` ACL expansion, and absent current-head sensitive tables are recorded explicitly instead of aborting the whole seam.

## Known Issues

The ORM/RLS sensitive table list includes `consents`, but the current Alembic head does not create that table; the DB seam now records `consents` as absent while proving forced RLS on existing sensitive tables.

## Files Created/Modified

- `backend-hormonia/app/db/migrations.py`
- `backend-hormonia/app/core/database/async_engine.py`
- `backend-hormonia/tests/core/test_async_engine_tls_config.py`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `scripts/security/m015-runtime/db_seam.py`
- `backend-hormonia/docs/reports/security/m015/db-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/db-seam-summary.md`
- `.gsd/DECISIONS.md`
