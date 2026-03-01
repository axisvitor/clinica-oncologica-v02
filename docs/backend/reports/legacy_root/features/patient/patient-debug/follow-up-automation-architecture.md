# Follow-Up Automation & Patient Monitoring System Architecture

## Executive Summary

**System Purpose**: Automated patient engagement, monitoring, and intervention system that ensures continuous care through scheduled messages, quizzes, alerts, and follow-up actions.

**Key Components**:
- **Patient Monitor Agent**: Tracks adherence, engagement, and status
- **Flow Coordinator Agent**: Orchestrates treatment flow progression
- **Follow-Up System Service**: Manages automated follow-up actions
- **Celery Tasks**: Scheduled automation for flows and follow-ups
- **Alert System**: Detects and escalates patient concerns

---

## 1. TRIGGER MECHANISMS

### 1.1 Follow-Up Task Triggers

**Primary Trigger: Celery Beat Scheduler** (`/backend-hormonia/app/celery_app.py`)

```python
celery_app.conf.beat_schedule = {
    # Follow-up tasks (defined but NOT YET CONFIGURED)
    "execute-pending-follow-ups": {
        "task": "tasks.follow_up.execute_pending_follow_ups",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
        "options": {"queue": "follow_up"}
    },
    "process-escalation-alerts": {
        "task": "tasks.follow_up.process_escalation_alerts",
        "schedule": crontab(minute="*/10"),  # Every 10 minutes
        "options": {"queue": "follow_up"}
    },
    "cleanup-old-contexts": {
        "task": "tasks.follow_up.cleanup_old_contexts",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
        "options": {"queue": "follow_up"}
    }
}
```

**⚠️ CRITICAL FINDING**: These schedules are defined in `/backend-hormonia/app/tasks/follow_up.py` (lines 534-549) but **NOT REGISTERED** in the main `celery_app.py`. This means follow-up tasks are **NOT RUNNING AUTOMATICALLY**.

**Status**: ❌ **NOT ACTIVE** - Manual execution only

---

### 1.2 Daily Flow Automation Triggers

**Active Triggers** (Configured in `celery_app.py`):

```python
"check-pending-flows": {
    "task": "flow_automation.check_and_start_pending_flows",
    "schedule": 900.0,  # Every 15 minutes
    "options": {"queue": "flows"}
},

"send-daily-reminders": {
    "task": "flow_automation.send_daily_reminders",
    "schedule": crontab(hour=9, minute=0),  # 9:00 AM Sao Paulo
    "options": {"queue": "flows"}
},

"send-daily-flow-questions": {
    "task": "flow_automation.send_daily_flow_questions",
    "schedule": crontab(hour=8, minute=0),  # 8:00 AM Sao Paulo (PRIMARY FLOW DRIVER)
    "options": {"queue": "flows"}
},

"resume-paused-flows": {
    "task": "flow_automation.resume_paused_flows",
    "schedule": 21600.0,  # Every 6 hours
    "options": {"queue": "flows"}
}
```

**Status**: ✅ **ACTIVE** - Running on schedule

---

### 1.3 Patient Monitoring Triggers

**Monitoring Agent Execution** (`PatientMonitorAgent`):

**Trigger Mechanism**: **NOT AUTOMATIC** - Requires manual task dispatch

```python
# Expected usage (currently not configured):
task = {
    "type": "check_patient_status",
    "payload": {"patient_id": "<uuid>"}
}
await patient_monitor_agent.process_task(task)
```

**Available Monitoring Tasks**:
1. `check_patient_status` - Check patient engagement and status
2. `monitor_adherence` - Calculate adherence rate (70% threshold)
3. `detect_engagement_drop` - Identify disengaged patients

**Status**: ⚠️ **MANUAL ONLY** - No automated scheduler

---

## 2. PATIENT MONITORING SYSTEM

### 2.1 PatientMonitorAgent Architecture

**Location**: `/backend-hormonia/app/agents/patient/patient_monitor.py`

**Core Capabilities**:

```python
AgentCapabilities = [
    "PATIENT_ADAPTATION",
    "FLOW_COORDINATION"
]
```

**Monitoring Configuration**:

```python
monitoring_config = {
    "check_in_window_hours": 24,
    "max_missed_checkins": 2,
    "engagement_threshold_days": 7,
    "adherence_alert_threshold": 0.7  # 70% adherence rate
}
```

---

### 2.2 Adherence Monitoring Logic

**Function**: `_monitor_adherence(payload)` (Lines 124-224)

**Calculation Method**:

```python
# Get completed quizzes in period (default 30 days)
completed_sessions = db.query(QuizSession).filter(
    QuizSession.patient_id == patient_id,
    QuizSession.status == "completed",
    QuizSession.completed_at >= start_date
).count()

# Calculate expected quizzes based on treatment phase
if current_day <= 15:
    expected_quizzes = days_back // 5  # Every 5 days
elif current_day <= 45:
    expected_quizzes = days_back // 10  # Every 10 days
else:
    expected_quizzes = days_back // 30  # Monthly

# Adherence rate calculation
adherence_rate = completed_sessions / max(expected_quizzes, total_sessions)

# Trigger alert if below threshold
if adherence_rate < 0.7:
    alerts.append(f"Low adherence: {adherence_rate:.1%}")
```

**Triggers**:
- **Alert**: Adherence < 70%
- **Warning Logged**: Patient ID, adherence percentage

---

### 2.3 Engagement Detection

**Function**: `_detect_engagement_drop(payload)` (Lines 226-355)

**Detection Logic**:

