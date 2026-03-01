# Database Usage Analysis

**Generated at:** Sun Feb  8 18:59:10 -03 2026

## Summary
- **Total Tables in DB**: 48
- **Mapped Models**: 39
- **Active Tables**: 39

## ⚠️ Orphan Tables (In DB, No Model)
These tables exist in the database but do not have a corresponding SQLAlchemy model loaded in `app/models`. They might be:
- Deprecated tables
- Raw SQL tables
- Many-to-Many association tables (implicit)

- `alembic_version`
- `audit_log_entries`
- `audit_logs_archive`
- `audit_trail`
- `quiz_response_migration_log`
- `security_audit_log`
- `whatsapp_contacts`
- `whatsapp_instances`
- `whatsapp_messages`

## ❌ Missing Tables (In Model, No DB)
These models are defined in code but the table is missing in the DB (Migration pending?).

