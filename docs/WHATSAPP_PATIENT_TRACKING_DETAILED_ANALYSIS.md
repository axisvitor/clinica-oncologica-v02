# WhatsApp Patient Tracking - Comprehensive Business Logic Analysis

**Analysis Date:** November 5, 2025  
**Codebase:** Clínica Oncológica Backend (Hormonia)  
**Scope:** Very Thorough - All systems examined  

---

## Executive Summary

The WhatsApp patient tracking system implements a sophisticated distributed architecture for managing patient communication workflows. It combines:
- **Saga Pattern** for atomic patient onboarding
- **Event-Driven Flow Engine** for step-by-step patient journeys
- **Celery Task Queue** for asynchronous message processing
- **Redis-based Rate Limiting** for API protection
- **Dead Letter Queue (DLQ)** for failed message recovery
- **Idempotency** guarantees to prevent duplicate messages

**Key Finding:** The system has comprehensive error handling and recovery mechanisms, but shows minimal production usage (mostly test data with 0 active flows in production).

---

# 1. PATIENT JOURNEY - Complete Flow

## 1.1 Stage: Patient Registration & Onboarding Saga

**Entry Point:** `POST /api/v2/patients` (Rate Limited: 20/hour)

**System:** Saga Orchestrator Pattern
**File:** `app/coordination/saga_orchestrator.py`
**Status Enum:** `SagaStatus` (PENDING, RUNNING, COMPLETED, COMPENSATING, COMPENSATED, FAILED)
**Retry Logic:** 3 max retries with exponential backoff

### Saga Steps Sequence:

```
Step 0: STARTED
  ↓
Step 1: STEP_1_PATIENT_CREATED
  - Create patient record in database
  - Unique constraints: phone, cpf
  - Default flow_state: FlowState.ONBOARDING
  - Default current_day: 0
  - Compensation: Delete patient if later steps fail
  ↓
Step 2: STEP_2_FIREBASE_USER_CREATED (optional)
  - Create Firebase auth user
  - Compensation: Delete Firebase user
  ↓
Step 3: STEP_3_FLOW_INITIALIZED
  - Create PatientFlowState record
  - Assign flow template version (initial_15_days)
  - Initialize step_data with patient context
  - Compensation: Mark flow as failed
  ↓
Step 4: STEP_4_MESSAGE_SENT
  - Send welcome message via WhatsApp
  - Compensation: Log message failure (no undo)
  ↓
COMPLETED
```

**Code Reference:** `PatientOnboardingSaga` model (lines 33-47)
- `status`: Current saga state
- `current_step`: 0-4 tracking
- `retry_count`: Number of attempts
- `max_retries`: Default 3
- `execution_log`: JSONB array of all step executions
- `next_retry_at`: Scheduled retry time
- `error_message` & `error_type`: Failure details

**Failure Handling:**
- If any step fails: Transitions to FAILED or COMPENSATING
- Triggers compensating transactions in reverse order
- Can be manually retried if `can_retry()` returns true
- Max retries = 3 (configurable)
- Exponential backoff between retries

---

## 1.2 Patient State Management

**Patient Model:** `app/models/patient.py::Patient`

### Flow States (Enum):
```python
class FlowState(enum.Enum):
    ONBOARDING = "onboarding"        # Initial 15-day onboarding
    ACTIVE = "active"                 # Actively receiving messages
    PAUSED = "paused"                 # Temporarily paused
    COMPLETED = "completed"           # Flow completed
    CANCELLED = "cancelled"           # Cancelled/Inactive
```

### Patient Attributes Tracked:
- `id` (UUID, PK)
- `doctor_id` (FK to users)
- `phone` (unique, indexed)
- `name` (required)
- `flow_state` (enum, default: ONBOARDING)
- `current_day` (integer, default: 0)
- `treatment_type`, `treatment_start_date`
- `cpf`, `diagnosis`, `treatment_phase` (indexed)
- `doctor_notes` (text)
- `patient_data` (JSONB metadata)
- `deleted_at` (soft delete support)

### Relationships:
- `messages` → Message (cascade delete)
- `flow_states` → PatientFlowState (cascade delete)
- `quiz_sessions` → QuizSession (cascade delete)
- `onboarding_sagas` → PatientOnboardingSaga (cascade delete)

---

## 1.3 Message Model & Lifecycle

**Message Model:** `app/models/message.py::Message`

### Status States:
```python
class MessageStatus(enum.Enum):
    PENDING = "pending"              # Created, not yet sent
    SCHEDULED = "scheduled"          # Scheduled for future delivery
    SENDING = "sending"              # Currently being sent by Celery
    SENT = "sent"                    # Successfully sent to WhatsApp
    DELIVERED = "delivered"          # Delivered to patient
    READ = "read"                    # Patient has read
    FAILED = "failed"                # Delivery failed
    CANCELLED = "cancelled"          # Cancelled before sending
```