```python
# Calculate days since last activity
last_activity = max(patient.updated_at, last_quiz.started_at)
days_since_activity = (now - last_activity).days

# Compare recent vs past quiz activity
recent_quizzes = count_quizzes(last_N_days)
past_quizzes = count_quizzes(previous_N_days)

# Detect 50% drop
drop_percentage = (past_quizzes - recent_quizzes) / past_quizzes
engagement_dropped = drop_percentage > 0.5

# Engagement status classification
if days_since_activity <= 3:
    status = "active"
elif days_since_activity <= 7:
    status = "moderate"
elif engagement_dropped:
    status = "declining"
else:
    status = "low"
```

**Alert Triggers**:
- No activity > 7 days
- 50% drop in quiz participation
- Status = "declining" or "low"

---

## 3. FLOW COORDINATOR AGENT

### 3.1 Architecture Overview

**Location**: `/backend-hormonia/app/agents/patient/flow_coordinator/`

**Component Structure**:

```
flow_coordinator/
├── coordinator.py          # Main orchestrator
├── state_manager.py        # Context building
├── decision_engine.py      # Flow decisions
├── message_generator.py    # Message personalization
├── transition_handler.py   # Phase transitions
├── consensus_manager.py    # Agent coordination
└── models.py              # Data models
```

---

### 3.2 Flow Decision Engine

**Location**: `decision_engine.py`

**Decision Types** (enum `FlowDecision`):

```python
class FlowDecision(Enum):
    CONTINUE_CURRENT = "continue_current"           # Normal progression
    ADVANCE_PHASE = "advance_phase"                 # Move to next phase
    ADJUST_TIMING = "adjust_timing"                 # Optimize message times
    PERSONALIZE_CONTENT = "personalize_content"     # Adapt messages
    ESCALATE_INTERVENTION = "escalate_intervention" # Medical alert
    PAUSE_FLOW = "pause_flow"                      # Temporary halt
    RESUME_FLOW = "resume_flow"                    # Resume after pause
```

**Decision Logic** (Lines 108-170):

```python
async def make_flow_decision(context, analysis):
    progress_score = analysis["progress_score"]
    risk_level = analysis["risk_level"]
    engagement_score = analysis["engagement_score"]

    # HIGH RISK → Immediate intervention
    if risk_level == "high":
        if requires_consensus("escalate_intervention"):
            consensus = await seek_consensus(...)
            if consensus["reached"]:
                return FlowDecision.ESCALATE_INTERVENTION
        return FlowDecision.ESCALATE_INTERVENTION

    # LOW ENGAGEMENT → Personalize content
    if engagement_score < 0.4:
        return FlowDecision.PERSONALIZE_CONTENT

    # DAY 45 → Transition to monthly phase
    if current_day == 45:
        if requires_consensus("advance_phase"):
            consensus = await seek_consensus(...)
            if consensus["reached"]:
                return FlowDecision.ADVANCE_PHASE
        return FlowDecision.ADVANCE_PHASE

    # MODERATE PROGRESS → Optimize timing
    if progress_score > 0.7 and engagement_score < 0.6:
        return FlowDecision.ADJUST_TIMING

    # DEFAULT → Continue normal flow
    return FlowDecision.CONTINUE_CURRENT
```

---

### 3.3 Analysis Scoring System

**Location**: `decision_engine.py` - `analyze_flow_situation()` (Lines 45-106)

**Progress Score Calculation**:

```python
progress_factors = [
    adherence * 0.3,              # 30% weight - message response rate
    max(0, mood_trend) * 0.25,    # 25% weight - mood improvement
    engagement * 0.2,             # 20% weight - daily interaction
    quiz_rate * 0.25              # 25% weight - quiz completion
]

progress_score = sum(progress_factors)  # Range: 0.0 - 1.0
```

**Risk Level Assessment**:

```python
risk_score = len(risk_factors) / 5.0  # Max 5 risk factors

if risk_score >= 0.6:    # 3+ risk factors
    risk_level = "high"
elif risk_score >= 0.3:  # 1-2 risk factors
    risk_level = "medium"
else:
    risk_level = "low"
```

**Risk Factors Identified**:
- `mood_decline`: Mood trend < -0.6
- `low_engagement`: Response rate < 0.3
- `recurring_symptom`: Pattern detected in knowledge graph

---

## 4. FOLLOW-UP ACTION SYSTEM

### 4.1 System Architecture

**Location**: `/backend-hormonia/app/services/follow_up_system/`

**Component Structure**:

```
follow_up_system/
├── service.py                      # Main orchestrator
├── models.py                       # Data models
├── enums.py                        # Action types & escalation levels
├── context/
│   ├── manager.py                  # Context management
│   └── builder.py                  # Patient context builder
├── generators/
│   ├── empathy.py                  # Empathetic message generation
│   └── medical.py                  # Medical concern handling
├── scheduling/
│   ├── scheduler.py                # Action scheduler
│   ├── message.py                  # Message scheduling
│   └── escalation.py               # Escalation scheduling
├── execution/
│   ├── executor.py                 # Action executor
│   └── message.py                  # Message executor
├── escalation.py                   # Escalation manager
└── notifications.py                # Notification service
```

---

### 4.2 Follow-Up Action Types

**Enum**: `FollowUpType` (from `enums.py`)

```python
class FollowUpType(Enum):
    EMPATHETIC_RESPONSE = "empathetic_response"           # Compassionate reply
    MEDICAL_CLARIFICATION = "medical_clarification"       # Request more info
    ESCALATION_NOTIFICATION = "escalation_notification"   # Alert provider
    PROVIDER_ALERT = "provider_alert"                    # Direct alert
    CONVERSATION_CONTINUATION = "conversation_continuation" # Continue dialogue
```

---

### 4.3 Action Lifecycle

**Flow** (from `service.py`):

