# Flow Scheduling System - Quick Reference

## Daily Message Flow (High Level)

```
Celery Beat (Hourly)
    ↓
process_daily_flows() Task
    ↓
Get all active PatientFlowState records
    ↓
For each patient:
  ├─ Get current day (current_step)
  ├─ Load flow template for this day
  ├─ Calculate optimal send time (timezone + preferences)
  ├─ Check for quiz trigger (if day 30 of monthly flow)
  ├─ Generate personalized message (AI)
  ├─ Create Message record in database
  ├─ Schedule Celery task with ETA = send_time
  ├─ Store Celery task ID in message metadata
  └─ Advance flow state to next day
    ↓
Message reaches scheduled time
    ↓
Celery task executes send_message()
    ↓
UnifiedWhatsAppService sends via WhatsApp API
    ↓
Webhook confirms delivery
    ↓
Message status updated: SCHEDULED → SENT → DELIVERED
```

## Scheduled Tasks

| Task | Schedule | Purpose | Key Code |
|------|----------|---------|----------|
| `process-daily-flows` | Every hour | Process active flows, schedule messages | `app/tasks/flows/flow_tasks.py` |
| `send-daily-reminders` | 9 AM Sao Paulo daily | Send quiz reminders | `app/tasks/flow_automation.py` |
| `check-pending-flows` | Every 15 min | Auto-enroll new patients | `app/tasks/flow_automation.py` |
| `resume-paused-flows` | Every 6 hours | Resume paused flows | `app/tasks/flow_automation.py` |
| `cleanup-expired-quiz-links` | Daily 2 AM | Mark expired sessions | `app/tasks/flow_automation.py` |

## Database Tables

```sql
-- Flow Definitions
flow_kinds                  -- Flow templates (initial_15_days, monthly_recurring)
flow_template_versions      -- Template versions with steps/days
  └─ steps[]: {day, message_template, quiz_trigger?, ...}

-- Patient State
patient_flow_states         -- Current flow progress per patient
  ├─ patient_id
  ├─ flow_template_version_id
  ├─ current_step            -- Current day (1-based)
  ├─ status                  -- active, paused, completed
  ├─ next_scheduled_at       -- When next message should be sent
  └─ flow_metadata

-- Messages
messages                    -- Scheduled/sent messages
  ├─ patient_id
  ├─ content
  ├─ status                  -- scheduled, sent, delivered, failed
  ├─ scheduled_for           -- When to send
  ├─ whatsapp_id
  ├─ retry_count
  └─ message_metadata        -- {flow_context, source, celery_task_id, ...}

-- Templates
message_templates           -- Reusable message templates
quiz_sessions              -- Quiz tracking
```

## Key Classes & Methods

### FlowScheduler
Location: `app/domain/flows/core/scheduling.py`
```python
calculate_optimal_send_time(patient, current_day)
  → Returns DateTime when message should be sent
  → Considers: timezone, preferred_hour, randomization

should_skip_patient_flow(flow_state)
  → True if paused/completed/patient not found

check_quiz_trigger(patient_id, current_day, flow_type)
  → Returns quiz session if day==30 and monthly_recurring
```

### MessageScheduler
Location: `app/domain/messaging/scheduling/message_scheduler/scheduler.py`
```python
schedule_message(patient_id, content, scheduling_window)
  → Creates Message record
  → Calculates delivery time (timezone-aware)
  → Schedules Celery task
  → Returns message_id + task_id

on_delivery_failure(message_id, failure_reason)
  → Updates retry_count
  → If < MAX_RETRIES: schedule retry with exponential backoff
  → If >= MAX_RETRIES: route to DLQ, notify flow engine
```

### FlowEngine
Location: `app/domain/flows/engine/flow_engine.py`
```python
process_daily_flows(limit=100)
  → Main entry point for daily processing
  → Returns: {processed, success, error, messages_scheduled, ...}

_process_patient_daily_flow(flow_state)
  → Process single patient
  → Advance current_step
  → Schedule message
```

## Configuration

### Celery Beat Schedule
File: `app/celery_app.py`
```python
beat_schedule = {
    "process-daily-flows": {
        "schedule": 3600.0,  # Every hour (production)
        "kwargs": {"limit": 100},
    },
    "send-daily-reminders": {
        "schedule": crontab(hour=9, minute=0),  # 9 AM Sao Paulo
    },
    ...
}
```

### Message Scheduler Config
File: `app/domain/messaging/scheduling/message_scheduler/config.py`
```python
MAX_MESSAGE_LENGTH = 4096
MAX_DELIVERY_RETRIES = 3
RETRY_BASE_DELAY = 60  # seconds
OPTIMAL_BATCH_SIZE = 100
SCHEDULING_WINDOWS = {
    "BUSINESS_HOURS": (8, 22),
    "FLEXIBLE": (6, 23),
}
```

## Common Issues & Fixes

