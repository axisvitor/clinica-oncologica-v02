# Daily Messaging Flow - Complete Architecture Analysis

**Investigation Date:** 2025-12-24
**Research Agent:** Hive Mind Swarm (ID: swarm-1766595874246-h614td21f)
**Focus:** Daily message sending flow, scheduling mechanisms, and WhatsApp delivery

---

## Executive Summary

The daily messaging system uses a **multi-layered architecture** with Celery Beat scheduling, direct database queries, and WhatsApp integration via Evolution API. The system **DOES NOT use PatientFlowState table** for daily messages but instead queries the **patients table directly** using `flow_state` and `current_day` columns.

### Critical Finding: Two Separate Systems

1. **Daily Flow Questions** → Uses `patients` table directly (lines 276-414 in flow_automation.py)
2. **PatientFlowState System** → Used for quiz triggers and complex flows

---

## 1. Message Scheduling System

### 1.1 Celery Beat Configuration

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/celery_app.py`

```python
# Line 189-193: Daily flow questions scheduler
"send-daily-flow-questions": {
    "task": "flow_automation.send_daily_flow_questions",
    "schedule": crontab(hour=8, minute=0),  # Daily at 8:00 AM UTC
    "options": {"queue": "flows"},
}
```

**Key Details:**
- **Trigger:** Daily at 8:00 AM UTC (5:00 AM São Paulo time)
- **Queue:** `flows` queue for flow-related tasks
- **Task Name:** `flow_automation.send_daily_flow_questions`
- **File Location:** `/app/tasks/flow_automation.py` lines 219-414

### 1.2 Patient Selection Logic

**File:** `/app/tasks/flow_automation.py` lines 276-290

```python
active_patients = (
    db.query(Patient)
    .filter(
        Patient.flow_state == FlowState.ACTIVE,  # Use enum for type safety
        Patient.deleted_at.is_(None),
        Patient.treatment_start_date.isnot(None),
        Patient.phone_encrypted.isnot(None),  # Has phone
    )
    .limit(200)
    .all()
)
```

**Selection Criteria:**
1. ✅ `flow_state == FlowState.ACTIVE`
2. ✅ `deleted_at IS NULL` (not soft-deleted)
3. ✅ `treatment_start_date IS NOT NULL` (treatment started)
4. ✅ `phone_encrypted IS NOT NULL` (has phone for WhatsApp)
5. ⚠️ Limit: 200 patients per run

**CRITICAL ISSUE:** Only 200 patients processed per day. If the system has >200 active patients, some will be skipped.

### 1.3 Message Timing Logic

**Flow Phase Calculation** (lines 297-324):

```python
current_day = patient.current_day or 0

# If current_day is 0, calculate from treatment_start_date
if current_day == 0 and patient.treatment_start_date:
    current_day = (today - patient.treatment_start_date).days + 1

# Determine flow phase and if we should send today
if current_day <= 15:
    # INITIAL_15_DAYS: Daily messages
    flow_phase = "initial_15_days"
    should_send = True

elif current_day <= 45:
    # DAYS_16_45: Every 3 days
    flow_phase = "days_16_45"
    day_in_phase = current_day - 15
    should_send = day_in_phase % 3 == 0

else:
    # MONTHLY_RECURRING: Weekly check-ins (days 0, 7, 14, 21 of each 30-day cycle)
    flow_phase = "monthly_recurring"
    day_in_cycle = (current_day - 45) % 30
    should_send = day_in_cycle in [0, 7, 14, 21]
