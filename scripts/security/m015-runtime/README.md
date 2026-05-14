# M015 Synthetic Runtime Harness (S01)

This directory contains the committed harness substrate for M015/S01. The root entrypoint is:

```bash
./scripts/security/verify-m015-runtime-security.sh --seam db
```

## What S01 provides

- An isolated Docker Compose project with `postgres`, `dragonfly`, `api`, `worker`, and `db-probe` services.
- PostgreSQL TLS enabled with local-only CA/server certificates generated under `.m015-runtime/certs`.
- A generated synthetic env file at `.m015-runtime/m015.env` with production-like posture:
  - `APP_ENVIRONMENT=production`
  - `APP_ENABLE_DEBUG=false`
  - `ALLOW_AI_SIMULATION=false`
  - `WHATSAPP_ENABLE_SERVICE=false`
  - synthetic Gemini/WuzAPI/security keys only
  - PostgreSQL URLs using `sslmode=verify-full`, `sslrootcert=/m015-certs/ca.crt`, and `sslminversion=TLSv1.2`
- Postgres init roles:
  - `hormonia_app`: non-superuser database owner for the backend runtime.
  - `m015_rls_denied`: non-superuser role for later allow/deny RLS proof tasks.
- Phase-stamped runner diagnostics and sanitized evidence under `scripts/security/m015-runtime/evidence/<correlation-id>/`.

## Non-goals in this task

- This task does not prove Alembic migrations or RLS allow/deny behavior; later S01 tasks extend the DB seam for that proof.
- This harness does not start WuzAPI or any live provider service.
- This harness must not reuse `backend-hormonia/.env`, production volumes, production data, real patient data, or real provider payloads.

## Useful commands

```bash
# Show implemented seams.
./scripts/security/verify-m015-runtime-security.sh --list-seams

# Start DB seam substrate, check readiness, and tear down automatically.
./scripts/security/verify-m015-runtime-security.sh --seam db

# Keep the stack for inspection.
./scripts/security/verify-m015-runtime-security.sh --seam db --keep-stack --project-name m015-debug

# Idempotent teardown for an inspected stack.
./scripts/security/verify-m015-runtime-security.sh --seam db --project-name m015-debug --teardown-only

# Static validation without starting services.
docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet
```

## Generated material

`.m015-runtime/` is intentionally ignored by git. It contains generated env, certificates, and local logs. Treat it as scratch and delete it freely; the runner regenerates it.

Sanitized evidence under `scripts/security/m015-runtime/evidence/` is intended to be trackable when a future task needs to preserve proof output. Evidence must not contain DSNs, credentials, tokens, PHI, raw private paths, or provider payloads.

## Failure classes

The runner fails closed for unknown seams, omitted `--seam`, missing Docker/Compose/OpenSSL, Docker daemon unavailability, certificate generation failure, host port collision, Compose startup failure, Postgres TLS readiness timeout, Dragonfly timeout, API health timeout, and worker liveness failure. Failures include `correlation_id`, `seam`, `phase`, `status`, and a sanitized remediation class.
