# M006/S02 — Research

**Date:** 2026-03-14

## Summary

S02 supports the only active requirement, **R052**, but the real work is narrower than “drop old columns from `users`”. The live risk is that `backend-hormonia/app/models/user.py` still treats Firebase-era storage as transition-compatible runtime state: every canonical setter mirrors back into Firebase columns or `firebase_custom_claims` by default, and core auth/session helpers still preserve `firebase_uid` compatibility when canonical IDs are absent. That means a migration-first approach would be dishonest. The columns can only disappear after the runtime and fixtures stop behaving as if they still exist.

The repo is split in an interesting way. The newer shared helpers already model the target state: `backend-hormonia/app/api/v2/auth_session_shared.py` and `backend-hormonia/app/api/v2/user_cache_shared.py` are canonical `user_id`-first and strip `firebase_uid` from emitted payloads, and the narrow canonical contract pack already passes. But the older auth/session seam still serializes `firebase_uid`, allows `firebase_uid`-only compatibility fallback, and many fixtures still override `get_current_user_from_session()` with Firebase-shaped payloads. The biggest surprise is that some of the heaviest Firebase-era code (`FirebaseUserSyncService`, old `SessionService`) appears to be tests-only or runtime-dead now; the main live blockers are smaller: the `User` helper layer, a few direct ORM readers, and a lot of fixture drift.

Primary recommendation: execute S02 as **runtime narrowing first, migration second**. First remove direct app readers/writers that still depend on `users.firebase_*` / `firebase_uid`, then republish the `User` helper API so canonical writes stop mirroring legacy storage, then add the new Alembic revision that drops the Firebase-named `users` columns and `ix_users_firebase_uid`. Treat `auth_provider` as a separate decision gate: it is not Firebase-prefixed, but it is still written by login/reset/admin-create flows and still anchors integration tests.

## Recommendation

Take S02 in this order:

1. **Start from the active requirement boundary.** This slice supports **R052** by removing structural residue with proof, but it must preserve the already-validated schema/runtime closeout surfaces from **R051** and **R053**. In practice that means using the existing M005 replay runner and mounted backend proof, not inventing a new schema-only success definition.
2. **Narrow live readers before touching Alembic.** The current app still has direct ORM reads of legacy `users` fields:
   - `backend-hormonia/app/dependencies/auth_role_dependencies.py` falls back to `User.firebase_uid` for admin session loading.
   - `backend-hormonia/app/dependencies/auth_session_cache.py` still serializes `firebase_uid`, writes passive `firebase_uid` cache entries, and permits `firebase_uid`-only session compatibility when canonical IDs are missing.
   - `backend-hormonia/app/services/analytics/admin_stats_service.py` still computes `active_now` from `User.firebase_last_sign_in` and even comments as if `last_login` does not exist.
   - `backend-hormonia/app/api/v2/routers/physicians/crud.py` still searches `User.firebase_display_name` and preserves compatibility claims in `firebase_custom_claims`.
   - `backend-hormonia/app/repositories/user.py` still exposes `get_by_firebase_uid()`, but repo grep shows no app callers.
3. **Republish the `User` model helper contract before column removal.** Right now canonical helpers still mirror legacy storage by default:
   - `set_last_login()` writes `firebase_last_sign_in`
   - `set_auth_created_at()` writes `firebase_created_at`
   - `set_email_verified()` writes `firebase_email_verified`
   - `set_display_name()` writes `firebase_display_name`
   - `set_photo_url()` writes `firebase_photo_url`
   - all profile/settings helpers mirror into `firebase_custom_claims`
   S02 needs to either flip those defaults to canonical-only or remove the legacy mirror logic entirely; otherwise the runtime will keep repopulating the columns the migration wants to delete.
4. **Then add the schema revision after `m005_s03_t02_align_audit_history_head`.** The clearest first cut is dropping:
   - `users.firebase_uid`
   - `users.firebase_last_sign_in`
   - `users.firebase_created_at`
   - `users.firebase_email_verified`
   - `users.firebase_display_name`
   - `users.firebase_photo_url`
   - `users.firebase_custom_claims`
   - `users.last_firebase_sync`
   - `ix_users_firebase_uid`
   Use `backend-hormonia/alembic/versions/f7d2c1b9a4e6_add_firebase_columns_to_users.py` as the teardown reference for what must be unwound.