### Delivery Status (Detailed Tracking):
```python
class DeliveryStatus(enum.Enum):
    SCHEDULED = "scheduled"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

### Message Types:
```python
class MessageType(enum.Enum):
    TEXT = "text"
    BUTTON = "button"
    LIST = "list"
    MEDIA = "media"
    LOCATION = "location"
    QUIZ_INTRO = "quiz_intro"
    QUIZ_QUESTION = "quiz_question"
    QUIZ_ENCOURAGEMENT = "quiz_encouragement"
    QUIZ_COMPLETION = "quiz_completion"
    MONTHLY_QUIZ_LINK = "monthly_quiz_link"
    MONTHLY_QUIZ_REMINDER = "monthly_quiz_reminder"
    MONTHLY_QUIZ_EXPIRED = "monthly_quiz_expired"
    MONTHLY_QUIZ_COMPLETED = "monthly_quiz_completed"
```

### Message Fields:
- `patient_id` (FK, cascade delete)
- `direction` (INBOUND | OUTBOUND)
- `type` (MessageType enum)
- `content` (text, max 4096 chars)
- `message_metadata` (JSONB)
- `idempotency_key` (SHA256 hash, prevents duplicates)
- `whatsapp_id` (Evolution API message ID)
- `status` (MessageStatus)
- `delivery_status` (DeliveryStatus)
- `scheduled_for` (datetime for scheduled messages)
- `sent_at`, `delivered_at`, `read_at` (timestamps)
- `retry_count` (integer)
- `last_retry_at` (datetime)
- `failure_reason` (text)
- `next_retry_at` (datetime for retries)

---

# 2. MESSAGE FLOW & TRIGGERING LOGIC

## 2.1 Message Scheduling & Sending Pipeline

**Architecture:** Multi-layered with 4 convergence points

### Layer 1: Entry Points (Message Initiation)

Multiple services can trigger messages:
- `MessageSender` (main service)
- `FlowEngine` (flow step execution)
- `MonthlyQuizService` (quiz links)
- `PatientService` (welcome messages)

### Layer 2: Unified Routing Service

**Service:** `UnifiedWhatsAppService` (`app/services/unified_whatsapp_service.py`)

Determines messaging mode:
```python
class MessagingMode(str, Enum):
    QUEUE = "queue"      # Queue-based with retry/backoff
    DIRECT = "direct"    # Direct sending without queue
    LEGACY = "legacy"    # Legacy mode (deprecated)
```

**Decision Logic:**
- QUEUE mode: Bulk messages, scheduled messages, high-priority flows
- DIRECT mode: Immediate simple messages
- Default: QUEUE (ensures reliability)

### Layer 3: Queue Processing

**For QUEUE mode:**
1. Message created in database with `status=PENDING`
2. Message queued to WhatsApp queue
3. `WhatsAppMessageService` processes queue
4. `WhatsAppHelper` applies rate limiting
5. Message status transitions to `SENDING`

### Layer 4: Evolution API Client (Convergence Point)

**Single source of truth** for WhatsApp API communication:
- Implements retry logic with exponential backoff
- Handles rate limiting at API level
- Manages instance connections
- Processes webhooks

---

## 2.2 Message Scheduling Workflow

**Service:** `MessageScheduler` (`app/services/message_scheduler.py`)

### Scheduling Windows (Time-based):
```python
class SchedulingWindow(Enum):
    MORNING = (9:00, 12:00)
    AFTERNOON = (12:00, 17:00)
    EVENING = (17:00, 20:00)
    BUSINESS_HOURS = (9:00, 18:00)
    EXTENDED_HOURS = (8:00, 21:00)
```

### Optimal Delivery Time Calculation:

**Steps:**
1. Get patient timezone from metadata (default: "America/Sao_Paulo")
2. Get current time in patient timezone
3. Check if within scheduling window:
   - **If yes:** Schedule 15 minutes from now
   - **If no:** Schedule next window start time
4. Convert back to UTC
5. Ensure time is not in the past (fallback: 30 minutes from now)

**Code:** `_calculate_optimal_delivery_time()` (lines 582-648)

### Celery Task Scheduling:

**Once optimal time calculated:**
1. Create Message record in database
2. Save `scheduled_for` timestamp
3. Use distributed lock: `async_message_delivery_lock(patient_id, timeout=10)`
4. Call `send_flow_message.apply_async(eta=delivery_time)`
5. Store Celery task ID in message metadata

**Distributed Lock Purpose:** Ensures messages for same patient are scheduled in correct order (prevents race conditions)

---

## 2.3 Message Sending Trigger Points

### Automatic Triggers:

**1. Celery Beat (Scheduled Tasks)**

```python
celery_app.conf.beat_schedule = {
    "process-scheduled-messages": {
        "task": "process_scheduled_messages",
        "schedule": 30.0,  # Every 30 seconds
        "kwargs": {"limit": 100}
    },
    "process-daily-flows": {
        "task": "app.tasks.flows.process_daily_flows",
        "schedule": 3600.0,  # Every hour
        "kwargs": {"limit": 100}
    },
    "check-expired-quiz-links": {
        "task": "app.tasks.quiz_link_tasks.check_expired_links",
        "schedule": 1800.0,  # Every 30 minutes
        "kwargs": {"limit": 100}
    },
    "process-monthly-quizzes": {
        "task": "app.tasks.flows.process_monthly_quizzes",
        "schedule": 3600.0,  # Every hour
        "kwargs": {"limit": 100}
    }
}
```

**2. Flow Engine Execution**

**Service:** `FlowEngine` (`app/services/flow_engine.py`)

When patient transitions flow steps:
- Execute MESSAGE step → send_message()
- Message type determined by flow template
- Content personalized based on patient context
- Scheduled according to window settings

**3. Manual API Trigger**

Endpoint: `POST /api/messages` or `POST /api/flow/send-message`

Allows doctors/admins to send messages manually with same scheduling logic.

---

## 2.4 Message Sequence & Timing Rules

### Processing Messages in Scheduled Window:

**File:** `app/tasks/messaging.py::process_scheduled_messages()`

**Algorithm:**
```
1. Query: SELECT * FROM messages 
   WHERE status = 'SCHEDULED' 
   AND scheduled_for <= NOW()
   ORDER BY scheduled_for ASC
   LIMIT {limit}