```
1. CREATION (process_response_follow_up)
   ├─ Update conversation context
   ├─ Generate empathetic follow-up (EmpathyGenerator)
   ├─ Handle medical concerns (MedicalConcernGenerator)
   ├─ Create escalation alert (EscalationManager)
   └─ Handle response-type specific actions

2. SCHEDULING (_schedule_action_by_type)
   ├─ Store in Redis (ActionScheduler)
   ├─ Schedule by type:
   │  ├─ EMPATHETIC → MessageScheduler
   │  ├─ ESCALATION → EscalationScheduler
   │  └─ PROVIDER_ALERT → EscalationScheduler

3. EXECUTION (execute_pending_actions)
   ├─ Rehydrate from Redis
   ├─ Get pending actions (scheduled_for <= now)
   ├─ Execute by type:
   │  ├─ EMPATHETIC → _send_empathetic_response
   │  ├─ MEDICAL → _send_medical_clarification
   │  ├─ ESCALATION → _send_escalation_notification
   │  ├─ PROVIDER → _send_provider_alert
   │  └─ CONVERSATION → _send_conversation_continuation
   ├─ Update status (completed/failed)
   ├─ Persist to Redis
   └─ Cleanup old actions (>24 hours)
```

---

### 4.4 Redis Persistence & Rehydration

**Storage Layer**: `FollowUpRedisStore` (`/backend-hormonia/app/services/follow_up/redis_store.py`)

**Rehydration Process** (`service.py` - Lines 84-138):

```python
async def rehydrate_from_redis():
    """Restore in-memory state after service restart"""

    # 1. Load pending actions from Redis
    pending_action_dicts = await redis_store.get_pending_actions(limit=1000)
    for action_dict in pending_action_dicts:
        action = _dict_to_follow_up_action(action_dict)
        pending_actions[action.action_id] = action

    # 2. Load active alerts
    active_alert_dicts = await redis_store.get_active_alerts()
    for alert_dict in active_alert_dicts:
        alert = _dict_to_escalation_alert(alert_dict)
        active_alerts[alert.alert_id] = alert

    # 3. Conversation contexts loaded on-demand (7-day TTL)
    #    via context_manager.get_context()
```

**⚠️ CRITICAL**: Rehydration is called in Celery task (`follow_up.py` line 63) but **ONLY IF** the task is running. With tasks not registered in `celery_app.py`, rehydration never happens automatically.

---

## 5. ALERT GENERATION SYSTEM

### 5.1 Quiz Alert Rules

**Location**: `/backend-hormonia/app/config/quiz_alert_rules.py`

**Rule Structure**:

```python
class QuizAlertRule:
    rule_id: str
    name: str
    description: str
    severity: AlertSeverity  # INFO | WARNING | CRITICAL
    condition: Callable[[Dict], bool]  # Evaluation function
    message_template: str
    recommendation: str
```

**Alert Severity Levels**:

```python
class AlertSeverity(Enum):
    INFO = "info"         # Monitoring needed
    WARNING = "warning"   # Attention required
    CRITICAL = "critical" # Immediate action required
```

---

### 5.2 Critical Alert Rules

**Total Rules**: 14 (5 critical, 7 warning, 2 info)

**Critical Alerts** (Lines 143-191):

1. **pain_score_critical** (Lines 143-152)
   - **Condition**: `pain_scale >= 7 OR pain_level >= 7`
   - **Action**: Immediate analgesia and urgent consultation
   - **Severity**: CRITICAL

2. **fever_with_chills** (Lines 153-162)
   - **Condition**: `has_fever AND has_chills`
   - **Concern**: Possible neutropenia febril
   - **Action**: Urgent medical evaluation
   - **Severity**: CRITICAL

3. **severe_bleeding** (Lines 163-172)
   - **Condition**: `severe_bleeding OR hemorrhage`
   - **Action**: Emergency referral
   - **Severity**: CRITICAL

4. **multiple_severe_symptoms** (Lines 173-181)
   - **Condition**: `≥3 symptoms with severity ≥7`
   - **Action**: Complete medical assessment, possible hospitalization
   - **Severity**: CRITICAL

5. **respiratory_distress** (Lines 182-191)
   - **Condition**: `breathing_difficulty >= 8 OR severe_dyspnea`
   - **Action**: Urgent evaluation and possible oxygen therapy
   - **Severity**: CRITICAL

---

### 5.3 Warning Alert Rules

**Warning Alerts** (Lines 193-261):

1. **prolonged_nausea** - Nausea ≥4 days
2. **significant_weight_loss** - Weight loss ≥5% in 1 month
3. **severe_fatigue** - Fatigue level ≥8
4. **persistent_diarrhea** - Diarrhea ≥3 days or >5 episodes/day
5. **moderate_pain** - Pain level 5-6
6. **oral_mucositis** - Grade ≥2 or difficulty eating
7. **peripheral_neuropathy** - Neuropathy scale ≥6

---

### 5.4 Alert Evaluation Process

**Function**: `QuizAlertRule.evaluate(responses)` (Lines 58-72)

```python
def evaluate(responses: Dict[str, Any]) -> bool:
    """Check if rule condition is met"""
    try:
        return self.condition(responses)
    except Exception as e:
        logger.error(f"Rule {rule_id} evaluation error: {e}")
        return False
```

**Helper Functions** (Lines 99-137):

```python
def _get_numeric_value(responses, key, default=0.0):
    """Safely extract numeric value"""
    try:
        value = responses.get(key, default)
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def _count_high_severity_symptoms(responses, threshold=7.0):
    """Count symptoms above threshold"""
    count = 0
    for key, value in responses.items():
        if key.endswith(("_scale", "_level", "_intensity")):
            if float(value) >= threshold:
                count += 1
    return count
```

---

## 6. STATE MACHINE & TRANSITIONS

### 6.1 Flow State Transitions

**Location**: `/backend-hormonia/app/domain/flows/core/state_machine.py`

**Valid Transitions** (Lines 142-148):

