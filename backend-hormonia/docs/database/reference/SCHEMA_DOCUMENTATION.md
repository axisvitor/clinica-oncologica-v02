# Database Schema Documentation

> **Auto-generated:** 2025-11-26 15:00:00
> **Database:** PostgreSQL 14+ on Amazon RDS (sa-east-1)
> **Total Tables:** 56

## Table of Contents

- [Core](#core)
- [Admin & Security](#admin--security)
- [Messaging](#messaging)
- [WhatsApp](#whatsapp)
- [Flows](#flows)
- [Quiz](#quiz)
- [Medical](#medical)
- [Audit & Logging](#audit--logging)
- [System](#system)

---

## Core

### `patients`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `doctor_id` | `uuid` | ✗ | - |
| `phone` | `character varying(20)` | ✗ | - |
| `name` | `character varying(255)` | ✗ | - |
| `email` | `character varying(255)` | ✓ | - |
| `birth_date` | `date` | ✓ | - |
| `treatment_type` | `character varying(100)` | ✓ | - |
| `treatment_start_date` | `date` | ✓ | - |
| `treatment_phase` | `character varying(50)` | ✓ | - |
| `diagnosis` | `text` | ✓ | - |
| `flow_state` | `flow_state` | ✗ | 'onboarding'::flow_state |
| `current_day` | `integer` | ✗ | 0 |
| `doctor_notes` | `text` | ✓ | - |
| `cpf_encrypted` | `text` | ✓ | - |
| `cpf_hash` | `character varying(64)` | ✓ | - |
| `email_encrypted` | `bytea` | ✓ | - |
| `email_hash` | `character varying(64)` | ✓ | - |
| `phone_encrypted` | `bytea` | ✓ | - |
| `phone_hash` | `character varying(64)` | ✓ | - |
| `idempotency_key` | `character varying(64)` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✗ | now() |
| `updated_at` | `timestamp with time zone` | ✗ | now() |
| `metadata` | `jsonb` | ✓ | '{}'::jsonb |
| `deleted_at` | `timestamp with time zone` | ✓ | - |

**Foreign Keys:**
- `doctor_id` → `users.id`

**LGPD Compliance (Migrations 020, 024, 025, 028):**
- `cpf_encrypted`: AES-256-GCM encrypted CPF (Migration 020)
- `cpf_hash`: SHA-256 hash for searchable queries without decryption
- `email_encrypted`: AES-256-GCM encrypted email (Migration 028)
- `email_hash`: HMAC-SHA256 hash for email search
- `phone_encrypted`: AES-256-GCM encrypted phone (Migration 028)
- `phone_hash`: HMAC-SHA256 hash for phone search
- `idempotency_key`: Unique key for request deduplication (Migration 025)
- Original plaintext `cpf` column removed in Migration 024

**Indexes:** 26

---

### `users`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `email` | `character varying(255)` | ✗ | - |
| `hashed_password` | `character varying(255)` | ✓ | - |
| `full_name` | `character varying(255)` | ✓ | - |
| `role` | `user_role` | ✗ | 'doctor'::user_role |
| `is_active` | `boolean` | ✗ | true |
| `firebase_uid` | `character varying(255)` | ✓ | - |
| `auth_provider` | `auth_provider` | ✗ | 'local'::auth_provider |
| `firebase_last_sign_in` | `timestamp with time zone` | ✓ | - |
| `firebase_created_at` | `timestamp with time zone` | ✓ | - |
| `firebase_email_verified` | `boolean` | ✗ | false |
| `firebase_display_name` | `character varying(255)` | ✓ | - |
| `firebase_photo_url` | `character varying(500)` | ✓ | - |
| `firebase_custom_claims` | `jsonb` | ✗ | '{}'::jsonb |
| `last_firebase_sync` | `timestamp with time zone` | ✓ | - |
| `permissions` | `jsonb` | ✗ | '[]'::jsonb |
| `created_at` | `timestamp with time zone` | ✗ | now() |
| `updated_at` | `timestamp with time zone` | ✗ | now() |

**RBAC:**
- `permissions`: Granular permission array (e.g., `["patients:read", "patients:write"]`) (Migration 023)

**Indexes:** 10

---

### `user_profiles`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `user_id` | `uuid` | ✗ | - |
| `bio` | `text` | ✓ | - |
| `avatar_url` | `character varying(500)` | ✓ | - |
| `phone` | `character varying(20)` | ✓ | - |
| `specialty` | `character varying(255)` | ✓ | - |
| `license_number` | `character varying(100)` | ✓ | - |
| `years_of_experience` | `integer` | ✓ | - |
| `preferences` | `jsonb` | ✓ | '{}'::jsonb |
| `notification_settings` | `jsonb` | ✓ | '{}'::jsonb |
| `created_at` | `timestamp with time zone` | ✓ | now() |
| `updated_at` | `timestamp with time zone` | ✓ | now() |

**Foreign Keys:**
- `user_id` → `users.id`

**Indexes:** 3

---

### `contacts`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `name` | `character varying(255)` | ✗ | - |
| `email` | `character varying(255)` | ✓ | - |
| `phone` | `character varying(20)` | ✓ | - |
| `contact_type` | `character varying(50)` | ✓ | - |
| `related_patient_id` | `uuid` | ✓ | - |
| `related_user_id` | `uuid` | ✓ | - |
| `notes` | `text` | ✓ | - |
| `tags` | `ARRAY` | ✓ | - |
| `contact_metadata` | `jsonb` | ✓ | '{}'::jsonb |
| `created_at` | `timestamp with time zone` | ✓ | now() |
| `updated_at` | `timestamp with time zone` | ✓ | now() |

**Foreign Keys:**
- `related_patient_id` → `patients.id`
- `related_user_id` → `users.id`

**Indexes:** 4

---

## Admin & Security

### `admin_users`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `email` | `character varying(255)` | ✗ | - |
| `password_hash` | `character varying(255)` | ✗ | - |
| `first_name` | `character varying(100)` | ✗ | - |
| `last_name` | `character varying(100)` | ✗ | - |
| `role` | `admin_role_type` | ✗ | 'supervisor'::admin_role_type |
| `department` | `character varying(100)` | ✓ | - |
| `phone_number` | `character varying(20)` | ✓ | - |
| `is_active` | `boolean` | ✓ | true |
| `email_verified` | `boolean` | ✓ | false |
| `two_factor_enabled` | `boolean` | ✓ | false |
| `two_factor_secret` | `character varying(255)` | ✓ | - |
| `must_change_password` | `boolean` | ✓ | true |
| `failed_login_attempts` | `integer` | ✓ | 0 |
| `locked_until` | `timestamp with time zone` | ✓ | - |
| `last_login_at` | `timestamp with time zone` | ✓ | - |
| `last_login_ip` | `inet` | ✓ | - |
| `last_password_change` | `timestamp with time zone` | ✓ | CURRENT_TIMESTAMP |
| `max_concurrent_sessions` | `integer` | ✓ | 3 |
| `created_at` | `timestamp with time zone` | ✓ | CURRENT_TIMESTAMP |
| `updated_at` | `timestamp with time zone` | ✓ | CURRENT_TIMESTAMP |
| `created_by` | `uuid` | ✓ | - |
| `updated_by` | `uuid` | ✓ | - |
| `metadata` | `jsonb` | ✓ | '{}'::jsonb |

**Foreign Keys:**
- `updated_by` → `admin_users.id`
- `created_by` → `admin_users.id`

**Indexes:** 7

---

### `admin_roles`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `name` | `character varying(50)` | ✗ | - |
| `description` | `text` | ✓ | - |
| `is_system_role` | `boolean` | ✓ | false |
| `created_at` | `timestamp with time zone` | ✓ | CURRENT_TIMESTAMP |
| `updated_at` | `timestamp with time zone` | ✓ | CURRENT_TIMESTAMP |

**Indexes:** 2

---

### `admin_permissions`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `name` | `character varying(100)` | ✗ | - |
| `description` | `text` | ✓ | - |
| `category` | `character varying(50)` | ✗ | - |
| `created_at` | `timestamp with time zone` | ✓ | CURRENT_TIMESTAMP |

**Indexes:** 3

---

### `admin_role_permissions`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `role_id` | `uuid` | ✗ | - |
| `permission_id` | `uuid` | ✗ | - |
| `created_at` | `timestamp with time zone` | ✓ | CURRENT_TIMESTAMP |

**Foreign Keys:**
- `permission_id` → `admin_permissions.id`
- `role_id` → `admin_roles.id`

**Indexes:** 2

---

### `admin_user_permissions`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `admin_user_id` | `uuid` | ✗ | - |
| `permission_id` | `uuid` | ✗ | - |
| `granted_at` | `timestamp with time zone` | ✓ | CURRENT_TIMESTAMP |
| `granted_by` | `uuid` | ✓ | - |

**Foreign Keys:**
- `granted_by` → `admin_users.id`
- `permission_id` → `admin_permissions.id`
- `admin_user_id` → `admin_users.id`

**Indexes:** 2

---

### `admin_sessions`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `admin_user_id` | `uuid` | ✗ | - |
| `session_token` | `character varying(255)` | ✗ | - |
| `refresh_token` | `character varying(255)` | ✓ | - |
| `ip_address` | `inet` | ✓ | - |
| `user_agent` | `text` | ✓ | - |
| `device_fingerprint` | `character varying(255)` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✓ | CURRENT_TIMESTAMP |
| `last_activity` | `timestamp with time zone` | ✓ | CURRENT_TIMESTAMP |
| `expires_at` | `timestamp with time zone` | ✗ | - |
| `is_active` | `boolean` | ✓ | true |
| `logout_reason` | `character varying(100)` | ✓ | - |
| `metadata` | `jsonb` | ✓ | '{}'::jsonb |

**Foreign Keys:**
- `admin_user_id` → `admin_users.id`

**Indexes:** 8

---

### `admin_audit_log`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `admin_user_id` | `uuid` | ✓ | - |
| `session_id` | `uuid` | ✓ | - |
| `event_type` | `character varying(100)` | ✗ | - |
| `event_category` | `character varying(50)` | ✗ | - |
| `action` | `character varying(255)` | ✗ | - |
| `resource_type` | `character varying(100)` | ✓ | - |
| `resource_id` | `character varying(255)` | ✓ | - |
| `ip_address` | `inet` | ✓ | - |
| `user_agent` | `text` | ✓ | - |
| `endpoint` | `character varying(500)` | ✓ | - |
| `http_method` | `http_method_type` | ✓ | - |
| `details` | `jsonb` | ✓ | '{}'::jsonb |
| `changes` | `jsonb` | ✓ | - |
| `success` | `boolean` | ✓ | true |
| `error_message` | `text` | ✓ | - |
| `timestamp` | `timestamp with time zone` | ✓ | CURRENT_TIMESTAMP |
| `duration_ms` | `integer` | ✓ | - |
| `severity` | `severity_type` | ✓ | 'low'::severity_type |

**Foreign Keys:**
- `admin_user_id` → `admin_users.id`
- `session_id` → `admin_sessions.id`

**Indexes:** 7

---

### `admin_security_events`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `event_type` | `character varying(100)` | ✗ | - |
| `severity` | `severity_type` | ✗ | 'medium'::severity_type |
| `ip_address` | `inet` | ✓ | - |
| `user_agent` | `text` | ✓ | - |
| `admin_user_id` | `uuid` | ✓ | - |
| `session_id` | `uuid` | ✓ | - |
| `description` | `text` | ✓ | - |
| `details` | `jsonb` | ✓ | '{}'::jsonb |
| `endpoint` | `character varying(500)` | ✓ | - |
| `detected_at` | `timestamp with time zone` | ✓ | CURRENT_TIMESTAMP |
| `resolved_at` | `timestamp with time zone` | ✓ | - |
| `resolution_notes` | `text` | ✓ | - |
| `auto_resolved` | `boolean` | ✓ | false |
| `risk_score` | `integer` | ✓ | 0 |
| `threat_level` | `severity_type` | ✓ | 'low'::severity_type |

**Foreign Keys:**
- `admin_user_id` → `admin_users.id`
- `session_id` → `admin_sessions.id`

**Indexes:** 6

---

### `admin_ip_whitelist`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `ip_address` | `inet` | ✓ | - |
| `ip_range` | `cidr` | ✓ | - |
| `description` | `text` | ✓ | - |
| `added_by` | `uuid` | ✓ | - |
| `added_at` | `timestamp with time zone` | ✓ | CURRENT_TIMESTAMP |
| `is_active` | `boolean` | ✓ | true |
| `expires_at` | `timestamp with time zone` | ✓ | - |
| `last_used_at` | `timestamp with time zone` | ✓ | - |
| `usage_count` | `integer` | ✓ | 0 |

**Foreign Keys:**
- `added_by` → `admin_users.id`

**Indexes:** 4

---

### `admin_ip_blacklist`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `ip_address` | `inet` | ✗ | - |
| `reason` | `character varying(255)` | ✗ | - |
| `blocked_at` | `timestamp with time zone` | ✓ | CURRENT_TIMESTAMP |
| `blocked_by` | `uuid` | ✓ | - |
| `expires_at` | `timestamp with time zone` | ✓ | - |
| `is_permanent` | `boolean` | ✓ | false |
| `incident_id` | `uuid` | ✓ | - |
| `threat_level` | `severity_type` | ✓ | 'medium'::severity_type |
| `block_count` | `integer` | ✓ | 1 |
| `details` | `jsonb` | ✓ | '{}'::jsonb |
| `notes` | `text` | ✓ | - |

**Foreign Keys:**
- `blocked_by` → `admin_users.id`

**Indexes:** 3

---

## Messaging

### `messages`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `patient_id` | `uuid` | ✗ | - |
| `direction` | `message_direction` | ✗ | - |
| `type` | `message_type` | ✗ | 'text'::message_type |
| `content` | `text` | ✓ | - |
| `message_metadata` | `jsonb` | ✓ | '{}'::jsonb |
| `whatsapp_id` | `character varying(255)` | ✓ | - |
| `status` | `message_status` | ✗ | 'pending'::message_status |
| `scheduled_for` | `timestamp with time zone` | ✓ | - |
| `sent_at` | `timestamp with time zone` | ✓ | - |
| `delivered_at` | `timestamp with time zone` | ✓ | - |
| `read_at` | `timestamp with time zone` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✗ | now() |
| `updated_at` | `timestamp with time zone` | ✗ | now() |
| `delivery_status` | `deliverystatus` | ✓ | - |
| `retry_count` | `integer` | ✗ | 0 |
| `last_retry_at` | `timestamp with time zone` | ✓ | - |
| `failure_reason` | `text` | ✓ | - |
| `next_retry_at` | `timestamp with time zone` | ✓ | - |
| `idempotency_key` | `character varying(255)` | ✗ | - |
| `priority` | `message_priority` | ✗ | 'normal'::message_priority |

**Foreign Keys:**
- `patient_id` → `patients.id`

**Indexes:** 21

---

### `message_templates`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `name` | `character varying` | ✗ | - |
| `content` | `text` | ✗ | - |
| `variables` | `jsonb` | ✓ | - |
| `message_type` | `character varying` | ✗ | - |
| `media_url` | `character varying` | ✓ | - |
| `is_active` | `boolean` | ✗ | - |
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `created_at` | `timestamp with time zone` | ✗ | now() |
| `updated_at` | `timestamp with time zone` | ✗ | now() |

**Indexes:** 2

---

### `message_status_events`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `message_id` | `uuid` | ✗ | - |
| `status` | `character varying(50)` | ✗ | - |
| `previous_status` | `character varying(50)` | ✓ | - |
| `whatsapp_id` | `character varying(255)` | ✓ | - |
| `whatsapp_timestamp` | `timestamp with time zone` | ✓ | - |
| `error_code` | `character varying(50)` | ✓ | - |
| `error_message` | `text` | ✓ | - |
| `retry_count` | `integer` | ✓ | 0 |
| `metadata` | `jsonb` | ✓ | '{}'::jsonb |
| `evolution_event_type` | `character varying(100)` | ✓ | - |
| `evolution_payload` | `jsonb` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✗ | now() |

**Foreign Keys:**
- `message_id` → `messages.id`

**Indexes:** 5

---

### `notifications`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `user_id` | `uuid` | ✗ | - |
| `related_patient_id` | `uuid` | ✓ | - |
| `notification_type` | `character varying(50)` | ✗ | - |
| `priority` | `character varying(50)` | ✗ | 'medium'::character varying |
| `title` | `character varying(200)` | ✗ | - |
| `message` | `text` | ✗ | - |
| `action_url` | `character varying(500)` | ✓ | - |
| `action_label` | `character varying(100)` | ✓ | - |
| `notification_metadata` | `jsonb` | ✓ | - |
| `is_read` | `boolean` | ✗ | false |
| `read_at` | `timestamp with time zone` | ✓ | - |
| `is_archived` | `boolean` | ✗ | false |
| `archived_at` | `timestamp with time zone` | ✓ | - |
| `expires_at` | `timestamp with time zone` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✗ | CURRENT_TIMESTAMP |
| `updated_at` | `timestamp with time zone` | ✗ | CURRENT_TIMESTAMP |

**Foreign Keys:**
- `user_id` → `users.id`
- `related_patient_id` → `patients.id`

**Indexes:** 9

---

## WhatsApp

### `whatsapp_instances`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `text` | ✗ | - |
| `name` | `text` | ✗ | - |
| `status` | `text` | ✓ | 'disconnected'::text |
| `qr_code` | `text` | ✓ | - |
| `webhook_url` | `text` | ✓ | - |
| `phone_number` | `text` | ✓ | - |
| `profile_name` | `text` | ✓ | - |
| `profile_picture_url` | `text` | ✓ | - |
| `is_connected` | `boolean` | ✓ | false |
| `created_at` | `timestamp without time zone` | ✓ | now() |
| `updated_at` | `timestamp without time zone` | ✓ | now() |
| `last_activity` | `timestamp without time zone` | ✓ | - |
| `settings` | `json` | ✓ | - |

**Indexes:** 3

---

### `whatsapp_messages`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `text` | ✗ | - |
| `instance_name` | `text` | ✗ | - |
| `chat_id` | `text` | ✗ | - |
| `sender_id` | `text` | ✗ | - |
| `recipient_id` | `text` | ✗ | - |
| `message_type` | `text` | ✗ | - |
| `content` | `text` | ✓ | - |
| `media_url` | `text` | ✓ | - |
| `media_caption` | `text` | ✓ | - |
| `status` | `text` | ✓ | 'pending'::text |
| `external_id` | `text` | ✓ | - |
| `created_at` | `timestamp without time zone` | ✓ | now() |
| `updated_at` | `timestamp without time zone` | ✓ | now() |
| `sent_at` | `timestamp without time zone` | ✓ | - |
| `delivered_at` | `timestamp without time zone` | ✓ | - |
| `read_at` | `timestamp without time zone` | ✓ | - |
| `failed_at` | `timestamp without time zone` | ✓ | - |
| `retry_count` | `integer` | ✓ | 0 |
| `error_message` | `text` | ✓ | - |
| `message_data` | `json` | ✓ | - |

**Indexes:** 5

---

### `whatsapp_contacts`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `text` | ✗ | - |
| `instance_name` | `text` | ✗ | - |
| `phone_number` | `text` | ✗ | - |
| `formatted_number` | `text` | ✗ | - |
| `name` | `text` | ✓ | - |
| `profile_picture_url` | `text` | ✓ | - |
| `is_whatsapp_user` | `boolean` | ✓ | true |
| `last_seen` | `timestamp without time zone` | ✓ | - |
| `created_at` | `timestamp without time zone` | ✓ | now() |
| `updated_at` | `timestamp without time zone` | ✓ | now() |
| `contact_data` | `json` | ✓ | - |

**Indexes:** 3

---

### `whatsapp_delivery_failures`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `patient_id` | `uuid` | ✗ | - |
| `phone_number` | `character varying(20)` | ✗ | - |
| `message_type` | `character varying(50)` | ✗ | - |
| `message_content` | `text` | ✓ | - |
| `error_message` | `text` | ✗ | - |
| `error_code` | `character varying(50)` | ✓ | - |
| `retry_count` | `integer` | ✗ | 0 |
| `max_retries` | `integer` | ✗ | 3 |
| `next_retry_at` | `timestamp with time zone` | ✓ | - |
| `last_retry_at` | `timestamp with time zone` | ✓ | - |
| `status` | `character varying(20)` | ✗ | 'pending'::character varying |
| `resolved_at` | `timestamp with time zone` | ✓ | - |
| `dlq_metadata` | `jsonb` | ✓ | '{}'::jsonb |
| `reviewed_by` | `uuid` | ✓ | - |
| `original_message_id` | `uuid` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✗ | timezone('utc'::text, now()) |
| `updated_at` | `timestamp with time zone` | ✗ | timezone('utc'::text, now()) |

**Foreign Keys:**
- `original_message_id` → `messages.id`
- `patient_id` → `patients.id`
- `reviewed_by` → `users.id`

**Indexes:** 4

---

### `webhook_events`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `event_type` | `character varying(100)` | ✗ | - |
| `source` | `character varying(100)` | ✗ | 'evolution_api'::character var... |
| `payload` | `jsonb` | ✗ | - |
| `processed` | `boolean` | ✗ | false |
| `processed_at` | `timestamp with time zone` | ✓ | - |
| `retry_count` | `integer` | ✓ | 0 |
| `max_retries` | `integer` | ✓ | 3 |
| `next_retry_at` | `timestamp with time zone` | ✓ | - |
| `error_message` | `text` | ✓ | - |
| `error_stack_trace` | `text` | ✓ | - |
| `related_message_id` | `uuid` | ✓ | - |
| `related_patient_id` | `uuid` | ✓ | - |
| `event_hash` | `character varying(64)` | ✗ | - |
| `is_duplicate` | `boolean` | ✓ | false |
| `original_event_id` | `uuid` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✗ | now() |

**Indexes:** 9

---

## Flows

### `flow_states`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `patient_id` | `uuid` | ✗ | - |
| `flow_type` | `character varying(50)` | ✗ | - |
| `current_step` | `integer` | ✗ | 0 |
| `started_at` | `timestamp with time zone` | ✗ | - |
| `completed_at` | `timestamp with time zone` | ✓ | - |
| `state_data` | `jsonb` | ✓ | '{}'::jsonb |
| `created_at` | `timestamp with time zone` | ✗ | now() |
| `updated_at` | `timestamp with time zone` | ✗ | now() |

**Foreign Keys:**
- `patient_id` → `patients.id`

**Indexes:** 3

---

### `flow_messages`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `flow_template_version_id` | `uuid` | ✗ | - |
| `step_number` | `integer` | ✗ | - |
| `message_key` | `character varying(100)` | ✗ | - |
| `message_text` | `text` | ✗ | - |
| `message_type` | `character varying(50)` | ✓ | 'text'::character varying |
| `buttons` | `jsonb` | ✓ | - |
| `list_items` | `jsonb` | ✓ | - |
| `conditions` | `jsonb` | ✓ | - |
| `delay_seconds` | `integer` | ✓ | 0 |
| `created_at` | `timestamp with time zone` | ✓ | now() |

**Foreign Keys:**
- `flow_template_version_id` → `flow_template_versions.id`

**Indexes:** 6

---

### `flow_analytics`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `flow_template_version_id` | `uuid` | ✓ | - |
| `patient_id` | `uuid` | ✓ | - |
| `total_steps` | `integer` | ✓ | - |
| `completed_steps` | `integer` | ✓ | - |
| `success_rate` | `numeric` | ✓ | - |
| `avg_response_time_seconds` | `integer` | ✓ | - |
| `step_analytics` | `jsonb` | ✓ | - |
| `interaction_patterns` | `jsonb` | ✓ | - |
| `period_start` | `timestamp with time zone` | ✓ | - |
| `period_end` | `timestamp with time zone` | ✓ | - |
| `calculated_at` | `timestamp with time zone` | ✓ | now() |

**Foreign Keys:**
- `flow_template_version_id` → `flow_template_versions.id`
- `patient_id` → `patients.id`

**Indexes:** 6

---

### `flow_kinds`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `kind_key` | `character varying(50)` | ✗ | - |
| `display_name` | `character varying(255)` | ✗ | - |
| `description` | `text` | ✓ | - |
| `is_active` | `boolean` | ✓ | true |
| `created_at` | `timestamp with time zone` | ✓ | now() |
| `updated_at` | `timestamp with time zone` | ✓ | now() |

**Indexes:** 4

---

### `patient_flow_states`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `patient_id` | `uuid` | ✗ | - |
| `flow_template_version_id` | `uuid` | ✗ | - |
| `current_step` | `integer` | ✓ | 0 |
| `step_data` | `jsonb` | ✓ | '{}'::jsonb |
| `status` | `character varying(50)` | ✓ | 'active'::character varying |
| `started_at` | `timestamp with time zone` | ✓ | now() |
| `last_interaction_at` | `timestamp with time zone` | ✓ | now() |
| `completed_at` | `timestamp with time zone` | ✓ | - |
| `next_scheduled_at` | `timestamp with time zone` | ✓ | - |
| `flow_metadata` | `jsonb` | ✓ | '{}'::jsonb |
| `created_at` | `timestamp with time zone` | ✓ | now() |
| `updated_at` | `timestamp with time zone` | ✓ | now() |
| `version` | `integer` | ✗ | 0 |

**Foreign Keys:**
- `flow_template_version_id` → `flow_template_versions.id`
- `patient_id` → `patients.id`

**Indexes:** 11

---

### `flow_template_categories`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `category_key` | `character varying(50)` | ✗ | - |
| `display_name` | `character varying(255)` | ✗ | - |
| `description` | `text` | ✓ | - |
| `icon` | `character varying(100)` | ✓ | - |
| `sort_order` | `integer` | ✓ | 0 |
| `is_active` | `boolean` | ✓ | true |
| `created_at` | `timestamp with time zone` | ✓ | now() |

**Indexes:** 2

---

### `flow_template_shares`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `flow_template_version_id` | `uuid` | ✗ | - |
| `shared_by` | `uuid` | ✗ | - |
| `shared_with` | `uuid` | ✓ | - |
| `can_view` | `boolean` | ✓ | true |
| `can_edit` | `boolean` | ✓ | false |
| `can_reshare` | `boolean` | ✓ | false |
| `share_notes` | `text` | ✓ | - |
| `shared_at` | `timestamp with time zone` | ✓ | now() |
| `expires_at` | `timestamp with time zone` | ✓ | - |

**Foreign Keys:**
- `shared_by` → `users.id`
- `shared_with` → `users.id`
- `flow_template_version_id` → `flow_template_versions.id`

**Indexes:** 2

---

### `flow_template_stats`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `flow_template_version_id` | `uuid` | ✗ | - |
| `total_uses` | `integer` | ✓ | 0 |
| `active_instances` | `integer` | ✓ | 0 |
| `completed_instances` | `integer` | ✓ | 0 |
| `avg_completion_rate` | `numeric` | ✓ | - |
| `avg_duration_hours` | `numeric` | ✓ | - |
| `avg_rating` | `numeric` | ✓ | - |
| `total_ratings` | `integer` | ✓ | 0 |
| `last_calculated_at` | `timestamp with time zone` | ✓ | now() |

**Foreign Keys:**
- `flow_template_version_id` → `flow_template_versions.id`

**Indexes:** 2

---

### `flow_template_versions`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `flow_kind_id` | `uuid` | ✗ | - |
| `version_number` | `integer` | ✗ | - |
| `template_name` | `character varying(255)` | ✗ | - |
| `description` | `text` | ✓ | - |
| `steps` | `jsonb` | ✗ | - |
| `metadata` | `jsonb` | ✓ | '{}'::jsonb |
| `is_active` | `boolean` | ✓ | false |
| `is_draft` | `boolean` | ✓ | true |
| `published_at` | `timestamp with time zone` | ✓ | - |
| `deprecated_at` | `timestamp with time zone` | ✓ | - |
| `created_by` | `uuid` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✓ | now() |
| `updated_at` | `timestamp with time zone` | ✓ | now() |

**Foreign Keys:**
- `created_by` → `users.id`
- `flow_kind_id` → `flow_kinds.id`

**Indexes:** 5

---

## Quiz

### `quiz_templates`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `name` | `character varying(255)` | ✗ | - |
| `version` | `character varying(50)` | ✗ | - |
| `description` | `text` | ✓ | - |
| `questions` | `jsonb` | ✗ | - |
| `is_active` | `boolean` | ✗ | true |
| `category` | `character varying(100)` | ✓ | - |
| `tags` | `ARRAY` | ✓ | - |
| `passing_score` | `integer` | ✓ | - |
| `time_limit_minutes` | `integer` | ✓ | - |
| `randomize_questions` | `boolean` | ✓ | false |
| `created_at` | `timestamp with time zone` | ✗ | now() |
| `updated_at` | `timestamp with time zone` | ✗ | now() |

**Indexes:** 3

---

### `quiz_sessions`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `patient_id` | `uuid` | ✗ | - |
| `quiz_template_id` | `uuid` | ✗ | - |
| `status` | `character varying(50)` | ✗ | 'started'::character varying |
| `current_question` | `integer` | ✓ | 0 |
| `total_questions` | `integer` | ✓ | - |
| `answered_questions` | `integer` | ✓ | 0 |
| `score` | `numeric` | ✓ | - |
| `max_score` | `numeric` | ✓ | - |
| `passed` | `boolean` | ✓ | - |
| `started_at` | `timestamp with time zone` | ✗ | now() |
| `completed_at` | `timestamp with time zone` | ✓ | - |
| `time_spent_seconds` | `integer` | ✓ | - |
| `session_metadata` | `jsonb` | ✓ | '{}'::jsonb |
| `created_at` | `timestamp with time zone` | ✗ | now() |
| `updated_at` | `timestamp with time zone` | ✗ | now() |

**Foreign Keys:**
- `quiz_template_id` → `quiz_templates.id`
- `patient_id` → `patients.id`

**Indexes:** 16

---

### `quiz_responses`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `patient_id` | `uuid` | ✗ | - |
| `quiz_template_id` | `uuid` | ✗ | - |
| `quiz_session_id` | `uuid` | ✓ | - |
| `question_id` | `character varying(100)` | ✗ | - |
| `question_text` | `text` | ✗ | - |
| `response_type` | `character varying(50)` | ✗ | - |
| `response_value_text_backup` | `text` | ✗ | - |
| `is_correct` | `boolean` | ✓ | - |
| `points_earned` | `numeric` | ✓ | - |
| `response_metadata` | `jsonb` | ✓ | '{}'::jsonb |
| `responded_at` | `timestamp with time zone` | ✗ | - |
| `response_time_seconds` | `integer` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✗ | now() |
| `updated_at` | `timestamp with time zone` | ✗ | now() |
| `other_text` | `text` | ✓ | - |
| `response_value` | `jsonb` | ✓ | - |

**Foreign Keys:**
- `patient_id` → `patients.id`
- `quiz_session_id` → `quiz_sessions.id`
- `quiz_template_id` → `quiz_templates.id`

**Indexes:** 14

---

### `quiz_sessions_v2`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `patient_id` | `uuid` | ✗ | - |
| `template_version_id` | `uuid` | ✗ | - |
| `status` | `character varying(50)` | ✓ | 'started'::character varying |
| `started_at` | `timestamp with time zone` | ✓ | now() |
| `completed_at` | `timestamp with time zone` | ✓ | - |
| `session_data` | `jsonb` | ✓ | '{}'::jsonb |
| `created_at` | `timestamp with time zone` | ✓ | now() |

**Foreign Keys:**
- `template_version_id` → `quiz_template_versions_v2.id`
- `patient_id` → `patients.id`

**Indexes:** 3

---

### `quiz_template_versions_v2`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `template_id` | `uuid` | ✗ | - |
| `version_number` | `integer` | ✗ | - |
| `questions` | `jsonb` | ✗ | - |
| `scoring_rules` | `jsonb` | ✓ | - |
| `is_active` | `boolean` | ✓ | false |
| `is_draft` | `boolean` | ✓ | true |
| `published_at` | `timestamp with time zone` | ✓ | - |
| `created_by` | `uuid` | ✓ | - |
| `change_notes` | `text` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✓ | now() |

**Foreign Keys:**
- `template_id` → `quiz_templates.id`
- `created_by` → `users.id`

**Indexes:** 4

---

### `quiz_response_migration_log`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `quiz_response_id` | `uuid` | ✗ | - |
| `original_value` | `text` | ✓ | - |
| `converted_value` | `jsonb` | ✓ | - |
| `conversion_status` | `text` | ✗ | - |
| `error_message` | `text` | ✓ | - |
| `migrated_at` | `timestamp with time zone` | ✗ | now() |

**Indexes:** 3

---

## Medical

### `medical_reports`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `patient_id` | `uuid` | ✗ | - |
| `generated_by` | `uuid` | ✗ | - |
| `period_start` | `date` | ✗ | - |
| `period_end` | `date` | ✗ | - |
| `summary` | `text` | ✓ | - |
| `insights` | `jsonb` | ✓ | '{}'::jsonb |
| `charts_data` | `jsonb` | ✓ | '{}'::jsonb |
| `alerts` | `jsonb` | ✓ | '{}'::jsonb |
| `report_type` | `character varying(50)` | ✓ | - |
| `report_metadata` | `jsonb` | ✓ | '{}'::jsonb |
| `created_at` | `timestamp with time zone` | ✗ | now() |
| `updated_at` | `timestamp with time zone` | ✗ | now() |

**Foreign Keys:**
- `generated_by` → `users.id`
- `patient_id` → `patients.id`

**Indexes:** 5

---

### `appointments`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `patient_id` | `uuid` | ✗ | - |
| `doctor_id` | `uuid` | ✗ | - |
| `appointment_type` | `character varying(100)` | ✗ | - |
| `status` | `character varying(50)` | ✓ | 'scheduled'::character varying |
| `scheduled_at` | `timestamp with time zone` | ✗ | - |
| `duration_minutes` | `integer` | ✓ | 60 |
| `completed_at` | `timestamp with time zone` | ✓ | - |
| `cancelled_at` | `timestamp with time zone` | ✓ | - |
| `pre_appointment_notes` | `text` | ✓ | - |
| `post_appointment_notes` | `text` | ✓ | - |
| `appointment_metadata` | `jsonb` | ✓ | '{}'::jsonb |
| `created_at` | `timestamp with time zone` | ✓ | now() |
| `updated_at` | `timestamp with time zone` | ✓ | now() |

**Foreign Keys:**
- `doctor_id` → `users.id`
- `patient_id` → `patients.id`

**Indexes:** 5

---

### `alerts`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `patient_id` | `uuid` | ✗ | - |
| `type` | `character varying(100)` | ✗ | - |
| `severity` | `alert_severity` | ✗ | - |
| `message` | `text` | ✗ | - |
| `data` | `jsonb` | ✓ | '{}'::jsonb |
| `acknowledged` | `boolean` | ✗ | false |
| `acknowledged_by` | `uuid` | ✓ | - |
| `acknowledged_at` | `timestamp with time zone` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✗ | now() |
| `updated_at` | `timestamp with time zone` | ✗ | now() |

**Foreign Keys:**
- `patient_id` → `patients.id`
- `acknowledged_by` → `users.id`

**Indexes:** 8

---

### `patient_summaries`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `patient_id` | `uuid` | ✗ | - |
| `generated_by` | `uuid` | ✓ | - |
| `start_date` | `date` | ✗ | - |
| `end_date` | `date` | ✗ | - |
| `content` | `jsonb` | ✗ | '{}'::jsonb |
| `pdf_data` | `bytea` | ✓ | - |
| `token_usage` | `integer` | ✓ | - |
| `model_used` | `character varying(100)` | ✓ | 'gemini-2.5-flash-latest' |
| `generation_time_ms` | `integer` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✗ | now() |
| `updated_at` | `timestamp with time zone` | ✗ | now() |

**Foreign Keys:**
- `patient_id` → `patients.id`
- `generated_by` → `users.id`

**Description:**
AI-generated medical summaries for patients covering specific date ranges. Stores both structured JSON content and optional PDF export data.

**Indexes:** 3

---

## Audit & Logging

### `audit_logs`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `event_type` | `character varying(50)` | ✗ | - |
| `event_status` | `character varying(20)` | ✗ | 'success'::character varying |
| `user_id` | `uuid` | ✓ | - |
| `user_email` | `character varying(255)` | ✓ | - |
| `firebase_uid` | `character varying(255)` | ✓ | - |
| `ip_address` | `inet` | ✓ | - |
| `user_agent` | `character varying(500)` | ✓ | - |
| `resource` | `character varying(255)` | ✓ | - |
| `action` | `character varying(100)` | ✓ | - |
| `event_metadata` | `jsonb` | ✓ | '{}'::jsonb |
| `message` | `character varying(500)` | ✓ | - |
| `error_details` | `character varying(1000)` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✗ | now() |
| `updated_at` | `timestamp with time zone` | ✗ | now() |
| `session_id` | `character varying(255)` | ✓ | - |
| `session_token_hash` | `character varying(64)` | ✓ | - |
| `device_fingerprint` | `character varying(64)` | ✓ | - |
| `geolocation` | `jsonb` | ✓ | - |
| `user_role` | `character varying(50)` | ✓ | - |
| `event_category` | `character varying(50)` | ✓ | - |
| `resource_type` | `character varying(50)` | ✓ | - |
| `resource_id` | `uuid` | ✓ | - |
| `resource_identifiers` | `jsonb` | ✓ | - |
| `operation` | `character varying(20)` | ✓ | - |
| `http_method` | `character varying(10)` | ✓ | - |
| `endpoint` | `character varying(500)` | ✓ | - |
| `changes_before` | `jsonb` | ✓ | - |
| `changes_after` | `jsonb` | ✓ | - |
| `changed_fields` | `ARRAY` | ✓ | - |
| `description` | `text` | ✓ | - |
| `query_params` | `jsonb` | ✓ | - |
| `request_body_hash` | `character varying(64)` | ✓ | - |
| `status` | `character varying(20)` | ✓ | 'SUCCESS'::character varying |
| `http_status_code` | `integer` | ✓ | - |
| `error_code` | `character varying(50)` | ✓ | - |
| `error_stack_trace` | `text` | ✓ | - |
| `duration_ms` | `integer` | ✓ | - |
| `checksum` | `character varying(64)` | ✓ | - |
| `previous_checksum` | `character varying(64)` | ✓ | - |
| `integrity_verified` | `boolean` | ✓ | true |
| `reviewed` | `boolean` | ✓ | false |
| `reviewed_at` | `timestamp with time zone` | ✓ | - |
| `reviewed_by` | `uuid` | ✓ | - |
| `review_notes` | `text` | ✓ | - |
| `is_anomalous` | `boolean` | ✓ | false |
| `anomaly_score` | `numeric` | ✓ | - |
| `anomaly_reasons` | `ARRAY` | ✓ | - |
| `alert_generated` | `boolean` | ✓ | false |
| `alert_sent_at` | `timestamp with time zone` | ✓ | - |
| `alert_recipients` | `ARRAY` | ✓ | - |
| `retention_period_years` | `integer` | ✓ | 6 |
| `archive_eligible_at` | `timestamp with time zone` | ✓ | - |
| `archived` | `boolean` | ✓ | false |
| `archived_at` | `timestamp with time zone` | ✓ | - |
| `archive_location` | `character varying(500)` | ✓ | - |

**Foreign Keys:**
- `user_id` → `users.id`

**Indexes:** 27

---

### `audit_trail`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `table_name` | `character varying(255)` | ✗ | - |
| `record_id` | `uuid` | ✗ | - |
| `operation` | `character varying(50)` | ✗ | - |
| `old_data` | `jsonb` | ✓ | - |
| `new_data` | `jsonb` | ✓ | - |
| `changes` | `jsonb` | ✓ | - |
| `actor_id` | `uuid` | ✓ | - |
| `actor_type` | `character varying(50)` | ✓ | - |
| `actor_subject` | `character varying(255)` | ✓ | - |
| `ip_address` | `inet` | ✓ | - |
| `user_agent` | `text` | ✓ | - |
| `endpoint` | `character varying(500)` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✓ | now() |

**Indexes:** 5

---

### `audit_log_entries`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `event_type` | `character varying(100)` | ✗ | - |
| `entity_type` | `character varying(100)` | ✓ | - |
| `entity_id` | `uuid` | ✓ | - |
| `user_id` | `uuid` | ✓ | - |
| `old_values` | `jsonb` | ✓ | - |
| `new_values` | `jsonb` | ✓ | - |
| `metadata` | `jsonb` | ✓ | '{}'::jsonb |
| `ip_address` | `inet` | ✓ | - |
| `user_agent` | `text` | ✓ | - |
| `timestamp` | `timestamp with time zone` | ✓ | now() |

**Indexes:** 4

---

### `security_audit_log`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `event_type` | `character varying(100)` | ✗ | - |
| `phone_number` | `character varying(20)` | ✗ | - |
| `patient_id` | `uuid` | ✓ | - |
| `message_content` | `text` | ✓ | - |
| `source_metadata` | `jsonb` | ✓ | - |
| `risk_score` | `integer` | ✗ | 0 |
| `ip_address` | `character varying(45)` | ✓ | - |
| `user_agent` | `character varying(500)` | ✓ | - |
| `session_id` | `character varying(32)` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✗ | CURRENT_TIMESTAMP |
| `additional_data` | `jsonb` | ✓ | - |
| `alert_sent` | `boolean` | ✗ | false |

**Foreign Keys:**
- `patient_id` → `patients.id`

**Indexes:** 12

---

### `error_logs`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `error_type` | `character varying(100)` | ✗ | - |
| `error_message` | `text` | ✗ | - |
| `stack_trace` | `text` | ✓ | - |
| `context` | `jsonb` | ✗ | '{}'::jsonb |
| `count` | `integer` | ✗ | 1 |
| `first_seen` | `timestamp with time zone` | ✗ | CURRENT_TIMESTAMP |
| `last_seen` | `timestamp with time zone` | ✗ | CURRENT_TIMESTAMP |
| `resolved` | `boolean` | ✗ | false |
| `severity` | `character varying(20)` | ✗ | 'ERROR'::character varying |
| `created_at` | `timestamp with time zone` | ✗ | CURRENT_TIMESTAMP |
| `updated_at` | `timestamp with time zone` | ✗ | CURRENT_TIMESTAMP |

**Indexes:** 12

---

## System

### `system_health_snapshots`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `status` | `healthstatus` | ✗ | - |
| `health_score` | `double precision` | ✗ | - |
| `services_status` | `jsonb` | ✗ | - |
| `metrics` | `jsonb` | ✗ | - |
| `created_at` | `timestamp with time zone` | ✓ | now() |
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `updated_at` | `timestamp with time zone` | ✗ | now() |

**Indexes:** 3

---

### `system_incidents`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `title` | `character varying(255)` | ✗ | - |
| `description` | `text` | ✓ | - |
| `severity` | `incidentseverity` | ✗ | - |
| `status` | `incidentstatus` | ✗ | - |
| `service_name` | `character varying(100)` | ✗ | - |
| `started_at` | `timestamp with time zone` | ✗ | - |
| `resolved_at` | `timestamp with time zone` | ✓ | - |
| `meta_data` | `jsonb` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✓ | now() |
| `updated_at` | `timestamp with time zone` | ✓ | now() |
| `id` | `uuid` | ✗ | gen_random_uuid() |

**Indexes:** 2

---

### `alembic_version`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `version_num` | `character varying(255)` | ✗ | - |

**Indexes:** 1

---

### `user_sync_log`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `firebase_uid` | `character varying(255)` | ✗ | - |
| `supabase_user_id` | `uuid` | ✓ | - |
| `sync_action` | `character varying(50)` | ✗ | - |
| `sync_status` | `character varying(50)` | ✗ | - |
| `firebase_data` | `jsonb` | ✓ | - |
| `supabase_data` | `jsonb` | ✓ | - |
| `error_message` | `text` | ✓ | - |
| `retry_count` | `integer` | ✓ | 0 |
| `synced_at` | `timestamp with time zone` | ✓ | now() |
| `created_at` | `timestamp with time zone` | ✓ | now() |
| `updated_at` | `timestamp with time zone` | ✗ | now() |

**Foreign Keys:**
- `supabase_user_id` → `users.id`

**Indexes:** 5

---

### `patient_onboarding_saga`

| Column | Type | Nullable | Default |
|--------|------|----------|--------|
| `id` | `uuid` | ✗ | gen_random_uuid() |
| `patient_id` | `uuid` | ✓ | - |
| `doctor_id` | `uuid` | ✗ | - |
| `status` | `saga_status` | ✗ | 'STARTED'::saga_status |
| `current_step` | `integer` | ✗ | 0 |
| `retry_count` | `integer` | ✗ | 0 |
| `max_retries` | `integer` | ✗ | 3 |
| `patient_data` | `jsonb` | ✗ | - |
| `execution_log` | `jsonb` | ✗ | '[]'::jsonb |
| `error_message` | `text` | ✓ | - |
| `error_type` | `character varying(255)` | ✓ | - |
| `next_retry_at` | `timestamp with time zone` | ✓ | - |
| `started_at` | `timestamp with time zone` | ✗ | now() |
| `completed_at` | `timestamp with time zone` | ✓ | - |
| `failed_at` | `timestamp with time zone` | ✓ | - |
| `created_at` | `timestamp with time zone` | ✗ | now() |
| `updated_at` | `timestamp with time zone` | ✗ | now() |
| `last_retry_at` | `timestamp with time zone` | ✓ | - |

**Foreign Keys:**
- `doctor_id` → `users.id`
- `patient_id` → `patients.id`

**Indexes:** 6

---