2. For each message:
   a. Check idempotency (prevent duplicates)
   b. Get patient phone number
   c. Call WhatsApp Evolution API
   d. On success:
      - Set status = SENT
      - Set whatsapp_id = API response ID
      - Set sent_at = NOW()
      - Broadcast WebSocket event
   e. On failure:
      - Determine if retryable
      - If yes: Schedule retry
      - If no: Route to DLQ

3. Return: {total_processed, successful, failed}
```

### Retry Logic:

**Policies by Message Type:**

```python
retry_policies = {
    "default": {
        "max_retries": 3,
        "backoff_factor": 2,      # 5min, 10min, 20min
        "base_delay": 300         # 5 minutes
    },
    "flow_message": {
        "max_retries": 5,
        "backoff_factor": 1.5,    # 3min, 4.5min, 6.75min, ...
        "base_delay": 180         # 3 minutes
    },
    "quiz_message": {
        "max_retries": 3,
        "backoff_factor": 2,
        "base_delay": 300
    }
}
```

**Backoff Calculation:**
```
delay = base_delay * (backoff_factor ^ retry_count)
scheduled_for = NOW() + delay
```

Example for default policy:
- Attempt 1 fails: Retry in 5 minutes
- Attempt 2 fails: Retry in 10 minutes
- Attempt 3 fails: Retry in 20 minutes
- Attempt 4 fails: Send to DLQ (permanent failure)

---

# 3. AUTOMATION LOGIC

## 3.1 What's Automated vs Manual

### Fully Automated:

**Patient Onboarding:**
- ✅ Patient creation (Saga)
- ✅ Welcome message
- ✅ Flow initialization
- ✅ Compensation on failure

**Daily Message Processing:**
- ✅ Scheduled message pickup (every 30s)
- ✅ Optimal delivery time calculation
- ✅ Celery task scheduling
- ✅ Message sending via Evolution API
- ✅ Status updates (sent, delivered, read)
- ✅ Retry logic (automatic backoff)

**Flow Progression:**
- ✅ Daily flow processing (hourly)
- ✅ Step condition evaluation
- ✅ Step type execution (MESSAGE, QUESTION, ACTION)
- ✅ Next step scheduling
- ✅ Completion detection

**Quiz Management:**
- ✅ Quiz trigger checking (every 2 hours)
- ✅ Token generation for links
- ✅ Link expiry checking (every 30 min)
- ✅ Reminder sending
- ✅ Automatic token rotation

**Alert Processing:**
- ✅ Alert evaluation (every 5 min from Celery)
- ✅ Severity detection
- ✅ Notification routing
- ✅ Escalation logic

### Manual (Doctor-Initiated):

- 📝 Create patient
- 📝 Send ad-hoc message to patient
- 📝 Update patient information
- 📝 Cancel scheduled messages
- 📝 Reschedule messages
- 📝 Review failed messages from DLQ
- 📝 Pause/resume patient flow

### Semi-Automated:

- 🔄 Saga retry (automatic but can trigger manually)
- 🔄 DLQ processing (manual review then automatic retry)
- 🔄 Alert escalation (automatic but depends on rules)

---

## 3.2 Task Triggering Mechanisms

### Celery Beat Schedule (Primary):

**File:** `app/celery_app.py` (lines 84-147)

5 main periodic tasks:

```
┌─────────────────────────────────────┐
│  Celery Beat Scheduler              │
├─────────────────────────────────────┤
│ Every 30s: process_scheduled_messages      │
│ Every 5m:  retry_failed_messages           │
│ Every 1h:  process_daily_flows             │
│ Every 30m: check_expired_quiz_links        │
│ Every 1h:  process_monthly_quizzes         │
└─────────────────────────────────────┘
```

### Webhook Triggers (Event-Driven):

**Endpoint:** `POST /webhooks/whatsapp/evolution/{instance_name}`

**Events from Evolution API:**
- `message_send`: Message sent
- `message_status`: Status update (delivered, read)
- `message_received`: Patient response
- `connection_status`: Instance online/offline
- `media_upload`: Media availability

### Manual Triggers:

**API Endpoints:**
- `POST /api/messages` - Send message immediately
- `POST /api/messages/{id}/reschedule` - Reschedule message
- `POST /api/messages/{id}/cancel` - Cancel scheduled
- `POST /api/patients/{id}/send-message` - Send flow message

---

## 3.3 Flow Engine Task Processing

**Service:** `FlowEngine` (`app/services/flow_engine.py` - limited view shown)

**Celery Task:** `process_daily_flows()`

**Execution:**
```
1. Query all patients with flow_state IN (ONBOARDING, ACTIVE)
2. For each patient:
   a. Load patient data
   b. Load current flow state
   c. Load flow template version
   d. Build execution context:
      - patient_data (name, phone, treatment info)
      - flow_data (current step, state_data)
      - quiz_responses (recent quizzes)
      - message_count (engagement metric)
      - current_time (for time-based conditions)
   e. Evaluate step conditions:
      - quiz_response conditions
      - time_based conditions
      - patient_data conditions
      - message_count conditions
   f. If conditions met:
      - Execute current step
      - Transition to next step
      - Schedule next execution
   g. If not met:
      - Log condition failure
      - Retry next cycle
