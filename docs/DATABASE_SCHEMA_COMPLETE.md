# Database Schema Documentation - AWS RDS PostgreSQL

**Database:** postgres  
**Host:** database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com  
**Extracted:** 2025-10-24T19:37:47  
**Total Tables:** 48

---

## Table of Contents

1. [Admin & Security Tables](#admin--security-tables)
2. [Patient Management Tables](#patient-management-tables)
3. [Quiz & Assessment Tables](#quiz--assessment-tables)
4. [Flow Engine Tables](#flow-engine-tables)
5. [Messaging & Communication Tables](#messaging--communication-tables)
6. [Audit & Logging Tables](#audit--logging-tables)
7. [System Tables](#system-tables)

---

## Admin & Security Tables

### admin_users
**Purpose:** Administrative user accounts with role-based access control  
**Row Count:** 0  
**Primary Key:** id (UUID)

**Key Columns:**
- `id` - UUID, Primary Key
- `email` - VARCHAR, Unique
- `password_hash` - VARCHAR
- `name` - VARCHAR
- `is_active` - BOOLEAN (default: true)
- `is_super_admin` - BOOLEAN (default: false)
- `last_login_at` - TIMESTAMPTZ
- `created_at` - TIMESTAMPTZ
- `updated_at` - TIMESTAMPTZ

**Relationships:**
- Has many: admin_sessions, admin_audit_log, admin_security_events
- Belongs to: admin_roles (via admin_user_permissions)

---

### admin_roles
**Purpose:** Role definitions for RBAC system  
**Row Count:** 0  
**Primary Key:** id (UUID)

**Key Columns:**
- `id` - UUID, Primary Key
- `name` - VARCHAR(50), Unique
- `description` - TEXT
- `is_system_role` - BOOLEAN (default: false)
- `created_at` - TIMESTAMPTZ
- `updated_at` - TIMESTAMPTZ

**Constraints:**
- `valid_role_name` - Name must match pattern `^[a-z0-9_]+$`

---

### admin_permissions
**Purpose:** Granular permission definitions  
**Row Count:** 0  
**Primary Key:** id (UUID)

**Key Columns:**
- `id` - UUID, Primary Key
- `name` - VARCHAR(100), Unique
- `description` - TEXT
- `category` - VARCHAR(50)
- `created_at` - TIMESTAMPTZ

**Constraints:**
- `valid_permission_name` - Name must match pattern `^[a-z0-9_]+\.[a-z0-9_]+$`

**Indexes:**
- `idx_admin_permissions_category` on category

---

### admin_role_permissions
**Purpose:** Many-to-many relationship between roles and permissions  
**Row Count:** 0  
**Primary Key:** (role_id, permission_id)

**Foreign Keys:**
- `role_id` → admin_roles.id
- `permission_id` → admin_permissions.id

---

### admin_user_permissions
**Purpose:** Direct user permission assignments (overrides)  
**Row Count:** 0

**Foreign Keys:**
- `user_id` → admin_users.id
- `permission_id` → admin_permissions.id

---

### admin_sessions
**Purpose:** Active admin user sessions with security tracking  
**Row Count:** 0  
**Primary Key:** id (UUID)

**Key Columns:**
- `id` - UUID, Primary Key
- `admin_user_id` - UUID, Foreign Key
- `session_token` - VARCHAR(255), Unique
- `refresh_token` - VARCHAR(255)
- `ip_address` - INET
- `user_agent` - TEXT
- `device_fingerprint` - VARCHAR(255)
- `created_at` - TIMESTAMPTZ
- `expires_at` - TIMESTAMPTZ
- `last_activity_at` - TIMESTAMPTZ
- `is_active` - BOOLEAN

**Indexes:**
- `idx_admin_sessions_token` on session_token
- `idx_admin_sessions_user_id` on admin_user_id
- `idx_admin_sessions_active` on (admin_user_id, is_active, expires_at)

---

### admin_audit_log
**Purpose:** Comprehensive audit trail for all admin actions  
**Row Count:** 0  
**Primary Key:** id (UUID)

**Key Columns:**
- `id` - UUID, Primary Key
- `admin_user_id` - UUID, Foreign Key
- `session_id` - UUID, Foreign Key
- `event_type` - VARCHAR(100)
- `event_category` - VARCHAR(50)
- `action` - VARCHAR(255)
- `resource_type` - VARCHAR(100)
- `resource_id` - VARCHAR(255)
- `ip_address` - INET
- `user_agent` - TEXT
- `endpoint` - VARCHAR(500)
- `http_method` - ENUM (http_method_type)
- `details` - JSONB
- `changes` - JSONB
- `success` - BOOLEAN
- `error_message` - TEXT
- `timestamp` - TIMESTAMPTZ
- `duration_ms` - INTEGER
- `severity` - ENUM (severity_type)

**Indexes:**
- `idx_admin_audit_user_id` on admin_user_id
- `idx_admin_audit_timestamp` on timestamp
- `idx_admin_audit_event_type` on event_type
- `idx_admin_audit_resource` on (resource_type, resource_id)
- `idx_admin_audit_ip` on ip_address
- `idx_admin_audit_severity` on severity

---

### admin_security_events
**Purpose:** Security incident tracking and threat detection  
**Row Count:** 0  
**Primary Key:** id (UUID)

**Key Columns:**
- `id` - UUID, Primary Key
- `event_type` - VARCHAR(100)
- `severity` - ENUM (severity_type)
- `ip_address` - INET
- `user_agent` - TEXT
- `admin_user_id` - UUID, Foreign Key
- `session_id` - UUID, Foreign Key
- `description` - TEXT
- `details` - JSONB
- `endpoint` - VARCHAR(500)
- `detected_at` - TIMESTAMPTZ
- `resolved_at` - TIMESTAMPTZ
- `resolution_notes` - TEXT
- `auto_resolved` - BOOLEAN
- `risk_score` - INTEGER (0-100)
- `threat_level` - ENUM (severity_type)

**Constraints:**
- `valid_risk_score` - risk_score BETWEEN 0 AND 100

**Indexes:**
- `idx_security_events_user_id` on admin_user_id
- `idx_security_events_timestamp` on detected_at
- `idx_security_events_severity` on severity
- `idx_security_events_ip` on ip_address
- `idx_security_events_resolved` on resolved_at

---

### admin_ip_blacklist
**Purpose:** IP address blocking for security  
**Row Count:** 0  
**Primary Key:** id (UUID)

**Key Columns:**
- `id` - UUID, Primary Key
- `ip_address` - INET, Unique
- `reason` - VARCHAR(255)
- `blocked_at` - TIMESTAMPTZ
- `blocked_by` - UUID, Foreign Key
- `expires_at` - TIMESTAMPTZ
- `is_permanent` - BOOLEAN
- `incident_id` - UUID
- `threat_level` - ENUM (severity_type)
- `block_count` - INTEGER
- `details` - JSONB
- `notes` - TEXT

**Indexes:**
- `idx_ip_blacklist_active` on (ip_address, expires_at)

---

### admin_ip_whitelist
**Purpose:** Trusted IP addresses and ranges  
**Row Count:** 0  
**Primary Key:** id (UUID)

**Key Columns:**
- `id` - UUID, Primary Key
- `ip_address` - INET
- `ip_range` - CIDR
- `description` - TEXT
- `added_by` - UUID, Foreign Key
- `added_at` - TIMESTAMPTZ
- `is_active` - BOOLEAN
- `expires_at` - TIMESTAMPTZ
- `last_used_at` - TIMESTAMPTZ
- `usage_count` - INTEGER

**Constraints:**
- `ip_or_range_required` - Either ip_address OR ip_range must be set

**Indexes:**
- `unique_ip_or_range` on (ip_address, ip_range) - Unique
- `idx_ip_whitelist_active` on (ip_address, is_active)
- `idx_ip_whitelist_range` on ip_range

---

## Patient Management Tables

### patients
**Purpose:** Core patient records with medical information  
**Row Count:** TBD  
**Primary Key:** id (UUID)

**Key Columns:**
- `id` - UUID, Primary Key
- `name` - VARCHAR
- `email` - VARCHAR, Unique
- `phone` - VARCHAR
- `birth_date` - DATE
- `cpf` - VARCHAR, Unique
- `doctor_id` - UUID, Foreign Key
- `medical_history` - TEXT
- `treatment_type` - VARCHAR
- `diagnosis_date` - DATE
- `created_at` - TIMESTAMPTZ
- `updated_at` - TIMESTAMPTZ

**Relationships:**
- Belongs to: admin_users (doctor)
- Has many: quiz_sessions, quiz_responses, flow_states, messages

---

### user_profiles
**Purpose:** Extended user profile information  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### contacts
**Purpose:** Contact information for messaging  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

## Quiz & Assessment Tables

### quiz_templates
**Purpose:** Quiz template definitions  
**Row Count:** TBD  
**Primary Key:** id (UUID)

**Key Columns:**
- `id` - UUID, Primary Key
- `name` - VARCHAR
- `description` - TEXT
- `questions` - JSONB
- `version` - INTEGER
- `is_active` - BOOLEAN
- `created_at` - TIMESTAMPTZ
- `updated_at` - TIMESTAMPTZ

---

### quiz_sessions
**Purpose:** Patient quiz session tracking  
**Row Count:** TBD  
**Primary Key:** id (UUID)

**Key Columns:**
- `id` - UUID, Primary Key
- `patient_id` - UUID, Foreign Key
- `quiz_template_id` - UUID, Foreign Key
- `status` - VARCHAR (started, completed, cancelled)
- `started_at` - TIMESTAMPTZ
- `completed_at` - TIMESTAMPTZ
- `score` - NUMERIC
- `max_score` - NUMERIC
- `passed` - BOOLEAN
- `created_at` - TIMESTAMPTZ
- `updated_at` - TIMESTAMPTZ

**Foreign Keys:**
- `patient_id` → patients.id
- `quiz_template_id` → quiz_templates.id

---

### quiz_sessions_v2
**Purpose:** Enhanced quiz sessions with additional features  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### quiz_responses
**Purpose:** Individual quiz question responses  
**Row Count:** TBD  
**Primary Key:** id (UUID)

**Key Columns:**
- `id` - UUID, Primary Key
- `quiz_session_id` - UUID, Foreign Key
- `question_id` - VARCHAR
- `answer` - JSONB
- `is_correct` - BOOLEAN
- `score` - NUMERIC
- `created_at` - TIMESTAMPTZ

**Foreign Keys:**
- `quiz_session_id` → quiz_sessions.id

---

### quiz_template_versions_v2
**Purpose:** Version control for quiz templates  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

## Flow Engine Tables

### flow_kinds
**Purpose:** Flow type definitions  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### flow_states
**Purpose:** Patient flow state machine tracking  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### patient_flow_states
**Purpose:** Current flow state per patient  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### flow_messages
**Purpose:** Messages sent within flows  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### flow_analytics
**Purpose:** Flow execution analytics  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### flow_template_categories
**Purpose:** Flow template categorization  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### flow_template_shares
**Purpose:** Flow template sharing permissions  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### flow_template_stats
**Purpose:** Flow template usage statistics  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### flow_template_versions
**Purpose:** Flow template version control  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### patient_onboarding_saga
**Purpose:** Patient onboarding workflow state  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

## Messaging & Communication Tables

### messages
**Purpose:** Core messaging system  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### message_status_events
**Purpose:** Message delivery status tracking  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### whatsapp_messages
**Purpose:** WhatsApp message tracking  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### whatsapp_contacts
**Purpose:** WhatsApp contact information  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### whatsapp_instances
**Purpose:** WhatsApp instance configuration  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### whatsapp_delivery_failures
**Purpose:** Failed WhatsApp delivery tracking  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### webhook_events
**Purpose:** Incoming webhook event log  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

## Audit & Logging Tables

### audit_logs
**Purpose:** General application audit trail  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### audit_log_entries
**Purpose:** Detailed audit log entries  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### audit_trail
**Purpose:** Comprehensive audit trail  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### error_logs
**Purpose:** Application error logging  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### security_audit_log
**Purpose:** Security-specific audit events  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

## System Tables

### alembic_version
**Purpose:** Database migration version tracking  
**Row Count:** TBD  
**Primary Key:** version_num

---

### pg_stat_statements
**Purpose:** PostgreSQL query statistics (extension)  
**Row Count:** TBD

---

### pg_stat_statements_info
**Purpose:** pg_stat_statements metadata  
**Row Count:** TBD

---

### user_sync_log
**Purpose:** User synchronization tracking  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### users
**Purpose:** System user accounts  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### appointments
**Purpose:** Appointment scheduling (legacy/external system)  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### alerts
**Purpose:** System alerts and notifications  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

### medical_reports
**Purpose:** Medical report storage  
**Row Count:** TBD  
**Primary Key:** id (UUID)

---

## Custom Types (ENUMs)

### severity_type
Values: `low`, `medium`, `high`, `critical`

### http_method_type
Values: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`

---

## Database Statistics

- **Total Tables:** 48
- **Tables with RLS:** Multiple (security-focused)
- **Total Indexes:** 100+ (estimated)
- **Foreign Key Relationships:** 50+ (estimated)

---

## Security Features

1. **Row Level Security (RLS):** Enabled on sensitive tables
2. **Audit Logging:** Comprehensive audit trail for all admin actions
3. **IP Filtering:** Blacklist and whitelist support
4. **Session Management:** Secure session tracking with device fingerprinting
5. **Permission System:** Granular RBAC with role and user-level permissions
6. **Security Events:** Real-time threat detection and incident tracking

---

## Performance Optimizations

1. **Strategic Indexes:** Covering common query patterns
2. **JSONB Columns:** For flexible schema evolution
3. **Partitioning Ready:** Timestamp-based tables ready for partitioning
4. **Connection Pooling:** Configured for 30 connections with 40 overflow

---

## Compliance & Data Retention

- **LGPD Compliance:** Enabled
- **Audit Log Retention:** 365 days
- **Data Retention:** 730 days
- **Encryption:** Field-level encryption enabled

---

*Document generated from live database schema extraction*  
*Last Updated: 2025-10-24*