### Issue: Messages not being sent
**Diagnosis Steps**:
1. Check `messages` table: status = SCHEDULED?
2. Check Celery: is task in queue?
3. Check `message_metadata.celery_task_id`: valid?
4. Check logs: any send_message task errors?

**Common Causes**:
- Patient timezone invalid → use fallback
- Celery worker not running
- WhatsApp API key invalid
- Patient phone number invalid

### Issue: Flow not advancing
**Check**:
1. Is `patient_flow_states.status` = "active"?
2. Is `current_step` < max steps?
3. Are there any paused flow conditions?

### Issue: Duplicate messages sent
**Causes**:
- Celery task retried before status updated
- No idempotency check on message scheduling

**Solution**:
- Add unique constraint: (patient_id, flow_type, day, scheduled_for)
- Check existing scheduled message before creating

## Flow Types & Templates

```
initial_15_days
├─ Day 1-15: Daily messages
└─ Day 15: Quiz trigger

monthly_recurring
├─ Day 1-29: Daily messages
└─ Day 30: Monthly assessment quiz

hormonia_fluxo_hormonal    (hormone treatment)
hormonia_fluxo_quimio       (chemotherapy)
hormonia_fluxo_radio        (radiotherapy)
hormonia_fluxo_mama         (breast cancer)
hormonia_fluxo_prostata     (prostate cancer)
```

## Timezone Handling

```
Patient preferred_message_hour = 10 (10 AM in patient's timezone)

calculate_optimal_send_time():
  1. Get patient.timezone (e.g., "America/Sao_Paulo")
  2. Calculate: 10 AM in that timezone
  3. Convert to Sao Paulo for scheduling
  4. Add randomization: ±30 minutes
  5. Store in message.scheduled_for

Example:
  Patient: timezone="America/Sao_Paulo", preferred_hour=10
  Current time: 2025-12-22 14:00 Sao Paulo (11:00 AM in São Paulo)
  Scheduled: 2025-12-22 13:00 Sao Paulo (10:00 AM in São Paulo) ± 30 min
  → Actually schedules for 12:30-13:30 Sao Paulo
```

## Message Status Flow

```
PENDING
  ↓ (message created but not scheduled)
SCHEDULED
  ↓ (celery task waiting)
SENDING
  ↓ (being sent by worker)
SENT
  ↓ (delivered to WhatsApp)
DELIVERED
  ↓ (delivered to patient phone)
READ
  (patient read message)

Or on failure:
  SCHEDULED → FAILED → [retry] → SCHEDULED → ... → FAILED (DLQ)
```

## Key Files

```
Frontend Scheduling:
- app/celery_app.py                 # Beat schedule config

Daily Flow Processing:
- app/tasks/flows/flow_tasks.py     # process_daily_flows task
- app/domain/flows/core/scheduling.py   # FlowScheduler class

Message Scheduling:
- app/domain/messaging/scheduling/message_scheduler/scheduler.py
- app/domain/messaging/scheduling/message_scheduler/timezone_handler.py
- app/domain/messaging/scheduling/message_scheduler/task_scheduler.py
- app/domain/messaging/scheduling/message_scheduler/retry_handler.py

Flow Automation:
- app/tasks/flow_automation.py      # send_daily_reminders, etc.

Follow-ups:
- app/services/follow_up_system/service.py

Templates:
- app/config/flow_templates.yaml    # Message templates
- app/models/flow.py                # Flow models

Data Models:
- app/models/message.py             # Message model
- app/models/flow.py                # PatientFlowState, etc.
```

## Performance Notes

- **Batch Size**: Process 100 patients per hour
- **Memory**: O(n) growth with patient count (fix: stream results)
- **Database**: N+1 queries on flow processing (fix: batch fetch)
- **Retries**: Exponential backoff: 1min → 2min → 4min → 8min
- **Caching**: Flow states cached for 10 minutes
- **Locks**: Distributed Redis locks prevent race conditions

## Quick Debugging

```bash
# Check if task is in queue
celery -A app.celery_app inspect active_queues

# Check scheduled messages for patient
SELECT * FROM messages
WHERE patient_id = 'uuid'
ORDER BY created_at DESC;

# Check flow state
SELECT * FROM patient_flow_states
WHERE patient_id = 'uuid';

# Check Celery task status
from celery.result import AsyncResult
result = AsyncResult('task-id', app=celery_app)
result.status  # 'PENDING', 'STARTED', 'SUCCESS', 'FAILURE'

# Check message scheduling
SELECT status, COUNT(*) FROM messages
WHERE created_at > NOW() - INTERVAL '1 day'
GROUP BY status;
```

## Checklist for Production

- [ ] Celery workers running and healthy
- [ ] Redis available (broker + result backend)
- [ ] WhatsApp API credentials configured
- [ ] Patient timezones populated correctly
- [ ] Message templates loaded
- [ ] Database indexes on key columns
- [ ] Monitoring alerts set up
- [ ] Backup/recovery plan for failed messages
- [ ] Rate limiting configured
- [ ] Error logging enabled
