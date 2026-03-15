# M005/S03 — Research

**Date:** 2026-03-14

## Summary

S03 owns the remaining open part of **R051**: after S01 and S02, the migration control plane works and the Firebase historical boundary is named, but the current head still does **not** tell one canonical schema story. The clean `base -> head` replay reaches a single honest head (`m005_s02_t01_publish_firebase_history_boundary`), yet that head still builds `users.role` as `varchar`, leaves `audit_logs.event_type` as `varchar`, does not create `audit_logs.firebase_uid`, and keeps transitional columns in `firebase_sync_history` that the ORM no longer exposes. In other words: the graph is operable, but the head is still structurally contradictory.

The main surprise is that the remaining Firebase residue splits into two very different categories. Some Firebase-named fields are still carrying **live product data** under the wrong names: `firebase_last_sign_in`, `firebase_display_name`, `firebase_photo_url`, `firebase_email_verified`, and especially `firebase_custom_claims`, which now backs preferences, phone, specialty, and avatar metadata. Other residue is already **compatibility-only**: `firebase_uid` fallback lookups in session/auth helpers, `auth_provider` bookkeeping that is written but not branched on, and the dormant Firebase sync service that still writes Firebase-era state but currently has no runtime call sites outside its own file/tests.

The recommendation is to treat S03 as a **targeted convergence slice**, not a repo-wide metadata cleanup. Add new linear alignment revision(s) on top of the current single head and converge the tables that still define the live auth/audit story — `users`, `audit_logs`, and `firebase_sync_history` — while reusing the S01/S02 Postgres harness to prove that a fresh database and an existing S02 database land on the **same** final schema. Avoid using “make autogenerate clean” as the goal; the full ORM-vs-schema diff explodes far outside this slice.

## Recommendation

Take a narrow, explicit convergence approach:

- **Keep the graph linear.** The graph already has a single head, so S03 should add one or more new revisions from `m005_s02_t01_publish_firebase_history_boundary` instead of rewriting history or manufacturing merge work.
- **Scope the canonical-head work to the real contract tables.** The structural contradictions are concentrated in `users`, `audit_logs`, and `firebase_sync_history`; proving those tables plus their enums/indexes converge is enough to advance R051 honestly.
- **Republish live profile/settings data under neutral names instead of dropping it blindly.**
  - `firebase_last_sign_in` → canonical last-login field
  - `firebase_display_name` / `firebase_photo_url` / `firebase_email_verified` → canonical profile fields
  - `firebase_custom_claims` → neutral metadata/settings field or a split replacement, because it is currently live storage for preferences/profile data
- **Keep `firebase_uid` and `auth_provider` only if the remaining compatibility readers actually require them.** Today they are not part of the official runtime happy path, but they still exist in fallback code and tests. If S03 keeps them, publish them as compatibility-only; if S03 drops them, the slice must first isolate or remove the fallback readers.
- **Fix enum drift instead of leaning on Python-side coercion.** `UserRole` and `AuditEventType` are already canonical Python enums. The cleaner S03 move is to align PostgreSQL to those enums with idempotent backfill/`ALTER TYPE` logic rather than weakening the models back to strings.
- **Decide `audit_logs.firebase_uid` explicitly.** Current state is the worst of both worlds: the ORM and tests expect it, but the clean Alembic head does not create it and no historical revision ever added it. The safer default is to remove it from the ORM/index contract unless a concrete preserved-history use case is proven.
- **Finish the historical table cleanup honestly.** `firebase_sync_history` still carries `supabase_user_id`, `sync_action`, and `sync_status` from the pre-S02 shape. If S03 keeps the archival table, it should decide whether those columns still carry value; otherwise drop them in a one-way revision after backfill/snapshot logic if needed.
- **Verify convergence structurally, not cosmetically.** Add a migration proof that fingerprints `users`, `audit_logs`, `firebase_sync_history`, and enum presence after:
  1. `base -> S03 head`
  2. `S02 head -> S03 head`
  and asserts those paths end with the same columns, types, key indexes, and head revision.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Idempotent schema-alignment work on a dirty historical chain | `backend-hormonia/alembic/versions/ab1c2d3e4f55_align_core_schema_with_models.py` | It already shows the local pattern for `_column_exists`, enum ensure/backfill helpers, and additive alignment work without rewriting the graph |
