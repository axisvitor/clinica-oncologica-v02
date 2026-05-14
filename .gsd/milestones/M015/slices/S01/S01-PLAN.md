# S01: Synthetic Runtime Harness + DB TLS/RLS Proof

**Goal:** Build the M015 synthetic runtime harness substrate and prove the DB seam end to end: a single root runner can start an isolated Docker Compose stack with FastAPI, TLS-enabled PostgreSQL, and Dragonfly, apply Alembic migrations with synthetic-only configuration, verify strict TLS negotiation from the backend runtime, exercise RLS allow/deny behavior on sensitive tables, emit PHI/secret-safe evidence, and tear down idempotently. Owned requirements: R014 directly, R012 DB TLS/RLS portion, R015 no production/real PHI. Supporting requirements: R017/R018 evidence discipline and no silent deferred-item loss; R013 is not proven in this slice beyond shared harness substrate.
**Demo:** Run `./scripts/security/verify-m015-runtime-security.sh --seam db` to start the isolated backend runtime stack, apply migrations and synthetic fixtures, prove TLS negotiation and RLS allow/deny behavior, capture sanitized DB evidence, and tear down.

## Must-Haves

- Slice verification is defined before implementation and must pass before completion:
- `bash -n scripts/security/verify-m015-runtime-security.sh` succeeds.
- `docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet` succeeds without reading project `.env` files or referencing live WuzAPI/Gemini services for S01.
- `cd backend-hormonia && PYTHONPATH=. pytest tests/core/test_async_engine_tls_config.py tests/security/test_m015_runtime_harness.py -q` succeeds.
- `./scripts/security/verify-m015-runtime-security.sh --seam db` starts the isolated stack, waits for readiness, runs Alembic against the TLS PostgreSQL service, proves FastAPI starts with the same TLS DB configuration, inserts/selects a synthetic patient through the application role, proves a granted-but-unpolicied role is denied by RLS, writes sanitized evidence to `backend-hormonia/docs/reports/security/m015/db-seam-evidence.json` and `backend-hormonia/docs/reports/security/m015/db-seam-summary.md`, and tears down containers/volumes/temp certs idempotently.
- Evidence validation rejects DSNs with credentials, private keys/certs, cookies/tokens, Firebase/service-account material, real-looking CPF/email/phone/patient names, `/mnt/c` absolute paths, and raw SQL stderr that exposes secrets.
- Q3 Threat Surface:
- Abuse: DB TLS downgrade/MITM, RLS bypass through owner/superuser shortcuts, migration executed as the wrong role, evidence/runner log leakage, Docker project/volume contamination.
- Data exposure: synthetic rows only; no production DB, live provider credential, cookie, JWT, PHI, or private artifact path may appear in evidence.
- Input trust: runner CLI seam names, generated env/certs, Docker Compose env interpolation, Alembic output, and DB probe query results are untrusted and must be validated/redacted.
- Q4 Requirement Impact:
- Requirements touched: R012, R014, R015, R017, R018.
- Re-verify: DB engine TLS parsing, production posture baseline, Alembic operability, harness redaction, DB runtime seam.
- Decisions honored/revisited: D024 single seam-filterable runner and D025 S01 file layout/TLS proof boundary.

## Proof Level

- This slice proves: Operational runtime proof. Real runtime required: yes, local/CI Docker only. Human/UAT required: no. This proves the DB TLS/RLS seam and reusable harness substrate, not session/queue authorization, provider stubs, private artifacts, CDN/object-storage, browser flows, live providers, or production exploitation.

## Integration Closure

Upstream surfaces consumed: `backend-hormonia/Dockerfile`, `backend-hormonia/app/main.py`, `backend-hormonia/app/core/database/async_engine.py`, `backend-hormonia/alembic.ini`, `backend-hormonia/alembic/env.py`, and `backend-hormonia/alembic/versions/6f8c2d4a9b10_enable_rls_sensitive_tables.py`. New wiring introduced: root M015 runner, isolated Compose stack, generated TLS cert lifecycle, synthetic DB roles, DB seam probe, evidence/redaction output. Remaining before milestone end-to-end: S02 plugs session/Dragonfly/Taskiq proof into the same runner, S03 plugs WuzAPI/Gemini stubs, S04 plugs private artifact routes, and S05 makes the no-filter runner plus evidence matrix closure strict.

## Verification

