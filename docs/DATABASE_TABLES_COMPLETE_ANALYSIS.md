# Database Tables Complete Analysis - Hormonia Backend

**Date:** 2025-12-22
**Database:** PostgreSQL 14+ on AWS RDS (sa-east-1)
**Total Tables:** 77
**Total Indexes:** 479+

---

## Executive Summary

This document provides a comprehensive analysis of all database tables in the Hormonia oncology clinic backend system. Tables are organized by functional category with detailed information about purpose, columns, relationships, and utility.

---

## Table Categories Overview

| Category | Tables | Purpose |
|----------|--------|---------|
| **Core Auth & Users** | 3 | User accounts, sessions, Firebase sync |
| **Clinical/Patient** | 6 | Patients, treatments, medications, appointments |
| **Quiz & Flow** | 8 | Patient assessments, onboarding workflows |
| **Messaging** | 6 | WhatsApp integration, notifications, templates |
| **Audit & Compliance** | 4 | LGPD/HIPAA compliance, security logs |
| **System & Webhooks** | 8 | Health monitoring, webhooks, error tracking |
| **Analytics & Reports** | 4 | A/B testing, medical reports |

---

## 1. Core Authentication & Users (3 Tables)

### 1.1 `users`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Healthcare provider accounts with dual auth (local + Firebase) |
| **Key Columns** | `id`, `email`, `firebase_uid`, `role` (ADMIN/DOCTOR), `permissions` (JSONB), `is_active`, `is_locked` |
| **Relationships** | → patients (1:N), → sessions (1:N), → reports, → alerts, → treatments, → appointments |
| **Indexes** | `email` (unique), `firebase_uid` (unique) |
| **Utility** | Central user management, RBAC, account security |

### 1.2 `sessions`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Multi-device session management with security monitoring |
| **Key Columns** | `session_token`, `refresh_token`, `device_id`, `ip_address`, `location` (JSONB), `is_suspicious`, `risk_score` |
| **Relationships** | → users.id (FK, CASCADE) |
| **Indexes** | `session_token`, `refresh_token`, `device_id`, `is_active`, `expires_at` |
| **Utility** | Authentication, device tracking, suspicious activity detection |

### 1.3 `user_sync_log`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Firebase-PostgreSQL sync audit trail |
| **Key Columns** | `firebase_uid`, `user_id`, `operation`, `sync_direction`, `changes` (JSONB), `success` |
| **Relationships** | → users.id (FK, CASCADE) |
| **Indexes** | `firebase_uid`, `user_id`, `created_at` |
| **Utility** | Sync debugging, data integrity verification |

---

## 2. Clinical/Patient Tables (6 Tables)

### 2.1 `patients`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Core patient management with LGPD-compliant encrypted PII |
| **Key Columns** | `name`, `birth_date`, `doctor_id`, `flow_state`, `treatment_type`, `diagnosis` |
| **Encrypted PII** | `cpf_encrypted`, `email_encrypted`, `phone_encrypted` + hash columns for search |
| **Relationships** | → users.id (doctor), ← messages, ← quiz_sessions, ← treatments, ← appointments, ← alerts |
| **Indexes** | `cpf_hash`, `email_hash`, `phone_hash`, `flow_state`, `diagnosis` |
| **Utility** | Central patient entity, treatment tracking, LGPD compliance |

### 2.2 `treatments`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Patient treatment plans for oncology therapies |
| **Key Columns** | `patient_id`, `doctor_id`, `treatment_type` (enum), `status`, `start_date`, `planned_sessions`, `completed_sessions` |
| **Treatment Types** | quimioterapia, radioterapia, hormonioterapia, imunoterapia, cirurgia, outros |
| **Relationships** | → patients.id (CASCADE), → users.id (SET NULL), ← medications |
| **Indexes** | `patient_id`, `treatment_type`, `status`, `start_date` |
| **Utility** | Treatment protocol tracking, session management |

### 2.3 `medications`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Patient medication prescriptions and refill tracking |
| **Key Columns** | `patient_id`, `prescribed_by_id`, `treatment_id`, `name`, `dosage`, `frequency`, `refills_remaining` |
| **Relationships** | → patients.id (CASCADE), → users.id (SET NULL), → treatments.id (SET NULL) |
| **Indexes** | `patient_id`, `prescription_date`, `is_active` |
| **Utility** | Prescription management, refill tracking, adherence monitoring |

### 2.4 `appointments`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Patient appointment scheduling and lifecycle |
| **Key Columns** | `patient_id`, `practitioner_id`, `appointment_type`, `status`, `scheduled_at`, `duration_minutes` |
| **Appointment Types** | consultation, followup, treatment, exam, emergency, telemedicine |
| **Relationships** | → patients.id (CASCADE), → users.id (SET NULL) |
| **Indexes** | `patient_id`, `appointment_type`, `status`, `scheduled_at` |
| **Utility** | Scheduling, reminders, clinical documentation |

