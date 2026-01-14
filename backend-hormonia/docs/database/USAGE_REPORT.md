# Database Usage Analysis

**Generated at:** Data atual: 01/01/2026 
Digite a nova data: (dd-mm-aa)

## Summary
- **Total Tables in DB**: 77
- **Mapped Models**: 45
- **Active Tables**: 43

## ⚠️ Orphan Tables (In DB, No Model)
These tables exist in the database but do not have a corresponding SQLAlchemy model loaded in `app/models`. They might be:
- Deprecated tables
- Raw SQL tables
- Many-to-Many association tables (implicit)

- `admin_audit_log`
- `admin_ip_blacklist`
- `admin_ip_whitelist`
- `admin_permissions`
- `admin_role_permissions`
- `admin_roles`
- `admin_security_events`
- `admin_sessions`
- `admin_user_permissions`
- `admin_users`
- `alembic_version`
- `audit_log_entries`
- `audit_logs_archive`
- `audit_logs_archive_2025`
- `audit_logs_archive_2026`
- `audit_logs_archive_2027`
- `audit_logs_archive_2028`
- `audit_logs_archive_2029`
- `audit_logs_archive_2030`
- `audit_logs_archive_2031`
- `audit_trail`
- `contacts`
- `flow_states`
- `flow_template_categories`
- `flow_template_shares`
- `flow_template_stats`

- `security_audit_log`
- `user_profiles`
- `whatsapp_contacts`
- `whatsapp_instances`
- `whatsapp_messages`

## ❌ Missing Tables (In Model, No DB)
These models are defined in code but the table is missing in the DB (Migration pending?).

- `lgpd_audit_logs`
- `lgpd_data_access_requests`
