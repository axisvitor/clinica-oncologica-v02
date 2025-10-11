# Database Architecture Diagram

**Generated:** 2025-10-11
**Schema Version:** 20251010_010000 (Baseline Production)

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    HORMONIA HEALTHCARE DATABASE                         │
│                         PostgreSQL on AWS RDS                           │
│                                                                         │
│  33 Tables | 19 ENUMs | 42 Foreign Keys | 85+ Indexes                 │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Core Entity Relationships

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         AUTHENTICATION & USERS                            │
└───────────────────────────────────────────────────────────────────────────┘

         ┌─────────────┐
         │    users    │ ◄─── Firebase Integration
         │  (doctors,  │      - firebase_uid (unique)
         │   admins)   │      - auth_provider (local/firebase)
         └──────┬──────┘      - role (admin/doctor)
                │
                ├──────────────────────────────────────────┐
                │                                          │
                ▼                                          ▼
         ┌─────────────┐                           ┌─────────────┐
         │  sessions   │                           │ audit_logs  │
         │  (active    │                           │ (23 event   │
         │   sessions) │                           │   types)    │
         └─────────────┘                           └─────────────┘
                │                                          ▲
                │                                          │
                ▼                                          │
         ┌─────────────┐                                  │
         │ user_sync_  │                                  │
         │    log      │ ◄────────────────────────────────┘
         │ (Firebase   │      Security Event Tracking
         │   sync)     │
         └─────────────┘
```

---

## Patient Management Ecosystem

```
┌───────────────────────────────────────────────────────────────────────────┐
│                       PATIENT CORE DATA                                   │
└───────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────┐
                    │    patients      │
                    │  - flow_state    │ ◄─── Flow State Management
                    │  - current_day   │      (onboarding → active →
                    │  - cpf, diagnosis│       paused → completed)
                    └────────┬─────────┘
                             │
           ┌─────────────────┼─────────────────┬─────────────────┐
           │                 │                 │                 │
           ▼                 ▼                 ▼                 ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐     ┌──────────┐
    │treatments│      │appoint-  │      │medica-   │     │consents  │
    │ (6 types)│      │ ments    │      │ tions    │     │ (7 types)│
    └──────────┘      │ (6 types)│      └──────────┘     └──────────┘
                      └──────────┘
```

---

## Communication System

```
┌───────────────────────────────────────────────────────────────────────────┐
│                    WHATSAPP COMMUNICATION PIPELINE                        │
└───────────────────────────────────────────────────────────────────────────┘

  Incoming Webhooks                   Message Processing              Delivery
        │                                     │                           │
        ▼                                     ▼                           ▼
┌─────────────────┐              ┌──────────────────┐        ┌──────────────────┐
│ webhook_events  │──────────────▶│    messages      │────────▶│ message_status_  │
│ (Evolution API) │              │  - scheduled_for │        │     events       │
│ - 17 columns    │              │  - retry_count   │        │  (delivery       │
│ - event_hash    │              │  - status        │        │   tracking)      │
│ - retry logic   │              └────────┬─────────┘        └──────────────────┘
└─────────────────┘                       │
        ▲                                  │ Failed delivery
        │                                  ▼
        │                         ┌──────────────────┐
        │                         │  whatsapp_       │
        │                         │  delivery_       │
        └─────────────────────────│  failures (DLQ)  │
              Retry Processing    │  - 8 reasons     │
                                  │  - review flow   │
                                  └──────────────────┘

┌─────────────────┐
│ webhook_        │  Idempotency Layer (24h TTL)
│ idempotency     │  - Prevents duplicate processing
│ - event_id (PK) │  - TTL: 24 hours
│ - expires_at    │  - Auto-cleanup
└─────────────────┘
```

---

## Quiz & Assessment System

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          QUIZ SYSTEM                                      │
└───────────────────────────────────────────────────────────────────────────┘

    Template Definition         Patient Sessions          Results & Alerts
            │                           │                         │
            ▼                           ▼                         ▼
    ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
    │quiz_templates│──────────▶│quiz_sessions │──────────▶│    alerts    │
    │ - name       │          │ - status     │          │ - severity   │
    │ - version    │          │ - score      │          │ - status     │
    │ - questions  │          │ - started_at │          │ - patient_id │
    │   (JSONB)    │          └──────┬───────┘          └──────────────┘
    └──────────────┘                 │
            │                        │
            │                        ▼
            │                ┌──────────────┐
            └────────────────▶│quiz_responses│
                             │ - question_id │
                             │ - response_   │
                             │   value       │
                             │ - metadata    │
                             └──────────────┘

Constraints:
- Unique (name, version) on quiz_templates
- Unique (quiz_session_id, question_id) on quiz_responses
- Partial unique index: ONE active session per patient/template
  WHERE status = 'started'
```