### 2.5 `consents`
| Attribute | Details |
|-----------|---------|
| **Purpose** | LGPD consent management for treatment and data sharing |
| **Key Columns** | `patient_id`, `consent_type`, `status`, `legal_text`, `granted_at`, `expires_at`, `signature_data` (JSONB) |
| **Consent Types** | treatment, data_sharing, research, communication, telemedicine, photography |
| **Relationships** | → patients.id (CASCADE), → users.id (consented_by) |
| **Indexes** | `patient_id`, `consent_type`, `status`, `expires_at` |
| **Utility** | Legal basis for data processing (LGPD Art. 7), consent versioning |

### 2.6 `patient_summaries`
| Attribute | Details |
|-----------|---------|
| **Purpose** | AI-generated patient consultation summaries |
| **Key Columns** | `patient_id`, `summary_type`, `content` (JSONB), `ai_generated`, `reviewed_by` |
| **Relationships** | → patients.id (CASCADE), → users.id (reviewer) |
| **Utility** | Clinical documentation, AI-assisted summaries |

---

## 3. Quiz & Flow System (8 Tables)

### 3.1 `quiz_templates`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Versioned patient assessment templates |
| **Key Columns** | `name`, `version`, `questions` (JSONB), `scoring_rules` (JSONB), `is_active` |
| **Utility** | Assessment framework, versioned questionnaires |

### 3.2 `quiz_sessions`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Patient quiz tracking with state management |
| **Key Columns** | `patient_id`, `template_id`, `status`, `started_at`, `completed_at`, `score` |
| **Relationships** | → patients.id (CASCADE), → quiz_templates.id |
| **Utility** | Quiz progress tracking, completion monitoring |

### 3.3 `quiz_responses`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Individual question answers |
| **Key Columns** | `session_id`, `question_id`, `answer` (JSONB), `score`, `answered_at` |
| **Relationships** | → quiz_sessions.id (CASCADE) |
| **Utility** | Answer storage, scoring calculations |

### 3.4 `flow_kinds`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Flow type definitions |
| **Key Columns** | `name`, `description`, `config` (JSONB) |
| **Utility** | Flow categorization and configuration |

### 3.5 `flow_template_versions`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Version-controlled conversation templates |
| **Key Columns** | `flow_kind_id`, `version`, `template` (JSONB), `is_active` |
| **Relationships** | → flow_kinds.id |
| **Utility** | Template versioning, A/B testing support |

### 3.6 `patient_flow_states`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Patient progress tracking through flows |
| **Key Columns** | `patient_id`, `flow_kind_id`, `current_step`, `state_data` (JSONB), `completed_at` |
| **Relationships** | → patients.id (CASCADE), → flow_kinds.id |
| **Utility** | Flow progression, state management |

### 3.7 `flow_analytics`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Flow performance metrics |
| **Key Columns** | `flow_kind_id`, `completion_rate`, `avg_duration`, `drop_off_points` (JSONB) |
| **Utility** | Flow optimization, bottleneck detection |

### 3.8 `patient_onboarding_saga`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Distributed transaction management for onboarding |
| **Key Columns** | `patient_id`, `status` (SagaStatus enum), `current_step`, `steps_completed` (JSONB), `error_message` |
| **Relationships** | → patients.id (CASCADE) |
| **Indexes** | `patient_id`, `status`, `created_at` |
| **Utility** | Saga pattern implementation, orphan detection, compensation handling |

---

## 4. Messaging & Notifications (6 Tables)

### 4.1 `messages`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Core WhatsApp messaging table |
| **Key Columns** | `patient_id`, `direction` (IN/OUT), `message_type`, `content`, `status`, `whatsapp_message_id` |
| **Relationships** | → patients.id (CASCADE) |
| **Indexes** | `patient_id`, `status`, `created_at`, `whatsapp_message_id` |
| **Utility** | WhatsApp integration, message lifecycle tracking |

### 4.2 `message_status_events`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Message audit trail from Evolution API webhooks |
| **Key Columns** | `message_id`, `status`, `event_timestamp`, `error_code`, `raw_payload` (JSONB) |
| **Relationships** | → messages.id (CASCADE) |
| **Utility** | Delivery tracking, debugging, compliance |

### 4.3 `webhook_events` (Evolution API)
| Attribute | Details |
|-----------|---------|
| **Purpose** | Evolution API event storage for replay |
| **Key Columns** | `event_id`, `event_type`, `payload` (JSONB), `status`, `retry_count`, `event_hash` (SHA256) |
| **Utility** | Dead letter queue, deduplication, webhook replay |