```

**Message Frequency:**
- **Days 1-15:** Daily (15 messages)
- **Days 16-45:** Every 3 days (10 messages)
- **Days 46+:** Weekly on days 0, 7, 14, 21 of each 30-day cycle (4 messages/month)

---

## 2. Flow State Management

### 2.1 Patient Table Schema

**File:** `/app/models/patient.py` lines 84-91

```python
flow_state = Column(
    Enum(FlowState, values_callable=lambda x: [e.value for e in x], name="flow_state"),
    default=FlowState.ONBOARDING,
    nullable=False,
)
current_day = Column(Integer, default=0, nullable=False)
```

**FlowState Enum Values:**
- `ONBOARDING` - Initial patient registration
- `ACTIVE` - Active treatment flow
- `PAUSED` - Temporarily paused
- `COMPLETED` - Treatment completed
- `CANCELLED` - Cancelled/discontinued

### 2.2 State Transitions

**File:** `/app/domain/flows/core/state_machine.py` lines 141-159

Valid state transitions:
```python
valid_transitions = {
    "initial_15_days": ["days_16_45", "monthly_recurring", "completed"],
    "days_16_45": ["monthly_recurring", "completed"],
    "monthly_recurring": ["completed", "paused"],
    "paused": ["monthly_recurring", "completed"],
    "completed": [],  # No transitions from completed
}
```

### 2.3 Current Day Tracking

**Critical Finding:** The `current_day` field in the `patients` table is **NOT automatically incremented**. It relies on:

1. Manual updates by flow engine
2. Calculation from `treatment_start_date` when `current_day == 0`

**Potential Issue:** If `current_day` is not updated, patients may receive incorrect messages or be skipped.

---

## 3. Message Template System

### 3.1 Template Configuration

**File:** `/app/config/flow_templates.yaml`

```yaml
flow_types:
  daily_checkin:
    name: "Daily Check-in"
    frequency: "daily"

    timing:
      start_hour: 9
      end_hour: 16
      timezone: "America/Sao_Paulo"

    personalization:
      ai_optimization: true
      sentiment_analysis: true
```

### 3.2 Fallback Templates

**File:** `/app/tasks/flow_automation.py` lines 255-275

```python
FLOW_MESSAGES = {
    "initial_15_days": {
        "content": "Olá {patient_name}! 👋 Como você está se sentindo hoje? ...",
        "intent": "daily_checkin_initial",
    },
    "days_16_45": {
        "content": "Olá {patient_name}! 🌟 Esperamos que você esteja bem. ...",
        "intent": "periodic_checkin",
    },
    "monthly_recurring": {
        "content": "Olá {patient_name}! 📋 Esta é sua verificação semanal. ...",
        "intent": "weekly_checkin",
    },
}
```

**Personalization:** Templates use `{patient_name}` placeholder which is replaced with `patient.name` (line 346-348).

### 3.3 Template Loader

**File:** `/app/domain/flows/core/message_template_loader.py` lines 54-121

**Multi-Layer Fallback System:**
1. **Primary:** Load from template_loader (database/YAML)
2. **Fallback:** Use predefined Portuguese templates
3. **Last Resort:** Return None (flow skips the day)

**Error Handling:**
- TemplateLoadError → fallback
- FileNotFoundError → fallback
- Generic exceptions → fallback with full trace

---

## 4. WhatsApp Integration & Delivery

### 4.1 Message Creation

**File:** `/app/tasks/flow_automation.py` lines 350-366

```python
message = Message(
    patient_id=patient.id,
    direction=MessageDirection.OUTBOUND,
    type=MessageType.TEXT,
    content=message_content,
    status=MessageStatus.PENDING,
    message_metadata={
        "source": "daily_flow_question",
        "flow_phase": flow_phase,
        "flow_day": current_day,
        "template_intent": template_data["intent"],
        "patient_phone": patient_phone,
    },
)
```

### 4.2 WhatsApp Service

**File:** `/app/domain/messaging/whatsapp/whatsapp_service.py` lines 158-246

```python
async def send_message(self, message: Message, retry_count: int = 0) -> Dict[str, Any]:
    # Get patient phone
    patient = self.patient_repo.get_by_id(message.patient_id)
    phone_number = self._get_patient_phone(patient)

    # Send via Evolution API
    result = await self._send_via_evolution(
        phone_number=phone_number,
        content=message.content,
        message_type=message.type,
    )

    # Update message status
    message.status = MessageStatus.SENT
    message.whatsapp_id = result.get("key", {}).get("id")
    message.sent_at = datetime.now(timezone.utc)
