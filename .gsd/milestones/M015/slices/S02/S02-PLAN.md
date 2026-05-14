# S02: Cross-Process Session Revocation + Queue Worker Proof

**Goal:** Prove and harden cross-process staff-session revocation through the M015 synthetic runtime stack: cookie-backed current sessions succeed, revoked/expired sessions fail closed even with stale Redis cache entries or cache misses, explicit user revocation invalidates Dragonfly, and a real Taskiq worker re-checks PostgreSQL session state before accepting queued work. Owned requirement: R013. Supporting requirements: R014, R015, R017, R018, plus S01's R012 DB substrate. Decision honored: D027.
**Demo:** Run the M015 session seam through the harness to show a current synthetic session succeeds, revoked/expired sessions fail closed across cache and DB fallback, and a queued worker scenario participates without accepting stale authorization.

## Must-Haves

- Slice verification is defined before implementation and must pass before completion.
- Q3 Threat Surface:
- Abuse: stale Redis cache can authorize a DB-revoked/expired staff session; cache miss can incorrectly deny a still-active session; queued work can execute after session revocation if the worker trusts submission-time state; legacy header/Bearer transports can reopen session replay surfaces.
- Data exposure: staff profile/session metadata and downstream PHI-bearing API/worker actions are at risk if stale authorization succeeds; this slice uses synthetic users/sessions only and must not persist raw cookies, session IDs, passwords, non-example emails, DSNs, provider payloads, host paths, SQL, or PHI-shaped values.
- Input trust: HTTP cookies/headers, Redis `session:<id>` payloads, PostgreSQL session rows, Taskiq arguments/results, runner CLI seam names, Compose env interpolation, and probe logs are untrusted and must be validated/redacted.
- Q4 Requirement Impact:
- Requirements touched: R013 primary; R014 runtime harness extension; R015 synthetic-only/no production data; R017 concrete sanitized evidence; R018 explicit non-goals/no silent deferred seams; R012 is consumed as S01 DB substrate, not re-proven.
- Re-verify: cookie-only staff auth, `get_current_user_from_session`, `auth_session_shared.get_user_data_from_session`, `/api/v2/users/me`, `/api/v2/users/sessions/{session_id}`, Redis cache fallback/rehydration/invalidation, Taskiq broker import/dispatch/result behavior, runner fail-closed seam selection, and evidence redaction.
- Decisions honored/revisited: D027 DB-authoritative cookie-only session proof; MEM003 fail-closed PHI/auth boundaries; MEM094 explicit Taskiq task module import; no roadmap reassessment required because code validated the S02 assumptions.
- `cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/security/test_m015_runtime_harness.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py -q` exits 0.
- `bash -n scripts/security/verify-m015-runtime-security.sh` and `docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet` exit 0.
- `./scripts/security/verify-m015-runtime-security.sh --list-seams` lists both `db` and `session`, while unknown/omitted seams still fail closed before setup.
- `./scripts/security/verify-m015-runtime-security.sh --seam session` exits 0, starts the isolated PostgreSQL/Dragonfly/API/worker stack, runs migrations/fixtures, dispatches a real Taskiq task, writes `backend-hormonia/docs/reports/security/m015/session-seam-evidence.json` and `backend-hormonia/docs/reports/security/m015/session-seam-summary.md`, and tears down.
- Session evidence proves: cookie-backed current synthetic session succeeds; legacy `X-Session-ID`/Bearer-only transport is rejected; Redis cache miss falls back to an active DB session; DB-revoked and DB-expired sessions are denied despite stale Redis cache; `/api/v2/users/sessions/{session_id}` invalidates the corresponding Redis session cache; a queued worker task submitted before revocation denies after the gate when DB state is revoked.
- Durable evidence passes `scripts/security/m015-runtime/redaction.py` validation and contains only hashes/booleans/status classes, never raw cookies, session IDs, passwords, non-example emails, DSNs, local host paths, SQL statements, provider payloads, or PHI-shaped values.
- Evidence summary explicitly lists non-goals and remaining seams: S03 provider stubs, S04 private artifacts, S05 final matrix/all-seam closure, browser/frontend flows, live provider credentials, production data, and live JWT/Bearer claims.

## Proof Level

- This slice proves: Operational runtime integration proof. Real runtime required: yes — separate FastAPI, PostgreSQL, Dragonfly, and Taskiq worker containers/processes under the M015 Compose harness. Human/UAT required: no. This slice proves the session/cache/DB/worker boundary only; DB TLS/RLS remains upstream S01 evidence and provider/artifact/final matrix seams remain downstream.

## Integration Closure

Consumes the S01 runner/Compose substrate, TLS PostgreSQL, Dragonfly, FastAPI readiness, migration pattern, redaction guard, and sanitized evidence directory. Introduces the `session` seam, product session correctness fixes, explicit Taskiq task discovery for the M015 worker proof, a session probe service, and durable session evidence artifacts. After S02, downstream S03/S04 can rely on cookie-backed session behavior when proving provider and artifact routes; S05 still must assemble the full evidence matrix and strict closure gate.

