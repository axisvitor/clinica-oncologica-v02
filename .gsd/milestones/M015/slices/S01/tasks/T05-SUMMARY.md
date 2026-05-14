---
id: T05
parent: S01
milestone: M015
key_files:
  - backend-hormonia/tests/security/test_m015_runtime_harness.py
  - backend-hormonia/tests/core/test_async_engine_tls_config.py
  - backend-hormonia/app/db/migrations.py
  - scripts/security/m015-runtime/redaction.py
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/docker-compose.yml
  - backend-hormonia/docs/reports/security/m015/db-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/db-seam-summary.md
key_decisions:
  - Keep durable DB seam evidence fail-closed against credentials, PHI-shaped values, provider/service-account material, raw host/cert paths, and SQL stderr.
  - Normalize async-style TLS minimum/maximum aliases to libpq-compatible migration query keys while rejecting unknown ssl* options without echoing DSNs.
duration: 
verification_result: passed
completed_at: 2026-05-14T06:36:45.731Z
blocker_discovered: false
---

# T05: Hardened the M015 DB harness contract tests and closed the S01 DB seam gate with fresh sanitized TLS/RLS evidence.

**Hardened the M015 DB harness contract tests and closed the S01 DB seam gate with fresh sanitized TLS/RLS evidence.**

## What Happened

Finalized the M015 DB runtime harness contract surface so the closure gate is regression-safe without requiring Docker for every edit. The contract suite now proves fail-closed seam CLI behavior, Compose isolation from project env files and live provider services, repo-relative evidence path wiring, psycopg/libpq-compatible migration TLS option normalization and rejection of unsupported TLS options without leaking DSNs, and durable-evidence redaction guardrails for credentials, private keys/certs, cookies/tokens, Firebase/service-account material, CPF/email/phone/patient/provider payloads, raw Windows mount paths, runtime cert paths, and unsafe raw SQL stderr. The current runtime run regenerated sanitized DB seam evidence and summary artifacts showing Alembic completion as the synthetic app role, FastAPI DB-backed readiness over verify-full TLS, PostgreSQL TLSv1.3/TLS_AES_256_GCM_SHA384, RLS catalog posture, app-role allow behavior, denied-role select/insert blocking, and idempotent teardown.

## Verification

Ran the exact S01 must-have gates in the current attempt: runner shell syntax, isolated Docker Compose config rendering, focused TLS/runtime harness pytest contract suite, and the full DB seam runtime verification command. The final runtime command wrote validator-clean evidence to backend-hormonia/docs/reports/security/m015/db-seam-evidence.json and backend-hormonia/docs/reports/security/m015/db-seam-summary.md with correlation_id m015-20260514T063333Z-1254497 and teardown complete.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash -n scripts/security/verify-m015-runtime-security.sh` | 0 | ✅ pass | 16ms |
| 2 | `docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet` | 0 | ✅ pass | 770ms |
| 3 | `cd backend-hormonia && PYTHONPATH=. pytest tests/core/test_async_engine_tls_config.py tests/security/test_m015_runtime_harness.py -q` | 0 | ✅ pass | 21879ms |
| 4 | `cd .. && ./scripts/security/verify-m015-runtime-security.sh --seam db` | 0 | ✅ pass | 77384ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
- `backend-hormonia/tests/core/test_async_engine_tls_config.py`
- `backend-hormonia/app/db/migrations.py`
- `scripts/security/m015-runtime/redaction.py`
- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `backend-hormonia/docs/reports/security/m015/db-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/db-seam-summary.md`