```

**Phone Number Formatting** (lines 301-322):
```python
def _get_patient_phone(self, patient: Patient) -> str:
    phone = patient.phone_number
    if not phone:
        raise ValueError(f"Patient {patient.id} has no phone number")

    # Format for WhatsApp (remove non-digits, ensure country code)
    phone = "".join(filter(str.isdigit, phone))
    if not phone.startswith("55"):  # Brazil
        phone = "55" + phone

    return phone
```

### 4.3 Evolution API Client

**File:** `/app/integrations/evolution/client.py` lines 163-168

```python
async def send_text_message(self, phone_number: str, message: str, delay: Optional[int] = None) -> Dict[str, Any]:
    """Send text message via WhatsApp."""
    return await self.message_sender.send_text_message(phone_number, message, delay)
```

**Configuration** (lines 56-68):
```python
# URL configuration - prioritize Railway internal service
if self.railway_service and hasattr(settings, "WHATSAPP_EVOLUTION_RAILWAY_URL"):
    self.base_url = settings.WHATSAPP_EVOLUTION_RAILWAY_URL.rstrip("/")
else:
    self.base_url = (
        base_url or
        getattr(settings, "WHATSAPP_EVOLUTION_API_URL", "http://localhost:8080")
    ).rstrip("/")
```

### 4.4 Retry Mechanism

**File:** `/app/domain/messaging/whatsapp/whatsapp_service.py` lines 219-236

```python
except EvolutionAPIError as e:
    logger.error(f"Evolution API error sending message {message.id}: {e}")

    # Handle retry
    if retry_count < self._get_max_retries(message):
        await self._schedule_retry(message, retry_count + 1)
        return {
            "success": False,
            "retry_scheduled": True,
            "retry_count": retry_count + 1,
        }
    else:
        # Mark as failed
        message.status = MessageStatus.FAILED
        message.message_metadata["error"] = str(e)
        self.db.commit()
```

**Retry Policies** (lines 128-140):
```python
self.retry_policies = {
    "flow_message": {
        "max_retries": 5,
        "backoff_factor": 1.5,
        "base_delay": 180,  # 3 minutes
    },
    "quiz_message": {
        "max_retries": 3,
        "backoff_factor": 2,
        "base_delay": 300
    },
}
```

**Backoff Calculation** (lines 372-382):
```python
policy = self.retry_policies.get("default")
delay = policy["base_delay"] * (policy["backoff_factor"] ** (retry_count - 1))

