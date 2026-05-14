# S02 Research: Cross-Process Session Revocation + Queue Worker Proof

## Summary

S02 is a **targeted-but-risky runtime integration slice**: the stack substrate from S01 exists, but session authorization currently has two runtime red-signal candidates that S02 should either fix or intentionally prove safe. The selected seam should exercise the real FastAPI process, Dragonfly cache, PostgreSQL fallback, and a Taskiq worker process with synthetic-only users/sessions and redaction-validated evidence.

Key findings for the planner:

- The M015 runner/Compose stack currently implements only `--seam db`; S02 must add `--seam session`, a `session-probe` service/script, session evidence artifacts, and teardown updates.
- Staff auth is now **cookie-only**. `X-Session-ID` and `Authorization: Bearer ...` are intentionally rejected for staff auth. S02 should not reintroduce JWT/Bearer acceptance; phrase evidence as the runtime proof of the current cookie-backed session boundary.
- `get_current_user_from_session()` uses Redis first and falls back to DB only on Redis exception/timeout, **not on cache miss**. A valid DB session whose Redis entry was evicted currently looks invalid instead of using DB fallback.
- Cache-hit session auth does not generally re-check DB session state. `/api/v2/auth/verify-session` performs its own DB session check, but many endpoints (for example `/api/v2/users/me`) rely on the dependency result and can mask stale Redis behavior unless the auth helper is fixed.
- `/api/v2/auth/sessions/{session_id}` (legacy include of `users.revoke_session`) marks the DB row revoked but does **not** invalidate `session:<id>` in Redis. This is the clearest stale-cache revocation risk to prove/fix.
- The S01 worker liveness check does not prove Taskiq task import or dispatch. Current worker command is `taskiq worker app.taskiq_broker:broker`; local `taskiq worker --help` confirms default discovery only searches `**/tasks.py`, while this repo's tasks live in `app/tasks/*_taskiq.py` plus `app/tasks/smoke_test.py`. Use explicit task modules (preferred for S02) or `--fs-discover --tasks-pattern '**/*_taskiq.py'`.

## Active Requirements / Constraints

- **R012**: indirectly supported by using the S01 DB substrate; S02 should not reopen DB TLS/RLS proof except as runtime dependency evidence.
- **R014**: directly extended by starting the synthetic stack and proving API/cache/DB/worker boundaries.
- **R015**: all users, sessions, passwords, request bodies, cache keys, and queue messages must be synthetic only; durable evidence must not persist raw cookies, raw session IDs, passwords, real emails, PHI-shaped names/CPF/phone, provider payloads, host paths, or DSNs.
- **R017**: evidence must include concrete command, timestamps, versions, status codes, DB/cache/worker outcomes, and sanitized diagnostics.
- **R018**: S02 summary/evidence should explicitly list non-goals: provider stubs (S03), private artifacts (S04), final matrix/all-seam closure (S05), browser/frontend flows, live JWT/Bearer/provider claims, production data.

Relevant memories:

- MEM003: fail closed at PHI/auth boundaries and log structured diagnostics without PHI/secrets.
- MEM094: Taskiq worker needs explicit modules or FS discovery for this repo's `*_taskiq.py` task layout.
- MEM096: S02 is intentionally before provider/artifact slices because downstream runtime checks rely on authenticated session behavior.

## Recommendation

Build S02 as two layers:

1. **Product/session correctness contracts first**: fix/guard canonical session auth so DB session state is authoritative for active/revoked/expired sessions even when Redis has stale data, and so DB fallback works on cache miss. Also ensure explicit user-initiated session revocation invalidates Redis.
2. **Runtime harness proof second**: add a `session_seam.py` probe and one M015-only Taskiq task module that exercise existing API endpoints and a real queued worker task through Dragonfly. The probe should write `session-seam-evidence.json` and `session-seam-summary.md` using the existing `redaction.py` guard.

Avoid adding a public/product API endpoint only for the harness. The proof can use existing endpoints plus a harness-mounted Taskiq module.

## Implementation Landscape

### Files and purpose

- `scripts/security/verify-m015-runtime-security.sh`
  - Currently hard-fails anything except `--seam db` and only updates DB evidence teardown fields.
  - Add `session` to usage/list/validation; add `run_session_seam`; add `SESSION_EVIDENCE_JSON` / `SESSION_SUMMARY_MD`; make teardown evidence update seam-aware.
  - Extend `sanitize_stream` to redact `Cookie:` / `Set-Cookie:` if session probe logs ever contain HTTP headers.

- `scripts/security/m015-runtime/docker-compose.yml`
  - Existing services: `postgres`, `dragonfly`, `api`, `worker`, `db-probe`.
  - Add `session-probe` service similar to `db-probe` with mounts for `session_seam.py`, `redaction.py`, output dir, and the M015 Taskiq task module.
  - Change `worker` command from `taskiq worker app.taskiq_broker:broker` to an explicit module command such as:
    - `taskiq worker --app-dir /app app.taskiq_broker:broker app.tasks.m015_session_security_taskiq --workers 1`
  - Prefer explicit S02 module over broad FS discovery to avoid importing unrelated provider/task modules during S02.

- `scripts/security/m015-runtime/session_seam.py` (new)
  - Runtime probe inside Compose network.
  - Responsibilities: run Alembic head (or call a shared migration helper), seed synthetic local-auth user(s), drive CSRF/login/session/revoke requests against `http://api:8080`, manipulate Dragonfly `session:<id>` keys for fallback/stale-cache cases, dispatch Taskiq tasks, collect evidence, validate redaction, write JSON/Markdown.
  - Should use `X-Forwarded-Proto: https` and `Host: api` like `db_seam.py` health probes.
  - Should never persist raw session IDs/cookies/CSRF values; store SHA-256 hashes and boolean/header-flag summaries only.

- `scripts/security/m015-runtime/m015_session_security_taskiq.py` (new harness task, mounted into `/app/app/tasks/m015_session_security_taskiq.py`)
  - Register with `from app.taskiq_broker import broker`.
  - Task should receive a raw synthetic `session_id` only through the queue, then re-check PostgreSQL session row at execution time and return sanitized result: `allowed` for active/not-expired, `denied` with reason `session_revoked` or `session_expired` otherwise.
  - For queued-before-revocation determinism, accept a Redis gate key derived from the session hash; task waits for the gate before checking DB. Probe enqueues task, revokes session, sets gate, then waits for result.

- `scripts/security/m015-runtime/redaction.py`
  - Existing denylist is strong. Session evidence must avoid keys with `TOKEN`, `SECRET`, `PASSWORD`, or raw `Cookie`/`Set-Cookie` strings because the denylist will (correctly) reject them.
  - Use names like `csrf_double_submit`, `session_id_hash`, `cache_state`, not `csrf_token` or `cookie_header`.

- `backend-hormonia/app/dependencies/auth_session_cache.py`
  - Current central resolver for `get_current_user_from_session`.
  - Likely needs changes so cache miss uses DB fallback, and cache hit validates DB session state (or at least checks a DB-backed revocation/expiration contract) before returning embedded user data.
  - Existing helper `_get_user_from_db_by_session()` in `auth_dependencies.py` already filters `is_active`, `revoked_at is null`, `expires_at > now`.

- `backend-hormonia/app/dependencies/auth_session_contract.py`
  - Keeps cookie-only resolution; do not re-enable headers/Bearer.
  - May need to pass a session-state validator callback through to `auth_session_cache.resolve_session_user_data()`.

- `backend-hormonia/app/dependencies/auth_dependencies.py`
  - `get_current_user_from_session()` wires cache/DB fallback loaders. Add any new callback here.
  - `_get_user_from_db_by_session()` is already the safest DB source of truth for active sessions.

- `backend-hormonia/app/api/v2/auth_session_shared.py`
  - Many routers use this lighter helper directly. It currently accepts embedded Redis session payloads without DB session-state recheck and has no DB fallback on cache miss.
  - Either refactor this helper to call the canonical contract or add the same active/revoked/expired DB validation here.

- `backend-hormonia/app/api/v2/routers/users.py`
  - `revoke_session()` currently updates DB only. Add `redis_cache=Depends(get_redis_cache)` and invalidate the target `session:<id>` via the same compatibility pattern used by auth logout, or move invalidation helper to a shared module.
  - Use `/api/v2/users/me` for runtime stale-cache proof because `/api/v2/auth/verify-session` has its own DB recheck and can hide dependency-level bugs.

- `backend-hormonia/app/api/v2/routers/auth.py`
  - Useful existing pieces: login, logout, verify-session, `_invalidate_session_cache`, `_invalidate_all_user_sessions_cache`, CSRF endpoint.
  - Do not create cross-router import cycles just to reuse `_invalidate_session_cache`; moving that helper to a shared auth utility is cleaner.

- `backend-hormonia/app/taskiq_broker.py`
  - Uses `ListQueueBroker` + `RedisAsyncResultBackend` and reads `TASKIQ_BROKER_URL`; S01 env already points to Dragonfly.
  - Producer script should call `await broker.startup()` before `.kiq()` and `await broker.shutdown()` after waiting for results.

- `backend-hormonia/tests/security/test_m015_runtime_harness.py` and `scripts/security/m015-runtime/tests/test_runner_contract.py`
  - Update static contracts for `session` seam, `session-probe`, worker explicit task module, session evidence paths, and redaction-clean session evidence shape.

- New focused tests suggested:
  - `backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py` for cache-hit stale DB revocation, cache-miss DB fallback, expired DB session denial, shared helper parity, and `users.revoke_session` cache invalidation.

### Existing endpoint/flow details

- Login: `POST /api/v2/auth/login` with body `{email, password, remember_me}`.
- CSRF: `GET /api/v2/auth/csrf-token`; all mutating cookie-backed auth endpoints need matching `X-CSRF-Token` header and `csrf_token` cookie.
- Current session proof: `GET /api/v2/users/me` or `GET /api/v2/auth/verify-session` with `Cookie: session_id=<id>`.
- Single-session revoke path: `DELETE /api/v2/auth/sessions/{session_id}` because `users_router` is included under `/api/v2/auth` for legacy support.
- Logout current session: `DELETE /api/v2/auth/logout`.
- Staff auth rejects header-only `X-Session-ID` and `Authorization: Bearer ...`; probe should use only `session_id` cookie.

## Natural Seams / Work Units

1. **Auth correctness seam**
   - Add failing tests first for stale Redis cache + DB revoked/expired and cache-miss DB fallback.
   - Update canonical session helpers and shared helper parity.
   - Fix `users.revoke_session()` Redis invalidation.

2. **Taskiq worker seam**
   - Add M015 harness task module and explicit worker import.
   - Implement active-session task and queued-before-revocation task with Redis gate.
   - Keep task return values sanitized and evidence-safe.

3. **Probe/evidence seam**
   - Add `session_seam.py` with API client, CSRF handling, direct Redis/DB setup, Taskiq dispatch, evidence builder, summary renderer, and redaction validation.
   - Evidence should record only status classes/hashes/counts/booleans, not raw HTTP headers/cookies.

4. **Runner/Compose seam**
   - Add `--seam session`, session-probe service, seam-specific logs, failure diagnostics, and teardown result update.
   - Preserve S01 `--seam db` behavior.

5. **Contract/verification seam**
   - Static tests for CLI/Compose/redaction.
   - Focused unit contracts for auth helpers.
   - Final runtime `--seam session` proof.

## First Proof

Highest-risk proof should be a **red unit contract before harness plumbing**:

1. Simulate Redis returning an embedded active-looking session payload while the DB loader/session-state validator reports the session revoked or expired. Expected result: 401 and cache invalidation attempt. Current code is likely to return the embedded payload without touching DB.
2. Simulate Redis cache miss for an active DB session. Expected result: DB fallback succeeds and cache rehydrates. Current code is likely to raise 401 on miss.
3. Prove `/api/v2/auth/sessions/{session_id}` invalidates Redis in addition to DB. Current route only updates DB.

Then prove Taskiq import/dispatch with the minimal M015 task module before writing the full API scenario evidence; worker liveness alone is not enough.

## Suggested Runtime Scenario Matrix

Use synthetic user(s) under `example.invalid`; store only hashes in evidence.

- **current_session_allows**: seed user, get CSRF, login via API, call `/api/v2/users/me`; expect 200 and role `doctor`/`admin` class only.
- **cache_miss_db_fallback_allows**: delete `session:<id>` from Dragonfly while DB row remains active; call `/api/v2/users/me`; expect 200 and Redis rehydration.
- **single_revoke_stale_cache_denies**: create two sessions for the same synthetic user; use session A to call `DELETE /api/v2/auth/sessions/{session_b}`; then call `/api/v2/users/me` with session B; expect 401 and Redis key absent.
- **expired_stale_cache_denies**: set `expires_at` in DB to the past while Redis payload remains; call `/api/v2/users/me`; expect 401.
- **fallback_revoked_or_expired_denies**: delete Redis key and mark DB revoked/expired; call `/api/v2/users/me`; expect 401 via DB fallback.
- **worker_active_allows**: dispatch M015 Taskiq task with active session; wait result from Redis result backend; expect `allowed`.
- **worker_queued_revoked_denies**: dispatch task before revocation with a Redis gate; revoke/expire DB session and leave/recreate stale Redis payload; set gate; task result must be `denied` with reason `session_revoked`/`session_expired`.

## Evidence Shape Notes

Recommended durable artifacts:

- `backend-hormonia/docs/reports/security/m015/session-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/session-seam-summary.md`

Include:

- `schema_version`, `command`, `probe_command`, `correlation_id`, `seam`, `started_at`, `completed_at`.
- `service_versions`: FastAPI app version from `/health`, Python, Taskiq, taskiq-redis, redis-py, PostgreSQL/Dragonfly image names.
- `migrations`: Alembic command/exit/head/current revisions if session probe applies migrations itself.
- `api_runtime`: health/readiness status classes.
- `session_cases`: case names, endpoint path, method, expected/actual status code, result (`allowed`/`denied`), denial reason class, DB state class, cache state class, hashed session IDs.
- `worker_queue`: broker type, result backend class, task module, dispatch result, queued-before-revocation proof, sanitized task return values.
- `redaction`, `teardown`, `non_goals`.

Avoid evidence keys/values that trigger `redaction.py`: raw `Cookie:` / `Set-Cookie:`, `Authorization`, keys containing `TOKEN`/`SECRET`/`PASSWORD` with values, raw emails outside `example.invalid`, patient/provider payload fields, host paths, DSNs, SQL text.

## Verification

Recommended commands after implementation:

```bash
bash -n scripts/security/verify-m015-runtime-security.sh
docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet
python -m unittest scripts/security/m015-runtime/tests/test_runner_contract.py
```

```bash
cd backend-hormonia && PYTHONPATH=. pytest \
  tests/security/test_m015_runtime_harness.py \
  tests/security/test_m015_s02_session_runtime_contract.py \
  tests/api/v2/test_auth_session_priority.py \
  tests/api/v2/test_auth_session_shared_canonical_identity.py \
  tests/api/v2/test_auth_hard_cut_cleanup.py \
  -q
```

Final runtime proof:

```bash
./scripts/security/verify-m015-runtime-security.sh --seam session
```

Do not mark S02 complete unless the runtime command exits 0 and both session evidence artifacts pass `validate_no_sensitive_evidence()`.

## Skill Discovery

Installed skills directly relevant by prompt inventory: `api-design` (if any internal/public HTTP surface changes are proposed), `observability` (S01-style evidence/failure diagnostics), `test`, `verify-before-complete`, and `security-review`. No installed Taskiq/Dragonfly-specific skill was present.

`npx skills find` results checked but not installed:

- Taskiq: no skill found.
- DragonflyDB: no skill found.
- FastAPI: possible optional installs, but local code patterns are more relevant for this slice:
  - `npx skills add wshobson/agents@fastapi-templates` (16.9K installs)
  - `npx skills add mindrally/skills@fastapi-python` (8.6K installs)
  - `npx skills add jeffallan/claude-skills@fastapi-expert` (3K installs)
- Redis/Dragonfly-compatible work:
  - `npx skills add redis/agent-skills@redis-development` (2.7K installs)
  - `npx skills add mindrally/skills@redis-best-practices` (1.5K installs)
- PostgreSQL skills exist but S01 already established DB/TLS/RLS patterns; S02 should not need a new DB-design skill.

## Risks / Watch-outs

- **Do not use `/api/v2/auth/verify-session` as the only stale-cache proof**; it re-checks DB in the route and can hide stale dependency behavior. Use `/api/v2/users/me` or another dependency-only endpoint.
- **CSRF is enforced** for mutating cookie-backed endpoints. The probe needs double-submit CSRF, but durable evidence must not include raw CSRF values or keys named like secrets/tokens.
- **Rate limiting uses Dragonfly**. Avoid proving DB fallback by stopping Dragonfly entirely; that may fail closed at rate limiting before auth fallback. Prefer deleting only `session:<id>` to simulate cache miss while Dragonfly stays healthy.
- **Task timing can flake** if a queued task races revocation. Use a Redis gate key so the task is queued before revocation but checks authorization only after the probe sets the gate.
- **Worker task discovery is currently a false-green risk**. Explicit module import is the safest S02 fix.
- **Evidence redaction is strict**. Test with `validate_no_sensitive_evidence()` before final runtime run; summary text can fail if it says `Set-Cookie: ...`, `PASSWORD=...`, or raw SQL.
- **Keep scope honest**: S02 proves session/cache/DB/worker boundaries only. Provider stubs, artifacts, final matrix, frontend/browser, live providers, and production exploitation remain S03-S05/non-goals.

## Sources / Local Findings

- `scripts/security/verify-m015-runtime-security.sh`: DB-only CLI, seam validation, env generation, readiness, teardown/evidence update.
- `scripts/security/m015-runtime/docker-compose.yml`: S01 Compose services and current worker command.
- `scripts/security/m015-runtime/db_seam.py`: evidence/event/redaction pattern to mirror.
- `scripts/security/m015-runtime/redaction.py`: denylist constraints for durable evidence.
- `backend-hormonia/app/dependencies/auth_session_cache.py`: Redis-first auth resolution and current fallback limitations.
- `backend-hormonia/app/dependencies/auth_dependencies.py`: DB fallback query filters active/revoked/expired correctly.
- `backend-hormonia/app/api/v2/auth_session_shared.py`: shared helper needs parity with canonical auth.
- `backend-hormonia/app/api/v2/routers/auth.py`: login/logout/verify-session and cache invalidation helpers.
- `backend-hormonia/app/api/v2/routers/users.py`: user/session routes; `revoke_session()` DB-only revocation gap.
- `backend-hormonia/app/taskiq_broker.py`: Dragonfly-backed Taskiq broker/result backend.
- `backend-hormonia/app/tasks/smoke_test.py`: existing Taskiq examples but not sufficient for authorization proof.
- Local `taskiq worker --help`: default `--tasks-pattern ['**/tasks.py']`, positional `broker [modules ...]`, `--fs-discover`, `--tasks-pattern` options.
