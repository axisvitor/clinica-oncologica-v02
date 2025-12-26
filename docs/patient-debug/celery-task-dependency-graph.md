# Celery Task Dependency Graph

## Visual Task Execution Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                       CELERY BEAT SCHEDULER                          │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
                           │
        ┌──────────────────┼──────────────────┬──────────────────┐
        │                  │                  │                  │
        ▼                  ▼                  ▼                  ▼
┌────────────────┐ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│ FLOW TASKS     │ │ FOLLOW-UP      │ │ MONITORING     │ │ MAINTENANCE    │
│ Queue: flows   │ │ Queue: N/A ❌  │ │ Queue: default │ │ Queue: maint   │
└────────┬───────┘ └────────┬───────┘ └────────┬───────┘ └────────┬───────┘
         │                  │                  │                  │
         │                  │                  │                  │
         ├──────────────────┤                  │                  │
         │                  │                  │                  │
         ▼                  ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ send_daily_flow │ │ execute_pending │ │ check_patient_  │ │ cleanup_old_    │
│ _questions      │ │ _follow_ups     │ │ alerts          │ │ flow_data       │
│ ⏰ 8:00 AM      │ │ ⏰ */5 min ❌   │ │ ⏰ */5 min      │ │ ⏰ Daily 2AM    │
│ ✅ ACTIVE       │ │ ❌ NOT RUNNING  │ │ ✅ ACTIVE       │ │ ✅ ACTIVE       │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │                   │
         │                   │                   │                   │
         ▼                   ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Query Patients  │ │ Rehydrate Redis │ │ Query Quiz      │ │ Delete Old      │
│ with            │ │ • pending_      │ │ Responses       │ │ Flows >90 days  │
│ flow_state=     │ │   actions       │ │ • Evaluate      │ └─────────────────┘
│ ACTIVE          │ │ • active_alerts │ │   alert_rules   │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Determine       │ │ Get Actions     │ │ Create          │
│ Flow Phase:     │ │ where:          │ │ EscalationAlert │
│ • 1-15: Daily   │ │ scheduled_for   │ │ if severity >=  │
│ • 16-45: /3     │ │ <= NOW()        │ │ WARNING         │
│ • 46+: Weekly   │ └────────┬────────┘ └────────┬────────┘
└────────┬────────┘          │                   │
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Create Message  │ │ Execute by Type:│ │ Send Provider   │
│ from Template   │ │ • EMPATHETIC    │ │ Notification    │
└────────┬────────┘ │ • MEDICAL       │ │ • Email         │
         │          │ • ESCALATION    │ │ • SMS (critical)│
         │          │ • PROVIDER      │ └─────────────────┘
         │          │ • CONVERSATION  │
         │          └────────┬────────┘
         │                   │
         ▼                   ▼
┌─────────────────┐ ┌─────────────────┐
│ Send via        │ │ Update Action   │
│ WhatsApp        │ │ Status:         │
│ (UnifiedService)│ │ • completed     │
└────────┬────────┘ │ • failed        │
         │          │ • retry         │
         │          └────────┬────────┘
         │                   │
         ▼                   ▼
┌─────────────────┐ ┌─────────────────┐
│ Update Patient  │ │ Persist to      │
│ Flow State      │ │ Redis           │
└─────────────────┘ └─────────────────┘


┌────────────────────────────────────────────────────────────────────┐
│                      OTHER SCHEDULED TASKS                         │
└────────────────────────────────────────────────────────────────────┘

┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ send_daily_     │ │ check_pending_  │ │ resume_paused_  │ │ process_monthly │
│ reminders       │ │ flows           │ │ flows           │ │ _quizzes        │
│ ⏰ 9:00 AM      │ │ ⏰ */15 min     │ │ ⏰ */6 hours    │ │ ⏰ Hourly       │
│ ✅ ACTIVE       │ │ ✅ ACTIVE       │ │ ✅ ACTIVE       │ │ ✅ ACTIVE       │
└─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────┘
         │                   │                   │                   │
         ▼                   ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Get Patients    │ │ Get Patients    │ │ Get Flows:      │ │ Get Patients    │