```python
valid_transitions = {
    "initial_15_days": ["days_16_45", "monthly_recurring", "completed"],
    "days_16_45": ["monthly_recurring", "completed"],
    "monthly_recurring": ["completed", "paused"],
    "paused": ["monthly_recurring", "completed"],
    "completed": []  # Terminal state
}
```

**Transition Validation** (`_validate_state_transitions` - Lines 126-179):

```python
# 1. Get previous flow states
previous_states = db.query(PatientFlowState).filter(
    patient_id == patient_id,
    created_at < current_flow.created_at
).order_by(created_at.desc()).limit(5)

# 2. Check if transition is valid
if previous_states:
    last_flow_type = previous_states[0].flow_type
    if new_flow_type not in valid_transitions[last_flow_type]:
        if new_flow_type != last_flow_type:  # Allow continuation
            raise ValidationError(f"Invalid transition: {last_flow_type} -> {new_flow_type}")

# 3. Check for duplicate active flows
active_flows_count = db.query(PatientFlowState).filter(
    patient_id == patient_id,
    state_data["status"] != "completed"
).count()

if active_flows_count > 0:
    logger.warning(f"Multiple active flows for patient {patient_id}")
```

---

### 6.2 Flow Phase Transition Logic

**Location**: `transition_handler.py` - `transition_flow_phase()` (Lines 38-57)

```python
async def transition_flow_phase(context: FlowContext):
    """Transition patient to monthly recurring phase"""

    # Update flow state metadata
    context.flow_state.state_data.update({
        "phase_transition": {
            "from": "daily_intensive",
            "to": "monthly_recurring",
            "transitioned_at": now_sao_paulo().isoformat(),
            "transitioned_by": agent_id
        }
    })

    # Change flow type
    context.flow_state.flow_type = FlowType.MONTHLY_RECURRING.value

    db.commit()
```

**Trigger Conditions** (`decision_engine.py` - Line 144):

```python
if current_day == 45:  # Day 45 transition
    if requires_consensus("advance_phase"):
        consensus = await seek_consensus(
            "phase_transition",
            {
                "patient_id": str(patient_id),
                "from_phase": "daily",
                "to_phase": "monthly",
                "progress_score": progress_score
            }
        )
        if consensus["consensus_reached"]:
            return FlowDecision.ADVANCE_PHASE
    else:
        return FlowDecision.ADVANCE_PHASE
```

---

## 7. CELERY TASK SCHEDULING

### 7.1 Registered Flow Tasks

**Active in `celery_app.py`** (Lines 108-203):

```python
# FLOW PROCESSING (Every hour)
"process-daily-flows": {
    "task": "app.tasks.flows.process_daily_flows",
    "schedule": 3600.0,  # 1 hour
    "kwargs": {"limit": 100}
},

# DAILY QUESTIONS (8:00 AM Sao Paulo) ⭐ PRIMARY FLOW DRIVER
"send-daily-flow-questions": {
    "task": "flow_automation.send_daily_flow_questions",
    "schedule": crontab(hour=8, minute=0),
    "options": {"queue": "flows"}
},

# DAILY REMINDERS (9:00 AM Sao Paulo)
"send-daily-reminders": {
    "task": "flow_automation.send_daily_reminders",
    "schedule": crontab(hour=9, minute=0),
    "options": {"queue": "flows"}
},

# START PENDING FLOWS (Every 15 minutes)
"check-pending-flows": {
    "task": "flow_automation.check_and_start_pending_flows",
    "schedule": 900.0,
    "options": {"queue": "flows"}
},

# RESUME PAUSED (Every 6 hours)
"resume-paused-flows": {
    "task": "flow_automation.resume_paused_flows",
    "schedule": 21600.0,
    "options": {"queue": "flows"}
},

# PATIENT ALERTS (Every 5 minutes)
"check-patient-alerts": {
    "task": "app.tasks.alerts.check_patient_alerts",
    "schedule": 300.0
},

# MONTHLY QUIZ (Every hour)
"process-monthly-quizzes": {
    "task": "app.tasks.flows.process_monthly_quizzes",
    "schedule": 3600.0,
    "kwargs": {"limit": 100}
}
```

---

### 7.2 Missing Follow-Up Task Registration

**⚠️ CRITICAL GAP**: Follow-up tasks defined but NOT registered

**Expected in `celery_app.py`** (from `follow_up.py` lines 534-549):

```python
# ❌ NOT PRESENT IN celery_app.py
"execute-pending-follow-ups": {
    "task": "tasks.follow_up.execute_pending_follow_ups",
    "schedule": crontab(minute="*/5"),  # Every 5 minutes
    "options": {"queue": "follow_up"}
},

"process-escalation-alerts": {
    "task": "tasks.follow_up.process_escalation_alerts",
    "schedule": crontab(minute="*/10"),  # Every 10 minutes
    "options": {"queue": "follow_up"}
},

"cleanup-old-contexts": {
    "task": "tasks.follow_up.cleanup_old_contexts",
    "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
    "options": {"queue": "follow_up"}
}
```

**Impact**: Follow-up actions are created but **NEVER EXECUTED** automatically.

---

## 8. TASK FAILURE & TIMEOUT HANDLING

### 8.1 Task Retry Configuration

**Location**: `follow_up.py` - Task decorators

```python
@shared_task(
    bind=True,
    base=DatabaseTask,
    name="tasks.follow_up.execute_pending_follow_ups",
    max_retries=task_configs.alerts.max_retries,  # From config
    default_retry_delay=task_configs.alerts.default_retry_delay,
    soft_time_limit=300,  # 5 minutes
    time_limit=360,       # 6 minutes hard limit
    queue="follow_up"
)
def execute_pending_follow_ups(self):
    ...
    if self.request.retries < self.max_retries:
        raise self.retry(exc=e)
```

---

### 8.2 Exponential Backoff for Flows

**Location**: `scheduling.py` - `reschedule_failed_flow()` (Lines 350-384)

