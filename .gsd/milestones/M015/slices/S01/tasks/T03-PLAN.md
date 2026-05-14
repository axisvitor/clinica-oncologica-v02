---
estimated_steps: 17
estimated_files: 5
skills_used: []
---

# T03: Added the M015 DB seam probe, redaction guard, Compose wiring, and root-path test shims; exact unit gate now passes, while full runtime verification stops at a migration URL option failure that needs continuation.

Why: This task closes the S01 demo itself: the runner must not merely start containers; it must apply the real migration graph and prove DB TLS/RLS behavior through network/process boundaries with sanitized evidence.

Expected executor skills_used frontmatter: `tdd`, `verify-before-complete`, `observability`, `security-review`.
Estimated scope: about 10 steps / 5 files.

Do:
1. Add `scripts/security/m015-runtime/db_seam.py` as the one-shot probe run by the `db-probe` service from the backend image/network.
2. From the probe, wait for PostgreSQL over `sslmode=verify-full` using the generated CA, then run `python -m alembic -c alembic.ini upgrade head` against the non-superuser `hormonia_app` URL with sanitized subprocess output.
3. Verify FastAPI starts and reports `/health` healthy while configured with the same TLS DB URL; do not accept a proof where only an out-of-band DB client negotiated TLS.
4. Collect TLS evidence using `pg_stat_ssl` for the current backend/probe connection (`ssl=true`, protocol TLSv1.2+ or TLSv1.3, cipher present) plus sanitized server posture (`SHOW ssl`), without writing DSNs or cert paths.
5. Collect catalog evidence for `patients`, `messages`, `quiz_sessions`, `quiz_responses`, `lgpd_audit_logs`, `lgpd_data_access_requests`, and `consents`: table exists when expected, `relrowsecurity=true`, `relforcerowsecurity=true`, `PUBLIC` privileges revoked, and policy names/roles are present.
6. Insert one synthetic patient row as `hormonia_app` using only generated UUIDs and a non-PHI sentinel; evidence may record a hash/correlation ID, never the row value.
7. Grant schema/table privileges to `m015_rls_denied` without creating a matching RLS policy, then prove that role cannot see or insert the synthetic patient because of RLS (not merely because of missing table privileges). Treat unexpected allow as a red security failure.
8. Add `scripts/security/m015-runtime/redaction.py` or equivalent shared helper to validate evidence before writing; reject credentialed URLs, `BEGIN ... PRIVATE KEY`, cookies, authorization headers, Firebase/service-account material, real-looking CPF/email/phone, raw `/mnt/c` paths, and non-synthetic patient/provider payloads.
9. Write `backend-hormonia/docs/reports/security/m015/db-seam-evidence.json` and `backend-hormonia/docs/reports/security/m015/db-seam-summary.md` with command, timestamps, service versions, migration head/current, TLS result, RLS allow/deny result, teardown result, and explicit non-goals for S02-S05 seams.
10. Ensure runner teardown runs on success and failure; if `--keep-runtime` is later added for debugging, it must be opt-in and must still redact output.

Failure Modes (Q5): Postgres TLS handshake failure -> TLS phase red; migration failure -> migration phase red with offending revision if available; API cannot start with strict TLS -> runtime phase red; app role cannot access due wrong migration owner/policy -> RLS allow red; denied role can access -> RLS deny red; redaction hit -> evidence phase red and no green summary.

Load Profile (Q6): shared resources are DB connections, Alembic locks, Docker logs, and evidence files. Per run performs one migration graph, one synthetic insert, catalog queries, and two role probes. At 10x, Postgres max connections/Alembic schema locks and Docker CPU break first; keep pool sizes minimal and project names isolated.

Negative Tests (Q7): sslmode disabled or verify-full CA mismatch must fail; migration as superuser/app owner shortcut must not bypass RLS proof; denied role with table grants but no policy must fail; empty evidence or evidence containing denylisted sensitive patterns must fail.

## Inputs

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `scripts/security/m015-runtime/postgres-init/001-roles.sh`
- `backend-hormonia/app/core/database/async_engine.py`
- `backend-hormonia/alembic.ini`
- `backend-hormonia/alembic/env.py`
- `backend-hormonia/alembic/versions/6f8c2d4a9b10_enable_rls_sensitive_tables.py`
- `backend-hormonia/app/models/patient.py`

## Expected Output

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/db_seam.py`
- `scripts/security/m015-runtime/redaction.py`
- `backend-hormonia/docs/reports/security/m015/db-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/db-seam-summary.md`

## Verification

./scripts/security/verify-m015-runtime-security.sh --seam db

## Observability Impact

Creates the durable DB evidence artifacts and per-phase failure classes that downstream S02-S05 can reuse. A future agent can inspect the JSON/summary for TLS protocol/cipher, migration state, RLS catalog flags, allow/deny outcomes, redaction verdict, and teardown status without sensitive material.