│ with Pending    │ │ without Active  │ │ • status=paused │ │ in Monthly      │
│ Quiz Sessions   │ │ Flows           │ │ • updated >48h  │ │ Phase (day>45)  │
│ >24h old        │ │ (created <7d)   │ └────────┬────────┘ └────────┬────────┘
└────────┬────────┘ └────────┬────────┘          │                   │
         │                   │                   │                   │
         ▼                   ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Send WhatsApp   │ │ Determine       │ │ Resume Flow:    │ │ Check if Day 30 │
│ Reminder        │ │ Template:       │ │ • Clear paused  │ │ of Monthly      │
│ "Complete seu   │ │ • Treatment     │ │   flag          │ │ Cycle           │
│ questionário"   │ │   type          │ │ • Update status │ └────────┬────────┘
└─────────────────┘ │ • Cancer type   │ └─────────────────┘          │
                    │ • Default       │                              │
                    └────────┬────────┘                              │
                             │                                       │
                             ▼                                       ▼
                    ┌─────────────────┐                   ┌─────────────────┐
                    │ Start Flow:     │                   │ Trigger Monthly │
                    │ • Create        │                   │ Quiz via        │
                    │   FlowState     │                   │ QuizTrigger     │
                    │ • Send first    │                   │ Service         │
                    │   message       │                   └─────────────────┘
                    └─────────────────┘
```

---

## Task Execution Matrix

| Task Name | Schedule | Queue | Status | Dependencies | Triggers |
|-----------|----------|-------|--------|--------------|----------|
| **send_daily_flow_questions** | Daily 8AM | flows | ✅ Active | None | Creates Message records |
| **send_daily_reminders** | Daily 9AM | flows | ✅ Active | Quiz sessions | Sends WhatsApp reminders |
| **check_pending_flows** | Every 15m | flows | ✅ Active | Patient records | Starts new flows |
| **resume_paused_flows** | Every 6h | flows | ✅ Active | Paused flows | Resumes flows |
| **process_monthly_quizzes** | Hourly | default | ✅ Active | Patient phase | Triggers monthly quiz |
| **check_patient_alerts** | Every 5m | default | ✅ Active | Quiz responses | Creates alerts |
| **execute_pending_follow_ups** | Every 5m | follow_up | ❌ **NOT ACTIVE** | FollowUpAction | Executes follow-ups |
| **process_escalation_alerts** | Every 10m | follow_up | ❌ **NOT ACTIVE** | EscalationAlert | Escalates alerts |
| **cleanup_old_contexts** | Daily 3AM | follow_up | ❌ **NOT ACTIVE** | Redis contexts | Cleans old data |
| **cleanup_old_flow_data** | Daily 2AM | maintenance | ✅ Active | Old flows | Deletes old records |
| **cleanup_expired_quiz_links** | Daily | maintenance | ✅ Active | Quiz sessions | Updates expired |

---

## Task Dependency Chain

```
┌──────────────────────────────────────────────────────────────────┐
│                     PRIMARY PATIENT FLOW                         │
└──────────────────────────────────────────────────────────────────┘

1. send_daily_flow_questions (8AM)
   └─> Creates Message (PENDING)
       └─> UnifiedWhatsAppService.send_message()
           └─> EvolutionClient.send_text()
               └─> Message.status = SENT
                   └─> Patient receives WhatsApp message

2. Patient responds via WhatsApp
   └─> Webhook received (evolution_webhook_handler)
       └─> ResponseProcessor.process_patient_message()
           └─> AI Analysis (Gemini)
               ├─> Creates FollowUpAction (if needed)
               │   └─> [WAITING] execute_pending_follow_ups ❌
               │       └─> Would execute: Send empathetic response
               │
               ├─> Creates EscalationAlert (if severe)
               │   └─> [WAITING] process_escalation_alerts ❌
               │       └─> Would notify: Provider via SMS/Email
               │
               └─> Updates ConversationContext
                   └─> Stored in Redis (7-day TTL)