# Example: Flow message retries
# Retry 1: 180s (3 min)
# Retry 2: 270s (4.5 min)
# Retry 3: 405s (~7 min)
# Retry 4: 607s (~10 min)
# Retry 5: 910s (~15 min)
```

---

## 5. Daily Automation Workflow

### Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. CELERY BEAT SCHEDULER (8:00 AM UTC Daily)                   │
│    File: app/celery_app.py line 189                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. SEND_DAILY_FLOW_QUESTIONS TASK                               │
│    File: app/tasks/flow_automation.py line 219                  │
│    Queue: flows                                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. QUERY ACTIVE PATIENTS (Limit 200)                            │
│    SELECT * FROM patients WHERE:                                 │
│      - flow_state = 'active'                                     │
│      - deleted_at IS NULL                                        │
│      - treatment_start_date IS NOT NULL                          │
│      - phone_encrypted IS NOT NULL                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. FOR EACH PATIENT:                                             │
│    a. Calculate current_day (from DB or treatment_start_date)    │
│    b. Determine flow phase (initial/intermediate/recurring)      │
│    c. Check if message should be sent today                      │
│       - Days 1-15: Daily                                         │
│       - Days 16-45: Every 3 days                                 │
│       - Days 46+: Weekly (0, 7, 14, 21 of 30-day cycle)          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                  ┌──────┴──────┐
                  │ Should Send? │
                  └──────┬──────┘
                         │ YES
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. GET MESSAGE TEMPLATE                                          │
│    - Load from FLOW_MESSAGES dict (hardcoded)                    │
│    - Personalize with patient.name                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. CREATE MESSAGE RECORD                                         │
│    INSERT INTO messages:                                         │
│      - patient_id                                                │
│      - direction = OUTBOUND                                      │
│      - type = TEXT                                               │
│      - content (personalized)                                    │
│      - status = PENDING                                          │
│      - metadata (flow_phase, flow_day, etc.)                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. SEND VIA WHATSAPP SERVICE                                     │
│    File: app/services/unified_whatsapp_service.py                │
│    Mode: DIRECT (synchronous)                                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. GET PATIENT PHONE                                             │
│    - Decrypt phone_encrypted via patient.phone property          │
│    - Format: Add "55" prefix if missing                          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. EVOLUTION API CLIENT                                          │
│    File: app/integrations/evolution/client.py                    │
│    POST /message/sendText/{instance_name}                        │
│    Body: { number: phone, text: content }                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                  ┌──────┴──────┐
                  │   Success?   │
                  └──────┬──────┘
                         │
            ┌────────────┴────────────┐
            │ YES                     │ NO
            ▼                         ▼
┌───────────────────────┐  ┌──────────────────────────┐
│ 10a. UPDATE MESSAGE    │  │ 10b. SCHEDULE RETRY       │
│ - status = SENT        │  │ - status = PENDING        │
│ - whatsapp_id          │  │ - scheduled_for (+delay)  │
│ - sent_at              │  │ - retry_count++           │
│ - COMMIT               │  │ - Max 5 retries           │
└───────────────────────┘  └──────────────────────────┘
                                     │
                                     ▼
                          ┌──────────────────────────┐
                          │ 10c. RETRY EXHAUSTED?     │
                          │ - Mark as FAILED          │
                          │ - Log error               │
                          └──────────────────────────┘
```

---

## 6. Critical Issues & Bottlenecks

### 6.1 CRITICAL: 200 Patient Limit

**Location:** `app/tasks/flow_automation.py` line 289

```python
.limit(200)
```

**Impact:**
- Only 200 patients processed per day
- If system has >200 active patients, some are **randomly excluded**
- No guarantee which patients are selected (depends on database order)

**Recommendation:**
- Remove limit and use batch processing
- Or implement pagination to process all patients
- Or increase frequency (e.g., every 4 hours with offset)

### 6.2 Potential: current_day Not Updated

**Issue:** The `patients.current_day` field relies on:
1. Manual updates by flow engine
2. Fallback calculation when `current_day == 0`

**Risk:**
- If flow engine fails to update `current_day`, patients may:
  - Receive wrong messages
  - Be skipped entirely
  - Get stuck in one phase

**Verification Needed:**
- Check if flow engine updates `current_day` reliably
- Add monitoring for patients with stale `current_day`

### 6.3 WhatsApp Delivery Failures

**File:** `app/tasks/flow_automation.py` lines 380-385

```python
except Exception as send_error:
    logger.warning(
        f"Failed to send via WhatsApp for patient {patient.id}: {send_error}. "
        f"Message queued for retry."
    )
    # Message is already in DB with PENDING status for retry
```

**Potential Issues:**
1. No explicit retry scheduling in this block
2. Message marked as PENDING but no retry task queued
3. Relies on separate `retry_failed_messages` task (runs every 5 min)

**Gap:** If WhatsApp fails during daily task, retry delay is 0-5 minutes (random).

### 6.4 Stuck Messages

