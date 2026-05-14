---
id: T01
parent: S02
milestone: M015
key_files:
  - backend-hormonia/app/dependencies/auth_session_cache.py
  - backend-hormonia/app/dependencies/auth_dependencies.py
  - backend-hormonia/app/dependencies/auth_session_contract.py
  - backend-hormonia/app/api/v2/auth_session_shared.py
  - backend-hormonia/app/core/redis_manager/manager.py
  - backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py
  - backend-hormonia/tests/security/test_m015_runtime_harness.py
  - scripts/security/m015-runtime/m015_session_security_taskiq.py
  - scripts/security/m015-runtime/docker-compose.yml
  - backend-hormonia/docs/reports/security/m015/session-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/session-seam-summary.md
key_decisions:
  - PostgreSQL session rows are the authorization authority for both Redis cache hits and misses; Redis is only a stale-prone cache/rehydration layer.
  - Staff-session auth remains cookie-only; legacy header, bearer, and query transports are rejected rather than re-enabled.
  - Redis fallback rehydration is best-effort and preserves canonical session metadata, but DB failures remain fail-closed.
  - M015 production-mode explicit revocation probes use CSRF double-submit tokens instead of bypassing middleware.
duration: 
verification_result: passed
completed_at: 2026-05-14T10:13:59.022Z
blocker_discovered: false
---

# T01: Made staff-session authorization DB-authoritative across Redis cache hits, cache misses, helper callers, and the M015 runtime seam.

**Made staff-session authorization DB-authoritative across Redis cache hits, cache misses, helper callers, and the M015 runtime seam.**

## What Happened

Implemented and verified DB-authoritative session resolution for staff sessions. Redis cache hits now require PostgreSQL session validation before embedded Redis payloads are trusted; cache misses and Redis errors fall back to the active session row and rehydrate Dragonfly best-effort; revoked, expired, missing, inactive-user, and DB-unavailable cases fail closed with the expected 401/403/503 classes. Direct helper users in `auth_session_shared.get_user_data_from_session()` use the same DB-authoritative behavior. The cookie-only staff-session transport contract remains intact: `X-Session-ID`, query session IDs, and bearer-only requests are rejected when no session cookie is present. During the auto-fix pass, slice-level runtime verification exposed three harness/runtime integration issues that were fixed because they directly exercised this contract: `RedisManager.create_session()` now preserves metadata during fallback rehydration, the session seam explicit revocation probe fetches and sends the production CSRF double-submit token pair, and the Taskiq worker service receives the synthetic psycopg connection string needed to re-check PostgreSQL session state.

## Verification

Verified the exact T01 pytest contract, the expanded static/backend harness contract, Docker Compose configuration, Python syntax for the session seam modules, and the real M015 session seam. The final runtime evidence shows current cookie sessions allowed, cache-miss fallback allowed and rehydrated, revoked/expired stale-cache sessions denied, explicit revocation invalidated Dragonfly and denied follow-up access, legacy transports denied without cookies, Taskiq worker denied queued work after DB re-check, redaction passed, and teardown completed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py -q` | 0 | ✅ pass — 38 passed | 22295ms |
| 2 | `docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && PYTHONPATH=backend-hormonia python -m py_compile scripts/security/m015-runtime/session_seam.py scripts/security/m015-runtime/m015_session_security_taskiq.py && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/security/test_m015_runtime_harness.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py -q` | 0 | ✅ pass — 65 passed, 1 skipped | 23403ms |
| 3 | `./scripts/security/verify-m015-runtime-security.sh --seam session` | 0 | ✅ pass — session seam evidence/result passed with teardown complete | 111735ms |

## Deviations

In addition to the originally listed auth dependency/shared-helper files, the auto-fix updated `RedisManager.create_session()` and the M015 session seam harness/Compose contract because slice-level verification found real runtime failures in cache rehydration, CSRF-protected explicit revocation, and worker DB re-check wiring.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_session_cache.py`
- `backend-hormonia/app/dependencies/auth_dependencies.py`
- `backend-hormonia/app/dependencies/auth_session_contract.py`
- `backend-hormonia/app/api/v2/auth_session_shared.py`
- `backend-hormonia/app/core/redis_manager/manager.py`
- `backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
- `scripts/security/m015-runtime/m015_session_security_taskiq.py`
- `scripts/security/m015-runtime/docker-compose.yml`
- `backend-hormonia/docs/reports/security/m015/session-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/session-seam-summary.md`