3. check_patient_alerts (Every 5m)
   └─> Query QuizSession.responses
       └─> Evaluate quiz_alert_rules.py
           ├─> If CRITICAL: Create EscalationAlert
           │   └─> [WAITING] process_escalation_alerts ❌
           │
           └─> If WARNING: Create FollowUpAction
               └─> [WAITING] execute_pending_follow_ups ❌

4. process_monthly_quizzes (Hourly)
   └─> Get patients in monthly phase (day > 45)
       └─> Check if day 30 of cycle
           └─> QuizTriggerService._trigger_patient_quiz()
               └─> Creates QuizSession
                   └─> Sends quiz link via WhatsApp

┌──────────────────────────────────────────────────────────────────┐
│                    BROKEN DEPENDENCY CHAIN                       │
└──────────────────────────────────────────────────────────────────┘

FollowUpAction Created
   ↓
Stored in Redis (pending_actions)
   ↓
[BREAK] execute_pending_follow_ups NOT SCHEDULED ❌
   ↓
Actions accumulate in Redis but never execute
   ↓
Patient never receives follow-up messages
   ↓
Engagement drops, alerts missed

EscalationAlert Created
   ↓
Stored in Redis (active_alerts)
   ↓
[BREAK] process_escalation_alerts NOT SCHEDULED ❌
   ↓
Provider never notified
   ↓
Critical patient concerns unaddressed
```

---

## Queue Configuration

```python
# Celery worker queues
CELERY_QUEUES = {
    "default": {
        "binding_key": "default",
        "workers": 2,
        "tasks": [
            "process_scheduled_messages",
            "retry_failed_messages",
            "check_patient_alerts",
            "process_monthly_quizzes"
        ]
    },

    "flows": {
        "binding_key": "flows",
        "workers": 2,
        "tasks": [
            "send_daily_flow_questions",      # ✅ 8AM daily
            "send_daily_reminders",           # ✅ 9AM daily
            "check_pending_flows",            # ✅ Every 15m
            "resume_paused_flows",            # ✅ Every 6h
            "process_daily_flows"             # ✅ Hourly
        ]
    },

    "follow_up": {
        "binding_key": "follow_up",
        "workers": 0,  # ❌ NO WORKERS - Queue not configured
        "tasks": [
            "execute_pending_follow_ups",     # ❌ NOT REGISTERED
            "process_escalation_alerts",      # ❌ NOT REGISTERED
            "cleanup_old_contexts"            # ❌ NOT REGISTERED
        ]
    },

    "quiz": {
        "binding_key": "quiz",
        "workers": 1,
        "tasks": [
            "check_expired_links",
            "rotate_expired_token",
            "send_quiz_reminder"
        ]
    },

    "maintenance": {
        "binding_key": "maintenance",
        "workers": 1,
        "tasks": [
            "cleanup_old_flow_data",          # ✅ Daily 2AM
            "cleanup_expired_quiz_links",     # ✅ Daily
            "cleanup_old_completed_sagas"     # ✅ Daily
        ]
    }
}
```

---

## Task Retry & Failure Handling

```python
# Task configuration matrix
TASK_CONFIG = {
    "send_daily_flow_questions": {
        "max_retries": 3,
        "retry_delay": 60,  # 1 minute
        "soft_time_limit": 300,  # 5 minutes
        "time_limit": 360,  # 6 minutes
        "autoretry_for": [ConnectionError, TimeoutError]
    },

    "execute_pending_follow_ups": {
        "max_retries": 3,
        "retry_delay": 300,  # 5 minutes
        "soft_time_limit": 300,
        "time_limit": 360,
        "autoretry_for": [ConnectionError]
    },

    "process_escalation_alerts": {
        "max_retries": 5,  # Higher retries for critical
        "retry_delay": 180,  # 3 minutes
        "soft_time_limit": 300,
        "time_limit": 360,
        "autoretry_for": [ConnectionError, SMTPException]
    },

    "check_patient_alerts": {
        "max_retries": 2,
        "retry_delay": 120,  # 2 minutes
        "soft_time_limit": 180,
        "time_limit": 240,
        "autoretry_for": [DatabaseError]
    }
}
```

---

## Failure Scenarios & Recovery

### Scenario 1: Task Execution Failure

```
Task: send_daily_flow_questions fails at 8:00 AM
   ↓
