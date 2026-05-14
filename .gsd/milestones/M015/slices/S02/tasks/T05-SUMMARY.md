---
id: T05
parent: S02
milestone: M015
key_files:
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/docker-compose.yml
  - scripts/security/m015-runtime/session_seam.py
  - scripts/security/m015-runtime/m015_session_security_taskiq.py
  - backend-hormonia/docs/reports/security/m015/session-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/session-seam-summary.md
  - backend-hormonia/tests/security/test_m015_runtime_harness.py
key_decisions:
  - Stable session seam evidence is generated only after the real root runner passes with teardown complete and redaction validation true.
  - Synthetic production-mode session revocation uses the real CSRF double-submit boundary instead of bypassing middleware.
  - Taskiq worker proof uses PostgreSQL state as the authority and receives only synthetic runtime connection configuration.
duration: 
verification_result: passed
completed_at: 2026-05-14T10:15:30.013Z
blocker_discovered: false
---

# T05: Ran the M015 session seam end-to-end and refreshed redaction-validated session evidence with current/cache-miss/revoked/expired/revocation/worker outcomes.

**Ran the M015 session seam end-to-end and refreshed redaction-validated session evidence with current/cache-miss/revoked/expired/revocation/worker outcomes.**

## What Happened

Ran the root M015 session seam through the isolated Docker runtime stack and refreshed stable sanitized evidence artifacts. The run brought up PostgreSQL with TLS, Dragonfly, FastAPI, and the real Taskiq worker; applied migrations; exercised cookie-backed staff auth, cache-miss fallback/rehydration, stale-cache revoked and expired denial, explicit user revocation cache invalidation, legacy transport denial, and queued worker PostgreSQL re-check; wrote `session-seam-evidence.json` and `session-seam-summary.md`; and completed teardown. During the auto-fix, earlier red runs exposed real runtime wiring issues that were corrected before the final green run: RedisManager metadata-preserving rehydration, CSRF token handling for DELETE revocation probes, and worker synthetic DB connection configuration.

## Verification

Verified shell/Compose/static/backend contracts and the real `./scripts/security/verify-m015-runtime-security.sh --seam session` runner. The final evidence has `result=passed`, `seam=session`, redaction `validated=true`, current session 200, cache miss fallback 200 with cache rehydrated, revoked and expired stale-cache sessions 401, legacy transports 401, explicit revocation 200 followed by 401 and cache missing, Taskiq worker denial reason `revoked_or_expired`, non-goals recorded, and teardown complete.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && PYTHONPATH=backend-hormonia python -m py_compile scripts/security/m015-runtime/session_seam.py scripts/security/m015-runtime/m015_session_security_taskiq.py && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/security/test_m015_runtime_harness.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py -q` | 0 | ✅ pass — 65 passed, 1 skipped | 23403ms |
| 2 | `./scripts/security/verify-m015-runtime-security.sh --seam session` | 0 | ✅ pass — session seam passed and wrote stable evidence/summary artifacts | 111735ms |

## Deviations

The T05 runtime seam initially failed during this auto-fix on cache rehydration, CSRF-protected explicit revocation, and worker DB re-check wiring; those runtime defects were fixed before recording the task complete.

## Known Issues

None.

## Files Created/Modified

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `scripts/security/m015-runtime/session_seam.py`
- `scripts/security/m015-runtime/m015_session_security_taskiq.py`
- `backend-hormonia/docs/reports/security/m015/session-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/session-seam-summary.md`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
