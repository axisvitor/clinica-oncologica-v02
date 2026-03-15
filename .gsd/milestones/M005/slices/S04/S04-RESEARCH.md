# M005/S04 — Research

**Date:** 2026-03-14

## Summary

S04 does **not** own or support any **Active** requirement in `.gsd/REQUIREMENTS.md`; `R052` remains explicitly parked in M006. This slice instead closes the remaining M005 milestone gap and strengthens the already-validated `R053` with **final-schema-specific** runtime proof: the missing evidence is not more schema diffing, but the real backend booting on `m005_s03_t02_align_audit_history_head` and replaying the post-M004 critical backend loops on both a freshly bootstrapped database and an upgraded existing database.

The repo already contains almost all the ingredients S04 needs. S03 left a clean structural oracle in `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py`, the shared pytest harness now provisions Postgres via `alembic upgrade head` whenever `TEST_DATABASE_URL` is set, and M004/S06 already published a replayable mounted runner plus seeded proof-user flow. What is still missing is **composition around the final schema**: no current proof explicitly says “prepare the S03 head from both database histories, then boot the backend against that schema and re-run the post-M004 backend loops.”

The main surprise is that the current proof surfaces are honest in different ways, but not interchangeable. `TestClient(app)` under pytest is *not* the same as mounted backend startup: `app/core/lifespan.py` detects `TESTING=1` / pytest and skips external-service initialization. Meanwhile the strongest post-M004 auth/runtime suites still use dependency overrides and Redis doubles, which makes them excellent contract proof for DB/session behavior but weaker as mounted-infra proof. S04 should therefore be built as a **two-layer proof**: reuse the Alembic-backed pytest packs for schema-state replay, then add a thin mounted backend proof on top of the same head instead of inventing a brand-new monolithic suite.

## Recommendation

Implement S04 as a **proof orchestrator**, not as another broad test family.

1. **Keep the structural preparation exactly where S03 left it.** Reuse the phase model from `tests/migrations/test_canonical_schema_head_convergence.py`: one path from `base -> head`, one from `m005_s02_t01_publish_firebase_history_boundary -> head`. That is already the canonical definition of “fresh” vs “existing-upgrade” for this milestone.
2. **Replay the post-M004 backend loops on top of that head through the shared Postgres pytest harness.** The best existing pack is:
   - `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py`
   - `backend-hormonia/tests/integration/test_local_auth_core_flow.py`
   - `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`
   These are the same critical backend loops M004/S06 treated as authoritative.
3. **Add a thin mounted backend proof against the same schema head.** Do not rely on `TestClient(app)` to claim “backend sobe”. Either:
   - extend `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` with a backend-only mode, or
   - create an S04-specific thin runner that reuses the same patterns: blank Firebase env, WuzAPI mock token, seeded local-auth proof user, readiness/config probes, and one real login/session flow against live uvicorn.
4. **Do not widen back into full frontend/browser smoke unless S04 finds a schema-only regression that requires it.** M004/S06 already validated mounted full-stack auth/session and route smoke. The new delta in S04 is the final schema, so the new proof should stay backend-centric unless execution proves otherwise.

The safest execution shape is one published replay command that runs **serially** and emits stable artifacts/logs, rather than a long manual checklist. The runner should prepare the database phase, run the focused pytest pack under `TEST_DATABASE_URL`, then boot uvicorn against the same database with `TESTING` unset and probe live backend truth surfaces (`/health/ready`, `/api/v2/system/config`, and at least one real login/session flow).

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Prepare fresh vs existing database states honestly | `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` | It already defines the exact two histories S04 must consume: `base -> head` and `m005_s02_t01_publish_firebase_history_boundary -> head`. |
| Provision runtime tests from the real Alembic head | `backend-hormonia/tests/conftest.py` `TEST_DATABASE_URL` path | The shared harness already resets `public` and runs `alembic upgrade head` before API/integration tests when a real Postgres URL is supplied. |
| Replay the post-M004 backend loops | `tests/api/v2/test_system_auth_hard_cut_operational.py`, `tests/integration/test_local_auth_core_flow.py`, `tests/integration/test_auth_hard_cut_end_to_end.py` | These are already the canonical backend proofs for readiness/config + session-first login/verify/reset/logout behavior. S04 should replay them on the final head, not restate them in new assertions. |
| Mounted proof seeding and runtime diagnostics | `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` + `.gsd/milestones/M004/slices/S06/seed-proof-user.py` | S06 already solved the operational details: blank Firebase envs, WuzAPI mock, masked proof-user artifacts, status/log files, and live readiness/config probes. |

## Existing Code and Patterns

- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` — authoritative S03 structural oracle; resets `public`, upgrades from both fresh and existing-upgrade starting points, and asserts they land on `m005_s03_t02_align_audit_history_head` with the same fingerprint.
- `backend-hormonia/tests/conftest.py` — shared runtime harness; with `TEST_DATABASE_URL` set it provisions Postgres via `alembic upgrade head` instead of `Base.metadata.create_all()`, then wires `get_db` / `get_async_db` into the transactional test session.
- `backend-hormonia/tests/conftest.py` `_ensure_*` guards — useful to keep older runtime suites alive, but not a structural oracle. They can patch missing columns/indexes after provisioning, so S04 should use them only for runtime replay, not to infer canonical schema correctness.
- `backend-hormonia/app/core/lifespan.py` — critical distinction: pytest / `TESTING=1` causes startup to skip external-service initialization. This is why `TestClient(app)` cannot be treated as mounted-backend proof.
- `backend-hormonia/tests/test_initialization.py` — mostly mocked coverage for bootstrap scripts like `init_system.py` / `init_database.py`; several tests construct initializers with `skip_migrations=True`. This is not sufficient evidence for S04.
- `backend-hormonia/tests/integration/test_local_auth_core_flow.py` — strongest concise backend loop for `login -> /users/me -> logout`, with DB session rows asserted directly.
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` — strongest backend auth lifecycle proof for `login -> verify-session -> protected route -> reset -> password change -> logout-all -> logout`, but it still overrides Redis via `get_redis_cache`.
- `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py` — strongest no-Firebase readiness/system/config proof, but it also uses dependency overrides and monkeypatched Redis. Good for runtime narrative surfaces; not sufficient alone for mounted auth truth.
- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` — existing mounted runner that boots uvicorn + frontend, blanks Firebase envs, probes `/health/ready` and `/api/v2/system/config`, and seeds proof credentials.
- `.gsd/milestones/M004/slices/S06/seed-proof-user.py` — reusable seeded proof-user pattern using `SessionLocal`; writes only masked artifacts to `/tmp` and can target any ambient `DATABASE_URL`.
- `backend-hormonia/tests/integration/conftest.py` — stale integration harness that still documents “Real Firebase authentication” and uses raw `DATABASE_URL`; avoid treating it as the S04 source of truth.
- `backend-hormonia/tests/api/v2/conftest.py` — broad API fixtures still create generic users with `firebase_uid`; S04 should prefer the local-auth-specific fixtures from the focused auth packs to avoid compatibility-noise in the final-schema proof.

## Constraints

- `R052` is still out of scope for this slice. S04 should not drift into repo-wide residue cleanup just because the mounted proof surfaces old compatibility seams.
- S04’s success condition is specifically **backend on the final S03 head**. Anything that proves auth/session without pinning `m005_s03_t02_align_audit_history_head` is insufficient.
- `TestClient(app)` under pytest is intentionally softer than live startup because `app/core/lifespan.py` skips external-service init in test mode.
- `backend-hormonia/tests/conftest.py` drops and recreates `public` when `TEST_DATABASE_URL` is used. Runtime replay and migration replay must therefore run **serially**, not in parallel, and should not share a database with a live uvicorn process at the same time.
- The S06 mounted runner inherits ambient runtime env like `DATABASE_URL` / `REDIS_URL`; unlike S01/S03, S04 is allowed to depend on runtime services beyond the database because this slice is about mounted backend truth, not Alembic control-plane purity.
- The current S06 runner always starts the frontend and expects `frontend-hormonia/node_modules` to exist. That is valid but heavier than S04 strictly needs.
- Some current proof suites still use Redis doubles or dependency overrides. That is acceptable for the pytest layer, but S04 must add a live-mounted layer so those doubles do not become the final word.

## Common Pitfalls

- **Treating `tests/test_initialization.py` as mounted proof** — it mainly validates scripts with mocks and `skip_migrations=True`; it does not prove uvicorn boot on the canonical head.
- **Using `TestClient(app)` to claim “backend sobe”** — pytest mode suppresses part of the real startup path.
- **Letting `_ensure_*` schema guards stand in for head correctness** — they are a compatibility net for runtime suites, not evidence that the S03 head itself is correct.
- **Reusing generic fixtures that still populate `firebase_uid`** — that can make the final-schema proof look more Firebase-shaped than the live contract actually is.
- **Running migration/runtime packs concurrently against one `TEST_DATABASE_URL`** — the shared harness resets `public`, so concurrent runs can create false failures or kill a live mounted server mid-proof.
- **Reusing the full S06 frontend runner unchanged by inertia** — it works, but S04 may be cleaner and faster with a backend-only mode or thin wrapper unless a frontend path is genuinely needed.

## Open Risks

- The mounted backend may expose a runtime env dependency that pytest currently hides via `TESTING=1` — especially around Redis/session startup or other external-service initialization.
- The focused auth packs prove DB/session semantics, but because they override Redis they may miss a live cache/session wiring regression that only appears on a mounted server.
- The shared pytest harness still patches legacy-live columns into some tables. A runtime suite that only passes because of those guards could mask real final-head drift.
- Residual compatibility mirrors in `users` were intentionally left alive in S03. A mounted proof may surface a still-live reader that the current focused packs do not touch.
- `backend-hormonia/tests/integration/conftest.py` and older integration docs still advertise Firebase-era assumptions; if execution accidentally follows that path, S04 can widen into historical noise instead of final-schema proof.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| Alembic / SQLAlchemy migrations | `wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` | available — highest relevant search result (215 installs); no directly relevant installed skill exists in `<available_skills>` |
| FastAPI runtime proof | `mindrally/skills@fastapi-python` | available — strong runtime-focused candidate (2.1K installs); no directly relevant installed skill exists in `<available_skills>` |
| PostgreSQL schema/runtime validation | `mindrally/skills@postgresql-best-practices` | available — more relevant to final-schema proof than optimization-only packs (269 installs); no directly relevant installed skill exists in `<available_skills>` |

## Sources

- The final missing milestone proof is explicitly “boot the real backend on this consolidated head and replay the post-M004 critical loops against both freshly bootstrapped and upgraded schemas.” (source: [M005 S03 summary](.gsd/milestones/M005/slices/S03/S03-SUMMARY.md))
- Clean and upgraded database histories already converge on the same authoritative head `m005_s03_t02_align_audit_history_head`, with the exact two histories S04 should reuse. (source: [test_canonical_schema_head_convergence.py](backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py))
- The shared pytest harness now provisions Postgres via `alembic upgrade head` when `TEST_DATABASE_URL` is set, but then applies multiple `_ensure_*` schema guards that can mask drift if used as a structural oracle. (source: [tests/conftest.py](backend-hormonia/tests/conftest.py))
- Pytest/test-mode startup is not equivalent to mounted startup because `app/core/lifespan.py` skips external-service initialization when `PYTEST_CURRENT_TEST`, `TESTING=1`, or a test environment is detected. (source: [app/core/lifespan.py](backend-hormonia/app/core/lifespan.py))
- The old initialization suite is mostly mocked script coverage and uses `skip_migrations=True`, so it does not satisfy S04’s mounted-backend proof need. (source: [tests/test_initialization.py](backend-hormonia/tests/test_initialization.py), [scripts/init_database.py](backend-hormonia/scripts/init_database.py), [scripts/init_system.py](backend-hormonia/scripts/init_system.py))
- The strongest existing post-M004 backend loop proofs are the operational no-Firebase pack plus the two auth integration packs; these are the right loops for S04 to replay on the final schema. (source: [test_system_auth_hard_cut_operational.py](backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py), [test_local_auth_core_flow.py](backend-hormonia/tests/integration/test_local_auth_core_flow.py), [test_auth_hard_cut_end_to_end.py](backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py))
- The mounted operational precedent already exists: S06 published a replayable runner that blanks Firebase envs, seeds a masked proof user, boots the live stack, and probes `/health/ready` plus `/api/v2/system/config`. (source: [run-mounted-proof.sh](.gsd/milestones/M004/slices/S06/run-mounted-proof.sh), [seed-proof-user.py](.gsd/milestones/M004/slices/S06/seed-proof-user.py), [S06 summary](.gsd/milestones/M004/slices/S06/S06-SUMMARY.md))
- The older integration harness is stale for this slice because it still describes “Real Firebase authentication” and raw `DATABASE_URL` integration patterns. (source: [tests/integration/conftest.py](backend-hormonia/tests/integration/conftest.py))
- Skill search surfaced an Alembic-specific candidate with the highest relevant install count. (source: [sqlalchemy-alembic-expert-best-practices-code-review](https://skills.sh/wispbit-ai/skills/sqlalchemy-alembic-expert-best-practices-code-review))
- Skill search surfaced a FastAPI-focused candidate better aligned with runtime proof than generic template packs. (source: [fastapi-python](https://skills.sh/mindrally/skills/fastapi-python))
- Skill search surfaced a PostgreSQL best-practices candidate that is more directly relevant to final-schema/runtime validation than optimization-only packs. (source: [postgresql-best-practices](https://skills.sh/mindrally/skills/postgresql-best-practices))