3. Return metrics:
   - total_patients_processed
   - successful_transitions
   - failed_transitions
   - errors
```

---

# 4. STATE MANAGEMENT

## 4.1 Patient Flow State Tracking

**Model:** `PatientFlowState` (`app/models/flow.py`)

### States Hierarchy:

```
Global Patient State (patients.flow_state):
├── ONBOARDING
├── ACTIVE
├── PAUSED
├── COMPLETED
└── CANCELLED

Flow-Specific State (patient_flow_states.status):
├── active
├── paused
├── completed
└── failed
```

### State Transitions:

```
ONBOARDING → ACTIVE
  Trigger: Completion of onboarding flow
  
ACTIVE → PAUSED
  Trigger: Doctor action or patient request
  Effect: Messages suspended
  
ACTIVE → COMPLETED
  Trigger: All flow steps completed
  Effect: No more automatic messages
  
PAUSED/COMPLETED/ACTIVE → CANCELLED
  Trigger: Doctor cancellation or patient withdrawal
  Effect: Cascade delete (soft/hard depending on config)
```

### State Data Storage:

**JSONB `state_data` field tracks:**
- `current_step_id`: Current position in flow
- `step_data`: Data from previous steps
- `quiz_responses`: Recent quiz answers
- `message_history`: Recent messages sent
- `status_updates`: Status change history
- `delivery_failures`: Failed message tracking
- `skip_waiting_for_message`: Message failure flags
- `last_delivery_failure`: Timestamp of last failure
- `flow_context`: Flow-specific context

---

## 4.2 Message Status Tracking

**Dual Tracking System:**

**1. Message Table (Current Status):**
```
messages.status = PENDING | SCHEDULED | SENDING | SENT | DELIVERED | READ | FAILED | CANCELLED
```

**2. Message Status Events Table (History):**
```sql
CREATE TABLE message_status_events (
  id UUID PRIMARY KEY,
  message_id UUID FOREIGN KEY,
  old_status VARCHAR,
  new_status VARCHAR,
  timestamp TIMESTAMP,
  details JSONB
);
```

Every status change creates an event record for audit trail.

---

## 4.3 Saga State Machine

**Model:** `PatientOnboardingSaga` (`app/models/patient_onboarding_saga.py`)

### State Transitions:

```
STARTED (created)
   ↓
IN_PROGRESS (any processing)
   ├─ STEP_1_PATIENT_CREATED
   ├─ STEP_2_FIREBASE_USER_CREATED
   ├─ STEP_3_FLOW_INITIALIZED
   ├─ STEP_4_MESSAGE_SENT
   ↓
Success Path:
   COMPLETED (all steps succeeded)
   
Failure Path:
   FAILED (any step failed, max retries not exceeded)
   RETRY_SCHEDULED (pending retry)
   COMPENSATING (executing compensating transactions)
   COMPENSATED (rollback complete)
   FAILED (permanent failure, retries exhausted)
```

### Retry Configuration:

```python
retry_count: Integer         # 0-3 (default max)
max_retries: Integer         # Configured in model
next_retry_at: DateTime      # Scheduled retry time
can_retry(): Boolean         # status in [FAILED, RETRY_SCHEDULED] 
                             # AND retry_count < max_retries
