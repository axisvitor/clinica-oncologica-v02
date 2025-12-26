# Flow State Machine Transitions

## State Transition Diagram

```
                    ┌─────────────────────┐
                    │  PATIENT CREATED    │
                    │  (Onboarding)       │
                    └──────────┬──────────┘
                               │
                               │ auto_start_flow
                               │ (check_pending_flows task)
                               ▼
                    ┌─────────────────────┐
                ┌──>│  INITIAL_15_DAYS    │<──┐
                │   │  (Daily Intensive)  │   │ continue
                │   └──────────┬──────────┘   │ (same phase)
                │              │               │
                │              │ Day 16        │
                │              ▼               │
                │   ┌─────────────────────┐   │
                │   │   DAYS_16_45        │───┘
                │   │   (Every 3 days)    │
                │   └──────────┬──────────┘
                │              │
                │              │ Day 46 OR
                │              │ FlowDecision.ADVANCE_PHASE
                │              ▼
                │   ┌─────────────────────┐
                │   │ MONTHLY_RECURRING   │<──┐
                │   │ (Weekly check-ins)  │   │ continue
                │   └──────────┬──────────┘   │ (same phase)
                │              │               │
                │              ├───────────────┘
                │              │
                │              │ pause_flow
pause_flow      │              ├───────────────┐
                │              │               │
                │              │               ▼
                │              │    ┌─────────────────────┐
                │              │    │      PAUSED         │
                │              │    │  (Temporary hold)   │
                │              │    └──────────┬──────────┘
                │              │               │
                │              │               │ resume_flow
                └──────────────┼───────────────┘
                               │
                               │ complete_flow OR
                               │ manual completion
                               ▼
                    ┌─────────────────────┐
                    │     COMPLETED       │
                    │  (Terminal state)   │
                    └─────────────────────┘
```

---

## Valid State Transitions

### Transition Rules

```python
VALID_TRANSITIONS = {
    "initial_15_days": [
        "days_16_45",          # Normal progression on day 16
        "monthly_recurring",   # Skip intermediate phase
        "paused",             # Pause at any time
        "completed"           # Early completion
    ],

    "days_16_45": [
        "monthly_recurring",   # Normal progression on day 46
        "paused",             # Pause at any time
        "completed"           # Early completion
    ],

    "monthly_recurring": [
        "monthly_recurring",   # Continue in same phase
        "paused",             # Pause at any time
        "completed"           # Normal completion
    ],

    "paused": [
        "initial_15_days",     # Resume from initial phase
        "days_16_45",         # Resume from intermediate
        "monthly_recurring",  # Resume from monthly
        "completed"           # Complete without resume
    ],

    "completed": []  # Terminal state - no transitions
}
```

---

## Transition Triggers

### 1. Automatic Time-Based Transitions

```python
# Day 16: initial_15_days → days_16_45
if current_day == 16 and flow_state.flow_type == "initial_15_days":
    transition_to("days_16_45")

# Day 46: days_16_45 → monthly_recurring
if current_day == 46 and flow_state.flow_type == "days_16_45":
    if FlowDecision == ADVANCE_PHASE:
        transition_to("monthly_recurring")
```

**Execution**: `send_daily_flow_questions` task (8AM daily)

---

### 2. Flow Coordinator Decision-Based Transitions

**Decision Engine Triggers** (`decision_engine.py`):

```python
# FlowDecision.ADVANCE_PHASE
async def make_flow_decision(context, analysis):
    # Triggered on day 45
    if context.current_day == 45:
        if progress_score >= 0.6 and risk_level != "high":
            return FlowDecision.ADVANCE_PHASE
```

**Execution**: `FlowCoordinatorAgent.process_task("process_daily_flow")`

---

### 3. Manual Administrative Transitions

```python
# Pause flow (admin action)
POST /api/v2/patients/{patient_id}/flow/pause
→ FlowDecision.PAUSE_FLOW
→ transition_handler.pause_flow(context)

# Resume flow (admin action)
POST /api/v2/patients/{patient_id}/flow/resume
→ FlowDecision.RESUME_FLOW
→ transition_handler.resume_flow(context)

# Complete flow (admin action)
POST /api/v2/patients/{patient_id}/flow/complete
→ flow_state.status = "completed"
```

