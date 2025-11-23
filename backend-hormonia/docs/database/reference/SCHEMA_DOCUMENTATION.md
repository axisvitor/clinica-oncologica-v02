# Complete Database Schema Documentation

**Generated:** 2025-11-21
**Database:** PostgreSQL
**Total Tables:** 56
**Total Relationships:** 57
**User-Defined Types:** 14

---

## 📊 Executive Summary

### Database Statistics
- **Total Tables:** 56
- **Total Columns:** 1091
- **Total Indexes:** 320
- **Foreign Key Relationships:** 57
- **User-Defined Types (Enums):** 14

## 🗂️ Table Organization by Domain

### Admin & Security (10 tables)

| Table | Columns | Indexes | Foreign Keys |
|-------|---------|---------|--------------|
| `admin_audit_log` | 19 | 7 | 2 |
| `admin_ip_blacklist` | 12 | 3 | 1 |
| `admin_ip_whitelist` | 10 | 4 | 1 |
| `admin_permissions` | 5 | 3 | 0 |
| `admin_role_permissions` | 3 | 2 | 2 |
| `admin_roles` | 6 | 2 | 0 |
| `admin_security_events` | 16 | 6 | 2 |
| `admin_sessions` | 13 | 8 | 1 |
| `admin_user_permissions` | 4 | 2 | 3 |
| `admin_users` | 24 | 7 | 2 |

### Audit & Logging (14 tables)

| Table | Columns | Indexes | Foreign Keys |
|-------|---------|---------|--------------|
| `audit_log_entries` | 11 | 4 | 0 |
| `audit_logs` | 56 | 27 | 1 |
| `audit_logs_archive` | 56 | 1 | 0 |
| `audit_logs_archive_2025` | 56 | 1 | 0 |
| `audit_logs_archive_2026` | 56 | 1 | 0 |
| `audit_logs_archive_2027` | 56 | 1 | 0 |
| `audit_logs_archive_2028` | 56 | 1 | 0 |
| `audit_logs_archive_2029` | 56 | 1 | 0 |
| `audit_logs_archive_2030` | 56 | 1 | 0 |
| `audit_logs_archive_2031` | 56 | 1 | 0 |
| `audit_trail` | 14 | 5 | 0 |
| `error_logs` | 12 | 12 | 0 |
| `security_audit_log` | 13 | 12 | 1 |
| `user_sync_log` | 12 | 5 | 1 |

### Messaging & WhatsApp (8 tables)

| Table | Columns | Indexes | Foreign Keys |
|-------|---------|---------|--------------|
| `contacts` | 12 | 4 | 2 |
| `flow_messages` | 11 | 6 | 1 |
| `message_status_events` | 13 | 5 | 1 |
| `messages` | 21 | 21 | 1 |
| `whatsapp_contacts` | 11 | 3 | 0 |
| `whatsapp_delivery_failures` | 18 | 4 | 3 |
| `whatsapp_instances` | 13 | 3 | 0 |
| `whatsapp_messages` | 20 | 5 | 0 |

### Patients & Medical (5 tables)

| Table | Columns | Indexes | Foreign Keys |
|-------|---------|---------|--------------|
| `appointments` | 14 | 5 | 2 |
| `medical_reports` | 13 | 5 | 2 |
| `patient_flow_states` | 14 | 11 | 2 |
| `patient_onboarding_saga` | 18 | 6 | 2 |
| `patients` | 18 | 22 | 1 |

### Quiz & Flow (13 tables)

| Table | Columns | Indexes | Foreign Keys |
|-------|---------|---------|--------------|
| `flow_analytics` | 12 | 6 | 2 |
| `flow_kinds` | 7 | 4 | 0 |
| `flow_states` | 9 | 3 | 1 |
| `flow_template_categories` | 8 | 2 | 0 |
| `flow_template_shares` | 10 | 2 | 3 |
| `flow_template_stats` | 10 | 2 | 1 |
| `flow_template_versions` | 14 | 5 | 2 |
| `quiz_response_migration_log` | 7 | 3 | 0 |
| `quiz_responses` | 17 | 11 | 3 |
| `quiz_sessions` | 16 | 16 | 2 |
| `quiz_sessions_v2` | 8 | 3 | 2 |
| `quiz_template_versions_v2` | 11 | 4 | 2 |
| `quiz_templates` | 13 | 3 | 0 |

### System & Meta (6 tables)

| Table | Columns | Indexes | Foreign Keys |
|-------|---------|---------|--------------|
| `alembic_version` | 1 | 1 | 0 |
| `alerts` | 11 | 8 | 2 |
| `notifications` | 17 | 9 | 2 |
| `user_profiles` | 12 | 3 | 1 |
| `users` | 17 | 9 | 0 |
| `webhook_events` | 17 | 9 | 0 |

## 🔤 User-Defined Types (Enums)

| Type Name | Values | Used In |
|-----------|--------|---------|
| `admin_role_type` | super_admin, admin, manager, supervisor | admin_users.role |
| `alert_severity` | low, medium, high, critical | alerts.severity |
| `auth_provider` | local, firebase, google, apple | users.auth_provider |
| `deliverystatus` | scheduled, queued, sending, sent, delivered, read, failed, cancelled | messages.delivery_status |
| `flow_state` | onboarding, active, paused, completed, inactive, cancelled | patients.flow_state |
| `http_method_type` | GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD | admin_audit_log.http_method |
| `message_direction` | inbound, outbound | messages.direction |
| `message_priority` | critical, high, normal, low | messages.priority |
| `message_status` | pending, sent, delivered, read, failed, scheduled, sending | messages.status |
| `message_type` | text, button, list, media, location, quiz_intro, quiz_question, quiz_encouragement, quiz_completion, monthly_quiz_link, monthly_quiz_reminder, monthly_quiz_expired, monthly_quiz_completed | messages.type |
| `messagestatus` | pending, scheduled, sending, sent, failed, delivered, read |  |
| `saga_status` | STARTED, STEP_1_PATIENT_CREATED, STEP_2_FIREBASE_USER_CREATED, STEP_3_FLOW_INITIALIZED, STEP_4_MESSAGE_SENT, COMPLETED, FAILED, COMPENSATING, COMPENSATED, RETRY_SCHEDULED | patient_onboarding_saga.status |
| `severity_type` | low, medium, high, critical | admin_audit_log.severity, admin_ip_blacklist.threat_level, admin_security_events.severity, ... |
| `user_role` | doctor, admin | users.role |