| Proving clean replay and existing-db upgrade on real Postgres | `backend-hormonia/tests/migrations/test_alembic_operability.py` + `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py` | S01/S02 already built the harness for scrubbed-env replay, schema reset, and existing-db upgrade proof; S03 should extend it, not invent a new migration runner |
| Publishing historical data without pretending it is live domain state | `backend-hormonia/alembic/versions/m005_s02_t01_publish_firebase_history_boundary.py` + `backend-hormonia/app/models/user_sync_log.py` | These already establish the naming and modeling pattern for explicit archival Firebase residue |
| Keeping the Alembic graph honest when branches/heads matter | `backend-hormonia/alembic/versions/lgpd01_add_patient_deletion_audit.py` + official Alembic branch docs | Local precedent and official docs both favor explicit merge/head semantics over rewriting the past to look linear |

## Existing Code and Patterns

- `backend-hormonia/alembic/versions/f7d2c1b9a4e6_add_firebase_columns_to_users.py` — introduced `firebase_uid`, `auth_provider`, Firebase profile fields, `firebase_custom_claims`, and `last_firebase_sync`; any final removal/rename should happen in **new** revisions, not by editing this one.
- `backend-hormonia/app/models/user.py` — still declares `firebase_uid`, `auth_provider`, all Firebase profile fields, `firebase_custom_claims`, and `last_firebase_sync` as live ORM columns.
- `backend-hormonia/app/api/v2/routers/users.py` — already exports neutral `last_login` and `photo_url`, but still reads/writes preferences through `firebase_custom_claims`.
- `backend-hormonia/app/api/v2/routers/auth.py` — still writes phone, specialty, and avatar into `firebase_custom_claims`, which makes that column live metadata storage rather than dead auth residue.
- `backend-hormonia/app/api/v2/routers/physicians/crud.py` + `backend-hormonia/app/schemas/v2/physicians.py` — still publish `firebase_display_name`, `firebase_photo_url`, and `firebase_email_verified` as official physician API fields.
- `backend-hormonia/app/dependencies/auth_role_dependencies.py`, `auth_session_cache.py`, and `auth_dependencies.py` — explicitly treat canonical `id` / `user_id` as authoritative and `firebase_uid` only as fallback, but they still query `users.firebase_uid` on that fallback path.
- `backend-hormonia/app/services/auth.py` and `backend-hormonia/app/services/password_reset_service.py` — only write `AuthProvider.LOCAL`; there is no live branch logic on `auth_provider`, only state updates and test-visible bookkeeping.
- `backend-hormonia/app/services/firebase_user_sync_service.py` — still writes `firebase_uid`, `auth_provider=FIREBASE`, and Firebase profile metadata, but repo search found no runtime call sites outside the service itself/tests.
- `backend-hormonia/app/models/audit_log.py` — expects `audit_event_type` enum, `firebase_uid`, and `idx_audit_firebase_time`, even though the clean Alembic head does not create that column or enum.
- `backend-hormonia/alembic/versions/011_hipaa_audit.py` — still anchors `audit_logs` around varchar `event_type` plus legacy-desc index names; this is where the clean-path audit shape still comes from.
- `backend-hormonia/alembic/versions/lgpd03_add_ai_audit_event_types.py` — only alters `audit_event_type` **if it already exists**; on the clean replay path it does not, so the column stays `varchar`.
- `backend-hormonia/alembic/versions/033_fix_user_sync_log_schema.py` — explains why `firebase_sync_history` still carries `supabase_user_id`, `sync_action`, and `sync_status` after the S02 rename.
- `backend-hormonia/tests/integration/test_password_reset_migration_flow.py` — still uses `auth_provider` as migration-era state and will need proof updates if S03 retires or narrows that field.
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py` — currently contains unresolved merge markers and survives only because it is lazily imported on a compatibility path; it is not a safe dependency for S03 proof.

## Constraints

- **R051 is the active target.** S03 should close clean/existing schema convergence on the canonical live auth/audit contract; it should not expand into generic repo cleanup that belongs to M006.
- The graph already has a **single head** (`m005_s02_t01_publish_firebase_history_boundary`); S03 does not need cosmetic merge surgery.
- A broad `compare_metadata()` sweep currently reports large drift across unrelated tables/models. Using “clean autogenerate diff” as the slice goal would widen scope far beyond S03.
- `users.firebase_uid` still underpins compatibility-only fallback in `auth_session_cache.py`, `auth_role_dependencies.py`, `auth_dependencies.py`, and `session_service.py`; dropping the column requires isolating or deleting those readers first.
- `firebase_custom_claims` is still live storage for preferences, phone, specialty, and avatar metadata. It cannot be dropped until S03 republishes that data somewhere canonical.
- `users.role` and `audit_logs.event_type` are still `varchar` on the clean replay path even though the ORM expects enums; the runtime currently tolerates the mismatch with string/enum fallbacks instead of fixing it.
- `audit_logs.firebase_uid` is **not** backed by any Alembic revision. Preserving it now would require an explicit new migration decision rather than assuming the clean head already has it.
- `firebase_sync_history` clean replay still includes `supabase_user_id`, `sync_action`, and `sync_status`; dropping them is one-way archival cleanup that needs existing-db proof.
- Destructive migration proof still resets `public`; if S03 reuses the shared local Postgres URL, tests must stay serial.

## Common Pitfalls

- **Trying to clean the entire metadata diff** — the full ORM-vs-schema diff is much larger than S03. Limit convergence proof to `users`, `audit_logs`, `firebase_sync_history`, and their enums/indexes.
- **Dropping `firebase_custom_claims` as if it were dead auth data** — it is still backing live preferences/profile writes. Rename or split it before removal.
- **Assuming `audit_logs.firebase_uid` already exists as preserved history** — the clean Alembic head never creates it. Decide preserve-vs-delete explicitly.
- **Dropping `users.firebase_uid` before isolating compatibility readers** — session/auth fallback code still queries it, so schema cleanup can become runtime breakage fast.
- **Treating enum drift as cosmetic** — `UserRole` and `AuditEventType` are already first-class Python enums. Leaving the DB as strings keeps hidden coercion paths alive.
- **Treating the S02 rename as full `firebase_sync_history` convergence** — only the table name changed; the clean head still carries transitional columns from `033_fix_user_sync_log_schema.py`.

## Open Risks

- Renaming live profile fields to neutral names can break physician/admin/user response schemas, caches, and sparse-field selection if the slice does not dual-read and dual-serialize during the cut.
- Tightening `audit_logs.event_type` to a PostgreSQL enum can fail on upgraded databases if historical rows contain values outside `AuditEventType`; existing data needs auditing before `ALTER COLUMN ... TYPE`.
- Existing databases may still contain useful values in `supabase_user_id`, `sync_action`, or `sync_status`; dropping them without snapshot/mapping logic could erase historical context S02 intended to keep.
- `auth_provider` looks non-canonical, but it is still written by local auth/password reset flows and asserted in migration-era tests; removing it changes proof, not just DDL.
- `app/dependencies/auth_legacy_firebase.py` contains unresolved merge markers and will fail if S03 accidentally leans on legacy bearer/Firebase compatibility paths during verification.
- If S03 tries to eliminate every `firebase_uid` code path instead of just de-living the schema contract, it will likely spill into M006-level cleanup.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| Alembic / migration graph | `wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` | available — install with `npx skills add wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` |
| SQLAlchemy ORM | `bobmatnyc/claude-mpm-skills@sqlalchemy-orm` | available — install with `npx skills add bobmatnyc/claude-mpm-skills@sqlalchemy-orm` |
| PostgreSQL schema work | `mindrally/skills@postgresql-best-practices` | available — install with `npx skills add mindrally/skills@postgresql-best-practices` |
| FastAPI backend surfaces | `mindrally/skills@fastapi-python` | available — install with `npx skills add mindrally/skills@fastapi-python` |

## Sources

- Clean `upgrade head` currently reaches `m005_s02_t01_publish_firebase_history_boundary`, but the resulting `users.role` still stays `varchar` and only `auth_provider` exists as an enum; no historical revision creates `user_role` (source: [backend-hormonia/alembic/versions/f7d2c1b9a4e6_add_firebase_columns_to_users.py](backend-hormonia/alembic/versions/f7d2c1b9a4e6_add_firebase_columns_to_users.py), [backend-hormonia/app/models/user.py](backend-hormonia/app/models/user.py))
- The `User` ORM still exposes Firebase-era auth/profile fields and metadata bag as live schema contract (source: [backend-hormonia/app/models/user.py](backend-hormonia/app/models/user.py))
- `/api/v2/users/me` already republishes neutral `last_login` / `photo_url`, but preferences still live in `firebase_custom_claims` (source: [backend-hormonia/app/api/v2/routers/users.py](backend-hormonia/app/api/v2/routers/users.py))
- Auth profile update and avatar upload still write phone/specialty/avatar into `firebase_custom_claims`, proving it is current live metadata storage (source: [backend-hormonia/app/api/v2/routers/auth.py](backend-hormonia/app/api/v2/routers/auth.py))
- Physician read surfaces still publish Firebase-named profile fields as official API response contract (source: [backend-hormonia/app/api/v2/routers/physicians/crud.py](backend-hormonia/app/api/v2/routers/physicians/crud.py), [backend-hormonia/app/schemas/v2/physicians.py](backend-hormonia/app/schemas/v2/physicians.py))
- Session/admin fallback code treats canonical `id` / `user_id` as authoritative and `firebase_uid` only as compatibility fallback, but it still queries `users.firebase_uid` when canonical IDs are absent (source: [backend-hormonia/app/dependencies/auth_role_dependencies.py](backend-hormonia/app/dependencies/auth_role_dependencies.py), [backend-hormonia/app/dependencies/auth_session_cache.py](backend-hormonia/app/dependencies/auth_session_cache.py), [backend-hormonia/app/dependencies/auth_dependencies.py](backend-hormonia/app/dependencies/auth_dependencies.py))
- `auth_provider` is still written by local auth/password reset flows, but no live branch logic was found on it in app code (source: [backend-hormonia/app/services/auth.py](backend-hormonia/app/services/auth.py), [backend-hormonia/app/services/password_reset_service.py](backend-hormonia/app/services/password_reset_service.py))
- `FirebaseUserSyncService` still writes Firebase-era state, but repo search found no runtime call sites outside the service itself/tests (source: [backend-hormonia/app/services/firebase_user_sync_service.py](backend-hormonia/app/services/firebase_user_sync_service.py))
- There is no Alembic revision that adds `audit_logs.firebase_uid`; that expectation exists only in the ORM/index contract and tests (source: [backend-hormonia/app/models/audit_log.py](backend-hormonia/app/models/audit_log.py), [backend-hormonia/alembic/versions/011_hipaa_audit.py](backend-hormonia/alembic/versions/011_hipaa_audit.py))
- `lgpd03_add_ai_audit_event_types.py` only mutates `audit_event_type` if the enum already exists; on the clean replay path it does not, so `audit_logs.event_type` remains `varchar` (source: [backend-hormonia/alembic/versions/lgpd03_add_ai_audit_event_types.py](backend-hormonia/alembic/versions/lgpd03_add_ai_audit_event_types.py), [backend-hormonia/app/models/audit_log.py](backend-hormonia/app/models/audit_log.py))
- `firebase_sync_history` is only a rename in S02; the clean head still carries `supabase_user_id`, `sync_action`, and `sync_status` from the old table shape while the ORM no longer exposes them (source: [backend-hormonia/alembic/versions/033_fix_user_sync_log_schema.py](backend-hormonia/alembic/versions/033_fix_user_sync_log_schema.py), [backend-hormonia/alembic/versions/m005_s02_t01_publish_firebase_history_boundary.py](backend-hormonia/alembic/versions/m005_s02_t01_publish_firebase_history_boundary.py), [backend-hormonia/app/models/user_sync_log.py](backend-hormonia/app/models/user_sync_log.py))
- `ab1c2d3e4f55_align_core_schema_with_models.py` is the local precedent for guarded alignment revisions with enum creation/backfill helpers (source: [backend-hormonia/alembic/versions/ab1c2d3e4f55_align_core_schema_with_models.py](backend-hormonia/alembic/versions/ab1c2d3e4f55_align_core_schema_with_models.py))
- Alembic’s official branch documentation explicitly favors explicit merge/head handling over pretending the graph is linear when it is not (source: [Alembic branches docs](https://github.com/sqlalchemy/alembic/blob/main/docs/build/branches.rst))
- The lazy Firebase compatibility module currently contains unresolved merge markers, so it is unsafe as a proof dependency despite staying off the happy path (source: [backend-hormonia/app/dependencies/auth_legacy_firebase.py](backend-hormonia/app/dependencies/auth_legacy_firebase.py))
