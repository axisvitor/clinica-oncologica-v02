# Real Database Analysis

**Environment:** Production database from `backend-hormonia/.env`  
**Executed at (Sao Paulo):** 2026-02-08 18:47:03 -03  
**Mode:** Read-only inspection + migration-backed cleanup + docs regeneration

## Executive Summary
- The real database is reachable and healthy for inspection.
- A/B testing legacy tables were removed via Alembic revision `8d2a7c4b1f55`.
- Documentation under `docs/database` was regenerated from the live schema after removal.
- Current inventory is consistent: **48 real tables** and **48 table docs**.
- Model mapping currently covers **39/48 tables**; **9 tables** remain outside `app/models`.

## Database Snapshot

| Metric | Value |
| :--- | :--- |
| Database | `postgres` |
| User | `neoplasias` |
| Total size | `18 MB` |
| Public tables | `48` |
| Tables with PK | `48` |
| Tables without PK | `0` |

## Model Coverage (from `USAGE_REPORT.md`)

| Metric | Value |
| :--- | :--- |
| Total Tables in DB | `48` |
| Mapped Models | `39` |
| Active Tables (intersection) | `39` |
| Orphan Tables (DB without model) | `9` |
| Missing Tables (model without DB) | `0` |

Orphan tables listed in the generated report:
- `alembic_version`
- `audit_log_entries`
- `audit_logs_archive`
- `audit_trail`
- `quiz_response_migration_log`
- `security_audit_log`
- `whatsapp_contacts`
- `whatsapp_instances`
- `whatsapp_messages`

## Heaviest Tables (by total size)

| Table | Total Size | Live Rows (est.) | Dead Rows (est.) |
| :--- | :--- | :--- | :--- |
| `lgpd_audit_logs` | `616 kB` | `277` | `0` |
| `messages` | `536 kB` | `114` | `22` |
| `whatsapp_messages` | `488 kB` | `151` | `20` |
| `patients` | `368 kB` | `35` | `13` |
| `webhook_events` | `320 kB` | `10` | `7` |
| `patient_flow_states` | `288 kB` | `20` | `33` |
| `patient_onboarding_saga` | `264 kB` | `26` | `7` |
| `flow_template_versions` | `248 kB` | `3` | `3` |
| `sessions` | `224 kB` | `100` | `1` |
| `audit_logs` | `224 kB` | `8` | `0` |

## Health Observations
- No high-traffic table was found with `seq_scan > 1000` and `idx_scan = 0`.
- 7 tables currently have `dead_rows > live_rows` (small absolute sizes, but worth routine maintenance):
  - `alembic_version`
  - `flow_kinds`
  - `patient_flow_states`
  - `quiz_sessions`
  - `whatsapp_contacts`
  - `quiz_responses`
  - `quiz_templates`

## Documentation Review Outcome
- `docs/database/SCHEMA.md` regenerated from live schema.
- `docs/database/USAGE_REPORT.md` regenerated with current counts/date.
- Individual docs in `docs/database/tables/*.md` regenerated.
- A/B docs removed from `docs/database/tables/ab_*.md`.
- Stale table docs no longer present in live DB were removed from `tables/`.
- New live tables without docs were generated (`lgpd_*`, `message_archives`).

## Recommended Next Actions
1. Decide ownership for the 9 orphan tables (keep as raw-SQL/system tables or add explicit models).
2. Keep a scheduled job to regenerate DB docs (e.g., weekly or per migration).
3. Add CI guard to fail when `docs/database/tables` diverges from real schema snapshot.