---

## Flow Management System

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        FLOW VERSIONING SYSTEM                             │
└───────────────────────────────────────────────────────────────────────────┘

    Flow Types              Versioned Templates         Patient Progress
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌────────────────────┐      ┌─────────────────┐
│  flow_kinds   │────────▶│ flow_template_     │─────▶│ patient_flow_   │
│ - flow_type   │         │    versions        │      │    states       │
│ - name        │         │ - version          │      │ - current_step  │
│ - category    │         │ - status (draft,   │      │ - state_data    │
│ - is_active   │         │   published)       │      │ - started_at    │
└───────────────┘         │ - messages (JSONB) │      └─────────────────┘
                          │ - quiz_templates   │
                          │   (JSONB)          │
                          │ - is_current       │
                          └────────────────────┘

Architecture Example:
  FlowKind: "hormone_therapy"
    ├─ FlowTemplateVersion v1.0 (published, is_current=true)
    ├─ FlowTemplateVersion v1.1 (draft)
    └─ FlowTemplateVersion v2.0 (draft)
         └─ PatientFlowState (patient progress in v1.0)
```

---

## Analytics & Reporting

```
┌───────────────────────────────────────────────────────────────────────────┐
│                     ANALYTICS & REPORTING LAYER                           │
└───────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐         ┌──────────────────┐         ┌──────────────┐
│ flow_analytics   │         │  flow_messages   │         │ medical_     │
│ - total_messages │         │ - step_name      │         │   reports    │
│ - response_time  │         │ - message_type   │         │ - summary    │
│ - engagement_    │         │ - scheduled_for  │         │ - insights   │
│   score          │         └──────────────────┘         │ - charts_data│
└──────────────────┘                                      └──────────────┘

┌──────────────────┐
│ notifications    │  User Notifications (6 types, 4 priorities)
│ - type           │  - info, warning, error, success, alert, reminder
│ - priority       │  - low, medium, high, urgent
│ - is_read        │
└──────────────────┘
```

---

## A/B Testing System

```
┌───────────────────────────────────────────────────────────────────────────┐
│                    A/B TESTING SYSTEM (HIPAA COMPLIANT)                   │
└───────────────────────────────────────────────────────────────────────────┘

  Experiment Definition    Patient Assignment         Metrics Collection
          │                        │                           │
          ▼                        ▼                           ▼
  ┌──────────────┐        ┌──────────────┐          ┌──────────────────┐
  │ab_experiments│───────▶│ab_variant_   │◄─────────│ab_experiment_    │
  │ - name       │        │  assignments │          │   metrics        │
  │ - status     │        │ - variant    │          │ - event_type     │
  │ - metrics    │        │ - anonymous_ │          │ - response_time  │
  │ - safety_    │        │   patient_id │          │ - engagement_    │
  │   checks     │        │ - safety_    │          │   score          │
  └──────┬───────┘        │   level      │          └──────────────────┘
         │                └──────────────┘                    │
         │                                                    │
         ▼                                                    ▼
  ┌──────────────┐                                  ┌──────────────────┐
  │ab_experiment_│                                  │ab_experiment_    │
  │  monitoring  │                                  │   results        │
  │ - safety_    │                                  │ - p_value        │
  │   violations │                                  │ - winner         │
  │ - emergency_ │                                  │ - statistical_   │
  │   stop       │                                  │   significance   │
  └──────────────┘                                  └──────────────────┘
         │
         ▼
  ┌──────────────┐
  │ab_experiment_│  Audit Trail (HIPAA Compliance)
  │   audit      │  - All actions logged
  │ - action     │  - Actor tracking
  │ - timestamp  │  - State changes
  └──────────────┘
```

---

## Foreign Key Cascade Strategy

```
┌───────────────────────────────────────────────────────────────────────────┐
│                      CASCADE RULES SUMMARY                                │
└───────────────────────────────────────────────────────────────────────────┘

CASCADE (24 relationships) - Delete dependent records
├─ patients.doctor_id → users.id (CASCADE)
├─ messages.patient_id → patients.id (CASCADE)
├─ quiz_sessions.patient_id → patients.id (CASCADE)
├─ quiz_responses.patient_id → patients.id (CASCADE)
├─ treatments.patient_id → patients.id (CASCADE)
├─ appointments.patient_id → patients.id (CASCADE)
├─ medications.patient_id → patients.id (CASCADE)
├─ consents.patient_id → patients.id (CASCADE)
├─ notifications.user_id → users.id (CASCADE)
├─ sessions.user_id → users.id (CASCADE)
├─ user_sync_log.user_id → users.id (CASCADE)
├─ whatsapp_delivery_failures.patient_id → patients.id (CASCADE)
├─ message_status_events.message_id → messages.id (CASCADE)
├─ flow_template_versions.kind_id → flow_kinds.id (CASCADE)
├─ quiz_responses.quiz_session_id → quiz_sessions.id (CASCADE)
└─ (+ 9 more A/B testing cascades)