5. **Treat `auth_provider` as an explicit scope call, not an incidental deletion.** It is still written in:
   - `backend-hormonia/app/services/auth.py`
   - `backend-hormonia/app/services/password_reset_service.py`
   - `backend-hormonia/app/api/v2/routers/auth.py`
   - `backend-hormonia/app/api/v2/routers/admin/users.py`
   and integration tests still assert migration from `AuthProvider.FIREBASE` to `AuthProvider.LOCAL`. Dropping it may be right, but it is a broader contract change than removing the Firebase-prefixed residue.
6. **Rebuild the proof pack around the real blast radius.** The existing M005 runner is necessary but not sufficient because it only replays:
   - `tests/api/v2/test_system_auth_hard_cut_operational.py`
   - `tests/integration/test_local_auth_core_flow.py`
   - `tests/integration/test_auth_hard_cut_end_to_end.py`
   It will not catch `physicians` search drift or `admin_stats_service` semantics. S02 should keep the M005 runner and add focused proof for physician detail/search and user/admin metrics after the column cut.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Fresh/existing schema replay plus mounted backend proof | `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` | Already serializes `canonical_head -> pytest_replay -> mounted_backend -> live_auth_probe` and is the honest integrated proof surface for post-migration runtime behavior. |
| Clean replay vs existing-upgrade fingerprint comparison | `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` | Already fingerprints the target `users` / `audit_logs` / `firebase_sync_history` head for both histories; S02 should extend or reuse it instead of inventing ad hoc schema checks. |
| Historical Firebase sync boundary | `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py` + `backend-hormonia/app/models/user_sync_log.py` | They already publish `firebase_sync_history` as explicit archival residue. S02 should preserve this boundary while deleting live `users` residue. |
| Canonical session/user helper pattern | `backend-hormonia/app/api/v2/auth_session_shared.py` + `backend-hormonia/app/api/v2/user_cache_shared.py` | These files already implement the target pattern: canonical `user_id` lookups, embedded canonical session envelopes, and `firebase_uid` stripping before emission. |
| Focused canonical contract proof | `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py`, `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py`, `backend-hormonia/tests/api/v2/test_canonical_user_profile_contracts.py` | These suites already describe the desired post-cut behavior and passed locally, so S02 should expand from them rather than rewrite proof from scratch. |

## Existing Code and Patterns

- `backend-hormonia/app/models/user.py` — Canonical profile/settings fields already exist, but the Firebase-era columns are still present and every canonical setter mirrors back into them by default.
- `backend-hormonia/alembic/versions/m005_s03_t01_republish_users_canonical_contract.py` — Backfilled canonical `users` storage from the legacy Firebase columns/claims; this is the migration baseline S02 must now narrow further.
- `backend-hormonia/alembic/versions/m005_s03_t02_align_audit_history_head.py` — Current canonical head. Any S02 schema drop should branch from here, not from an older Firebase-era revision.
- `backend-hormonia/alembic/versions/f7d2c1b9a4e6_add_firebase_columns_to_users.py` — Original add/drop shape for `firebase_uid`, `auth_provider`, `firebase_*`, `last_firebase_sync`, and `ix_users_firebase_uid`; use it as the teardown inventory.
- `backend-hormonia/app/dependencies/auth_session_cache.py` — Still the main compatibility seam keeping `firebase_uid` structurally alive in session payloads, cache hydration, and fallback lookup logic.
- `backend-hormonia/app/dependencies/auth_session_contract.py` — Cookie-only transport is already honest, but it still delegates to session-cache logic that preserves `firebase_uid` compatibility deeper down.
- `backend-hormonia/app/dependencies/auth_role_dependencies.py` — Admin session loader still falls back to `User.firebase_uid` when canonical IDs are absent.
- `backend-hormonia/app/api/v2/auth_session_shared.py` — Already the canonical pattern to follow: reject `firebase_uid`-only session payloads and require canonical IDs.
- `backend-hormonia/app/api/v2/user_cache_shared.py` — Already canonical `user_id`-only cache/DB lookup with `firebase_uid` stripping before emission.
- `backend-hormonia/app/services/analytics/admin_stats_service.py` — Still computes “active users” from `firebase_last_sign_in`; this is live behavior, not cosmetic residue.
- `backend-hormonia/app/api/v2/routers/physicians/crud.py` — Uses canonical getters for output, but still searches `firebase_display_name` and preserves compatibility claims in `firebase_custom_claims` during updates.
- `backend-hormonia/app/repositories/user.py` — `get_by_firebase_uid()` exists but repo grep found no app callers, making it a low-risk deletion once the column disappears.
- `backend-hormonia/app/service_provider.py` — Runtime now wires `SimpleSessionService`, which means the old Firebase-centric `SessionService` is not the active session service anymore.
- `backend-hormonia/tests/api/v2/conftest.py` and `backend-hormonia/tests/conftest.py` — Shared fixtures still inject `firebase_uid` and still derive `last_login` from `firebase_last_sign_in`, so a lot of S02 work is fixture republication rather than runtime surgery.
- `backend-hormonia/tests/integration/test_auth_fallback.py` — Explicitly asserts `firebase_uid` survives Redis/Postgres fallback; this is a direct proof surface that must be deleted or republished if S02 removes the compatibility path.
- `backend-hormonia/app/models/user_sync_log.py` — Historical `firebase_sync_history` model is already honest archival residue and should remain outside the live `users` cleanup.