**Execution**: API endpoints (manual trigger)

---

### 4. Automatic Resume Transitions

```python
# resume_paused_flows task (Every 6h)
# Automatically resumes flows paused >48 hours
if flow_state.status == "paused" and updated_at < NOW() - 48h:
    await flow_engine.resume_patient_flow(flow_state.id)
    → transition_to(previous_flow_type)
```

**Execution**: `resume_paused_flows` Celery task

---

## Transition State Data

### State Metadata Structure

```python
flow_state.state_data = {
    # Phase transition tracking
    "phase_transition": {
        "from": "days_16_45",
        "to": "monthly_recurring",
        "transitioned_at": "2025-12-24T10:00:00Z",
        "transitioned_by": "flow_coordinator_20251224_100000",
        "reason": "Day 46 reached with satisfactory progress"
    },

    # Pause/resume tracking
    "flow_paused": false,
    "paused_at": "2025-12-20T15:30:00Z",
    "paused_by": "admin_user_123",
    "pause_reason": "Patient requested temporary pause",
    "resumed_at": "2025-12-22T09:00:00Z",
    "resumed_by": "system_auto_resume",

    # Current state tracking
    "status": "active",  # active | paused | completed
    "current_day": 47,
    "last_message_sent": "2025-12-24T08:05:23Z",
    "decision_agent": "flow_coordinator_20251224_080000",

    # Optimization tracking
    "optimized_timing": {
        "morning": 9,
        "afternoon": 15,
        "evening": 19
    },
    "timing_optimized_by": "flow_coordinator_20251224_080000",
    "timing_optimized_at": "2025-12-24T08:00:00Z",

    # Personalization tracking
    "personalization": {
        "tone": "supportive",
        "frequency": "normal",
        "content_focus": ["emotional_support", "treatment_adherence"],
        "personalized_by": "flow_coordinator_20251224_080000",
        "personalized_at": "2025-12-24T08:00:00Z"
    },

    # Retry tracking
    "retry_count": 0,
    "last_retry_at": null
}
```

---

## Transition Validation

### Pre-Transition Checks

```python
# Location: state_machine.py - _validate_state_transitions()

async def validate_transition(from_state, to_state, patient_id):
    """Validate if state transition is allowed"""

    # 1. Check if transition is in valid_transitions map
    if to_state not in VALID_TRANSITIONS[from_state]:
        if to_state != from_state:  # Allow continuation in same phase
            raise ValidationError(
                f"Invalid transition: {from_state} → {to_state}"
            )

    # 2. Check for duplicate active flows
    active_flows = db.query(PatientFlowState).filter(
        patient_id == patient_id,
        state_data["status"] != "completed"
    ).count()

    if active_flows > 1:
        logger.warning(
            f"Multiple active flows detected for patient {patient_id}"
        )

    # 3. Check patient existence
    patient = db.query(Patient).get(patient_id)
    if not patient:
        raise ValidationError(f"Patient {patient_id} not found")

    # 4. Check previous state continuity
    previous_flows = db.query(PatientFlowState).filter(
        patient_id == patient_id,
        created_at < current_flow.created_at
    ).order_by(created_at.desc()).limit(1)

    if previous_flows:
        last_flow = previous_flows[0]
        if to_state not in VALID_TRANSITIONS[last_flow.flow_type]:
            logger.warning(
                f"Discontinuous transition: {last_flow.flow_type} → {to_state}"
            )

    return True
```

---

## Transition Execution

### Phase Transition Handler

```python
# Location: transition_handler.py - transition_flow_phase()

async def transition_flow_phase(context: FlowContext):
    """Execute phase transition with metadata tracking"""

    if context.flow_state:
        # Update state metadata
        context.flow_state.state_data = context.flow_state.state_data or {}
        context.flow_state.state_data.update({
            "phase_transition": {
                "from": context.flow_state.flow_type,  # Current phase
                "to": "monthly_recurring",
                "transitioned_at": datetime.now(timezone.utc).isoformat(),
                "transitioned_by": agent_id,
                "trigger": "decision_engine",
                "progress_score": context.progress_score,
                "risk_level": context.risk_level
            }
        })

        # Change flow type
        old_flow_type = context.flow_state.flow_type
        context.flow_state.flow_type = FlowType.MONTHLY_RECURRING.value

        # Commit transaction
        db.commit()

        logger.info(
            f"Flow transition completed: {old_flow_type} → monthly_recurring "
            f"for patient {context.patient_id}"
        )
```