SET NULL (15 relationships) - Preserve records, clear reference
├─ treatments.doctor_id → users.id (SET NULL)
├─ appointments.practitioner_id → users.id (SET NULL)
├─ medications.prescribed_by_id → users.id (SET NULL)
├─ alerts.acknowledged_by → users.id (SET NULL)
├─ consents.consented_by_id → users.id (SET NULL)
├─ consents.witness_id → users.id (SET NULL)
├─ whatsapp_delivery_failures.reviewed_by → users.id (SET NULL)
├─ whatsapp_delivery_failures.original_message_id → messages.id (SET NULL)
├─ alerts.quiz_session_id → quiz_sessions.id (SET NULL)
└─ (+ 6 more flow/message references)

RESTRICT (3 relationships) - Prevent deletion
├─ quiz_sessions.quiz_template_id → quiz_templates.id (RESTRICT)
├─ quiz_responses.quiz_template_id → quiz_templates.id (RESTRICT)
└─ patient_flow_states.template_version_id → flow_template_versions.id (RESTRICT)
```

---

## Index Performance Matrix

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        HIGH-PERFORMANCE TABLES                            │
└───────────────────────────────────────────────────────────────────────────┘

Table                      Indexes    Type                Purpose
─────────────────────────────────────────────────────────────────────────────
quiz_sessions              9          Composite           Session queries
quiz_responses             8          Composite           Response lookup
webhook_events             6          Composite           Event processing
message_status_events      4          Composite           Status tracking
audit_logs                 5          Composite           Security monitoring
ab_experiment_metrics      4          Composite           A/B analysis
sessions                   7          Single + Composite  Session management
patients                   4          Single              Patient lookup
messages                   5          Single              Message queries

Special Indexes:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Partial Unique Index (quiz_sessions):
  CREATE UNIQUE INDEX ix_quiz_session_active_unique
  ON quiz_sessions (patient_id, quiz_template_id)
  WHERE status = 'started';

Purpose: Ensures only ONE active session per patient/template
```

---

## Data Type Standards

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         DATA TYPE CONVENTIONS                             │
└───────────────────────────────────────────────────────────────────────────┘

Entity IDs         → UUID(as_uuid=True)       (PostgreSQL native UUID)
Timestamps         → DateTime(timezone=True)   (Always timezone-aware)
Metadata           → JSONB                     (Indexed, queryable JSON)
ENUMs              → PostgreSQL ENUM           (Native enum types)
Decimal Numbers    → Numeric(precision, scale) (e.g., Numeric(5,2) for scores)
Short Text         → String(length)            (Varchar with explicit length)
Long Text          → Text                      (Unlimited text)
Boolean Flags      → Boolean                   (Native boolean)
IP Addresses       → INET                      (Native IP type for audit_logs)
```

---

## ENUM Types Summary

```
┌───────────────────────────────────────────────────────────────────────────┐
│                            19 ENUM TYPES                                  │
└───────────────────────────────────────────────────────────────────────────┘

Authentication (2)
  ├─ user_role: admin, doctor
  └─ auth_provider: local, firebase

Patient & Flow (1)
  └─ flow_state: onboarding, active, paused, completed, inactive

Communication (4)
  ├─ messagedirection: inbound, outbound
  ├─ messagetype: 13 types (text, button, quiz types, monthly quiz)
  ├─ messagestatus: 8 statuses
  └─ deliverystatus: 8 delivery states

Monitoring (2)
  ├─ alertseverity: low, medium, high, critical
  └─ alertstatus: pending, active, acknowledged, resolved, dismissed

Clinical (6)
  ├─ treatmenttype: 6 treatment types
  ├─ treatmentstatus: 5 statuses
  ├─ appointmenttype: 6 types
  ├─ appointmentstatus: 6 statuses
  ├─ consenttype: 7 types
  └─ consentstatus: 5 statuses

Notifications (2)
  ├─ notificationtype: 6 types
  └─ notificationpriority: 4 levels

DLQ (2)
  ├─ failurereason: 8 reasons
  └─ dlqstatus: 6 statuses

A/B Testing (3)
  ├─ experimentstatus: 5 lifecycle states
  ├─ varianttype: control, treatment
  └─ patientsafetylevel: safe, restricted, excluded

Security (1)
  └─ audit_event_type: 23 event types
```

---

## Critical Path: Message Delivery

```
┌───────────────────────────────────────────────────────────────────────────┐
│                    MESSAGE DELIVERY CRITICAL PATH                         │
└───────────────────────────────────────────────────────────────────────────┘