```

---

# 5. BUSINESS RULES & CONSTRAINTS

## 5.1 Scheduling Rules

### Time-Based Constraints:

**1. Optimal Delivery Window:**
- Messages scheduled within patient's preferred window
- Falls back to BUSINESS_HOURS if not specified
- Respects patient timezone (default: America/Sao_Paulo)

**2. Minimum Scheduling Buffer:**
- 15 minutes between message creation and sending
- Prevents race conditions
- Allows for cancellation window

**3. Fallback Delay:**
- If calculated time in past: Use 30 minutes from now
- Ensures messages never scheduled backwards

### Message Frequency Constraints:

**Configurable per flow type:**
- Maximum messages per day
- Minimum interval between messages
- "Quiet hours" (no messages between 22:00-08:00)

**Rate Limiting:**
```python
RATE_LIMITS = {
    "/api/messages/send": (30, 60),     # 30/minute
    "/api/patients": (100, 60),         # 100/minute
    default: (60, 60)                   # 60/minute default
}
```

## 5.2 Retry & Backoff Strategies

### Exponential Backoff Formula:

```
delay_seconds = base_delay * (backoff_factor ^ retry_count)
next_attempt = NOW() + delay
```

### Example Progression (Default Policy):

| Retry | Delay | Total Wait | Status |
|-------|-------|-----------|--------|
| 0 (initial) | - | - | SENDING |
| 1 | 5m | 5m | PENDING (retry) |
| 2 | 10m | 15m | PENDING (retry) |
| 3 | 20m | 35m | PENDING (retry) |
| 4 (exceeded) | - | - | FAILED (DLQ) |

### Jitter (Not Visible in Code):

Actual implementation may add randomization to prevent thundering herd.

---

## 5.3 Delivery Guarantees

### Idempotency:

**Mechanism:** Idempotency Key

```python
idempotency_key = SHA256(patient_id + content + message_type)
```

**Storage:**
- Redis cache (TTL: 24 hours) - fast path
- Database unique constraint - persistent

**Race Condition Handling:**
- Two processes try to send same message simultaneously
- First one commits successfully
- Second detects IntegrityError
- Queries database to find duplicate
- Returns existing message ID (no duplicate sent)

**Code:** `IdempotentMessageSender` (lines 412-632)

### At-Least-Once Delivery:

**Guarantees:**
- Message either sent successfully OR
- Scheduled for retry OR
- Routed to DLQ for manual review

**No message is lost:**
- All states persistent in database
- Webhook confirms delivery (but not required)
- Manual retry always possible

---

# 6. ERROR HANDLING & RECOVERY

## 6.1 Failure Categories

### 1. Network Errors (Transient)

**Detection:** Timeout, connection refused, DNS failure

**Handling:**
- Automatic retry (exponential backoff)
- Max 3 attempts for default messages
- Max 5 attempts for flow messages

**DLQ Route:** If all retries exhausted

### 2. Rate Limiting (Transient)

**Detection:** HTTP 429 or WhatsApp API rate_limit error

**Handling:**
- Immediate queue back
- Retry after rate limit window
- Progressive backoff applied

**Special:** Flow messages get 5 attempts (higher tolerance)

### 3. Invalid Phone Number (Permanent)

**Detection:** WhatsApp API error code for invalid number

**Categorization:**
- `INVALID_PHONE` → Permanent failure
- `BLOCKED_NUMBER` → Permanent failure

**Handling:**
- No retries
- Immediately to DLQ
- Doctor notified

**Code:** `_categorize_failure_reason()` (lines 992-1030)

### 4. API Errors (Various)

**Codes handled:**
- 400: Bad request (invalid format) → Permanent
- 401/403: Authentication → Permanent
- 404: Resource not found → Permanent
- 500/502/503/504: Server errors → Transient (retry)

### 5. Max Retries Exceeded

**Handling:**
- Message marked as FAILED
- Routed to DLQ
- Doctor notified
- Flow engine updated (skip waiting for this message)

---

## 6.2 Error Recovery Strategies

### Automatic Recovery:

**1. Message Retry Queue:**
```
Failed Message → Scheduled Retry → Celery Task
   ↓ (success)      ↓ (failure)      ↓
SENT status      Next Backoff    Retry Check
                                  ↓
                            Max Retries?
                            ├─ No: Loop
                            └─ Yes: DLQ
```

**2. Saga Compensation:**
```
Saga Fails
   ↓
Execute Compensating Transactions
   ├─ Step 4 → (no compensation)
   ├─ Step 3 → Mark flow failed
   ├─ Step 2 → Delete Firebase user
   └─ Step 1 → Delete patient
       ↓
Schedule Retry (3 attempts max)
       ↓
    COMPENSATED or FAILED
