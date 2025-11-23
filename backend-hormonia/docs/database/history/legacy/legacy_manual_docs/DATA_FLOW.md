# Data Flow Documentation

This document describes how data flows through the Hormonia Backend system across different business processes.

## Table of Contents

- [Data Flow Overview](#data-flow-overview)
- [Patient Onboarding Flow](#patient-onboarding-flow)
- [Quiz Participation Flow](#quiz-participation-flow)
- [Message Delivery Flow](#message-delivery-flow)
- [Treatment Management Flow](#treatment-management-flow)
- [Authentication Flow](#authentication-flow)
- [Flow Engine Execution](#flow-engine-execution)
- [Alert Generation Flow](#alert-generation-flow)

---

## Data Flow Overview

### System Architecture

```
┌─────────────┐
│   Client    │ (Web/Mobile App, WhatsApp)
└──────┬──────┘
       │ HTTP/WebSocket
       ▼
┌─────────────────────┐
│   FastAPI Backend   │
│   (API Layer)       │
└──────┬──────────────┘
       │
       ├──> Authentication & Authorization
       ├──> Business Logic
       └──> Database Operations
              │
              ▼
       ┌──────────────┐
       │  PostgreSQL  │
       │   Database   │
       └──────────────┘
              │
              ├──> Audit Logs
              ├──> Analytics
              └──> Webhooks
```

---

## Patient Onboarding Flow

### Saga Pattern (4-Step Transaction)

```
Step 1: Create Patient Record
│
│ INSERT INTO patients (doctor_id, phone, name, email, ...)
│ Status: STEP_1_PATIENT_CREATED
│
├─> Success: Continue to Step 2
└─> Failure: Retry (max 3x) or FAILED
    │
    ▼
Step 2: Create Firebase User
│
│ Firebase Admin SDK: createUser({email, phone})
│ UPDATE patients SET metadata.firebase_uid = ...
│ Status: STEP_2_FIREBASE_USER_CREATED
│
├─> Success: Continue to Step 3
└─> Failure: Compensate Step 1 (delete patient)
    │
    ▼
Step 3: Initialize Flow State
│
│ INSERT INTO patient_flow_states (patient_id, flow_template_version_id, ...)
│ Status: STEP_3_FLOW_INITIALIZED
│
├─> Success: Continue to Step 4
└─> Failure: Compensate Step 2, Step 1
    │
    ▼
Step 4: Send Welcome Message
│
│ INSERT INTO messages (patient_id, type='quiz_intro', ...)
│ Trigger: Celery task for WhatsApp delivery
│ Status: STEP_4_MESSAGE_SENT → COMPLETED
│
├─> Success: Saga COMPLETED
└─> Failure: Compensate Step 3, Step 2, Step 1
```

**Database Tables Involved:**
1. `patient_onboarding_saga` - Saga orchestration
2. `patients` - Patient record
3. `patient_flow_states` - Flow tracking
4. `messages` - Welcome message

**Saga Execution Log (JSONB):**
```json
{
  "execution_log": [
    {
      "step": 1,
      "action": "create_patient",
      "status": "success",
      "timestamp": "2025-11-15T12:00:00Z"
    },
    {
      "step": 2,
      "action": "create_firebase_user",
      "status": "success",
      "timestamp": "2025-11-15T12:00:01Z",
      "message": "Firebase UID: xyz123"
    },
    {
      "step": 3,
      "action": "initialize_flow",
      "status": "success",
      "timestamp": "2025-11-15T12:00:02Z"
    },
    {
      "step": 4,
      "action": "send_welcome_message",
      "status": "success",
      "timestamp": "2025-11-15T12:00:03Z"
    }
  ]
}
```

---

## Quiz Participation Flow

### Session-Based Quiz Flow

```
1. Start Quiz Session
   │
   │ INSERT INTO quiz_sessions (patient_id, quiz_template_id, status='started')
   │ Set expiration_date = started_at + 48 hours
   │
   ├─> Check: Only one active session allowed (partial unique index)
   └─> Trigger: Send first question via WhatsApp
       │
       ▼
2. Patient Responds to Questions
   │
   │ For each question:
   │   INSERT INTO quiz_responses (
   │     patient_id,
   │     quiz_session_id,
   │     question_id,
   │     response_value (JSONB),
   │     responded_at
   │   )
   │   UPDATE quiz_sessions SET
   │     current_question = current_question + 1,
   │     answered_questions = answered_questions + 1
   │
   ├─> Check: Unique constraint (quiz_session_id, question_id)
   └─> Trigger: Send next question or completion message
       │
       ▼
3. Complete Quiz Session
   │
   │ UPDATE quiz_sessions SET
   │   status = 'completed',
   │   completed_at = NOW(),
   │   score = calculated_score,
   │   passed = (score >= passing_score)
   │
   ├─> Trigger: Alert generation (if thresholds exceeded)
   └─> Trigger: Update flow_analytics
       │
       ▼
4. Generate Alerts (if needed)
   │
   │ INSERT INTO alerts (
   │   patient_id,
   │   type,
   │   severity,
   │   message,
   │   data.quiz_session_id
   │ )
   │
   └─> Notify: Doctor notification
```

**Database Tables:**
1. `quiz_templates` - Quiz definition
2. `quiz_sessions` - Active session
3. `quiz_responses` - Patient answers (JSONB)
4. `alerts` - Generated alerts

**Response Value JSONB Examples:**
```json
// Multiple choice
{
  "selected": ["option1", "option2"]
}

// Scale (1-10)
{
  "value": 7,
  "type": "scale"
}

// Open text
{
  "text": "Patient's written response"
}

// Boolean
{
  "text": "yes",
  "boolean": true
}
```

---

## Message Delivery Flow

### WhatsApp Message Lifecycle

```
1. Create Message
   │
   │ INSERT INTO messages (
   │   patient_id,
   │   direction='outbound',
   │   type,
   │   content,
   │   idempotency_key,  -- Prevent duplicates
   │   priority,
   │   status='pending'
   │ )
   │
   └─> Check: Unique (patient_id, idempotency_key)
       │
       ▼
2. Schedule for Delivery
   │
   │ UPDATE messages SET
   │   status = 'scheduled',
   │   scheduled_for = NOW() + delay
   │
   └─> Trigger: Celery task (priority queue)
       │
       ▼
3. Send via WhatsApp (Celery Worker)
   │
   │ UPDATE messages SET status = 'sending'
   │ Call: Evolution API / Twilio
   │   └─> Success:
   │       UPDATE messages SET
   │         status = 'sent',
   │         sent_at = NOW(),
   │         whatsapp_id = response.id
   │   └─> Failure:
   │       UPDATE messages SET
   │         status = 'failed',
   │         failure_reason = error,
   │         retry_count = retry_count + 1
   │
   └─> If failed: Schedule retry (exponential backoff)
       │
       ▼
4. Webhook Status Updates
   │
   │ Webhook: message.delivered
   │   UPDATE messages SET
   │     status = 'delivered',
   │     delivered_at = NOW()
   │
   │ Webhook: message.read
   │   UPDATE messages SET
   │     status = 'read',
   │     read_at = NOW()
   │
   └─> Insert: webhook_idempotency (prevent replay)
```

**Database Tables:**
1. `messages` - Message records
2. `webhook_idempotency` - Deduplication
3. `message_status_events` - Status history (not in current models)

**Idempotency Key Generation:**
```python
idempotency_key = f"{patient_id}:{message_type}:{content_hash}:{timestamp}"
```

---

## Treatment Management Flow

### Treatment Lifecycle

```
1. Create Treatment Plan
   │
   │ INSERT INTO treatments (
   │   patient_id,
   │   doctor_id,
   │   treatment_type,
   │   status='planned',
   │   start_date,
   │   protocol
   │ )
   │
   └─> Trigger: Appointment scheduling
       │
       ▼
2. Add Medications
   │
   │ For each medication:
   │   INSERT INTO medications (
   │     patient_id,
   │     treatment_id,
   │     prescribed_by_id,
   │     name,
   │     dosage,
   │     frequency,
   │     prescription_date
   │   )
   │
   └─> Trigger: Patient notification
       │
       ▼
3. Schedule Appointments
   │
   │ INSERT INTO appointments (
   │   patient_id,
   │   practitioner_id,
   │   appointment_type,
   │   scheduled_at
   │ )
   │
   └─> Trigger: Appointment reminders
       │
       ▼
4. Track Progress
   │
   │ UPDATE treatments SET
   │   status = 'active',
   │   completed_sessions = completed_sessions + 1
   │
   └─> Trigger: Update flow_analytics
       │
       ▼
5. Complete Treatment
   │
   │ UPDATE treatments SET
   │   status = 'completed',
   │   end_date = NOW()
   │
   │ UPDATE medications SET
   │   is_active = false,
   │   discontinued_date = NOW()
   │
   └─> Trigger: Generate medical_report
```

**Database Tables:**
1. `treatments` - Treatment plan
2. `medications` - Prescriptions
3. `appointments` - Scheduled visits
4. `medical_reports` - Summary reports

---

## Authentication Flow

### Login Process

```
1. User Attempts Login
   │
   │ POST /api/v2/auth/login
   │   {email, password}
   │
   └─> Check: Rate limiting (5 attempts/minute)
       │
       ▼
2. Authenticate User
   │
   │ SELECT * FROM users WHERE email = ?
   │   └─> Verify: bcrypt.checkpw(password, hashed_password)
   │       └─> Success:
   │           INSERT INTO sessions (
   │             user_id,
   │             session_token (JWT),
   │             device_id,
   │             ip_address,
   │             expires_at = NOW() + 24 hours
   │           )
   │           INSERT INTO audit_logs (LOGIN_SUCCESS)
   │           RESET users.failed_login_attempts = 0
   │       └─> Failure:
   │           INSERT INTO audit_logs (LOGIN_FAILURE)
   │           UPDATE users SET
   │             failed_login_attempts = failed_login_attempts + 1
   │           IF failed_login_attempts >= 5:
   │             UPDATE users SET
   │               is_locked = true,
   │               locked_until = NOW() + 30 minutes
   │             INSERT INTO audit_logs (ACCOUNT_LOCKED)
   │
   └─> Return: JWT token + refresh token
       │
       ▼
3. Session Management
   │
   │ On each request:
   │   UPDATE sessions SET last_activity = NOW()
   │   CHECK: expires_at > NOW()
   │   CHECK: is_active = true
   │
   └─> If expired or invalid:
       UPDATE sessions SET is_active = false
       INSERT INTO audit_logs (SESSION_EXPIRED)
```

**Database Tables:**
1. `users` - User accounts
2. `sessions` - Active sessions
3. `audit_logs` - Security events

---

## Flow Engine Execution

### Versioned Flow Execution

```
1. Select Active Flow Version
   │
   │ SELECT ftv.* FROM flow_template_versions ftv
   │ JOIN flow_kinds fk ON fk.id = ftv.flow_kind_id
   │ WHERE fk.kind_key = 'onboarding'
   │ AND ftv.is_active = true
   │ ORDER BY ftv.version_number DESC
   │ LIMIT 1
   │
   └─> Get latest active version
       │
       ▼
2. Initialize Patient Flow State
   │
   │ INSERT INTO patient_flow_states (
   │   patient_id,
   │   flow_template_version_id,
   │   current_step = 0,
   │   status = 'active'
   │ )
   │
   └─> Start flow execution
       │
       ▼
3. Execute Flow Steps
   │
   │ For each step in ftv.steps (JSONB):
   │   - Load message from flow_messages
   │   - Evaluate conditions
   │   - Send message via WhatsApp
   │   - Wait for response
   │   - UPDATE patient_flow_states SET
   │       current_step = current_step + 1,
   │       step_data = {...}  # Store response
   │
   └─> Track in flow_analytics
       │
       ▼
4. Complete Flow
   │
   │ UPDATE patient_flow_states SET
   │   status = 'completed',
   │   completed_at = NOW()
   │
   │ UPDATE flow_analytics SET
   │   completion_rate = 1.0,
   │   engagement_score = calculated_score
   │
   └─> Trigger next flow or exit
```

**Database Tables:**
1. `flow_kinds` - Flow type definitions
2. `flow_template_versions` - Versioned templates
3. `patient_flow_states` - Patient progress
4. `flow_messages` - Template messages
5. `flow_analytics` - Performance metrics

---

## Alert Generation Flow

### Real-Time Alert Processing

```
1. Trigger Event
   │
   │ Sources:
   │   - Quiz completion (high-risk responses)
   │   - Message patterns (negative sentiment)
   │   - Scheduled checks (missed appointments)
   │
   └─> Evaluate alert rules
       │
       ▼
2. Evaluate Alert Criteria
   │
   │ IF quiz_response.response_value @> '{"value": 9, "type": "scale"}'
   │ AND question_id = 'pain_level'
   │ THEN severity = 'critical'
   │
   └─> Generate alert
       │
       ▼
3. Create Alert Record
   │
   │ INSERT INTO alerts (
   │   patient_id,
   │   type = 'high_pain_level',
   │   severity = 'critical',
   │   message = 'Patient reported pain level 9/10',
   │   data = {
   │     "quiz_session_id": "...",
   │     "question_id": "pain_level",
   │     "response_value": 9
   │   },
   │   acknowledged = false
   │ )
   │
   └─> Trigger notification
       │
       ▼
4. Send Notification
   │
   │ INSERT INTO notifications (
   │   user_id = patient.doctor_id,
   │   related_patient_id = patient.id,
   │   notification_type = 'alert',
   │   priority = 'urgent',
   │   title = 'Patient Alert: High Pain Level',
   │   message = '...',
   │   action_url = '/patients/{patient_id}/alerts'
   │ )
   │
   └─> Push notification / Email / SMS
```

**Database Tables:**
1. `alerts` - Alert records
2. `notifications` - User notifications
3. `quiz_responses` - Trigger source

---

## Data Flow Patterns

### Transactional Consistency

**Database Transactions:**
```python
with db.begin():
    # All or nothing
    patient = create_patient(...)
    flow_state = create_flow_state(patient.id, ...)
    message = create_message(patient.id, ...)

    db.flush()  # Check constraints

    # If any fails, rollback all
```

### Eventual Consistency

**Celery Tasks:**
```python
# Immediate: Create record
patient = create_patient(...)
db.commit()

# Async: Send notification
send_welcome_message.delay(patient.id)
```

### Optimistic Locking

**Prevent Race Conditions:**
```python
# Load with version
flow_state = db.query(PatientFlowState).filter_by(id=...).first()

# Modify
flow_state.current_step += 1
flow_state.version += 1

# Save with version check
db.execute(
    update(PatientFlowState)
    .where(
        PatientFlowState.id == flow_state.id,
        PatientFlowState.version == old_version
    )
    .values(...)
)

if db.rowcount == 0:
    raise ConcurrentModificationError()
```

---

## See Also

- [SCHEMA_OVERVIEW.md](./SCHEMA_OVERVIEW.md) - Schema organization
- [RELATIONSHIPS.md](./RELATIONSHIPS.md) - Table relationships
- [TABLES_REFERENCE.md](./TABLES_REFERENCE.md) - Table details
- [/docs/architecture/](../architecture/) - System architecture