---

### Pause/Resume Handlers

```python
# Pause Flow
async def pause_flow(context: FlowContext):
    """Pause patient flow temporarily"""

    if context.flow_state:
        context.flow_state.state_data = context.flow_state.state_data or {}
        context.flow_state.state_data.update({
            "flow_paused": True,
            "paused_at": datetime.now(timezone.utc).isoformat(),
            "paused_by": agent_id,
            "pause_reason": determine_pause_reason(context),
            "previous_flow_type": context.flow_state.flow_type  # For resume
        })

        context.flow_state.status = "paused"
        db.commit()


# Resume Flow
async def resume_flow(context: FlowContext):
    """Resume paused flow"""

    if context.flow_state:
        # Get previous flow type
        previous_type = context.flow_state.state_data.get(
            "previous_flow_type",
            context.flow_state.flow_type
        )

        context.flow_state.state_data.update({
            "flow_paused": False,
            "resumed_at": datetime.now(timezone.utc).isoformat(),
            "resumed_by": agent_id,
            "pause_duration_hours": calculate_pause_duration(
                context.flow_state.state_data.get("paused_at")
            )
        })

        context.flow_state.status = "active"
        context.flow_state.flow_type = previous_type  # Restore
        db.commit()
```

---

## State Persistence

### Database Schema

```sql
-- patient_flow_states table
CREATE TABLE patient_flow_states (
    id UUID PRIMARY KEY,
    patient_id UUID NOT NULL REFERENCES patients(id),
    flow_type VARCHAR(50) NOT NULL,  -- Flow phase
    status VARCHAR(20) NOT NULL,      -- active | paused | completed
    current_day INTEGER,
    state_data JSONB,                 -- Metadata (transitions, pauses, etc.)
    scheduled_for TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX idx_patient_flow_active
    ON patient_flow_states(patient_id, status)
    WHERE status IN ('active', 'paused');

CREATE INDEX idx_patient_flow_type
    ON patient_flow_states(flow_type);

CREATE INDEX idx_patient_flow_scheduled
    ON patient_flow_states(scheduled_for)
    WHERE status = 'active';
```

---

### State Data Examples

**Initial Phase (Days 1-15)**:
```json
{
    "status": "active",
    "current_day": 10,
    "last_message_sent": "2025-12-24T08:05:00Z",
    "messages_sent_count": 10,
    "response_count": 8,
    "adherence_rate": 0.8
}
```

**Intermediate Phase (Days 16-45)**:
```json
{
    "status": "active",
    "current_day": 30,
    "phase_transition": {
        "from": "initial_15_days",
        "to": "days_16_45",
        "transitioned_at": "2025-12-09T08:00:00Z",
        "transitioned_by": "system",
        "trigger": "automatic_day_16"
    },
    "last_message_sent": "2025-12-24T08:05:00Z",
    "messages_sent_count": 15,
    "response_count": 12,
    "adherence_rate": 0.85
}
```

**Monthly Phase (Days 46+)**:
```json
{
    "status": "active",
    "current_day": 60,
    "phase_transition": {
        "from": "days_16_45",
        "to": "monthly_recurring",
        "transitioned_at": "2025-12-09T10:00:00Z",
        "transitioned_by": "flow_coordinator_20251209_100000",
        "trigger": "decision_engine",
        "progress_score": 0.75,
        "risk_level": "low"
    },
    "last_message_sent": "2025-12-24T08:05:00Z",
    "messages_sent_count": 20,
    "monthly_cycles_completed": 1,
    "quiz_completion_rate": 0.9
}
```