```python
async def reschedule_failed_flow(flow_state, retry_delay_hours=1):
    """Calculate reschedule time with exponential backoff"""

    # Get retry count from flow state
    retry_count = flow_state.state_data.get("retry_count", 0)

    # Exponential backoff: 1h, 2h, 4h, 8h (max 8h)
    delay_hours = retry_delay_hours * (2 ** min(retry_count, 3))

    reschedule_time = now + timedelta(hours=delay_hours)

    logger.info(
        f"Rescheduling flow {flow_state.id} for patient {flow_state.patient_id} "
        f"in {delay_hours}h (attempt {retry_count + 1})"
    )

    return reschedule_time
```

**Backoff Schedule**:
- Attempt 1: 1 hour delay
- Attempt 2: 2 hours delay
- Attempt 3: 4 hours delay
- Attempt 4+: 8 hours delay (capped)

---

### 8.3 Action Cleanup

**Location**: `follow_up.py` - Lines 161-169

```python
# Clean up completed/failed actions older than 24 hours
cleanup_threshold = now - timedelta(hours=24)

for action_id, action in list(pending_actions.items()):
    if action.status in ["completed", "failed"]:
        if action.executed_at and action.executed_at < cleanup_threshold:
            del pending_actions[action_id]
            cleaned_count += 1
```

---

## 9. DEBUGGING ENTRY POINTS

### 9.1 Manual Task Execution

**Execute Follow-Up Task Manually**:

```python
from app.tasks.follow_up import execute_pending_follow_ups

# Trigger manually
result = execute_pending_follow_ups.delay()
print(result.get())
```

---

### 9.2 Monitor Agent Execution

**Execute Patient Monitor Agent**:

```python
from app.agents.patient.patient_monitor import PatientMonitorAgent
from app.tasks.base import get_db_session

with get_db_session() as db:
    monitor = PatientMonitorAgent(db)

    # Check adherence
    result = await monitor.process_task({
        "task_type": "monitor_adherence",
        "payload": {
            "patient_id": "<uuid>",
            "days_back": 30
        }
    })
    print(result)
```

---

### 9.3 Flow Coordinator Debug

**Execute Flow Coordinator**:

```python
from app.agents.patient.flow_coordinator import FlowCoordinatorAgent

coordinator = FlowCoordinatorAgent(db)
await coordinator._initialize()

result = await coordinator.process_task({
    "type": "process_daily_flow",
    "payload": {
        "patient_id": "<uuid>",
        "current_day": 20
    }
})
print(result)
```

---

### 9.4 Follow-Up System Health Check

**Check System Health**:

```python
from app.services.follow_up_system import FollowUpSystemService

follow_up = FollowUpSystemService(db)
health = await follow_up.health_check()
print(health)
```

**Expected Output**:

```json
{
    "service": "FollowUpSystemService",
    "timestamp": "2025-12-24T05:30:00-03:00",
    "healthy": true,
    "storage": {
        "backend": "redis",
        "healthy": true,
        "stats": {
            "pending_actions": 15,
            "active_alerts": 3
        }
    },
    "stats": {
        "pending_actions": 15,
        "active_alerts": 3,
        "total_actions": 127,
        "total_alerts": 18
    }
}
```

---

## 10. CRITICAL ISSUES IDENTIFIED

### Issue 1: Follow-Up Tasks Not Registered ⚠️ HIGH PRIORITY

**Problem**: Tasks defined in `follow_up.py` but NOT in `celery_app.py`

**Impact**: Follow-up actions are created but never executed automatically

**Fix Required**:

```python
# Add to celery_app.py beat_schedule:
"execute-pending-follow-ups": {
    "task": "tasks.follow_up.execute_pending_follow_ups",
    "schedule": crontab(minute="*/5"),
    "options": {"queue": "follow_up"}
},
"process-escalation-alerts": {
    "task": "tasks.follow_up.process_escalation_alerts",
    "schedule": crontab(minute="*/10"),
    "options": {"queue": "follow_up"}
},
"cleanup-old-contexts": {
    "task": "tasks.follow_up.cleanup_old_contexts",
    "schedule": crontab(hour=3, minute=0),
    "options": {"queue": "follow_up"}
}
```

---

### Issue 2: Patient Monitor Agent Not Automated ⚠️ MEDIUM PRIORITY

**Problem**: PatientMonitorAgent has no scheduled trigger

**Impact**: Adherence and engagement monitoring only happens manually

**Fix Required**: Create Celery task to periodically execute monitoring

```python
@shared_task
def monitor_patient_adherence():
    """Periodic patient adherence monitoring"""
    with get_db_session() as db:
        # Get all active patients
        patients = db.query(Patient).filter(Patient.status == "active").all()

        monitor = PatientMonitorAgent(db)
        for patient in patients:
            await monitor.process_task({
                "task_type": "monitor_adherence",
                "payload": {
                    "patient_id": str(patient.id),
                    "days_back": 30
                }
            })

# Add to beat_schedule:
"monitor-patient-adherence": {
    "task": "tasks.monitoring.monitor_patient_adherence",
    "schedule": crontab(hour="*/6"),  # Every 6 hours
    "options": {"queue": "monitoring"}
}
```

---

### Issue 3: Redis Rehydration Only on Task Execution ⚠️ MEDIUM PRIORITY

**Problem**: Rehydration only happens when Celery task runs

**Impact**: After service restart, follow-up actions lost until task runs

**Fix Required**: Add rehydration on application startup

```python
# In app/core/lifespan.py startup:
async def startup_event():
    ...
    # Rehydrate follow-up system
    follow_up_service = FollowUpSystemService(db)
    await follow_up_service.rehydrate_from_redis()
    logger.info("Follow-up system rehydrated from Redis")
```

---

## 11. WORKFLOW DIAGRAMS

