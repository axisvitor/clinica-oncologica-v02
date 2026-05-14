# M015 Synthetic Runtime Harness

This directory contains the isolated Docker Compose harness for M015 runtime security seams. The root entrypoint is:

```bash
./scripts/security/verify-m015-runtime-security.sh --seam {db|session}
```

## Implemented seams

### `db`

Proves the M015 DB substrate with synthetic services only:

- `postgres`, `dragonfly`, `api`, `worker`, and `db-probe` services in an isolated Compose project.
- PostgreSQL TLS enabled with local-only CA/server certificates generated under `.m015-runtime/certs`.
- Alembic migration execution, app-role connectivity, TLS evidence, and RLS allow/deny proof.
- Redaction-validated artifacts:
  - `backend-hormonia/docs/reports/security/m015/db-seam-evidence.json`
  - `backend-hormonia/docs/reports/security/m015/db-seam-summary.md`

### `session`

Proves M015/S02 cross-process staff-session revocation through the same synthetic stack:

- `session-probe` runs `session_seam.py`; the real worker imports `app.tasks.m015_session_security_taskiq`.
- API proof uses cookie-backed staff auth against `/api/v2/users/me`.
- Negative transport proof confirms legacy `X-Session-ID` and bearer-only requests fail closed without the session cookie.
- Explicit revocation proof uses `/api/v2/users/sessions/{session_id}` and verifies Dragonfly session cache deletion.
- Cache/DB proof covers active cache hits, cache-miss PostgreSQL fallback with cache rehydration, revoked stale-cache denial, and expired stale-cache denial.
- Worker proof queues Taskiq work before revocation and requires the worker to re-check PostgreSQL before returning `denied/revoked_or_expired`.
- Redaction-validated artifacts:
  - `backend-hormonia/docs/reports/security/m015/session-seam-evidence.json`
  - `backend-hormonia/docs/reports/security/m015/session-seam-summary.md`

## Synthetic runtime posture

The runner generates `.m015-runtime/m015.env` with production-like safety defaults and synthetic-only values:

- `APP_ENVIRONMENT=production`
- `APP_ENABLE_DEBUG=false`
- `ALLOW_AI_SIMULATION=false`
- `WHATSAPP_ENABLE_SERVICE=false`
- synthetic Gemini/WuzAPI/security keys only
- PostgreSQL URLs using `sslmode=verify-full`, `sslrootcert=/m015-certs/ca.crt`, and `ssl_min_protocol_version=TLSv1.2`

The Compose file must not use `backend-hormonia/.env`, production volumes, production data, WuzAPI, Firebase credentials, real patient data, or live provider payloads.

## Useful commands

```bash
# Show implemented seams.
./scripts/security/verify-m015-runtime-security.sh --list-seams

# Start DB seam, check readiness, write evidence, and tear down automatically.
./scripts/security/verify-m015-runtime-security.sh --seam db

# Start session seam, check API/cache/DB/worker behavior, write evidence, and tear down automatically.
./scripts/security/verify-m015-runtime-security.sh --seam session

# Keep the stack for inspection.
./scripts/security/verify-m015-runtime-security.sh --seam session --keep-stack --project-name m015-debug

# Idempotent teardown for an inspected stack.
./scripts/security/verify-m015-runtime-security.sh --seam session --project-name m015-debug --teardown-only

# Static validation without starting services.
docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet
```

## Recovery notes

- Unknown or omitted seams fail closed before setup; rerun with `--list-seams` if unsure.
- Missing Docker, Compose, OpenSSL, busy host ports, certificate generation failure, Compose startup failure, readiness timeout, probe failure, and teardown failure all emit `correlation_id`, `seam`, `phase`, `status`, and `failure_class`.
- Sanitized runner logs are written under `scripts/security/m015-runtime/evidence/<correlation-id>/`.
- `.m015-runtime/` is ignored scratch space for generated env files, certificates, and local logs. Delete it freely; the runner regenerates it.
- If `--keep-stack` was used, clean up with the same `--project-name` and `--teardown-only`.

## Evidence and redaction contract

Durable evidence is written via `write_validated_json`/`write_validated_text`. Artifacts must contain status codes, cache/DB/worker outcomes, hashed identifiers, booleans, timestamps, versions, failure classes, and non-goals only. They must not contain DSNs, credentials, tokens, private keys, raw cookies, raw session IDs, PHI, host-private paths, certificate paths, SQL statements, or live-provider payloads.

## Non-goals

- The `session` seam does not exercise provider artifact seams or live WhatsApp/Gemini/Firebase integrations.
- The harness never uses real patient/provider data.
- The session probe is intentionally small; load testing and provider matrix coverage belong to later slices.
