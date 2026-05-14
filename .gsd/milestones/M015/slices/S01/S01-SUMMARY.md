---
id: S01
parent: M015
milestone: M015
provides:
  - M015 root runtime runner substrate for the DB seam
  - Synthetic TLS PostgreSQL + Dragonfly + FastAPI + worker Compose harness
  - Alembic migration and DB TLS/RLS evidence artifacts for S01
  - Contract tests guarding runner, redaction, evidence, and migration TLS compatibility behavior
requires:
  []
affects:
  - R012 DB TLS/RLS runtime proof
  - R014 synthetic runtime harness
  - R015 no production/real PHI
  - R017/R018 sanitized evidence discipline
key_files:
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/docker-compose.yml
  - scripts/security/m015-runtime/db_seam.py
  - scripts/security/m015-runtime/redaction.py
  - scripts/security/m015-runtime/postgres-init/001-roles.sh
  - backend-hormonia/app/core/database/async_engine.py
  - backend-hormonia/app/db/migrations.py
  - backend-hormonia/tests/core/test_async_engine_tls_config.py
  - backend-hormonia/tests/security/test_m015_runtime_harness.py
  - backend-hormonia/docs/reports/security/m015/db-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/db-seam-summary.md
key_decisions:
  - Use ignored .m015-runtime/ scratch for generated env/certs/logs while keeping harness assets committed under scripts/security/m015-runtime/.
  - Fail closed for omitted/unknown seam selection and for unsupported migration TLS query options before claiming green evidence.
  - Keep async runtime TLS verification in the FastAPI path while normalizing migration DSNs to psycopg/libpq-compatible TLS keys.
  - Persist DB seam evidence only after redaction validation against credentials, PHI-shaped values, provider/service-account content, host/cert paths, and raw SQL stderr.
patterns_established:
  - Single seam-filterable runtime security runner with phase-stamped sanitized diagnostics and idempotent teardown.
  - Synthetic-only DB seam evidence shape recording command, versions, TLS protocol/cipher, migration role/head state, RLS catalog posture, allow/deny outcomes, non-goals, and redaction status.
  - Contract-first harness tests for CLI fail-closed behavior, Compose isolation, evidence paths, redaction denylist, and migration TLS compatibility.
observability_surfaces:
  - Runner stdout phase diagnostics with correlation_id, seam, phase, status, and sanitized remediation class.
  - Repo-local runtime event logs under scripts/security/m015-runtime/evidence/<correlation_id>/.
  - Durable sanitized evidence artifacts under backend-hormonia/docs/reports/security/m015/.
drill_down_paths:
  - backend-hormonia/docs/reports/security/m015/db-seam-summary.md
  - backend-hormonia/docs/reports/security/m015/db-seam-evidence.json
  - scripts/security/m015-runtime/evidence/
duration: ""
verification_result: passed
completed_at: 2026-05-14T06:48:27.643Z
blocker_discovered: false
---

# S01: S01

**Built and verified the M015 synthetic DB runtime seam: isolated Docker Compose stack, TLS PostgreSQL/FastAPI readiness, Alembic migrations, RLS allow/deny proof, sanitized evidence, and idempotent teardown.**

## What Happened

S01 established the reusable M015 runtime harness substrate and closed the DB seam. The root runner now fails closed unless `--seam db` is selected, creates ignored runtime scratch under `.m015-runtime/`, generates local-only PostgreSQL CA/server certificates, starts an isolated Docker Compose project with PostgreSQL, Dragonfly, FastAPI, worker, and db-probe services, applies the real Alembic graph using synthetic-only database configuration, checks FastAPI health/readiness through the app runtime, records PostgreSQL TLS negotiation evidence, and writes redaction-validated DB seam JSON/Markdown artifacts. The backend async engine now preserves strict asyncpg TLS behavior with verify-full/verify-ca handling, sanitized diagnostics, and TLS minimum-version support, while migration URL resolution normalizes async-style TLS aliases to libpq-compatible keys and rejects unknown ssl* options without echoing DSNs. Contract coverage now guards seam CLI validation, Compose isolation from project env files and live WuzAPI/Gemini services, evidence path discipline, redaction denylist behavior, migration TLS option filtering, and validator-clean durable evidence. The final runtime run regenerated `backend-hormonia/docs/reports/security/m015/db-seam-evidence.json` and `backend-hormonia/docs/reports/security/m015/db-seam-summary.md` with correlation_id `m015-20260514T063333Z-1254497`, TLSv1.3 / TLS_AES_256_GCM_SHA384, Alembic head `m013_s04_upload_deleted_at`, application-role insert allow evidence, denied-role RLS select/insert denial evidence, redaction passed, and teardown complete.

## Verification

