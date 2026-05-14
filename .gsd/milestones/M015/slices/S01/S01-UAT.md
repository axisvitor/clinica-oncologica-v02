# S01: S01 — UAT

**Milestone:** M015
**Written:** 2026-05-14T06:48:27.652Z

## UAT Type

Automated local/CI runtime UAT for the M015 DB security seam. No human browser flow is required.

## Preconditions

1. Docker Engine and Docker Compose v2 are available to the current shell.
2. The repository root is the working directory.
3. No service is already listening on the default M015 FastAPI/PostgreSQL ports, or alternate ports are supplied with `M015_API_PORT` / `M015_POSTGRES_PORT`.
4. No production DSNs, live provider credentials, real PHI, cookies, JWTs, or service-account material are needed; the runner generates synthetic-only secrets and certs.

## Steps

1. Run `bash -n scripts/security/verify-m015-runtime-security.sh`.
2. Run `docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet`.
3. Run `cd backend-hormonia && PYTHONPATH=. pytest tests/core/test_async_engine_tls_config.py tests/security/test_m015_runtime_harness.py -q`.
4. Return to the repository root and run `./scripts/security/verify-m015-runtime-security.sh --seam db`.
5. Inspect `backend-hormonia/docs/reports/security/m015/db-seam-summary.md` and `backend-hormonia/docs/reports/security/m015/db-seam-evidence.json`.

## Expected Outcomes

1. The shell syntax check exits 0.
2. Docker Compose renders the synthetic M015 stack without project env files or live WuzAPI/Gemini services.
3. The focused pytest suite passes all async TLS and M015 harness contract tests.
4. The DB seam runner emits phase-stamped setup/certs/compose/readiness/migrations/tls/rls/evidence/teardown diagnostics with a correlation ID, starts only isolated synthetic services, applies Alembic head, verifies FastAPI DB-backed readiness, records TLS protocol/cipher evidence, proves application-role allow and denied-role RLS behavior, validates redaction, writes DB seam evidence/summary artifacts, and tears down containers/volumes/temp certs idempotently.
5. Durable evidence contains no credentialed DSNs, private keys/certs, cookies/tokens, Firebase/service-account content, real-looking CPF/email/phone/patient names, raw `/mnt/c` paths, or unsafe SQL stderr.

## Edge Cases

- Omitted or unknown `--seam` values fail before setup/service startup.
- Unsupported migration TLS query options fail closed without leaking the source DSN.
- Redaction denylist hits remove/avoid green durable evidence.
- Runner failure diagnostics preserve last phase and sanitized remediation class for follow-up.

## Not Proven By This UAT

- S02 session/Dragonfly/Taskiq authorization semantics beyond the shared harness substrate.
- S03 WuzAPI/Gemini network-real stubs and provider failure modes.
- S04 private artifact app-route access controls.
- S05 all-seam aggregation/evidence matrix closure.
- Browser/frontend flows, CDN/object-storage guarantees, production exploitation, or live provider behavior.