```

**3. Flow State Recovery:**

When message delivery fails permanently:
```python
# Update flow state
flow_state.state_data["delivery_failures"].append({
    "message_id": message_id,
    "failure_timestamp": NOW(),
    "failure_reason": reason,
    "retry_count": count,
    "step": current_step
})
flow_state.state_data["skip_waiting_for_message"] = message_id
```

This prevents flow from waiting for response that won't arrive.

### Manual Recovery:

**1. DLQ Review:**
- Failed message appears in `whatsapp_delivery_failures` table
- Doctor can review failure reason
- Can manually retry message
- Can manually advance flow

**2. Saga Retry:**
- Failed saga retrievable by saga_id
- Can manually trigger retry
- View execution log of all attempts
- See error details

---

## 6.3 Dead Letter Queue (DLQ) System

**Model:** `FailedMessage` (`app/models/failed_message.py`)

**Table:** `whatsapp_delivery_failures`

### DLQ Content:

```python
class FailedMessage(BaseModel):
    patient_id: UUID
    phone_number: String(20)
    message_type: String(50)
    message_content: Text
    error_message: Text
    error_code: String(50)
    retry_count: Integer
    max_retries: Integer
    next_retry_at: DateTime
    last_retry_at: DateTime
    status: String  # pending_review | under_review | resolved | discarded
    resolved_at: DateTime
    dlq_metadata: JSONB  # Additional context
    reviewed_by: UUID (FK to users)
    original_message_id: UUID (FK to messages)
```

### DLQ Processing:

**Task:** `process_dead_letter_queue()` (every 2 hours)

**Workflow:**
```
1. Query: DLQ items with status = pending_review
2. Categorize failure:
   - NETWORK_ERROR → Try automatic retry
   - RATE_LIMIT → Queue for later
   - INVALID_PHONE → Mark as resolved (user error)
   - BLOCKED_NUMBER → Mark as resolved
   - API_ERROR → Manual review needed
3. Action:
   - If auto-retryable: Reschedule message
   - If manual needed: Notify doctor
   - If resolved: Update status
4. Create DLQ audit entry
```

### DLQ Statuses:

```
pending_review → under_review → resolved
                             → discarded
```

---

# 7. RATE LIMITING IMPLEMENTATION

## 7.1 Rate Limiter Architecture

**Middleware:** `RateLimitMiddleware` (`app/middleware/rate_limiter.py`)

**Implementation:** Token Bucket Algorithm

### Token Bucket Logic:

```python
def is_allowed(key: str) -> (bool, Optional[int]):
    current = time.time()
    time_passed = current - last_check[key]
    last_check[key] = current
    
    # Replenish tokens
    allowance[key] += time_passed * (rate / per)
    
    # Cap at maximum
    if allowance[key] > rate:
        allowance[key] = rate
    
    # Check allowance
    if allowance[key] < 1.0:
        retry_after = int((1.0 - allowance[key]) * (per / rate))
        return False, retry_after
    
    # Consume token
    allowance[key] -= 1.0
    return True, None
```

**Parameters:**
- `rate`: Number of tokens (requests allowed)
- `per`: Time window in seconds
- `allowance`: Current token count (replenished over time)
- `last_check`: Last check timestamp

### Rate Limit Configuration:

```python
RATE_LIMITS = {
    "/api/auth/login": (5, 60),           # 5/minute
    "/api/auth/register": (3, 60),        # 3/minute
    "/api/messages/send": (30, 60),       # 30/minute
    "/api/patients": (100, 60),           # 100/minute
    "/ws": (10, 60),                      # 10 connections/minute
    "default": (60, 60)                   # 60/minute default
}
```

---

## 7.2 Client Identification

**Priority Order:**

```
1. Authenticated User ID (from JWT token)
   Format: "user:{user_id}"
   
2. API Key
   Format: "api:{api_key}"
   
3. IP Address
   Format: "ip:{ip_address}"
   
4. X-Forwarded-For (proxy detection)
   Splits on comma, takes first IP
```

**Code:** `_get_client_id()` (lines 134-160)

---

## 7.3 Adaptive Rate Limiting (Optional)

**Class:** `AdaptiveRateLimiter` (extends `RateLimiter`)

**Features:**
- Reputation scoring per client (0.5 to 2.0 multiplier)
- Dynamic rate adjustment
- Automatic reputation recovery

**Reputation Changes:**
- Good behavior: +0.01 per request
- Violation: -0.1 per repeated violation
- Capped at 0.5 minimum, 2.0 maximum

**Effect:**
- Clean users: 2.0x normal rate
- Bad actors: 0.5x normal rate

---

## 7.4 WhatsApp-Specific Rate Limiting

**Service:** `WhatsAppHelper` (`app/utils/whatsapp_helper.py`)

**Queue Processing with Rate Limit:**

```
Process Queue
   ↓
For each message:
   ├─ Check Evolution API rate limits
   ├─ Calculate backoff if near limit
   ├─ Send message (or queue if rate limited)
   ├─ Update message status
   └─ Execute callbacks