Fresh closeout verification passed in this attempt: (1) `bash -n scripts/security/verify-m015-runtime-security.sh` exited 0 in 16ms; (2) `docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet` exited 0 in 770ms; (3) `cd backend-hormonia && PYTHONPATH=. pytest tests/core/test_async_engine_tls_config.py tests/security/test_m015_runtime_harness.py -q` exited 0 in 21879ms with 33 tests passing; (4) `cd .. && ./scripts/security/verify-m015-runtime-security.sh --seam db` exited 0 in 77384ms. The runtime evidence summary confirms command `./scripts/security/verify-m015-runtime-security.sh --seam db`, redaction `passed`, teardown `complete`, PostgreSQL SSL `on`, current connection SSL `passed`, protocol `TLSv1.3`, cipher `TLS_AES_256_GCM_SHA384`, FastAPI `/health` healthy, `/health/ready` ready with database dependency healthy, Alembic exit code 0 as `hormonia_app`, forced RLS/catalog posture for existing sensitive tables, app-role insert allowed, and denied-role select/insert blocked by RLS.

## Requirements Advanced

- R012 — DB TLS negotiation and RLS posture/allow-deny behavior are proven through the synthetic runtime DB seam.
- R014 — Runtime harness substrate now starts and tears down a synthetic production-like DB stack via a root runner.
- R015 — Evidence and runtime inputs are synthetic-only and redaction-validated against PHI/secrets/provider payloads.
- R017 — Evidence artifacts record concrete command/timestamp/version/TLS/RLS outcomes with sanitized diagnostics.
- R018 — Non-goals and downstream seams are explicitly recorded so deferred runtime items are not silently lost.

## Requirements Validated

- R012 — Fresh DB seam runtime verification exited 0 and recorded TLSv1.3/TLS_AES_256_GCM_SHA384 plus RLS allow/deny evidence.
- R014 — Runner started the isolated Compose stack, applied migrations, generated evidence, and completed teardown.
- R015 — Redaction validation passed for durable evidence and contract tests exercise denylisted PHI/secret/provider/path/SQL shapes.
- R017 — Evidence JSON/summary include command, versions, TLS protocol/cipher, migration state, RLS catalog and allow/deny outcomes.
- R018 — Evidence summary lists S02-S05 non-goals and slice summary records remaining seams not proven by S01.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

Health signal: FastAPI `/health` and `/health/ready` are checked inside the Compose network; PostgreSQL TLS, Dragonfly ping, worker liveness, Alembic head, TLS evidence, RLS proof, redaction status, and teardown status are captured. Failure signal: runner output and repo-local event logs include correlation_id, seam, phase, status, failure_class, last failed phase, sanitized compose status/log tail, and remediation class. Recovery procedure: rerun the exact seam command after addressing the named phase; use `--project-name <name> --teardown-only` for explicit cleanup if a debug `--keep-stack` run is left behind. Monitoring gaps: this is a local/CI runtime proof harness, not production monitoring, and S02-S05 must extend the same evidence discipline for sessions, providers, artifacts, and aggregate closure.

## Deviations

None.

## Known Limitations

S01 intentionally proves only the DB TLS/RLS seam and shared harness substrate. Session/queue authorization, provider stubs, private artifact routes, all-seam evidence matrix closure, browser/frontend flows, live providers, production exploitation, and CDN/object-storage behavior remain outside this slice and are assigned to S02-S05/non-goals.

## Follow-ups

Continue with S02 to extend the harness into cross-process session revocation, Dragonfly fallback, and Taskiq worker authorization proof; later slices should preserve the S01 redaction/evidence contract and avoid overclaiming seams not exercised by the selected runner mode.

## Files Created/Modified

- `.gitignore` — Ignores generated M015 runtime scratch material.
- `scripts/security/verify-m015-runtime-security.sh` — Root seam-filtered runner with setup/certs/compose/readiness/migrations/tls/rls/evidence/teardown diagnostics.
- `scripts/security/m015-runtime/docker-compose.yml` — Isolated synthetic Compose stack for PostgreSQL TLS, Dragonfly, FastAPI, worker, and db-probe.
- `scripts/security/m015-runtime/postgres-init/001-roles.sh` — Synthetic database role initialization for app and denied RLS probes.
- `scripts/security/m015-runtime/README.md` — Harness usage and TLS evidence notes.
- `scripts/security/m015-runtime/db_seam.py` — Runtime DB seam probe for Alembic, FastAPI readiness, TLS, RLS, evidence, and redaction validation.
- `scripts/security/m015-runtime/redaction.py` — Durable evidence denylist and atomic validated write helpers.
- `backend-hormonia/app/core/database/async_engine.py` — Async PostgreSQL TLS parsing, strict SSLContext setup, and sanitized diagnostics.
- `backend-hormonia/app/db/migrations.py` — Alembic-safe URL resolution with migration TLS option normalization/rejection.
- `backend-hormonia/tests/core/test_async_engine_tls_config.py` — Focused async engine TLS behavior and sanitization coverage.
- `backend-hormonia/tests/security/test_m015_runtime_harness.py` — Harness contract/redaction/migration URL/evidence coverage.
- `backend-hormonia/docs/reports/security/m015/db-seam-evidence.json` — Fresh sanitized DB seam runtime evidence from the current pass.
- `backend-hormonia/docs/reports/security/m015/db-seam-summary.md` — Fresh sanitized human-readable DB seam evidence summary from the current pass.
