---
estimated_steps: 15
estimated_files: 6
skills_used:
  - tdd
  - verify-before-complete
  - observability
---

# T01: Create isolated M015 runner and TLS runtime stack

Why: S01 needs a real, reproducible runtime substrate before the DB proof can be truthful; the existing `backend-hormonia/docker-compose.yml` has Dragonfly/API/worker/WuzAPI but no PostgreSQL TLS service and is too live-provider-oriented for this milestone.

Expected executor skills_used frontmatter: `tdd`, `verify-before-complete`, `observability`.
Estimated scope: about 8 steps / 6 files.

Do:
1. Create the root public entrypoint `scripts/security/verify-m015-runtime-security.sh` with strict shell mode, `--seam db`, `--help`, `--list-seams`, clear rejection for unknown seams, and a fail-closed default that does not claim unimplemented S02-S05 seams as green.
2. Add `scripts/security/m015-runtime/docker-compose.yml` using an isolated project name, no `env_file: .env`, no production/live provider service for S01, no production data volumes, and services for `postgres`, `dragonfly`, `api`, `worker` (started for substrate/readiness, queue proof deferred), and `db-probe`.
3. Add `scripts/security/m015-runtime/postgres-init/001-roles.sh` to create a non-superuser `hormonia_app` role/database owner and a separate granted-but-unpolicied `m015_rls_denied` role using synthetic passwords from generated env, not committed secrets.
4. Have the runner generate local-only CA/server certs under `.m015-runtime/certs` with SANs for `postgres`, `localhost`, and `127.0.0.1`; configure PostgreSQL `ssl=on`, `ssl_cert_file`, `ssl_key_file`, and permissions compatible with the official Postgres image.
5. Generate an ignored `.m015-runtime/m015.env` with synthetic strong keys, `APP_ENVIRONMENT=production`-like posture, `ALLOW_AI_SIMULATION=false`, a synthetic Gemini key, `WHATSAPP_ENABLE_SERVICE=false`, Redis/Dragonfly URLs, and DB URLs using `sslmode=verify-full`, `sslrootcert`, and `sslminversion=TLSv1.2`.
6. Add readiness helpers for Docker Compose, Postgres TLS, Dragonfly ping, FastAPI `/health`, and worker process liveness; all logs must mask env values and DSNs.
7. Update `.gitignore` for `.m015-runtime/` generated certs/env/log scratch while leaving committed harness assets and sanitized evidence trackable.
8. Add a short `scripts/security/m015-runtime/README.md` documenting S01 usage, non-goals, generated material, and teardown.

Failure Modes (Q5): Docker/Compose/OpenSSL unavailable -> setup failure, not green; cert generation failure -> setup failure before services start; port collision -> fail with the configured port and cleanup; API readiness timeout -> show sanitized compose status/log tail; malformed seam -> non-zero exit and no service startup.

Load Profile (Q6): shared resources are Docker daemon, local ports, Postgres volume, Dragonfly memory, and backend image build cache. Per run is one isolated stack and one DB proof; at 10x parallelism, port/project/volume collisions and Docker resource exhaustion break first, so use unique project names and configurable API port.

Negative Tests (Q7): unknown `--seam` fails; missing Docker/OpenSSL detected before partial green; generated env must not reuse `.env`; teardown can be run twice; evidence directory creation must not require production paths.

## Inputs

- `backend-hormonia/docker-compose.yml`
- `backend-hormonia/Dockerfile`
- `backend-hormonia/app/main.py`
- `.gitignore`

## Expected Output

- `.gitignore`
- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `scripts/security/m015-runtime/postgres-init/001-roles.sh`
- `scripts/security/m015-runtime/README.md`

## Verification

bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet

## Observability Impact

Introduces the runner's phase model, sanitized setup/readiness output, compose status capture, teardown reporting, and ignored scratch location. Future agents can inspect `scripts/security/m015-runtime/README.md`, runner output, and generated sanitized evidence rather than raw Docker secrets.