1. Message Creation
   ┌─────────┐
   │messages │ status = 'pending'
   └────┬────┘
        │
2. Scheduling        ▼
   ┌─────────┐   scheduled_for = future_time
   │messages │   status = 'scheduled'
   └────┬────┘
        │
3. Sending           ▼
   ┌─────────┐   status = 'sending'
   │messages │   retry_count += 1
   └────┬────┘
        │
        ├─── SUCCESS ──────┐
        │                  │
        ▼                  ▼
   ┌─────────┐      ┌──────────────────┐
   │messages │      │message_status_   │ event_type = 'sent'
   │status = │      │     events       │ whatsapp_id = 'xxx'
   │'sent'   │      └──────────────────┘
   └────┬────┘
        │
4. Delivery          ▼
   ┌─────────┐   webhook from Evolution API
   │webhook_ │   event_type = 'message.delivered'
   │events   │   payload = {...}
   └────┬────┘
        │
        ▼                  ▼
   ┌─────────┐      ┌──────────────────┐
   │messages │      │message_status_   │ status = 'delivered'
   │status = │      │     events       │ whatsapp_timestamp
   │'delivered'│    └──────────────────┘
   └────┬────┘
        │
5. Read Receipt      ▼
   ┌─────────┐   webhook from Evolution API
   │webhook_ │   event_type = 'message.read'
   │events   │
   └────┬────┘
        │
        ▼                  ▼
   ┌─────────┐      ┌──────────────────┐
   │messages │      │message_status_   │ status = 'read'
   │status = │      │     events       │ read_at
   │'read'   │      └──────────────────┘
   └─────────┘

FAILURE PATH:
   ┌─────────┐   retry_count > MAX_RETRIES
   │messages │   status = 'failed'
   └────┬────┘
        │
        ▼
   ┌──────────────────┐
   │whatsapp_delivery_│  DLQ for manual review
   │   failures       │  - failure_reason
   │ (Dead Letter Q)  │  - dlq_status
   └──────────────────┘  - review workflow
```

---

## Security & Compliance

```
┌───────────────────────────────────────────────────────────────────────────┐
│                    SECURITY & COMPLIANCE FEATURES                         │
└───────────────────────────────────────────────────────────────────────────┘

HIPAA Compliance
├─ Patient Data Anonymization (A/B testing uses SHA-256 hashing)
├─ Comprehensive Audit Trail (audit_logs - 23 event types)
├─ Security Event Tracking (login, logout, access denied, etc.)
├─ Session Tracking (device info, IP, user agent)
├─ Consent Management (7 consent types, status tracking)
└─ Emergency Stop Capability (A/B testing safety)

Data Integrity
├─ 42 Foreign Key Constraints
├─ Check Constraints (quiz validation, status validation)
├─ Unique Constraints (prevent duplicates)
├─ Webhook Idempotency (24h TTL prevents duplicate processing)
├─ Dead Letter Queue (failed message tracking & review)
└─ JSONB Validation (structured metadata)

Performance
├─ 85+ Indexes for query optimization
├─ Composite Indexes on high-traffic queries
├─ Partial Indexes for conditional uniqueness
├─ JSONB for flexible metadata
└─ Proper data types (UUID, DateTime(tz), Numeric)
```

---

## Schema Statistics

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         DATABASE STATISTICS                               │
└───────────────────────────────────────────────────────────────────────────┘

Tables:                33
ENUM Types:            19
Foreign Keys:          42
Indexes:               85+
Model Files:           25
Migration Lines:       851

Cascade Rules:
  ├─ CASCADE:          24
  ├─ SET NULL:         15
  └─ RESTRICT:         3

Data Types:
  ├─ UUID:             Primary keys & foreign keys
  ├─ DateTime(tz):     All timestamps
  ├─ JSONB:            Metadata, configurations
  ├─ ENUM:             19 enum types
  ├─ Numeric:          Decimal precision (scores)
  ├─ String:           Short text
  ├─ Text:             Long text
  └─ INET:             IP addresses (audit_logs)

Schema Complexity:     HIGH (Enterprise-grade)
Compliance:            HIPAA-ready
Status:                ✅ Production-ready (1 fix required)
```

---

## Critical Finding

⚠️ **Table Name Mismatch (URGENT FIX REQUIRED)**

**Issue:**
- Migration creates: `webhook_events`
- Model expects: `evolution_webhook_events`

**Fix:**
```python
# File: backend-hormonia/app/models/message_events.py
# Line 103
class EvolutionWebhookEvent(BaseModel):
    __tablename__ = "webhook_events"  # ✅ Change from "evolution_webhook_events"
```

See: `docs/SCHEMA_CRITICAL_FIX_REQUIRED.md` for details.

---

**Diagram Version:** 1.0
**Last Updated:** 2025-10-11
**Status:** ✅ Complete