## Constraints

- `backend-hormonia/app/models/user.py` currently keeps legacy mirrors alive by default (`mirror_legacy=True` everywhere). Dropping columns without changing those defaults will turn normal canonical writes into runtime failures.
- `backend-hormonia/app/dependencies/auth_session_cache.py` still serializes `firebase_uid` and supports `firebase_uid`-only fallback when canonical IDs are absent. Removing the column before narrowing this seam will just move the breakage into session rehydration and cache compatibility.
- `backend-hormonia/app/dependencies/auth_role_dependencies.py` still uses `User.firebase_uid` as an admin-session fallback. If this survives the column drop, admin role routes will fail only on the less-traveled compatibility path.
- Direct app readers still exist for `firebase_last_sign_in` and `firebase_display_name`, so the migration is not just “schema + tests”.
- The M005 final-schema runner does not currently exercise physician search or admin metrics. S02 needs extra focused proof or it can falsely pass while leaving live Firebase-named readers behind.
- `firebase_sync_history` is an explicit historical boundary. Its `firebase_uid` is archival data, not live `users` contract residue, so S02 should not collapse it accidentally.
- `auth_provider` is still active in login/reset/admin-create flows and in migration integration tests. Treating it as “just another Firebase column” would widen the slice more than the roadmap text currently requires.
- `FirebaseUserSyncService` and the old `SessionService` appear app-dead but are still heavily covered by tests. That makes them execution noise unless S02 deliberately republishes them as historical/test-only or deletes them in coordination with S03.

## Common Pitfalls

- **Dropping the columns before changing the model helper defaults** — The helper API still mirrors canonical writes back into legacy columns and claims; remove the mirror contract first or the migration will fail on normal profile/auth writes.
- **Using the M005 runner as the only proof** — It proves the core auth/runtime path, but it does not cover physician search or admin metrics, where direct `firebase_*` readers still exist.
- **Cleaning runtime code while leaving fixture/session overrides Firebase-shaped** — Many shared fixtures still inject `firebase_uid` and `firebase_last_sign_in`; S02 can look “broken” or “unfinished” until those harnesses are republished too.
- **Treating `firebase_sync_history` as live residue** — That table is already the explicit archival boundary. Deleting or renaming it here would break the historical contract published in M005.
- **Silently widening into `auth_provider` removal** — That may be the right end state, but it has active runtime writers and integration proof today. Make it an explicit scope decision, not an incidental side effect of the Firebase-named column drop.

## Open Risks