## Verification

- The runner must emit session-scoped diagnostics (`setup`, `compose`, `readiness`, `session-probe`, `cache-fallback`, `revocation`, `worker`, `evidence`, `teardown`) with correlation IDs, sanitized probe logs, stable `session-seam-evidence.json`/`session-seam-summary.md`, status-code/cache/DB/worker outcome fields, worker denial reasons, and redaction-validated failure classes. Future agents should be able to distinguish API auth failures, Redis fallback issues, DB session-state mismatches, Taskiq dispatch/result failures, and teardown failures without seeing secrets or PHI.

## Tasks

- [x] **T01: Make DB session state authoritative for cache hits and cache misses** `est:2.5h`
  Why: Product auth must not authorize stale Redis data after PostgreSQL says the session is revoked/expired, and it must recover active DB sessions after Redis cache miss without accepting header/Bearer transports.
  - Files: `backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py`, `backend-hormonia/app/dependencies/auth_session_cache.py`, `backend-hormonia/app/dependencies/auth_session_contract.py`, `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/api/v2/auth_session_shared.py`
  - Verify: cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py -q

- [ ] **T02: Invalidate Redis on explicit session revocation** `est:1.5h`
  Why: `/api/v2/users/sessions/{session_id}` currently updates the DB row but can leave `session:<id>` in Dragonfly. It must invalidate cache at the revocation boundary, while DB revocation remains the hard fail-closed source if cache deletion fails.
  - Files: `backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py`, `backend-hormonia/app/dependencies/auth_session_invalidation.py`, `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/api/v2/routers/users.py`, `backend-hormonia/app/core/redis_manager/session_cache.py`
  - Verify: cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/api/v2/test_auth.py -q

- [ ] **T03: Wire the session seam runner, Compose service, and explicit Taskiq task module** `est:2h`
  Why: S01 proves worker liveness only. S02 must expose a `session` seam, mount a harness-only Taskiq module, and force the worker to import it so queue proof crosses the real broker/worker boundary.
  - Files: `scripts/security/verify-m015-runtime-security.sh`, `scripts/security/m015-runtime/docker-compose.yml`, `scripts/security/m015-runtime/m015_session_security_taskiq.py`, `backend-hormonia/tests/security/test_m015_runtime_harness.py`, `scripts/security/m015-runtime/tests/test_runner_contract.py`
  - Verify: bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_runtime_harness.py -q && cd .. && python scripts/security/m015-runtime/tests/test_runner_contract.py

- [ ] **T04: Build the session runtime probe and redaction-validated evidence** `est:2.5h`
  Why: The runner/worker wiring is not enough; S02 needs an executable probe that drives API/cache/DB/worker boundaries and writes durable PHI-safe evidence for the exact session cases claimed.
  - Files: `scripts/security/m015-runtime/session_seam.py`, `scripts/security/m015-runtime/README.md`, `backend-hormonia/tests/security/test_m015_runtime_harness.py`, `scripts/security/m015-runtime/tests/test_runner_contract.py`
  - Verify: PYTHONPATH=backend-hormonia python -m py_compile scripts/security/m015-runtime/session_seam.py scripts/security/m015-runtime/m015_session_security_taskiq.py && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_runtime_harness.py tests/security/test_m015_s02_session_runtime_contract.py -q

- [ ] **T05: Run the session seam and commit fresh sanitized evidence artifacts** `est:1h`
  Why: S02 is an operational proof slice and is not complete until the real root runner exercises the session seam and leaves durable redaction-validated evidence for S05.
  - Files: `backend-hormonia/docs/reports/security/m015/session-seam-evidence.json`, `backend-hormonia/docs/reports/security/m015/session-seam-summary.md`
  - Verify: bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/security/test_m015_runtime_harness.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py -q && cd .. && ./scripts/security/verify-m015-runtime-security.sh --seam session

## Files Likely Touched

- backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py
- backend-hormonia/app/dependencies/auth_session_cache.py
- backend-hormonia/app/dependencies/auth_session_contract.py
- backend-hormonia/app/dependencies/auth_dependencies.py
- backend-hormonia/app/api/v2/auth_session_shared.py
- backend-hormonia/app/dependencies/auth_session_invalidation.py
- backend-hormonia/app/api/v2/routers/auth.py
- backend-hormonia/app/api/v2/routers/users.py
- backend-hormonia/app/core/redis_manager/session_cache.py
- scripts/security/verify-m015-runtime-security.sh
- scripts/security/m015-runtime/docker-compose.yml
- scripts/security/m015-runtime/m015_session_security_taskiq.py
- backend-hormonia/tests/security/test_m015_runtime_harness.py
- scripts/security/m015-runtime/tests/test_runner_contract.py
- scripts/security/m015-runtime/session_seam.py
- scripts/security/m015-runtime/README.md
- backend-hormonia/docs/reports/security/m015/session-seam-evidence.json
- backend-hormonia/docs/reports/security/m015/session-seam-summary.md