**Scenario:** Messages can get stuck in PENDING if:
1. WhatsApp service is down during daily task
2. Retry mechanism fails
3. Evolution API returns non-standard error

**Mitigation:** Celery Beat task `retry-pending-welcome-messages` (every 10 min) catches stuck messages.

**File:** `app/celery_app.py` lines 93-97

```python
"retry-pending-welcome-messages": {
    "task": "retry_pending_welcome_messages",
    "schedule": 600.0,  # Every 10 minutes
    "kwargs": {"limit": 50, "min_age_minutes": 5, "max_age_hours": 24},
}
```

---

## 7. Quiz Messages vs Daily Messages

### 7.1 Quiz Scheduling

**File:** `app/domain/flows/scheduling/quiz_scheduler.py`

Quiz messages use **PatientFlowState** table, not patients table directly.

**Trigger Logic** (lines 45-90):
```python
async def should_trigger_quiz(self, flow_type: str, current_day: int, flow_state: PatientFlowState) -> bool:
    from app.domain.quizzes.quiz_trigger_policy import QuizTriggerPolicy

    is_quiz_day = QuizTriggerPolicy.is_quiz_day(
        current_day, flow_type, days_since_enrollment
    )
```

**Quiz Days:**
- Initial assessment: Day 45
- Monthly assessments: Every 30 days after day 45

### 7.2 Key Difference

| Feature | Daily Messages | Quiz Messages |
|---------|----------------|---------------|
| **Source Table** | `patients` | `patient_flow_states` |
| **Trigger** | Celery Beat (daily) | Flow engine + quiz policy |
| **Frequency** | Daily/3-day/weekly | Monthly |
| **Template** | Hardcoded dict | Database + YAML |
| **Delivery** | Direct WhatsApp | Link + WhatsApp fallback |

---

## 8. Timing & Performance

### 8.1 Daily Schedule

```
00:00 UTC - Daily quiz session cleanup (every 2 hours)
02:00 UTC - Cleanup expired quiz links
08:00 UTC - 🔥 SEND DAILY FLOW QUESTIONS (main task)
09:00 UTC - Send daily reminders (pending quizzes)
```

### 8.2 Processing Time

**Estimated:**
- 200 patients × 2s/patient = ~7 minutes total
- WhatsApp API: ~500ms per message
- Database queries: ~100ms per patient
- Template processing: ~50ms per patient

**Actual:** Depends on WhatsApp API latency and database load.

### 8.3 Rate Limiting

**Evolution API** (file: `app/integrations/evolution/client.py` line 94):
```python
rate_limit = getattr(settings, "EVOLUTION_RATE_LIMIT", 10)
self.rate_limiter = RateLimiter(requests_per_second=rate_limit)
```

**Default:** 10 messages/second = 600 messages/minute

**Impact:** With 200 patients, rate limiting should not be an issue.

---

## 9. Error Handling & Recovery

### 9.1 Message States

```
PENDING → SENT (success)
        ↓
        FAILED (after 5 retries)
```

### 9.2 Retry Chain

1. **Immediate Retry:** WhatsApp service (5 retries with backoff)
2. **Scheduled Retry:** `retry_failed_messages` task (every 5 min)
3. **Stuck Message Recovery:** `retry-pending-welcome-messages` (every 10 min)

### 9.3 Dead Letter Queue

**File:** `app/celery_app.py` lines 166-170

```python
"process-whatsapp-dlq": {
    "task": "app.tasks.messaging.process_whatsapp_dlq",
    "schedule": 600.0,  # Every 10 minutes
    "kwargs": {"limit": 50},
}
```

Messages that fail all retries are moved to DLQ for manual intervention.

---

## 10. Monitoring & Observability

### 10.1 Logging