- Some broad legacy suites (`test_auth_fallback`, `test_auth_timeout`, route-validation/edge-case fixtures, and shared auth fixtures) still encode `firebase_uid`-based session behavior. They will fail noisily once S02 removes that compatibility, and they need deliberate republication rather than piecemeal patching.
- `backend-hormonia/app/services/analytics/admin_stats_service.py` currently uses a misleading metric definition (`firebase_last_sign_in` with a stale “we don't have last_login” comment). S02 needs to choose whether the canonical replacement is `last_login` or some other activity signal.
- `backend-hormonia/app/api/v2/routers/physicians/crud.py` still searches `firebase_display_name`. The M005 backfill suggests canonical `display_name` should already be enough, but S02 needs focused search proof after removing the fallback.
- If S02 decides to drop `auth_provider`, the password-reset migration proof and admin-created first-access flow need republication, not just model edits.
- The remaining tests-only Firebase services (`FirebaseUserSyncService`, old `SessionService`) may tempt the slice into dead-service cleanup work that belongs more naturally in S03 unless a precise proof surface still treats them as live.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `wshobson/agents@fastapi-templates` | available — 6.4K installs; strongest match for dependency/route patterns around session/auth helpers |
| SQLAlchemy / Alembic | `wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` | available — 216 installs; most relevant schema-replay skill for safe column/index drops |
| PostgreSQL | `github/awesome-copilot@postgresql-code-review` | available — 7.2K installs; useful if enum/index teardown or migration review gets tricky |

## Sources

- `User` still defines `firebase_uid`, `auth_provider`, and the remaining `firebase_*` / `last_firebase_sync` columns, and every canonical helper mirrors legacy storage by default. (source: `backend-hormonia/app/models/user.py`)
- M005 republished canonical `users` storage from the legacy Firebase fields but intentionally did not drop the old columns yet. (source: `backend-hormonia/alembic/versions/m005_s03_t01_republish_users_canonical_contract.py`)
- The current head is still `m005_s03_t02_align_audit_history_head`; any S02 migration has to branch from there and preserve the current convergence proof shape. (source: `backend-hormonia/alembic/versions/m005_s03_t02_align_audit_history_head.py`; `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py`)
- The original Firebase-era `users` migration created `firebase_uid`, `auth_provider`, all `firebase_*` columns, `last_firebase_sync`, and `ix_users_firebase_uid`, so those schema objects need explicit teardown rather than best-effort drift cleanup. (source: `backend-hormonia/alembic/versions/f7d2c1b9a4e6_add_firebase_columns_to_users.py`)
- The cookie-only transport is already honest, but deeper auth/session code still preserves `firebase_uid` compatibility via `auth_session_cache` and admin role fallback. (source: `backend-hormonia/app/dependencies/auth_session_contract.py`; `backend-hormonia/app/dependencies/auth_session_cache.py`; `backend-hormonia/app/dependencies/auth_role_dependencies.py`; `backend-hormonia/app/dependencies/auth_dependencies.py`)
- Newer shared helpers already implement the target pattern: canonical session IDs only, canonical `user_id` lookups, and `firebase_uid` stripping before emission. (source: `backend-hormonia/app/api/v2/auth_session_shared.py`; `backend-hormonia/app/api/v2/user_cache_shared.py`)
- Direct live app readers still exist for `User.firebase_last_sign_in` and `User.firebase_display_name`, while `UserRepository.get_by_firebase_uid()` has no app callers. (source: `backend-hormonia/app/services/analytics/admin_stats_service.py`; `backend-hormonia/app/api/v2/routers/physicians/crud.py`; `backend-hormonia/app/repositories/user.py`; local command `rg -n "User\.(firebase_uid|firebase_last_sign_in|firebase_display_name...)" ...`)
- Runtime uses `SimpleSessionService`; `FirebaseUserSyncService` and old `SessionService` appear only in tests, which makes them likely historical/dead surfaces rather than mounted-runtime blockers. (source: `backend-hormonia/app/service_provider.py`; local commands `rg -n "FirebaseUserSyncService..."` and `rg -n "SessionService..."`)
- Shared fixtures still inject `firebase_uid` and still derive `last_login` from `firebase_last_sign_in`, so S02 will need harness republication in addition to runtime/schema changes. (source: `backend-hormonia/tests/api/v2/conftest.py`; `backend-hormonia/tests/conftest.py`; `backend-hormonia/tests/api/v2/conftest_auth.py`)
- Broad fallback tests still expect `firebase_uid` to survive auth/session fallback, which will become invalid once S02 removes the compatibility path. (source: `backend-hormonia/tests/integration/test_auth_fallback.py`; `backend-hormonia/tests/unit/test_auth_dependencies.py`; `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py`)
- The explicit historical Firebase boundary lives in `firebase_sync_history` and is already proven separately; it should remain outside the live `users` cleanup. (source: `backend-hormonia/app/models/user_sync_log.py`; `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py`)
- The canonical contract pack already passes locally, so the public profile/session surfaces are closer to the target state than the schema suggests. (source: local command `cd backend-hormonia && .venv/bin/pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_canonical_user_profile_contracts.py`)
- The M005 replay runner currently replays only the auth/runtime packs and mounted backend proof, which means S02 needs extra focused proof for readers like physician search and admin metrics. (source: `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh`)