### 4.4 `whatsapp_delivery_failures`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Failed message DLQ for manual review |
| **Key Columns** | `message_id`, `error_type`, `error_message`, `reviewed_by`, `resolved_at` |
| **Relationships** | → messages.id, → users.id (reviewer) |
| **Utility** | Error handling, manual intervention workflow |

### 4.5 `notifications`
| Attribute | Details |
|-----------|---------|
| **Purpose** | System notification center |
| **Key Columns** | `user_id`, `notification_type`, `priority`, `title`, `message`, `is_read`, `expires_at` |
| **Relationships** | → users.id (CASCADE), → patients.id (optional) |
| **Indexes** | `user_id`, `is_read`, `priority`, `created_at` |
| **Utility** | User notifications, alerts, reminders |

### 4.6 `message_templates`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Reusable message templates with variable substitution |
| **Key Columns** | `name`, `content`, `variables` (JSONB), `category`, `is_active` |
| **Utility** | Template management, message standardization |

---

## 5. Audit & Compliance (4 Tables)

### 5.1 `audit_logs`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Security event tracking (30+ event types) |
| **Key Columns** | `event_type` (AuditEventType enum), `event_status`, `user_id`, `ip_address`, `user_agent`, `resource`, `action` |
| **Event Categories** | Authentication, Authorization, Account Management, Security |
| **Indexes** | Composite: (user_id, event_type, created_at), (ip_address, created_at), (event_type, event_status, created_at) |
| **Utility** | Security monitoring, incident response, HIPAA compliance |

### 5.2 `lgpd_audit_logs`
| Attribute | Details |
|-----------|---------|
| **Purpose** | **PRIMARY LGPD COMPLIANCE TABLE** - PII access tracking |
| **Key Columns** | `user_id`, `patient_id`, `action` (LGPDActionType), `data_category` (LGPDDataCategory), `fields_accessed` (JSONB), `legal_basis`, `purpose` |
| **Action Types** | view, create, update, delete, export, anonymize, consent_granted/revoked, share_internal/external |
| **Data Categories** | personal_basic, health, genetic, biometric, financial, authentication |
| **Indexes** | (patient_id, created_at), (user_id, created_at), (action, created_at), partial index on failures |
| **Utility** | LGPD Article 37 compliance, data access auditing, breach detection |

### 5.3 `lgpd_data_access_requests`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Data Subject Access Requests (DSAR) management |
| **Key Columns** | `patient_id`, `request_type` (access/rectification/erasure/portability), `status`, `deadline_at`, `responded_at`, `evidence_hash` |
| **Relationships** | → patients.id |
| **Utility** | LGPD Articles 18-19 compliance, 15-day response deadline tracking |

### 5.4 `alerts`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Clinical patient monitoring alerts |
| **Key Columns** | `patient_id`, `alert_type`, `severity` (LOW/MEDIUM/HIGH/CRITICAL), `description`, `acknowledged`, `acknowledged_by` |
| **Relationships** | → patients.id (CASCADE), → users.id (acknowledger) |
| **Indexes** | `patient_id`, `severity`, `acknowledged` |
| **Utility** | Risk monitoring, clinical alerts, team notifications |

---

## 6. System & Webhooks (8 Tables)

### 6.1 `webhook_endpoints`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Webhook configuration management |
| **Key Columns** | `url`, `status`, `events` (JSONB), `secret` (HMAC key), `retry_enabled`, `max_retries`, `timeout` |
| **Relationships** | ← webhook_deliveries, ← webhook_logs |
| **Utility** | External integrations, event-driven architecture |

### 6.2 `webhook_deliveries`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Webhook delivery attempts tracking |
| **Key Columns** | `webhook_id`, `event_type`, `payload` (JSONB), `status`, `attempt`, `response_time_ms`, `error` |
| **Relationships** | → webhook_endpoints.id (CASCADE) |
| **Utility** | Delivery monitoring, retry management |

### 6.3 `webhook_logs`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Webhook administrative audit trail |
| **Key Columns** | `webhook_id`, `event_type`, `action`, `details` (JSONB) |
| **Relationships** | → webhook_endpoints.id (CASCADE) |
| **Utility** | Configuration change tracking |

### 6.4 `webhook_idempotency`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Prevents duplicate webhook processing |
| **Key Columns** | `event_id`, `provider`, `status`, `retry_count`, `expires_at` |
| **Utility** | Idempotency enforcement, duplicate detection |

### 6.5 `system_health_snapshots`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Periodic system health monitoring |
| **Key Columns** | `status` (HEALTHY/DEGRADED/UNHEALTHY), `health_score` (0-100), `services_status` (JSONB), `metrics` (JSONB) |
| **Utility** | System monitoring, alerting, SLA tracking |

