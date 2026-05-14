---
id: S02
parent: M015
milestone: M015
provides:
  - DB-authoritative cookie-session behavior across Redis hits/misses and explicit revocation
  - Implemented M015 `session` runner seam with FastAPI/PostgreSQL/Dragonfly/Taskiq worker proof
  - Sanitized session runtime evidence artifacts and session probe diagnostics for downstream matrix closure
  - Authenticated runtime substrate for S03/S04 probes that need staff-session behavior
requires:
  - slice: S01
    provides: M015 runtime harness substrate, TLS PostgreSQL, Dragonfly, FastAPI readiness, migration pattern, evidence/redaction helper, and teardown discipline
affects:
  - S03
  - S04
  - S05
key_files:
  - backend-hormonia/app/dependencies/auth_session_cache.py
  - backend-hormonia/app/dependencies/auth_session_invalidation.py
  - backend-hormonia/app/api/v2/routers/auth.py
  - backend-hormonia/app/api/v2/routers/users.py
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/docker-compose.yml
  - scripts/security/m015-runtime/session_seam.py
  - scripts/security/m015-runtime/m015_session_security_taskiq.py
  - backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py
  - backend-hormonia/tests/security/test_m015_runtime_harness.py
  - backend-hormonia/docs/reports/security/m015/session-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/session-seam-summary.md
key_decisions:
  - PostgreSQL session rows are authoritative for authorization on both Redis cache hits and misses; Redis is a best-effort cache only.
  - Staff-session auth remains cookie-only and legacy header/Bearer/query transports stay rejected.
  - Explicit revocation invalidates Dragonfly best-effort after DB commit; cache deletion failure must not make revoked sessions valid.
  - The Taskiq session proof re-checks PostgreSQL session state at worker execution time and records only sanitized outcome fields.
patterns_established:
  - Runtime seams are added as fail-closed runner targets with explicit evidence paths and teardown status.
  - Session evidence stores hashes, booleans, status classes, and reason codes instead of raw cookies, session IDs, DSNs, SQL, or PHI-shaped values.
  - Harness-only Taskiq modules can prove queue/worker boundaries without importing the entire production task package chain unexpectedly.
observability_surfaces:
  - Runner phase diagnostics for setup, readiness, session-probe, cache-fallback, revocation, worker, evidence, and teardown with correlation IDs.
  - `backend-hormonia/docs/reports/security/m015/session-seam-evidence.json` for machine-readable sanitized outcomes.
  - `backend-hormonia/docs/reports/security/m015/session-seam-summary.md` for reviewer-readable runtime status and non-goals.
drill_down_paths:
  - .gsd/milestones/M015/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M015/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M015/slices/S02/tasks/T03-SUMMARY.md
  - .gsd/milestones/M015/slices/S02/tasks/T04-SUMMARY.md
  - .gsd/milestones/M015/slices/S02/tasks/T05-SUMMARY.md
  - backend-hormonia/docs/reports/security/m015/session-seam-summary.md
duration: ""
verification_result: passed
completed_at: 2026-05-14T10:27:10Z
---

# S02: Cross-Process Session Revocation + Queue Worker Proof

**DB-authoritative staff-session authorization now proves current, revoked, expired, cache-miss, explicit-revocation, legacy-transport, and queued-worker cases across the M015 PostgreSQL/Dragonfly/FastAPI/Taskiq runtime seam.**

## What Happened

S02 extended the S01 runtime harness from DB-only validation into the session/cache/worker boundary. The product auth path now treats PostgreSQL session rows as authoritative for Redis cache hits and misses, keeps staff auth cookie-only, rejects legacy header/Bearer-only transports, rehydrates Dragonfly only for still-active DB sessions, and fails closed for revoked, expired, inactive, missing, or DB-unavailable states. Explicit revocation paths in auth/users routes now invalidate Dragonfly best-effort after DB commit while preserving the DB row as the hard source of truth.

The harness gained a `session` seam, an explicit `session_seam.py` probe, a harness-only Taskiq module, Compose worker/probe mounts, and static/root verification shims. The real runner generated redaction-validated session evidence showing current cookie auth allowed, cache-miss fallback allowed and rehydrated, revoked/expired stale cache denied, explicit revocation removed cache and denied follow-up access, legacy transports denied, and queued worker work denied after a PostgreSQL re-check.

## Verification

Fresh S02 task evidence shows the key gates passed:

- `cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/security/test_m015_runtime_harness.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py -q` passed with 65 tests and 1 expected skip.
- `docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet` passed.
- Python compilation for `session_seam.py` and `m015_session_security_taskiq.py` passed.
- `./scripts/security/verify-m015-runtime-security.sh --seam session` exited 0 in the runtime harness.

Durable evidence at `backend-hormonia/docs/reports/security/m015/session-seam-summary.md` records result `passed`, redaction validation, teardown complete, and the expected current/cache-fallback/revoked/expired/explicit-revocation/worker outcomes.

## Requirements Advanced

