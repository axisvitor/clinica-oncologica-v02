# M015 Synthetic Runtime Harness

This directory contains the isolated Docker Compose harness for M015 runtime security seams. The root entrypoint is:

```bash
./scripts/security/verify-m015-runtime-security.sh [--seam {db|session|provider|artifact}]
```

No seam filter runs final all-seam closeout in deterministic order (`db`, `session`, `provider`, `artifact`) and validates the M015 evidence matrix. Unknown seams fail closed before setup.

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

### `provider`

Proves M015/S03 network-real provider boundaries through controlled local HTTP stubs:

- `provider-stub` receives WuzAPI-compatible and Gemini-compatible HTTP traffic inside the Compose network.
- `provider-probe` exercises WuzAPI success/client-error/server-error/timeout/duplicate-or-replay scenarios and Gemini success/server-error scenarios.
- `provider-worker` imports `app.tasks.m015_provider_security_taskiq` and proves Taskiq worker participation with configured local stub URLs.
- Stub observations contain only provider, endpoint, method, scenario, status class, header-presence booleans, body hash, and redaction verdicts.
- Durable evidence explicitly records local stub usage and `live_provider_used=false` for WuzAPI/Gemini.
- Redaction-validated artifacts:
  - `backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json`
  - `backend-hormonia/docs/reports/security/m015/provider-seam-summary.md`
  - `backend-hormonia/docs/reports/security/m015/provider-stub-observations.jsonl`

### `artifact`

Proves M015/S04 private artifact app-route runtime behavior through the synthetic Docker stack:

- `artifact-probe` applies Alembic head, creates synthetic staff sessions, and calls real FastAPI HTTP routes with cookie-backed sessions.
- Private upload app-route downloads cover owner/admin success and anonymous/cross-owner denial.
- Direct `/uploads/<private-relative-path>` denial is verified while intentionally public uploads remain public.
- Base report, enhanced builder, and enhanced export download/status behavior are exercised through real FastAPI routes backed by synthetic Redis/DB fixtures.
- Gated attachment routes require safe attachment headers, unsafe private/static redirects are denied, and evidence omits private bytes, paths, raw cookies/session IDs, PHI, DSNs, and raw `download_urls`.
- Redaction-validated artifacts:
  - `backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json`
  - `backend-hormonia/docs/reports/security/m015/artifact-seam-summary.md`

### Final M015 evidence matrix

The no-filter runner mode executes all implemented seams, then invokes `evidence_matrix.py` to write and validate:

- `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json`
- `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.md`

The matrix maps the M014-deferred runtime items and requirements R012/R013/R014/R015/R017/R018 to fresh evidence, fixed outcome, explicit non-goal, or a closure-blocking failure. The validator rejects missing rows, failed seams, stale evidence correlations, placeholders, raw sensitive content, raw download URLs/private paths, unclassified warnings, and unresolved red signals.

## Synthetic runtime posture

The runner generates `.m015-runtime/m015.env` with production-like safety defaults and synthetic-only values:

- `APP_ENVIRONMENT=production`
- `APP_ENABLE_DEBUG=false`
- `ALLOW_AI_SIMULATION=false`
- `WHATSAPP_ENABLE_SERVICE=false`
- synthetic Gemini/WuzAPI/security keys only
- PostgreSQL URLs using `sslmode=verify-full`, `sslrootcert=/m015-certs/ca.crt`, and `ssl_min_protocol_version=TLSv1.2`

The Compose file must not use `backend-hormonia/.env`, production volumes, production data, WuzAPI service containers, Firebase credentials, real patient data, live provider payloads, or CDN/object-storage/browser surfaces.

## Useful commands

```bash
# Run final all-seam closeout and validate the M015 evidence matrix.
./scripts/security/verify-m015-runtime-security.sh

# Show implemented seams.
./scripts/security/verify-m015-runtime-security.sh --list-seams

# Start DB seam, check readiness, write evidence, and tear down automatically.
./scripts/security/verify-m015-runtime-security.sh --seam db

# Start session seam, check API/cache/DB/worker behavior, write evidence, and tear down automatically.
./scripts/security/verify-m015-runtime-security.sh --seam session

# Start provider seam, check local WuzAPI/Gemini stubs and worker behavior, write evidence, and tear down automatically.
./scripts/security/verify-m015-runtime-security.sh --seam provider

# Start artifact seam, check upload/report app-route ownership and redaction-safe evidence, and tear down automatically.
./scripts/security/verify-m015-runtime-security.sh --seam artifact

# Keep the stack for inspection.
./scripts/security/verify-m015-runtime-security.sh --seam session --keep-stack --project-name m015-debug

# Idempotent teardown for an inspected stack.
./scripts/security/verify-m015-runtime-security.sh --seam session --project-name m015-debug --teardown-only

# Static validation without starting services.
docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet
```

## Recovery notes

- Unknown seams fail closed before setup; rerun with `--list-seams` if unsure.
- Missing Docker, Compose, OpenSSL, busy host ports, certificate generation failure, Compose startup failure, readiness timeout, probe failure, and teardown failure all emit `correlation_id`, `seam`, `phase`, `status`, and `failure_class`.
- Sanitized runner logs are written under `scripts/security/m015-runtime/evidence/<correlation-id>/`.
- `.m015-runtime/` is ignored scratch space for generated env files, certificates, and local logs. Delete it freely; the runner regenerates it.
- If `--keep-stack` was used, clean up with the same `--project-name` and `--teardown-only`.

## Evidence and redaction contract

Durable evidence is written via `write_validated_json`/`write_validated_text`. Artifacts must contain command names, correlation IDs, status codes/classes, cache/DB/worker/route outcomes, hashed identifiers, booleans, timestamps, versions, failure classes, teardown status, and non-goals only.

Evidence must not contain DSNs, credentials, tokens, private keys, raw Authorization/Cookie/Set-Cookie headers, raw session IDs, raw provider payloads, raw uploaded/report bytes, private filesystem paths, host-private paths, certificate paths, SQL statements, PHI-shaped values, raw `download_urls`, or live-provider payloads.

## Non-goals

- The harness never uses real patient/provider data or production systems.
- M015 does not execute production exploitation, broad DAST/fuzzing, frontend/browser UX validation, CDN proof, or object-storage proof.
- S04 artifact proof does not re-prove S01 DB TLS/RLS, S02 session revocation, S03 provider stubs, or S05 final all-seam matrix closure beyond consuming their established runtime/evidence substrate.