Celery auto-retry (attempt 2) at 8:01 AM
   ↓
If fails again → retry (attempt 3) at 8:02 AM
   ↓
If still fails → task marked FAILED
   ↓
Messages not sent for affected patients
   ↓
Recovery: Manual retry or wait for next day (8AM)
```

### Scenario 2: Follow-Up Task Not Running

```
Patient response creates FollowUpAction
   ↓
Action stored in Redis with scheduled_for = NOW + 5min
   ↓
execute_pending_follow_ups should run at :00, :05, :10...
   ↓
❌ Task not registered → never executes
   ↓
Action sits in Redis indefinitely
   ↓
Patient never receives follow-up
   ↓
Recovery: Manual execution via admin interface or CLI
```

### Scenario 3: Redis Connection Lost

```
Task attempts to store FollowUpAction
   ↓
Redis connection timeout
   ↓
Fallback to in-memory storage
   ↓
Action stored but not persisted
   ↓
Service restart → action lost
   ↓
Recovery: Reprocess patient response (if logged)
```

### Scenario 4: Critical Alert Not Escalated

```
Patient submits quiz with pain_scale = 9
   ↓
check_patient_alerts evaluates rules
   ↓
Creates CRITICAL EscalationAlert
   ↓
process_escalation_alerts should notify provider
   ↓
❌ Task not registered → no notification sent
   ↓
Provider unaware of critical patient condition
   ↓
Recovery: Manual alert monitoring dashboard
```

---

## Monitoring & Alerting

### Task Health Checks

```python
# monitor_flow_task_health (Every 5m)
def monitor_flow_task_health():
    """Check task execution health"""

    # 1. Check last execution times
    tasks_to_check = [
        "send_daily_flow_questions",
        "check_patient_alerts",
        "process_monthly_quizzes"
    ]

    for task_name in tasks_to_check:
        last_run = get_last_task_run(task_name)
        if last_run > expected_interval:
            alert(f"Task {task_name} overdue by {last_run - expected}")

    # 2. Check queue depths
    for queue in ["default", "flows", "quiz"]:
        depth = get_queue_depth(queue)
        if depth > threshold:
            alert(f"Queue {queue} backing up: {depth} tasks")

    # 3. Check task failure rates
    for task_name in tasks_to_check:
        failure_rate = get_failure_rate(task_name, window="1h")
        if failure_rate > 0.1:  # >10% failures
            alert(f"Task {task_name} high failure rate: {failure_rate:.1%}")
```

---

## Critical Path Analysis

**Most Critical Tasks** (Patient impact):

1. **send_daily_flow_questions** (8AM)
   - **Impact**: Primary patient engagement
   - **Failure**: No daily check-ins, patients feel abandoned
   - **SLA**: Must run within 15 minutes of 8AM

2. **check_patient_alerts** (Every 5m)
   - **Impact**: Detects critical conditions
   - **Failure**: Missed emergencies, safety risk
   - **SLA**: Must detect critical alerts within 5 minutes

3. **execute_pending_follow_ups** (Every 5m) ❌
   - **Impact**: Follow-up communication
   - **Failure**: No empathetic responses, poor experience
   - **SLA**: Should execute within 5 minutes of creation

4. **process_escalation_alerts** (Every 10m) ❌
   - **Impact**: Provider notification for critical issues
   - **Failure**: Provider unaware of urgent patient needs
   - **SLA**: Must notify within 10 minutes of critical alert

---

## Quick Fix Checklist

- [ ] **Register follow-up tasks in celery_app.py**
- [ ] **Start follow_up queue worker**
- [ ] **Verify Redis connectivity**
- [ ] **Test task execution manually**
- [ ] **Monitor task logs for errors**
- [ ] **Check queue depths**
- [ ] **Verify provider notifications working**
- [ ] **Test end-to-end flow**

---

**Document Version**: 1.0
**Last Updated**: 2025-12-24
**Critical Issues**: 3 tasks not registered