- The runner must emit phase-stamped, seam-scoped diagnostics (`setup`, `certs`, `compose`, `readiness`, `migrations`, `tls`, `rls`, `evidence`, `teardown`) with correlation IDs and sanitized service status. Evidence artifacts record command, timestamp, image/service versions, TLS protocol/cipher, RLS catalog state, allow/deny outcomes, and failure class without DSNs, credentials, tokens, PHI, raw private paths, or provider payloads. On failure, the last failed phase and sanitized remediation class must be visible from runner output and evidence validation errors.

## Tasks

- [x] **T01: Create isolated M015 runner and TLS runtime stack** `est:2h`
  Why: S01 needs a real, reproducible runtime substrate before the DB proof can be truthful; the existing `backend-hormonia/docker-compose.yml` has Dragonfly/API/worker/WuzAPI but no PostgreSQL TLS service and is too live-provider-oriented for this milestone.
  - Files: `.gitignore`, `scripts/security/verify-m015-runtime-security.sh`, `scripts/security/m015-runtime/docker-compose.yml`, `scripts/security/m015-runtime/postgres-init/001-roles.sh`, `scripts/security/m015-runtime/README.md`, `backend-hormonia/Dockerfile`
  - Verify: bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet

- [ ] **T02: Fix async PostgreSQL TLS handling for strict runtime participation** `est:1h30m`
  Why: The DB proof must include the actual FastAPI async DB path, not only an external psycopg probe. Current `app/core/database/async_engine.py` strips `sslmode=require/verify*` and builds an asyncpg SSL context with hostname verification disabled and `CERT_NONE`, so S01 must fix this before claiming runtime TLS posture.
  - Files: `backend-hormonia/app/core/database/async_engine.py`, `backend-hormonia/tests/core/test_async_engine_tls_config.py`
  - Verify: cd backend-hormonia && PYTHONPATH=. pytest tests/core/test_async_engine_tls_config.py tests/security/test_m014_s05_jwt_config_posture.py -q

- [ ] **T03: Implement DB seam probe with migrations, fixtures, TLS, RLS, and redacted evidence** `est:3h`
  Why: This task closes the S01 demo itself: the runner must not merely start containers; it must apply the real migration graph and prove DB TLS/RLS behavior through network/process boundaries with sanitized evidence.
  - Files: `scripts/security/verify-m015-runtime-security.sh`, `scripts/security/m015-runtime/db_seam.py`, `scripts/security/m015-runtime/redaction.py`, `backend-hormonia/docs/reports/security/m015/db-seam-evidence.json`, `backend-hormonia/docs/reports/security/m015/db-seam-summary.md`
  - Verify: ./scripts/security/verify-m015-runtime-security.sh --seam db

- [ ] **T04: Add harness contract tests and run the S01 closure gate** `est:1h30m`
  Why: S01 should be regression-safe after the first successful runtime proof. Unit/contract tests catch false-green runner changes, live-provider drift, and redaction regressions without requiring Docker for every small edit, while the final closure command still exercises the real DB seam.
  - Files: `backend-hormonia/tests/security/test_m015_runtime_harness.py`, `backend-hormonia/tests/core/test_async_engine_tls_config.py`, `scripts/security/verify-m015-runtime-security.sh`, `scripts/security/m015-runtime/docker-compose.yml`, `scripts/security/m015-runtime/redaction.py`
  - Verify: cd backend-hormonia && PYTHONPATH=. pytest tests/core/test_async_engine_tls_config.py tests/security/test_m015_runtime_harness.py -q && cd .. && ./scripts/security/verify-m015-runtime-security.sh --seam db

## Files Likely Touched

- .gitignore
- scripts/security/verify-m015-runtime-security.sh
- scripts/security/m015-runtime/docker-compose.yml
- scripts/security/m015-runtime/postgres-init/001-roles.sh
- scripts/security/m015-runtime/README.md
- backend-hormonia/Dockerfile
- backend-hormonia/app/core/database/async_engine.py
- backend-hormonia/tests/core/test_async_engine_tls_config.py
- scripts/security/m015-runtime/db_seam.py
- scripts/security/m015-runtime/redaction.py
- backend-hormonia/docs/reports/security/m015/db-seam-evidence.json
- backend-hormonia/docs/reports/security/m015/db-seam-summary.md
- backend-hormonia/tests/security/test_m015_runtime_harness.py