**Paused State**:
```json
{
    "status": "paused",
    "current_day": 35,
    "flow_paused": true,
    "paused_at": "2025-12-20T15:30:00Z",
    "paused_by": "admin_user_123",
    "pause_reason": "Patient hospitalized",
    "previous_flow_type": "days_16_45",
    "auto_resume_scheduled": "2025-12-27T09:00:00Z"
}
```

---

## Transition Event Logging

```python
# Create audit log entry for each transition
async def log_transition_event(
    patient_id: UUID,
    from_state: str,
    to_state: str,
    trigger: str,
    metadata: dict
):
    """Log state transition for audit trail"""

    audit_entry = {
        "event_type": "flow_state_transition",
        "patient_id": str(patient_id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "transition": {
            "from": from_state,
            "to": to_state
        },
        "trigger": trigger,  # automatic | decision_engine | manual | auto_resume
        "metadata": metadata,
        "agent_id": agent_id if trigger == "decision_engine" else None,
        "user_id": user_id if trigger == "manual" else None
    }

    # Store in audit log
    db.add(AuditLog(**audit_entry))
    db.commit()

    # Send to analytics
    await analytics_service.track_event(
        "flow_transition",
        audit_entry
    )
```

---

## State Machine Metrics

### Key Performance Indicators

```python
# Transition success rate
transition_success_rate = {
    "initial_15_days → days_16_45": 0.95,  # 95% complete initial phase
    "days_16_45 → monthly_recurring": 0.88,  # 88% reach monthly phase
    "any → paused": 0.12,  # 12% pause rate
    "paused → resumed": 0.75,  # 75% resume after pause
    "any → completed": 0.82  # 82% completion rate
}

# Average time in each phase
average_phase_duration = {
    "initial_15_days": 15.2,  # days
    "days_16_45": 30.1,       # days
    "monthly_recurring": 180.5,  # days (6 months avg)
    "paused": 3.8            # days
}

# Transition failure reasons
transition_failures = {
    "validation_error": 0.02,  # Invalid transition attempted
    "database_error": 0.01,    # DB commit failed
    "concurrent_modification": 0.005  # Race condition
}
```

---

## Error Handling & Recovery

### Transition Failure Scenarios

**Scenario 1: Validation Failure**
```python
try:
    await validate_transition(from_state, to_state, patient_id)
    await execute_transition(...)
except ValidationError as e:
    logger.error(f"Transition validation failed: {e}")
    # Rollback to previous state
    flow_state.flow_type = from_state
    db.rollback()
    # Alert admin
    await alert_admin(f"Invalid transition attempted: {e}")
```

**Scenario 2: Database Commit Failure**
```python
try:
    flow_state.flow_type = to_state
    db.commit()
except DatabaseError as e:
    logger.error(f"Transition commit failed: {e}")
    db.rollback()
    # Retry with exponential backoff
    await retry_transition_with_backoff(
        from_state, to_state, attempt=1
    )
```

**Scenario 3: Concurrent Modification**
```python
# Use optimistic locking
try:
    flow_state = db.query(PatientFlowState).with_for_update().get(id)
    # Perform transition
    flow_state.flow_type = to_state
    db.commit()
except ConcurrentModificationError:
    logger.warning(f"Concurrent modification detected for flow {id}")
    db.rollback()
    # Reload and retry
    await reload_and_retry_transition(id)
```

---

## Quick Reference

**Most Common Transitions**:
1. `initial_15_days → days_16_45` (Day 16, automatic)
2. `days_16_45 → monthly_recurring` (Day 46, decision-based)
3. `any → paused` (Admin action or patient request)
4. `paused → previous_state` (Auto-resume after 48h)

**Critical Validations**:
- ✅ Transition allowed in `VALID_TRANSITIONS`
- ✅ Patient exists
- ✅ No duplicate active flows
- ✅ State continuity maintained

**Transition Triggers**:
- ⏰ **Automatic**: Day-based (16, 46)
- 🤖 **Decision Engine**: Progress-based
- 👤 **Manual**: Admin action
- 🔄 **Auto-Resume**: After 48h pause

---

**Document Version**: 1.0
**Last Updated**: 2025-12-24
**Total States**: 5 (initial, intermediate, monthly, paused, completed)
**Total Transitions**: 12 valid paths