### 11.1 Daily Flow Processing Workflow

```
┌─────────────────────────────────────────────────────────┐
│  CELERY BEAT: send_daily_flow_questions (8:00 AM Sao Paulo)  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
           ┌─────────────────────┐
           │ Get Active Patients │
           │ (flow_state=ACTIVE) │
           └──────────┬──────────┘
                      │
                      ▼
              ┌───────────────┐
              │ For Each      │
              │ Patient       │
              └───────┬───────┘
                      │
                      ├────────────────────────────────┐
                      ▼                                ▼
            ┌──────────────────┐          ┌─────────────────────┐
            │ Calculate        │          │ Determine Flow      │
            │ current_day      │          │ Phase:              │
            │ from treatment_  │          │ • Days 1-15: Daily  │
            │ start_date       │          │ • Days 16-45: /3    │
            └────────┬─────────┘          │ • Days 46+: Weekly  │
                     │                    └──────────┬──────────┘
                     │                               │
                     ▼                               ▼
            ┌──────────────────┐          ┌─────────────────────┐
            │ Should Send      │──NO───>  │ Skip Patient        │
            │ Today?           │          └─────────────────────┘
            └────────┬─────────┘
                     │ YES
                     ▼
            ┌──────────────────┐
            │ Get Message      │
            │ Template for     │
            │ Flow Phase       │
            └────────┬─────────┘
                     │
                     ▼
            ┌──────────────────┐
            │ Personalize      │
            │ with Patient     │
            │ Name             │
            └────────┬─────────┘
                     │
                     ▼
            ┌──────────────────┐
            │ Create Message   │
            │ Record (PENDING) │
            └────────┬─────────┘
                     │
                     ▼
            ┌──────────────────┐
            │ Send via         │
            │ WhatsApp         │
            │ (UnifiedService) │
            └────────┬─────────┘
                     │
                     ├─────────────┬─────────────┐
                     ▼             ▼             ▼
              ┌──────────┐  ┌──────────┐ ┌──────────┐
              │ SUCCESS  │  │ FAILURE  │ │ TIMEOUT  │
              └────┬─────┘  └────┬─────┘ └────┬─────┘
                   │             │            │
                   ▼             ▼            ▼
              ┌──────────────────────────────────┐
              │ Update flow_state.state_data     │
              │ • last_message_sent              │
              │ • current_day                    │
              │ • decision_agent                 │
              └──────────────────────────────────┘
```

---

### 11.2 Follow-Up Action Lifecycle

```
┌─────────────────────────────────────────┐
│  Patient Sends WhatsApp Message         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│ ResponseProcessingResult                 │
│ • patient_id                             │
│ • structured_response                    │
│ • medical_concerns                       │
│ • escalation_required                    │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│ FollowUpSystemService.                   │
│   process_response_follow_up()           │
└──────────────┬───────────────────────────┘
               │
               ├─────────────────────────────┬──────────────────┐
               ▼                             ▼                  ▼
    ┌────────────────────┐       ┌───────────────────┐  ┌────────────────┐
    │ EmpathyGenerator   │       │ MedicalConcern    │  │ Escalation     │
    │ • Generate         │       │ Generator         │  │ Manager        │
    │   compassionate    │       │ • Handle medical  │  │ • Create alert │
    │   follow-up        │       │   concerns        │  │ • Notify       │
    │ • Use AI service   │       │ • Clarification   │  │   provider     │
    └──────────┬─────────┘       └─────────┬─────────┘  └────────┬───────┘
               │                           │                      │
               └───────────────┬───────────┴──────────────────────┘
                               │
                               ▼
                    ┌────────────────────────┐
                    │ FollowUpAction Created │
                    │ • action_id            │
                    │ • patient_id           │
                    │ • follow_up_type       │
                    │ • priority             │
                    │ • scheduled_for        │
                    │ • parameters           │
                    └──────────┬─────────────┘
                               │
                               ▼
                    ┌────────────────────────┐
                    │ ActionScheduler        │
                    │ • Store in Redis       │
                    │ • Store in memory      │
                    └──────────┬─────────────┘
                               │
                               ▼
                    ┌────────────────────────┐
                    │ Schedule by Type:      │
                    │ • Message → Message    │
                    │   Scheduler            │
                    │ • Escalation →         │
                    │   Escalation Scheduler │
                    └──────────┬─────────────┘
                               │
                               ▼
                    ┌────────────────────────┐
                    │ Wait for scheduled_for │
                    │ time to arrive         │
                    └──────────┬─────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────┐
│ CELERY TASK: execute_pending_follow_ups (Every 5 min)   │
│ ❌ NOT REGISTERED - Manual execution only               │
└──────────────┬───────────────────────────────────────────┘
               │
               ▼
    ┌────────────────────────┐
    │ Rehydrate from Redis   │
    │ (restore in-memory)    │
    └──────────┬─────────────┘
               │
               ▼
    ┌────────────────────────┐
    │ Get Pending Actions    │
    │ (scheduled_for <= now) │
    └──────────┬─────────────┘
               │
               ▼
    ┌────────────────────────┐
    │ Execute by Type:       │
    │ • EMPATHETIC →         │
    │   Send message         │
    │ • MEDICAL →            │
    │   Request info         │
    │ • ESCALATION →         │
    │   Alert provider       │
    │ • PROVIDER →           │
    │   Direct alert         │
    │ • CONVERSATION →       │
    │   Continue dialogue    │
    └──────────┬─────────────┘
               │
               ├─────────────┬─────────────┐
               ▼             ▼             ▼
        ┌──────────┐  ┌──────────┐ ┌──────────┐
        │ SUCCESS  │  │ FAILURE  │  │ RETRY    │
        └────┬─────┘  └────┬─────┘  └────┬─────┘
             │             │              │
             ▼             ▼              ▼
    ┌────────────────────────────────────────┐
    │ Update Action Status:                  │
    │ • status = "completed" or "failed"     │
    │ • executed_at = now                    │
    │ • execution_result = {...}             │
    │ Persist to Redis                       │
    └────────────────────────────────────────┘
```