**Key Log Points:**
1. Patient selection: `Found {len} patients with active flow_state`
2. Message sent: `Sent daily question to patient {id} [{phase} day {day}]`
3. Message skipped: `skipped += 1` (no individual log)
4. WhatsApp errors: `Failed to send via WhatsApp for patient {id}`

### 10.2 Metrics

**Return Value** (lines 405-411):
```python
return {
    "questions_sent": questions_sent,
    "skipped": skipped,
    "errors_count": len(errors),
    "errors": errors[:10],
    "timestamp": datetime.now(timezone.utc).isoformat(),
}
```

### 10.3 Missing Metrics

❌ No tracking of:
- Which flow phase each message belongs to
- Distribution of messages across phases
- Average processing time per patient
- WhatsApp API latency
- Retry success rate

---

## 11. Recommendations

### 11.1 High Priority

1. **Remove 200 patient limit**
   - Implement batch processing
   - Or run task multiple times per day with offset

2. **Add current_day monitoring**
   - Alert if patients have stale `current_day` (>7 days old)
   - Add database trigger to auto-increment daily

3. **Improve retry logging**
   - Log each retry attempt with details
   - Track retry success/failure rate

### 11.2 Medium Priority

4. **Add phase distribution metrics**
   - Track how many messages sent per phase
   - Monitor phase transitions

5. **Implement proper DLQ handling**
   - Alert on DLQ buildup
   - Add manual review interface

6. **Add WhatsApp health checks**
   - Pre-check Evolution API before sending batch
   - Abort if API is unhealthy

### 11.3 Low Priority

7. **Move templates to database**
   - Replace hardcoded FLOW_MESSAGES dict
   - Allow dynamic template updates

8. **Add message preview**
   - Log first 3 messages for debugging
   - Sample check for personalization

---

## 12. File Reference Index

### Core Files

1. **Scheduling:**
   - `/app/celery_app.py` - Celery Beat config (line 189)
   - `/app/tasks/flow_automation.py` - Main task (lines 219-414)
   - `/app/domain/flows/core/scheduling.py` - Flow scheduler service

2. **State Management:**
   - `/app/models/patient.py` - Patient model (lines 84-91)
   - `/app/models/enums.py` - FlowState enum
   - `/app/domain/flows/core/state_machine.py` - State transitions

3. **Templates:**
   - `/app/config/flow_templates.yaml` - Template config
   - `/app/domain/flows/core/message_template_loader.py` - Template loader

4. **WhatsApp:**
   - `/app/domain/messaging/whatsapp/whatsapp_service.py` - WhatsApp service
   - `/app/integrations/evolution/client.py` - Evolution API client

5. **Quiz System:**
   - `/app/domain/flows/scheduling/quiz_scheduler.py` - Quiz scheduler
   - `/app/domain/quizzes/quiz_trigger_policy.py` - Quiz trigger policy

---

## 13. Key Findings Summary

✅ **Working Correctly:**
- Daily scheduling via Celery Beat (8 AM UTC)
- Flow phase calculation (3 distinct phases)
- WhatsApp integration with retry
- Template personalization

⚠️ **Potential Issues:**
- 200 patient limit per day
- No verification of current_day updates
- Implicit retry mechanism for stuck messages
- Hardcoded templates (not in database)

🔴 **Critical Gaps:**
- No guarantee all active patients receive messages
- Limited observability (no phase metrics)
- No pre-send health checks

---

## 14. Next Steps for Investigation

1. **Verify Patient Count:** Check if system has >200 active patients
2. **Test current_day Updates:** Monitor 10 patients for 7 days
3. **Analyze Message Logs:** Review stuck messages from past 30 days
4. **WhatsApp Reliability:** Check Evolution API uptime/errors
5. **Phase Distribution:** Query database for patient distribution across phases

---

**Report Generated:** 2025-12-24T17:23:00Z
**Total Files Analyzed:** 12
**Lines of Code Reviewed:** ~2,500
**Critical Findings:** 3
**Recommendations:** 8