- R013 — Closed the runtime-only session/JWT deferral with DB-authoritative staff sessions across Redis cache hits/misses and a Taskiq worker boundary.
- R014 — Extended the synthetic runtime harness beyond DB TLS/RLS into session/cache/worker validation.
- R017 — Added redaction-validated session evidence with sanitized status classes and reason codes.
- R018 — Recorded downstream non-goals and remaining seams in the session evidence summary.

## Requirements Validated

- R013 — `./scripts/security/verify-m015-runtime-security.sh --seam session` exited 0 and recorded allowed current sessions, safe DB fallback, revoked/expired denial despite stale cache, explicit cache invalidation, legacy transport denial, and worker denial after DB re-check.
- R015 — The runner and evidence use only synthetic values and redaction validation rejects raw cookies/session IDs/DSNs/provider payloads/PHI-shaped values.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

- None.

## Operational Readiness

- **Health signal**: The session seam runner exits 0 with evidence result `passed`, redaction validated, and teardown complete.
- **Failure signal**: Non-zero runner exit, missing evidence, redaction failure, allowed revoked/expired/legacy/worker-denial cases, or teardown not marked complete.
- **Recovery**: Re-run the exact seam after addressing the named phase; use runner teardown support if a debug run leaves containers or volumes behind.
- **Monitoring gaps**: This is a local/CI synthetic runtime proof, not production monitoring. Provider stubs, artifact route proof, all-seam closure, browser/frontend flows, live provider credentials, and production exploitation remain downstream/non-goals.

## Deviations

S02 discovered and fixed runtime-adjacent issues outside the initial narrow auth files: Redis metadata-preserving rehydration, CSRF double-submit handling for production-mode explicit revocation probes, worker synthetic DB connection wiring, Firebase/auth test compatibility, and root-level pytest shims. These were required to keep the session runtime proof truthful.

## Known Limitations

S02 proves only the session/cache/worker seam. Provider stubs, private artifact routes, final all-seam matrix closure, browser/frontend flows, real provider credentials, production data, live JWT/Bearer claims, CDN/object-storage behavior, and production exploitation remain outside this slice.

## Follow-ups

Plan and execute S03 using the session seam as an authenticated runtime substrate for provider-related probes, while preserving redaction discipline and avoiding raw provider request bodies in evidence.

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_session_cache.py` — Made Redis-backed staff-session resolution DB-authoritative for cache hits and cache-miss fallback.
- `backend-hormonia/app/dependencies/auth_session_invalidation.py` — Added shared best-effort Redis invalidation helper for explicit session revocation paths.
- `backend-hormonia/app/api/v2/routers/auth.py` — Wired logout/session revocation paths into shared cache invalidation while preserving DB-first revocation.
- `backend-hormonia/app/api/v2/routers/users.py` — Invalidates Dragonfly when explicit user-session revocation succeeds.
- `scripts/security/verify-m015-runtime-security.sh` — Added the fail-closed `session` seam and evidence/teardown routing.
- `scripts/security/m015-runtime/docker-compose.yml` — Added session probe and explicit Taskiq worker module wiring for the runtime seam.
- `scripts/security/m015-runtime/session_seam.py` — Added the session runtime probe entrypoint.
- `scripts/security/m015-runtime/m015_session_security_taskiq.py` — Added harness-only Taskiq worker check that re-reads PostgreSQL session state.
- `backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py` — Added contract coverage for DB-authoritative sessions, cache fallback, revocation, and legacy transport rejection.
- `backend-hormonia/docs/reports/security/m015/session-seam-evidence.json` — Stored redaction-validated machine-readable session seam evidence.
- `backend-hormonia/docs/reports/security/m015/session-seam-summary.md` — Stored reviewer-readable session seam summary and non-goals.

## Forward Intelligence

### What the next slice should know
- The session seam can provide authenticated runtime setup for provider probes, but S03 should not reuse raw cookies/session IDs as evidence; carry only status/reason/hash summaries forward.
- The worker proof pattern is available via a harness-only Taskiq module and explicit Compose import. Use the same explicit import pattern for any S03 provider worker task.
- `./scripts/security/verify-m015-runtime-security.sh --list-seams` should list implemented seams; unknown/omitted seams must keep failing closed before setup.

### What's fragile
- CSRF-protected revocation probes require real double-submit token handling; bypassing middleware would make evidence weaker.
- Redis fallback rehydration must preserve canonical session metadata or runtime probes can pass unit tests but fail live.
- Root-level pytest shims exist because some automated gates call root paths while canonical tests live under `backend-hormonia/tests/`.

### Authoritative diagnostics
- `backend-hormonia/docs/reports/security/m015/session-seam-summary.md` — Best first stop for reviewer-readable status and non-goals.
- `backend-hormonia/docs/reports/security/m015/session-seam-evidence.json` — Best machine-readable source for status classes, phases, redaction, and teardown.
- `.gsd/milestones/M015/slices/S02/tasks/T05-SUMMARY.md` — Best narrative of the final runtime proof and defects fixed before green.

### What assumptions changed
- Redis was originally treated as an auth cache but not necessarily stale-hostile; S02 made PostgreSQL the explicit authority on both cache hits and misses.
- A static worker liveness proof was not enough; queued work now re-checks DB session state at execution time before allowing a selected action.