---

### 11.3 Alert Generation & Escalation

```
┌──────────────────────────────────────┐
│ Patient Completes Quiz               │
│ • Quiz responses submitted           │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ Quiz Alert Rules Evaluation          │
│ (quiz_alert_rules.py)                │
└──────────────┬───────────────────────┘
               │
               ├─────────────┬─────────────┬─────────────┐
               ▼             ▼             ▼             ▼
    ┌────────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
    │ CRITICAL (5)   │ │ WARNING(7) │ │ INFO (2)   │ │ NO ALERT   │
    │ • Pain ≥7      │ │ • Nausea   │ │ • Mild     │ │            │
    │ • Fever+Chills │ │   ≥4 days  │ │   symptoms │ │            │
    │ • Bleeding     │ │ • Weight   │ │ • Appetite │ │            │
    │ • Multiple ≥3  │ │   loss ≥5% │ │   changes  │ │            │
    │ • Respiratory  │ │ • Fatigue  │ └────────────┘ └────────────┘
    │   ≥8           │ │   ≥8       │
    └────┬───────────┘ │ • Diarrhea │
         │             │   ≥3 days  │
         │             │ • Pain 5-6 │
         │             │ • Mucositis│
         │             │ • Neuropathy│
         │             └────┬───────┘
         │                  │
         └──────────┬───────┘
                    │
                    ▼
         ┌────────────────────────┐
         │ Generate Alert Message │
         │ • Use rule template    │
         │ • Fill with patient    │
         │   data                 │
         └──────────┬─────────────┘
                    │
                    ▼
         ┌────────────────────────┐
         │ Create EscalationAlert │
         │ • alert_id             │
         │ • patient_id           │
         │ • escalation_level     │
         │ • concern_type         │
         │ • description          │
         │ • recommended_actions  │
         │ • notification_channels│
         └──────────┬─────────────┘
                    │
                    ▼
         ┌────────────────────────┐
         │ Store in Redis         │
         │ • active_alerts dict   │
         │ • TTL based on level   │
         └──────────┬─────────────┘
                    │
                    ├───────────────────┬──────────────────┐
                    ▼                   ▼                  ▼
         ┌────────────────┐  ┌────────────────┐ ┌────────────────┐
         │ CRITICAL       │  │ WARNING        │ │ INFO           │
         │ • Immediate    │  │ • Notify       │ │ • Log for      │
         │   notification │  │   provider     │ │   monitoring   │
         │ • Multiple     │  │   within 1h    │ │ • Next         │
         │   channels     │  │ • Single       │ │   checkup      │
         │ • SMS + Email  │  │   channel      │ │   review       │
         │ • Phone call   │  │ • Email        │ └────────────────┘
         └────┬───────────┘  └────┬───────────┘
              │                   │
              │                   ▼
              │        ┌────────────────────────┐
              │        │ CELERY TASK:           │
              │        │ process_escalation_    │
              │        │   alerts (10 min)      │
              │        │ ❌ NOT REGISTERED      │
              │        └──────────┬─────────────┘
              │                   │
              │                   ▼
              │        ┌────────────────────────┐
              │        │ Check unacknowledged   │
              │        │ alerts >30 min old     │
              │        └──────────┬─────────────┘
              │                   │
              │                   ▼
              │        ┌────────────────────────┐
              │        │ Escalate Level:        │
              │        │ LOW → MEDIUM           │
              │        │ MEDIUM → HIGH          │
              │        │ HIGH → CRITICAL        │
              │        └────────────────────────┘
              │
              ▼
   ┌────────────────────────┐
   │ NotificationService    │
   │ • Send to provider     │
   │ • SMS via Twilio       │
   │ • Email via SendGrid   │
   │ • In-app notification  │
   └────────────────────────┘
```

---

## 12. CONFIGURATION & CONSTANTS

### 12.1 Flow Phase Configuration

**Flow Phases** (from `send_daily_flow_questions` - Lines 256-275):

```python
FLOW_MESSAGES = {
    "initial_15_days": {
        "content": "Olá {patient_name}! 👋 Como você está se sentindo hoje?...",
        "intent": "daily_checkin_initial"
    },
    "days_16_45": {
        "content": "Olá {patient_name}! 🌟 Como está seu tratamento esta semana?...",
        "intent": "periodic_checkin"
    },
    "monthly_recurring": {
        "content": "Olá {patient_name}! 📋 Esta é sua verificação semanal...",
        "intent": "weekly_checkin"
    }
}
```

**Sending Frequency**:

```python
# Days 1-15: Daily
if current_day <= 15:
    should_send = True

# Days 16-45: Every 3 days
elif current_day <= 45:
    day_in_phase = current_day - 15
    should_send = (day_in_phase % 3 == 0)

# Days 46+: Weekly (days 7, 14, 21 of each 30-day cycle)
else:
    day_in_cycle = (current_day - 45) % 30
    should_send = day_in_cycle in [0, 7, 14, 21]
```

---

### 12.2 Quiz Trigger Configuration

**Quiz Trigger Days** (from `quiz_scheduler.py`):

```python
QUIZ_FLOW_CONSTANTS = {
    "MONTHLY_QUIZ_DAY": 30,  # Day of month to trigger quiz
    "INITIAL_ASSESSMENT_DAY": 15,
    "MID_TREATMENT_DAY": 45
}
```

**Trigger Conditions**:

```python
# Monthly quiz: Every 30 days
if flow_type == "monthly" and current_day % 30 == 0:
    trigger_quiz = True

# Initial assessment: Day 15
if flow_type == "day_1_15" and current_day == 15:
    trigger_quiz = True

# Mid-treatment: Day 45
if flow_type == "day_16_45" and current_day == 45:
    trigger_quiz = True
```

