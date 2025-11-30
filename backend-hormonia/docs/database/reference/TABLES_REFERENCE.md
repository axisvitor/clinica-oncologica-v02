# Tables Reference

> **Auto-generated:** 2025-11-26 15:00:00
> **Total Tables:** 56

## Quick Reference Table

| Table | Columns | Indexes | Foreign Keys | Description |
|-------|---------|---------|--------------|-------------|
| `admin_audit_log` | 19 | 7 | 2 | Admin action audit trail |
| `admin_ip_blacklist` | 12 | 3 | 1 | Blocked IP addresses |
| `admin_ip_whitelist` | 10 | 4 | 1 | Allowed IP addresses |
| `admin_permissions` | 5 | 3 | 0 | Granular permissions |
| `admin_role_permissions` | 3 | 2 | 2 | Role-permission mappings |
| `admin_roles` | 6 | 2 | 0 | Admin role definitions |
| `admin_security_events` | 16 | 6 | 2 | Security events (login, logout, etc) |
| `admin_sessions` | 13 | 8 | 1 | Active admin sessions |
| `admin_user_permissions` | 4 | 2 | 3 | User-specific permission overrides |
| `admin_users` | 24 | 7 | 2 | Admin panel users (separate auth) |
| `alembic_version` | 1 | 1 | 0 | Migration version tracking |
| `alerts` | 11 | 8 | 2 | System and clinical alerts |
| `appointments` | 14 | 5 | 2 | Scheduled appointments |
| `audit_log_entries` | 11 | 4 | 0 | Detailed audit entries |
| `audit_logs` | 56 | 27 | 1 | Application audit logs |
| `audit_logs_archive` | 56 | 1 | 0 | - |
| `audit_trail` | 14 | 5 | 0 | Change tracking |
| `contacts` | 12 | 4 | 2 | General contacts |
| `error_logs` | 12 | 12 | 0 | Application error logs |
| `flow_analytics` | 12 | 6 | 2 | Flow performance analytics |
| `flow_kinds` | 7 | 4 | 0 | Flow type definitions |
| `flow_messages` | 11 | 6 | 1 | Messages within flows |
| `flow_states` | 9 | 3 | 1 | Patient flow state machines |
| `flow_template_categories` | 8 | 2 | 0 | Flow template organization |
| `flow_template_shares` | 10 | 2 | 3 | Shared flow templates |
| `flow_template_stats` | 10 | 2 | 1 | Template usage statistics |
| `flow_template_versions` | 14 | 5 | 2 | Flow template versioning |
| `medical_reports` | 13 | 5 | 2 | AI-generated medical reports |
| `message_status_events` | 13 | 5 | 1 | Message delivery status tracking |
| `message_templates` | 9 | 2 | 0 | Reusable message templates |
| `messages` | 21 | 21 | 1 | WhatsApp/SMS messages |
| `notifications` | 17 | 9 | 2 | In-app notifications |
| `patient_flow_states` | 14 | 11 | 2 | Patient-specific flow states |
| `patient_onboarding_saga` | 18 | 6 | 2 | Saga pattern for onboarding |
| `patient_summaries` | 12 | 3 | 2 | AI-generated medical summaries |
| `patients` | 17 | 26 | 1 | Core patient records with treatment info |
| `pg_stat_statements` | 49 | 0 | 0 | - |
| `pg_stat_statements_info` | 2 | 0 | 0 | - |
| `quiz_response_migration_log` | 7 | 3 | 0 | Migration tracking |
| `quiz_responses` | 17 | 14 | 3 | Patient quiz answers |
| `quiz_responses_with_text` | 20 | 0 | 0 | - |
| `quiz_sessions` | 16 | 16 | 2 | Active quiz sessions |
| `quiz_sessions_v2` | 8 | 3 | 2 | V2 quiz sessions (monthly) |
| `quiz_template_versions_v2` | 11 | 4 | 2 | V2 quiz versioning |
| `quiz_templates` | 13 | 3 | 0 | Quiz definitions |
| `security_audit_log` | 13 | 12 | 1 | Security-specific auditing |
| `system_health_snapshots` | 7 | 3 | 0 | System health metrics |
| `system_incidents` | 11 | 2 | 0 | Incident tracking |
| `user_profiles` | 12 | 3 | 1 | Extended user profile data |
| `user_sync_log` | 12 | 5 | 1 | Firebase sync log |
| `users` | 18 | 10 | 0 | Firebase-authenticated users (includes permissions) |
| `webhook_events` | 17 | 9 | 0 | Incoming webhook payloads |
| `whatsapp_contacts` | 11 | 3 | 0 | WhatsApp contact sync |
| `whatsapp_delivery_failures` | 18 | 4 | 3 | Failed delivery tracking |
| `whatsapp_instances` | 13 | 3 | 0 | Evolution API instances |
| `whatsapp_messages` | 20 | 5 | 0 | WhatsApp message records |


## Statistics

- **Total Tables:** 56
- **Total Columns:** 810
- **Total Indexes:** 341
- **Tables with Foreign Keys:** 34

## New in Migrations 020-024 (LGPD & Performance)

### Migration 020: LGPD CPF Encryption
- Added `cpf_encrypted` and `cpf_hash` to `patients` table
- Created index `ix_patients_cpf_hash` for fast searchable queries
- Migrated existing plaintext CPF to encrypted format

### Migration 021: AI-Generated Patient Summaries
- Created `patient_summaries` table for AI-generated medical reports
- Stores structured JSON content and optional PDF data
- Tracks AI model usage and generation performance

### Migration 022: Cursor Pagination Indexes
- Added 8 composite indexes for efficient cursor-based pagination
- Performance improvement: Deep pagination 450ms → 5ms (99% faster)
- Affects tables: `messages`, `patients`, `quiz_responses`, `audit_logs`, `alerts`, `patient_flow_states`

### Migration 023: User Permissions (RBAC)
- Added `permissions` JSONB field to `users` table
- Created GIN index for efficient permission lookups
- Enables granular role-based access control

### Migration 024: Drop Plaintext CPF
- Removed deprecated plaintext `cpf` column from `patients`
- Completes LGPD compliance for PII data
- **Irreversible migration** - plaintext data permanently deleted

## Index Summary by Table

| Table | Index Count |
|-------|------------|
| `audit_logs` | 27 |
| `patients` | 26 |
| `messages` | 21 |
| `quiz_sessions` | 16 |
| `quiz_responses` | 14 |
| `error_logs` | 12 |
| `security_audit_log` | 12 |
| `patient_flow_states` | 11 |
| `notifications` | 9 |
| `users` | 10 |
| `webhook_events` | 9 |
| `admin_sessions` | 8 |
| `alerts` | 8 |
| `admin_audit_log` | 7 |
| `admin_users` | 7 |
| `admin_security_events` | 6 |
| `flow_analytics` | 6 |
| `flow_messages` | 6 |
| `patient_onboarding_saga` | 6 |
| `appointments` | 5 |