### 6.6 `system_incidents`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Incident tracking and management |
| **Key Columns** | `title`, `severity` (LOW/MEDIUM/HIGH/CRITICAL), `status`, `started_at`, `resolved_at`, `meta_data` (JSONB) |
| **Utility** | Incident management, root cause analysis |

### 6.7 `error_logs`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Error deduplication and tracking |
| **Key Columns** | `error_type`, `error_message`, `stack_trace`, `context` (JSONB), `count`, `first_seen`, `last_seen`, `resolved` |
| **Utility** | Error monitoring, deduplication, debugging |

### 6.8 `uploads`
| Attribute | Details |
|-----------|---------|
| **Purpose** | File upload tracking with security scanning |
| **Key Columns** | `user_id`, `file_name`, `file_size`, `storage_path`, `content_hash` (SHA256), `virus_scanned`, `virus_clean` |
| **Relationships** | → users.id (CASCADE) |
| **Utility** | File management, deduplication, security |

---

## 7. Analytics & Reports (4+ Tables)

### 7.1 `medical_reports`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Legacy patient summary reports with AI insights |
| **Key Columns** | `patient_id`, `generated_by`, `period_start`, `period_end`, `summary`, `insights` (JSONB) |
| **Relationships** | → patients.id (CASCADE), → users.id |
| **Utility** | Clinical documentation, AI-assisted reporting |

### 7.2 `reports`
| Attribute | Details |
|-----------|---------|
| **Purpose** | Generic system-generated reports |
| **Key Columns** | `type` (QUIZ_ANALYSIS/MONTHLY_SUMMARY/ALERT_SUMMARY), `status`, `content` (JSONB), `pdf_data` (binary) |
| **Utility** | Report generation, export functionality |

### 7.3 A/B Testing Tables (6 tables)
| Table | Purpose |
|-------|---------|
| `ab_experiments` | Experiment configurations with HIPAA compliance |
| `ab_variant_assignments` | Patient variant assignments (anonymized) |
| `ab_experiment_metrics` | Event tracking (sent, delivered, read, responded) |
| `ab_experiment_results` | Statistical analysis (p-value, Cohen's d, confidence intervals) |
| `ab_experiment_audit` | HIPAA/GDPR compliant audit trail |
| `ab_experiment_monitoring` | Real-time KPI monitoring with emergency stop |

---

## Relationship Diagram (Simplified)

```
                    ┌─────────────┐
                    │    users    │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ sessions │    │ patients │    │ consents │
    └──────────┘    └────┬─────┘    └──────────┘
                         │
    ┌────────────┬───────┼───────┬────────────┐
    │            │       │       │            │
    ▼            ▼       ▼       ▼            ▼
┌────────┐ ┌─────────┐ ┌─────┐ ┌──────────┐ ┌────────────┐
│messages│ │treatments│ │quiz_│ │appointments│ │onboarding_ │
└────────┘ └────┬────┘ │sess.│ └───────────┘ │saga        │
                │      └─────┘               └────────────┘
                ▼
         ┌───────────┐
         │medications│
         └───────────┘
```

---

## Key Design Patterns

### 1. **LGPD/HIPAA Compliance**
- AES-256 encryption for PII (cpf, email, phone)
- SHA-256 searchable hashes
- Granular field-level audit logging
- Consent versioning and revocation

### 2. **Soft Deletes**
- `deleted_at` column across core tables
- CASCADE rules for referential integrity
- Audit trail preservation

### 3. **JSONB Flexibility**
- `metadata`, `config`, `context` fields
- Schema evolution without migrations
- JSON Schema validation recommended

### 4. **Performance Optimization**
- 479+ indexes including composite indexes
- Partial indexes for common queries
- Eager loading strategies documented

### 5. **Event-Driven Architecture**
- Webhook system with retry and idempotency
- Message queue integration
- Real-time monitoring

---

## Recommendations

### Immediate (P0)
1. ✅ Pool configuration fixed (200 → 25 connections)
2. ✅ Unbounded queries fixed with LIMIT
3. ✅ N+1 queries optimized
4. ✅ CONCURRENTLY added to migrations

### Short-term (P1)
1. Implement data retention policies for audit tables
2. Add missing indexes on `error_logs.resolved`
3. Consolidate Report models

### Medium-term (P2)
1. Move PDF storage to cloud (S3)
2. Split large model files (ab_experiment.py)
3. Add JSON Schema validation for JSONB columns

### Long-term (P3)
1. Implement read replicas for analytics
2. Table partitioning for audit logs
3. Add `data_breach_log` table for LGPD Art. 48

---

**Generated by:** Claude Code Database Analysis Swarm
**Session ID:** swarm_1766435343296_fb67c8vrv