```

**Rate Limit Response:**
```python
HTTP 429 Too Many Requests
{
    "error": "rate_limit_exceeded",
    "retry_after": 60,
    "limit": "20/minute"
}
```

---

# 8. MESSAGE FLOW DIAGRAM (Complete)

```
┌────────────────────────────────────────────────────────────┐
│ PATIENT REGISTRATION (Saga Pattern)                        │
├────────────────────────────────────────────────────────────┤
│                                                             │
│ POST /api/v2/patients                                      │
│     ↓                                                       │
│ SagaOrchestrator.execute_patient_onboarding()             │
│     ↓                                                       │
│ Step 1: Create Patient Record                             │
│     ├─ Validate data                                       │
│     ├─ Check unique constraints (phone, cpf)              │
│     ├─ Insert into patients table                         │
│     └─ flow_state = ONBOARDING, current_day = 0           │
│     ↓                                                       │
│ [If Step 1 succeeds]                                      │
│ Step 2: Initialize Flow State                             │
│     ├─ Create PatientFlowState record                     │
│     ├─ Link to flow template (initial_15_days)            │
│     └─ state_data = empty JSONB                           │
│     ↓                                                       │
│ [If Step 2 succeeds]                                      │
│ Step 3: Send Welcome Message                              │
│     ├─ Create Message record                              │
│     ├─ type = TEXT, direction = OUTBOUND                  │
│     ├─ status = PENDING                                   │
│     ├─ Call WhatsApp Evolution API                        │
│     ├─ Set whatsapp_id on success                         │
│     └─ status = SENT                                       │
│     ↓                                                       │
│ [Success]                                                  │
│ Mark Saga as COMPLETED                                    │
│ Return patient ID to API                                  │
│     ↓                                                       │
│ [If any step fails]                                       │
│ Saga.status = FAILED                                      │
│ Saga.error_message = error details                        │
│ Saga.next_retry_at = NOW() + backoff                      │
│ Schedule automatic retry (max 3)                          │
│                                                             │
└────────────────────────────────────────────────────────────┘


┌────────────────────────────────────────────────────────────┐
│ DAILY MESSAGE SCHEDULING & SENDING                         │
├────────────────────────────────────────────────────────────┤
│                                                             │
│ Celery Beat triggers process_daily_flows()               │
│ (or process_scheduled_messages for messages)              │
│     ↓                                                       │
│ [Every hour for flows, every 30s for messages]            │
│     ↓                                                       │
│ Query: SELECT * FROM messages                             │
│        WHERE status = 'SCHEDULED'                          │
│        AND scheduled_for <= NOW()                          │
│        LIMIT {limit}                                       │
│     ↓                                                       │
│ For each message:                                         │
│     ├─ Check idempotency key                              │
│     │   ├─ Check Redis cache                              │
│     │   └─ Check database unique constraint               │
│     │       (Prevents duplicate sends)                     │
│     ├─ Get patient phone number                           │
│     ├─ Format for WhatsApp (+55 Brazil format)           │
│     ├─ Call UnifiedWhatsAppService.send_message()        │
│     │   ├─ Determine mode (QUEUE/DIRECT/LEGACY)          │
│     │   └─ Route through appropriate pipeline             │
│     ├─ On Success:                                        │
│     │   ├─ message.status = SENT                          │
│     │   ├─ message.whatsapp_id = API response ID          │
│     │   ├─ message.sent_at = NOW()                        │
│     │   ├─ Create MessageStatusEvent (audit)              │
│     │   ├─ Broadcast WebSocket event (real-time UI)       │
│     │   └─ Execute any registered callbacks               │
│     ├─ On Failure:                                        │
│     │   ├─ Categorize failure:                            │
│     │   │   ├─ Network? → Transient                       │
│     │   │   ├─ Rate limit? → Transient                    │
│     │   │   ├─ Invalid phone? → Permanent                 │
│     │   │   └─ API error? → Depends on code               │
│     │   ├─ If transient + retries < max:                  │
│     │   │   ├─ Calculate backoff delay                    │
│     │   │   ├─ message.retry_count++                      │
│     │   │   ├─ message.next_retry_at = NOW() + delay      │
│     │   │   ├─ message.status = PENDING                   │
│     │   │   └─ Schedule Celery retry task (with ETA)     │
│     │   └─ If permanent or max retries:                   │
│     │       ├─ message.status = FAILED                    │
│     │       ├─ message.failure_reason = reason            │
│     │       ├─ Route to DLQ                               │
│     │       └─ Notify flow engine (skip waiting)          │
│     └─ Commit transaction                                 │
│     ↓                                                       │
│ Return: {processed, successful, failed}                   │
│                                                             │
└────────────────────────────────────────────────────────────┘


