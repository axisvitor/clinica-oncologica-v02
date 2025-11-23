# Database Schema Overview

This document provides a high-level overview of the Hormonia Backend database schema, organized by functional domain.

## Table of Contents

- [Core Entities](#core-entities)
- [User & Security](#user--security)
- [Patient Management](#patient-management)
- [Messaging System](#messaging-system)
- [Quiz System](#quiz-system)
- [Flow Engine](#flow-engine)
- [Clinical Management](#clinical-management)
- [Notifications & Alerts](#notifications--alerts)
- [Analytics & Reporting](#analytics--reporting)
- [Audit & Compliance](#audit--compliance)

---

## Core Entities

The database is built around four core entities that represent the main business objects:

1. **Users** (`users`) - Healthcare providers
2. **Patients** (`patients`) - Patients under care
3. **Messages** (`messages`) - WhatsApp communications
4. **Quiz Templates** (`quiz_templates`) - Medical assessments

---

## User & Security

### Tables

| Table | Purpose | Key Features |
|-------|---------|--------------|
| `users` | Healthcare providers (doctors, admins) | Firebase auth, role-based access, account security |
| `sessions` | Active authentication sessions | Device tracking, IP geolocation, security risk scoring |
| `audit_logs` | Security event tracking | Login attempts, permission changes, suspicious activity |
| `user_sync_logs` | Firebase sync history | User creation/update tracking |

### User Roles

```python
class UserRole(enum.Enum):
    ADMIN = "admin"      # Full system access
    DOCTOR = "doctor"    # Patient management access
```

### Authentication Providers

```python
class AuthProvider(enum.Enum):
    LOCAL = "local"      # Email/password authentication
    FIREBASE = "firebase" # Firebase Authentication
```

### Key Features
- **Multi-factor authentication** ready
- **Account lockout** after failed attempts
- **Password change enforcement**
- **Device fingerprinting**
- **Session management** with revocation

---

## Patient Management

### Tables

| Table | Purpose | Key Features |
|-------|---------|--------------|
| `patients` | Patient records | UUID primary key, composite unique constraints, soft delete |
| `patient_flow_states` | Conversation flow tracking | Versioned templates, step tracking, optimistic locking |
| `patient_onboarding_saga` | Transaction orchestration | Saga pattern, retry logic, compensation |

### Patient Flow States

```python
class FlowState(enum.Enum):
    ONBOARDING = "onboarding"   # Initial setup phase
    ACTIVE = "active"           # Regular treatment
    PAUSED = "paused"           # Temporarily inactive
    COMPLETED = "completed"     # Treatment finished
    CANCELLED = "cancelled"     # Treatment cancelled
```

### Data Model Highlights

**Patient Record:**
- **Unique per doctor**: Composite constraints on (email, doctor_id), (cpf, doctor_id), (phone, doctor_id)
- **Brazilian healthcare**: CPF, diagnosis, treatment_phase fields
- **Flexible metadata**: JSONB column for additional attributes
- **Soft delete**: `deleted_at` timestamp for GDPR compliance

**Onboarding Saga:**
- **4-step process**: Patient → Firebase → Flow → Message
- **Automatic retry**: Up to 3 attempts with exponential backoff
- **Compensation**: Rollback on permanent failure
- **Audit trail**: Detailed execution log in JSONB

---

## Messaging System

### Tables

| Table | Purpose | Key Features |
|-------|---------|--------------|
| `messages` | WhatsApp messages | Bidirectional, priority queue, idempotency key |
| `message_status_events` | Delivery tracking | Webhook events, status history |
| `webhook_idempotency` | Duplicate prevention | 24-hour TTL, retry counting |

### Message Types

```python
class MessageType(enum.Enum):
    TEXT = "text"
    BUTTON = "button"
    LIST = "list"
    MEDIA = "media"
    QUIZ_INTRO = "quiz_intro"
    QUIZ_QUESTION = "quiz_question"
    MONTHLY_QUIZ_LINK = "monthly_quiz_link"
    # ... and more
```

### Message Status Flow

```
PENDING → SCHEDULED → SENDING → SENT → DELIVERED → READ
                          ↓
                        FAILED
```

### Key Features
- **Idempotency keys**: Prevent duplicate message sends
- **Priority queue**: CRITICAL > HIGH > NORMAL > LOW
- **Retry logic**: Automatic retry with backoff
- **Delivery tracking**: Webhook status updates
- **Rate limiting**: Per-patient message throttling

---

## Quiz System

### Tables

| Table | Purpose | Key Features |
|-------|---------|--------------|
| `quiz_templates` | Quiz definitions | Versioned, JSONB questions, active flag |
| `quiz_sessions` | Patient quiz sessions | Status tracking, scoring, 48-hour expiration |
| `quiz_responses` | Patient answers | JSONB values, unique per question/session |

### Quiz Session Status

```python
STATUS = ['started', 'completed', 'cancelled', 'expired']
```

### Response Types

```python
RESPONSE_TYPES = [
    'multiple_choice',
    'single_choice',
    'open_text',
    'scale',
    'boolean',
    'yes_no',
    'number',
    'date'
]
```

### JSONB Response Format

```json
{
  "response_value": {
    // Multiple choice
    "selected": ["option1", "option2"],

    // Scale
    "value": 7,
    "type": "scale",

    // Boolean
    "text": "yes",
    "boolean": true
  }
}
```

### Key Features
- **Auto-expiration**: Sessions expire after 48 hours
- **One active session**: Partial index ensures single active session per patient/template
- **Flexible responses**: JSONB supports all answer types
- **Scoring system**: Decimal precision for scores
- **Progress tracking**: Current question index, answered questions count

---

## Flow Engine

### Tables

| Table | Purpose | Key Features |
|-------|---------|--------------|
| `flow_kinds` | Flow type definitions | Separates flow types from versions |
| `flow_template_versions` | Versioned templates | Draft/active lifecycle, JSONB steps |
| `flow_analytics` | Performance metrics | Engagement scoring, response times |
| `flow_messages` | Template messages | Step-based message definitions |

### Template Versioning

```
FlowKind (onboarding)
  ├── FlowTemplateVersion 1 (active)
  ├── FlowTemplateVersion 2 (active)
  └── FlowTemplateVersion 3 (draft)
```

### Lifecycle States

```python
is_draft = True   # Under development
is_draft = False, is_active = False  # Published but inactive
is_draft = False, is_active = True   # Active in production
deprecated_at != None  # Archived
```

### Key Features
- **Version control**: Multiple versions per flow kind
- **Blue-green deployment**: Activate new version without downtime
- **Rollback support**: Reactivate previous versions
- **A/B testing**: Multiple active versions simultaneously
- **Optimistic locking**: Version field prevents concurrent updates

---

## Clinical Management

### Tables

| Table | Purpose | Key Features |
|-------|---------|--------------|
| `treatments` | Treatment plans | Type, status, protocol, session tracking |
| `appointments` | Patient appointments | Scheduling, practitioner assignment, status |
| `medications` | Prescriptions | Dosage, frequency, refills, warnings |
| `consents` | Patient consents | Type, status, digital signature, expiration |
| `medical_reports` | Generated reports | AI summaries, insights, charts |

### Treatment Types

```python
class TreatmentType(enum.Enum):
    QUIMIOTERAPIA = "quimioterapia"
    RADIOTERAPIA = "radioterapia"
    HORMONIOTERAPIA = "hormonioterapia"
    IMUNOTERAPIA = "imunoterapia"
    CIRURGIA = "cirurgia"
    OUTROS = "outros"
```

### Appointment Types

```python
class AppointmentType(enum.Enum):
    CONSULTATION = "consultation"
    FOLLOWUP = "followup"
    TREATMENT = "treatment"
    EXAM = "exam"
    EMERGENCY = "emergency"
    TELEMEDICINE = "telemedicine"
```

### Consent Management

```python
class ConsentStatus(enum.Enum):
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"
    EXPIRED = "expired"
```

### Key Features
- **Treatment tracking**: Sessions planned vs completed
- **Medication management**: Refills, discontinuation tracking
- **Appointment reminders**: Integration with notification system
- **Consent versioning**: Previous consent tracking
- **Digital signatures**: JSONB signature data

---

## Notifications & Alerts

### Tables

| Table | Purpose | Key Features |
|-------|---------|--------------|
| `alerts` | Patient monitoring | Severity, acknowledgment, quiz-linked |
| `notifications` | System notifications | Priority, read status, expiration |

### Alert Severity

```python
class AlertSeverity(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
```

### Notification Priority

```python
class NotificationPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
```

### Key Features
- **Quiz integration**: Alerts store `quiz_session_id` in JSONB data field
- **Acknowledgment tracking**: User and timestamp
- **Auto-expiration**: Notifications expire after TTL
- **Archive support**: Soft delete with archival
- **Action URLs**: Deep links to related resources

---

## Analytics & Reporting

### Tables

| Table | Purpose | Key Features |
|-------|---------|--------------|
| `flow_analytics` | Flow performance | Engagement scores, completion rates |
| `quiz_questions` | Question bank | Reusable quiz questions |
| `medical_reports` | Generated reports | AI summaries, insights, charts |

### Analytics Metrics

```python
# Flow Analytics
- total_messages_sent
- total_messages_received
- avg_response_time_minutes
- completion_rate (0.0 to 1.0)
- engagement_score (0.0 to 100.0)
- quiz_completion_rate
- avg_quiz_score

# Medical Reports
- summary (AI-generated text)
- insights (structured JSONB)
- charts_data (visualization data)
- alerts (identified issues)
```

### Key Features
- **Engagement scoring**: 0-100 scale for patient interaction quality
- **Response time tracking**: Average response time in minutes/seconds
- **Quiz analytics**: Completion and scoring metrics
- **Period-based reports**: Date range filtering
- **AI-powered insights**: OpenAI/Gemini integration

---

## Audit & Compliance

### Tables

| Table | Purpose | Key Features |
|-------|---------|--------------|
| `audit_logs` | Security events | Authentication, authorization, account management |
| `user_sync_logs` | Firebase sync | User creation/update tracking |
| `patient_onboarding_saga` | Transaction audit | Distributed transaction execution log |

### Audit Event Types

```python
class AuditEventType(enum.Enum):
    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"

    # Authorization
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGED = "permission_changed"

    # Account Management
    PASSWORD_CHANGED = "password_changed"
    ACCOUNT_LOCKED = "account_locked"

    # Security
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    CSRF_VIOLATION = "csrf_violation"
```

### Compliance Features

**HIPAA Readiness:**
- Audit trail for all PHI access
- Encryption support (field-level)
- Access control logging
- Session tracking with device info

**LGPD/GDPR Compliance:**
- Soft delete with `deleted_at`
- Data export capabilities
- Consent management
- Right to erasure support

### Key Features
- **IP address tracking**: Network information for security
- **User agent logging**: Device/browser identification
- **Event metadata**: Extensible JSONB for context
- **Performance indexes**: Efficient audit queries
- **Retention policies**: Configurable data retention

---

## Data Relationships Summary

```
users (1) ----< (N) patients
users (1) ----< (N) sessions
users (1) ----< (N) treatments
users (1) ----< (N) appointments
users (1) ----< (N) notifications

patients (1) ----< (N) messages
patients (1) ----< (N) patient_flow_states
patients (1) ----< (N) quiz_sessions
patients (1) ----< (N) quiz_responses
patients (1) ----< (N) treatments
patients (1) ----< (N) appointments
patients (1) ----< (N) medications
patients (1) ----< (N) alerts
patients (1) ----< (N) consents

quiz_templates (1) ----< (N) quiz_sessions
quiz_templates (1) ----< (N) quiz_responses
quiz_sessions (1) ----< (N) quiz_responses

flow_kinds (1) ----< (N) flow_template_versions
flow_template_versions (1) ----< (N) patient_flow_states
flow_template_versions (1) ----< (N) flow_messages

treatments (1) ----< (N) medications
```

---

## Schema Evolution

The schema evolves through Alembic migrations. Key principles:

1. **Backward compatibility**: Old code should work with new schema
2. **Forward compatibility**: New code should degrade gracefully
3. **Zero-downtime migrations**: Use non-blocking DDL operations
4. **Versioning**: Template and flow versioning for gradual rollouts

---

## Next Steps

- **Detailed Table Reference**: See [TABLES_REFERENCE.md](./TABLES_REFERENCE.md)
- **Relationship Diagrams**: See [RELATIONSHIPS.md](./RELATIONSHIPS.md)
- **Index Optimization**: See [INDEXES.md](./INDEXES.md)
- **Security Details**: See [SECURITY.md](./SECURITY.md)