---

### 12.3 Timing Configuration

**Message Send Times** (`scheduling.py` - Lines 51-141):

```python
# Patient timezone-aware scheduling
patient_tz = patient.timezone or "America/Sao_Paulo"
preferred_hour = patient.preferred_message_hour or 10  # 10 AM default

# Calculate send time
send_time = now.replace(
    hour=preferred_hour,
    minute=0,
    second=0,
    microsecond=0
)

# If time passed, schedule for tomorrow
if send_time <= now:
    send_time += timedelta(days=1)

# Add randomization (±30 minutes) to distribute load
random_minutes = random.randint(-30, 30)
send_time += timedelta(minutes=random_minutes)
```

**Validation Rules**:

```python
# Send time validation (Lines 313-348)
# 1. Not in the past
if send_time < now:
    return False, "Send time is in the past"

# 2. Not too far in future (max 7 days)
if send_time > now + timedelta(days=7):
    return False, "Send time is too far in the future"

# 3. Reasonable hours (8 AM - 10 PM patient timezone)
if hour < 8 or hour > 22:
    logger.warning(f"Outside reasonable hours (8-22)")
```

---

## 13. REDIS KEY STRUCTURE

**Follow-Up Actions** (from `FollowUpRedisStore`):

```
# Pending actions hash
Key: "followup:actions:pending"
Type: Hash
TTL: 7 days
Fields: {
    "<action_id>": {
        "action_id": "<uuid>",
        "patient_id": "<uuid>",
        "follow_up_type": "empathetic_response",
        "priority": "high",
        "scheduled_for": "2025-12-24T10:00:00-03:00",
        "status": "pending",
        "created_at": "2025-12-24T05:30:00-03:00",
        "parameters": {...}
    }
}

# Active alerts hash
Key: "followup:alerts:active"
Type: Hash
TTL: 7 days
Fields: {
    "<alert_id>": {
        "alert_id": "<uuid>",
        "patient_id": "<uuid>",
        "escalation_level": "critical",
        "concern_type": "severe_pain",
        "description": "...",
        "notification_channels": ["sms", "email"],
        "created_at": "2025-12-24T05:30:00-03:00"
    }
}

# Conversation contexts
Key: "followup:context:<patient_id>"
Type: Hash
TTL: 7 days
Fields: {
    "conversation_history": [...],
    "current_topic": "pain_management",
    "emotional_state": "anxious",
    "medical_context": {...},
    "last_updated": "2025-12-24T05:30:00-03:00"
}
```

---

## 14. SUMMARY & RECOMMENDATIONS

### Current State Assessment

| Component | Status | Automation | Priority |
|-----------|--------|------------|----------|
| Daily Flow Questions | ✅ Active | Scheduled (8AM) | ✅ Working |
| Patient Monitor Agent | ⚠️ Manual | Not scheduled | ⚠️ Needs Fix |
| Follow-Up Tasks | ❌ Inactive | Not registered | 🔴 **CRITICAL** |
| Flow Coordinator | ✅ Active | Event-driven | ✅ Working |
| Alert Rules | ✅ Active | On quiz completion | ✅ Working |
| Escalation Manager | ⚠️ Partial | Task not registered | ⚠️ Needs Fix |

---

### Critical Fixes Required

1. **Register Follow-Up Tasks in Celery Beat** 🔴
   - Add 3 missing tasks to `celery_app.py`
   - Impact: Enable automated follow-up execution
   - Effort: 5 minutes

2. **Schedule Patient Monitor Agent** ⚠️
   - Create periodic monitoring task
   - Impact: Automated adherence tracking
   - Effort: 30 minutes

3. **Add Startup Rehydration** ⚠️
   - Rehydrate from Redis on app startup
   - Impact: Prevent action loss on restart
   - Effort: 15 minutes

4. **Add Follow-Up Queue to Worker** ⚠️
   - Ensure `follow_up` queue is configured
   - Impact: Enable follow-up task processing
   - Effort: 5 minutes

---

### System Strengths

✅ **Well-Structured Architecture**: Clean separation of concerns
✅ **Comprehensive Alert Rules**: 14 rules covering critical to info
✅ **Redis Persistence**: Actions survive restarts (when tasks run)
✅ **Flow State Machine**: Valid transitions enforced
✅ **Daily Flow Automation**: Working as designed
✅ **Retry & Backoff**: Exponential backoff implemented

---

### Monitoring Recommendations

1. **Add Metrics Dashboard**:
   - Follow-up actions pending/executed
   - Alert counts by severity
   - Patient adherence trends
   - Agent execution success rates

2. **Add Alerting**:
   - Alert if follow-up queue grows >100
   - Alert if adherence drops below 50% average
   - Alert if critical alerts unacknowledged >1 hour

3. **Add Logging**:
   - Structured logs for all agent decisions
   - Log all state transitions
   - Log all follow-up executions

---

## 15. NEXT STEPS

1. **Immediate (Today)**:
   - [ ] Register follow-up tasks in `celery_app.py`
   - [ ] Test follow-up task execution
   - [ ] Verify Redis persistence working

2. **Short-term (This Week)**:
   - [ ] Create patient monitor automation task
   - [ ] Add startup rehydration
   - [ ] Add monitoring dashboard
   - [ ] Document agent coordination protocol

3. **Long-term (Next Sprint)**:
   - [ ] Implement consensus mechanism
   - [ ] Add machine learning for engagement prediction
   - [ ] Create admin UI for alert management
   - [ ] Build comprehensive testing suite

---

**Document Version**: 1.0
**Last Updated**: 2025-12-24
**Author**: Code Quality Analyzer
**Status**: Complete