┌────────────────────────────────────────────────────────────┐
│ FLOW PROGRESSION (Daily)                                   │
├────────────────────────────────────────────────────────────┤
│                                                             │
│ process_daily_flows() task                                 │
│ (Runs hourly from Celery Beat)                             │
│     ↓                                                       │
│ Query: SELECT patients WHERE                              │
│        flow_state IN ('ONBOARDING', 'ACTIVE')             │
│     ↓                                                       │
│ For each patient:                                         │
│     ├─ Load patient data                                  │
│     ├─ Load current PatientFlowState                      │
│     ├─ Load FlowTemplateVersion                           │
│     ├─ Build execution context:                           │
│     │   ├─ patient_data (name, phone, treatment)          │
│     │   ├─ flow_data (steps, current state)               │
│     │   ├─ quiz_responses (recent answers)                │
│     │   ├─ message_count (engagement metric)              │
│     │   └─ current_time (for time conditions)             │
│     ├─ Get current flow step                              │
│     ├─ Evaluate step conditions:                          │
│     │   ├─ quiz_response conditions                       │
│     │   ├─ time_based conditions                          │
│     │   ├─ patient_data conditions                        │
│     │   └─ message_count conditions                       │
│     ├─ If ALL conditions met:                             │
│     │   ├─ Execute step:                                  │
│     │   │   ├─ MESSAGE → Send message                     │
│     │   │   ├─ QUESTION → Ask question, wait response    │
│     │   │   ├─ DECISION → Evaluate logic                  │
│     │   │   ├─ ACTION → Execute action                    │
│     │   │   ├─ WAIT → Schedule next check                 │
│     │   │   └─ END → Mark flow completed                  │
│     │   ├─ Update state_data                              │
│     │   ├─ Transition to next step                        │
│     │   └─ Schedule next check (time-based)               │
│     ├─ If conditions NOT met:                             │
│     │   ├─ Log condition failure                          │
│     │   └─ Retry next cycle (hourly)                      │
│     └─ Commit changes                                      │
│     ↓                                                       │
│ Return: {processed, successful, failed}                   │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

---

# 9. KEY CODE REFERENCES

## Models:
- `Patient`: `/backend-hormonia/app/models/patient.py` (lines 17-228)
- `Message`: `/backend-hormonia/app/models/message.py` (lines 47-171)
- `PatientFlowState`: `/backend-hormonia/app/models/flow.py` (lines 12-53)
- `PatientOnboardingSaga`: `/backend-hormonia/app/models/patient_onboarding_saga.py` (lines 49-256)
- `FailedMessage (DLQ)`: `/backend-hormonia/app/models/failed_message.py` (lines 34-106)

## Services:
- `SagaOrchestrator`: `/backend-hormonia/app/coordination/saga_orchestrator.py`
- `WhatsAppService`: `/backend-hormonia/app/services/messaging/whatsapp_service.py`
- `MessageScheduler`: `/backend-hormonia/app/services/message_scheduler.py` (lines 76-1095)
- `FlowEngine`: `/backend-hormonia/app/services/flow_engine.py`
- `MessageSender`: `/backend-hormonia/app/services/message_sender.py`
- `IdempotentMessageSender`: `/backend-hormonia/app/services/messaging/whatsapp_service.py` (lines 412-632)

## Tasks:
- `process_daily_flows`: `/backend-hormonia/app/tasks/flows.py`
- `process_scheduled_messages`: `/backend-hormonia/app/tasks/messaging.py`
- Celery Config: `/backend-hormonia/app/celery_app.py` (lines 84-147)

## Rate Limiting:
- `RateLimitMiddleware`: `/backend-hormonia/app/middleware/rate_limiter.py` (lines 72-176)
- `AdaptiveRateLimiter`: `/backend-hormonia/app/middleware/rate_limiter.py` (lines 179-222)

## Documentation:
- Architecture: `/docs/WHATSAPP_MESSAGING_ARCHITECTURE.md`
- Rate Limiting: `/backend-hormonia/docs/RATE_LIMITING.md`
- Patient Journey: `/docs/PATIENT_JOURNEY_ANALYSIS.md`

---

# 10. SUMMARY TABLE

| Aspect | Implementation | Details |
|--------|---|---|
| **Patient States** | 5 enums | ONBOARDING, ACTIVE, PAUSED, COMPLETED, CANCELLED |
| **Message States** | 8 statuses | PENDING, SCHEDULED, SENDING, SENT, DELIVERED, READ, FAILED, CANCELLED |
| **Retry Policy** | Exponential backoff | 3-5 max retries, 2x backoff factor, 3-5min base delay |
| **Scheduling** | Time-window based | 5 windows: MORNING, AFTERNOON, EVENING, BUSINESS, EXTENDED |
| **Rate Limiting** | Token bucket | Per-IP or per-user, 5-100 requests/minute depending on endpoint |
| **Idempotency** | SHA256 hash | 24hr Redis cache + DB unique constraint |
| **Error Recovery** | Multi-level | Automatic retry → DLQ → Manual review |
| **Flow Execution** | Condition-based | Time, quiz response, patient data, message count conditions |
| **Automation** | Celery Beat | 30s, 5m, 1h, 30m schedules for various tasks |
| **Manual Control** | API & Dashboard | Send, reschedule, cancel, review DLQ items |

---

**Analysis Complete**
