# Flow Scheduling System - Issues & Recommended Fixes

## Executive Summary

The daily WhatsApp follow-up system is functional and well-designed, but has several issues that impact production reliability and performance:

- **4 Critical/High Issues** affecting data consistency
- **3 Medium Issues** affecting performance
- **5 Low Priority Issues** for long-term improvement

---

## Critical Issues (Fix First)

### 1. Database N+1 Query Problem

**Severity**: HIGH
**Impact**: Processing becomes slower as patient count grows
**Location**: `app/tasks/flows/flow_tasks.py` → `_process_single_patient_flow_safe()`

**Current Code Pattern**:
```python
active_flows = flow_repo.get_active_flows(limit=100)

for flow_state in active_flows:
    # This loads patient data for EACH flow
    patient = patient_repo.get(flow_state.patient_id)
    # Result: 100 queries instead of 1
```

**Problem**:
- 100 patients = 100 database queries (instead of 1-2)
- Scales O(n) with patient count
- Becomes bottleneck at scale

**Recommended Fix**:
```python
# Option 1: Use JOIN query
active_flows = db.query(PatientFlowState).join(Patient).filter(
    PatientFlowState.status == "active"
).limit(limit).all()  # Returns both together

# Option 2: Batch fetch
flow_ids = [f.patient_id for f in active_flows]
patients = patient_repo.get_many(patient_ids)
patient_map = {p.id: p for p in patients}

for flow_state in active_flows:
    patient = patient_map[flow_state.patient_id]
```

**Verification**:
```bash
# Check query count with:
from sqlalchemy import event
event.listen(Engine, "after_cursor_execute", print_query_count)

# Before fix: ~100 queries in 5 seconds
# After fix: ~2 queries in 500ms
```

---

### 2. Missing Flow State Synchronization on Message Failure

**Severity**: CRITICAL
**Impact**: Flow advances even if message fails to send
**Location**: Message scheduler doesn't notify flow engine of failures

**Current Flow**:
```
flow_state.current_step += 1  ← Advances immediately
db.commit()
    ↓
Schedule message
    ↓
[IF MESSAGE FAILS] → Flow state never reverted! ✗
```

**Problem**:
- Flow step advances BEFORE message is confirmed sent
- If WhatsApp API fails, patient doesn't receive message but flow advanced
- No retry mechanism for message → flow coordination
- Patient skips day's message permanently

**Recommended Fix**:
```python
# Option 1: Deferred advancement (recommended)
# Only advance AFTER message confirmed sent
message_result = await schedule_message(...)
if message_result.get("success"):
    flow_state.current_step += 1
    db.commit()
else:
    logger.error(f"Message failed, not advancing flow")
    return {"status": "failed", "error": message_result.error}

# Option 2: Async feedback loop
# Schedule message first, then advance when task completes
message = await schedule_flow_message(...)
# Register callback that advances flow on success
message_scheduler.on_success(
    message.id,
    callback=lambda: advance_flow(flow_state)
)
```

**Implementation**:
```python
# In app/domain/messaging/scheduling/message_scheduler/retry_handler.py

async def notify_flow_engine_failure(self, message):
    """Notify flow engine when message fails permanently."""

    # Get flow context from message metadata
    flow_context = message.message_metadata.get("flow_context", {})
    if not flow_context:
        return

    # Update flow state - either revert step or mark as requires_attention
    flow_state = self.db.query(PatientFlowState).filter(
        PatientFlowState.id == flow_context.get("flow_state_id")
    ).first()

    if flow_state:
        flow_state.state_data = flow_state.state_data or {}
        flow_state.state_data["last_message_failed"] = True
        flow_state.state_data["failed_day"] = flow_context.get("day")
        flow_state.state_data["failure_reason"] = message.failure_reason
        self.db.commit()

        logger.warning(
            f"Flow {flow_state.id} marked for review: "
            f"message failed on day {flow_context.get('day')}"
        )
```

---

### 3. Template Resolution Ambiguity

**Severity**: HIGH
**Impact**: Inconsistent message quality, version conflicts
**Location**: Multiple template sources (YAML, DB tables, MessageTemplate)

**Current System**:
```
Message Template Sources:
├── app/config/flow_templates.yaml       (static)
├── flow_template_versions table         (versioned)
├── message_templates table              (reusable)
└── MessageTemplate ORM model            (active)

Problem: No single source of truth!
```

**Current Resolution**:
```python
# app/domain/flows/core/message_handler.py

template = template_manager.get_template(template_name)
# Which source does this check first? Unclear!
# Could be stale, wrong version, or missing
```

**Recommended Fix**:
```python
# Create centralized TemplateResolver

class TemplateResolver:
    """
    Single source of truth for template resolution.
    Priority order (highest to lowest):
    1. Active flow_template_versions
    2. Active message_templates
    3. Fallback to flow_templates.yaml
    """

    async def get_template_for_flow(self, flow_type, day):
        # Get active template version for flow
        version = db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.flow_kind.kind_key == flow_type,
            FlowTemplateVersion.is_active == True
        ).first()

        if not version:
            logger.warning(f"No active version for {flow_type}")
            # Fallback to YAML
            return load_from_yaml(flow_type, day)

        # Get step for this day
        steps = version.steps or []
        day_step = next((s for s in steps if s["day"] == day), None)

        if not day_step:
            raise TemplateNotFoundError(f"No step for {flow_type} day {day}")

        # Get message template
        template = db.query(MessageTemplate).filter(
            MessageTemplate.id == day_step["message_template_id"]
        ).first()

        return template

    def get_fallback_template(self, template_name):
        """Fallback if template not in database."""
        return load_from_yaml(template_name)


# Update usage
async def generate_message(...):
    template = await resolver.get_template_for_flow(flow_type, day)
    return await ai_service.personalize(template.content, patient_data)
```

**Verification**:
```python
# Add test
def test_template_resolution_has_single_source():
    # Remove all YAML files
    # Verify system still works with DB-only templates
    # Verify active version is used, not deprecated ones
```

---

### 4. Incomplete Message Metadata Context

**Severity**: MEDIUM
**Impact**: Can't trace message failures back to flow
**Location**: `MessageScheduler.schedule_flow_message()`

**Current Implementation**:
```python
flow_metadata = {
    "flow_context": {
        "flow_day": flow_day,
        "flow_type": flow_type,
        "template_id": template_id,
        "personalized": True,
        "generated_at": datetime.now().isoformat(),
    }
}
```

**Missing Fields**:
- `flow_state_id` (to update on failure)
- `patient_id` (duplicate but useful)
- `template_version_id` (for reproduction)
- `personalization_config` (what was used?)
- `retry_strategy` (how to retry if fails?)

**Recommended Fix**:
```python
async def schedule_flow_message(
    self,
    patient_id: UUID,
    flow_day: int,
    flow_type: str,
    flow_state_id: UUID,  # Add this
    template_id: str,
    personalized_content: str,
    scheduling_window: SchedulingWindow = SchedulingWindow.BUSINESS_HOURS,
) -> Dict[str, Any]:
    """Schedule a flow-specific message with complete context."""

    flow_metadata = {
        "flow_context": {
            # Existing
            "flow_day": flow_day,
            "flow_type": flow_type,
            "template_id": template_id,
            "personalized": True,
            "generated_at": now_sao_paulo().isoformat(),

            # NEW: Complete context for recovery
            "flow_state_id": str(flow_state_id),  # For updating on failure
            "patient_id": str(patient_id),
            "template_version_id": self._get_template_version_id(template_id),
            "personalization_params": {
                "patient_name": patient.name,
                "treatment_type": patient.treatment_type,
                "days_enrolled": self._calculate_days_enrolled(patient),
            },
            "retry_strategy": {
                "max_retries": 3,
                "base_delay": 60,
                "backoff_factor": 2,
            },
            "original_scheduled_for": None,  # Will be set during scheduling
        }
    }

    return await self.schedule_message(...)
```

---

## Performance Issues (Improve Soon)

### 5. Message Scheduling Memory Leak

**Severity**: MEDIUM
**Location**: `app/domain/flows/core/flow_service.py` → `process_daily_flows()`

**Problem**:
```python
results = {
    "processed_patients": 0,
    "messages_scheduled": 0,
    "details": [],  # Accumulates all results in memory!
}

for flow_state in active_flows:
    result = await process_patient_flow(flow_state)
    results["details"].append(result)  # O(n) memory

# With 1000 patients: ~50KB per result × 1000 = 50MB per batch
# Per hour: 60 batches × 50MB = 3GB/hour!
```

**Recommended Fix**:
```python
# Option 1: Stream results to database
async def process_daily_flows_with_logging(limit: int = 100):
    """Process with streaming results to avoid memory buildup."""

    db = next(get_db())
    flow_engine = get_enhanced_flow_engine(db)
    flow_repo = FlowStateRepository(db)

    active_flows = flow_repo.get_active_flows(limit=limit)

    summary = {
        "processed_count": 0,
        "success_count": 0,
        "error_count": 0,
        "start_time": now_sao_paulo(),
        "batch_id": str(uuid.uuid4()),
    }

    # Log summary, NOT details
    for i, flow in enumerate(active_flows):
        try:
            result = await process_patient_flow(flow)
            summary["processed_count"] += 1

            if result["status"] == "success":
                summary["success_count"] += 1
            else:
                summary["error_count"] += 1

            # Log individual results to database instead of memory
            ProcessingLog.create(
                batch_id=summary["batch_id"],
                patient_id=flow.patient_id,
                status=result["status"],
                details=result.get("error", ""),
                processed_at=now_sao_paulo(),
            )

            # Periodic commit to flush
            if (i + 1) % 10 == 0:
                db.commit()
                logger.info(f"Processed {i+1}/{len(active_flows)} flows")

        except Exception as e:
            summary["error_count"] += 1
            ProcessingLog.create(
                batch_id=summary["batch_id"],
                patient_id=flow.patient_id,
                status="error",
                details=str(e),
            )

    db.commit()
    summary["end_time"] = now_sao_paulo()
    summary["duration"] = (summary["end_time"] - summary["start_time"]).total_seconds()

    # Log summary only
    logger.info(f"Batch {summary['batch_id']} complete: {summary}")

    return summary
```

---

### 6. Timezone Calculation Inefficiency

**Severity**: LOW
**Location**: `app/domain/messaging/scheduling/message_scheduler/timezone_handler.py`

**Problem**:
```python
async def calculate_optimal_delivery_time(self, patient, scheduling_window):
    # Converts string timezone to pytz object EVERY TIME
    patient_tz = pytz.timezone(patient.timezone)  # O(n) string parsing

    # With 100 patients/hour:
    # 100 × 3600 / 24h = 15,000 timezone conversions/day
```

**Recommended Fix**:
```python
from functools import lru_cache
import pytz

class TimezoneHandler:
    def __init__(self, config):
        self.config = config
        self._tz_cache = {}  # Simple dict cache

    def get_timezone(self, tz_name: str) -> pytz.timezone:
        """Get cached timezone object."""
        if tz_name not in self._tz_cache:
            try:
                self._tz_cache[tz_name] = pytz.timezone(tz_name)
            except pytz.exceptions.UnknownTimeZoneError:
                logger.warning(f"Unknown timezone {tz_name}, using Sao Paulo")
                self._tz_cache[tz_name] = pytz.timezone("America/Sao_Paulo")
        return self._tz_cache[tz_name]

    async def calculate_optimal_delivery_time(self, patient, scheduling_window):
        # Use cached timezone
        patient_tz = self.get_timezone(patient.timezone)  # O(1) lookup
        # ... rest of calculation
```

**Performance Impact**:
- Before: 15,000 string parsings/day
- After: 1 parsing per unique timezone (usually <50)
- Speedup: ~99% reduction in timezone operations

---

### 7. Missing Batch Query Optimization

**Severity**: MEDIUM
**Location**: `app/repositories/patient.py`, `app/repositories/flow.py`

**Problem**:
```python
# Current pattern - separate queries
flow_state = flow_repo.get_active_flow(patient_id)  # Query 1
template = template_service.get_template(flow_state.flow_type)  # Query 2
patient = patient_repo.get(patient_id)  # Query 3

# With 100 patients: 300+ queries!
```

**Recommended Fix**:
```python
# Add batch methods to repositories

class FlowStateRepository:
    def get_active_flows_with_templates(self, limit: int = 100):
        """Get flows with templates in single query."""
        return (
            self.db.query(PatientFlowState)
            .join(FlowTemplateVersion)
            .join(FlowKind)
            .filter(PatientFlowState.status == "active")
            .options(
                joinedload(PatientFlowState.template_version)
                    .joinedload(FlowTemplateVersion.kind)
            )
            .limit(limit)
            .all()
        )


class PatientRepository:
    def get_many(self, patient_ids: List[UUID]):
        """Get multiple patients in single query."""
        return self.db.query(Patient).filter(
            Patient.id.in_(patient_ids)
        ).all()
```

---

## Low Priority Issues (Backlog)

### 8. Insufficient Error Logging

**Issue**: Hard to debug why messages weren't sent
**Fix**: Add decision logging to FlowScheduler

```python
class FlowScheduler:
    async def process_daily_flows(self, limit: int = 1000):
        logger.info(f"Starting daily flow processing: {limit} patients")

        for flow_state in active_flows:
            try:
                # Log each decision point
                skip, reason = await self.should_skip_patient_flow(flow_state)
                if skip:
                    logger.debug(f"Skipping flow {flow_state.id}: {reason}")
                    continue

                # Log send time calculation
                send_time = await self.calculate_optimal_send_time(patient, day)
                logger.info(
                    f"Patient {patient.id} day {day}: "
                    f"calculated send_time={send_time}, "
                    f"timezone={patient.timezone}, "
                    f"preferred_hour={patient.preferred_message_hour}"
                )

                # Log quiz checks
                quiz_check = await self.check_quiz_trigger(...)
                if quiz_check["triggered"]:
                    logger.info(f"Quiz triggered for {patient.id}: {quiz_check}")

            except Exception as e:
                logger.error(
                    f"Error processing flow {flow_state.id}: {e}",
                    exc_info=True
                )
```

### 9. Missing Message Uniqueness Constraint

**Issue**: Could schedule duplicate messages
**Fix**: Add database constraint

```sql
ALTER TABLE messages ADD CONSTRAINT
    uq_daily_flow_message
    UNIQUE (patient_id, scheduled_for::date, flow_type, current_day)
    WHERE direction = 'OUTBOUND' AND deleted_at IS NULL;
```

### 10. Timezone Validation Missing

**Issue**: Invalid timezones crash the system
**Fix**: Validate on patient creation

```python
class Patient(BaseModel):
    timezone: str

    @validator('timezone')
    def validate_timezone(cls, v):
        if v not in pytz.all_timezones:
            raise ValueError(f"Invalid timezone: {v}")
        return v
```

### 11. Message Content Sanitization

**Issue**: User data interpolated without escaping
**Fix**: Use parameterized templates

```python
# Before (vulnerable)
message = f"Olá {patient.name}, seu tratamento..."

# After (safe)
from jinja2 import Template
template = Template("Olá {{ name }}, seu tratamento...")
message = template.render(name=patient.name)
```

### 12. Metadata Unbounded Growth

**Issue**: message_metadata can grow infinitely
**Fix**: Archive old metadata

```python
class Message(BaseModel):
    message_metadata: JSONB  # Add constraints

    def add_metadata(self, key, value):
        if not self.message_metadata:
            self.message_metadata = {}

        # Keep only recent metadata
        if len(self.message_metadata) > 20:
            # Archive to separate table
            self.archive_old_metadata()

        self.message_metadata[key] = value
```

---

## Implementation Priority Matrix

| Issue | Severity | Effort | Priority | When |
|-------|----------|--------|----------|------|
| N+1 Query | HIGH | Medium | 1 | Week 1 |
| Message Failure Sync | CRITICAL | Medium | 1 | Week 1 |
| Template Resolution | HIGH | High | 2 | Week 2 |
| Memory Leak | MEDIUM | Low | 2 | Week 2 |
| Timezone Cache | LOW | Low | 3 | Week 3 |
| Batch Queries | MEDIUM | Medium | 2 | Week 2 |
| Error Logging | LOW | Low | 3 | Week 3 |
| Metadata Context | MEDIUM | Low | 2 | Week 2 |
| Constraints | LOW | Low | 3 | Week 4 |
| Content Sanitization | LOW | Low | 3 | Week 4 |

---

## Testing Checklist

- [ ] Test N+1 query fix with 1000 patients
- [ ] Test flow state updates on message failure
- [ ] Test template resolution with missing DB entries
- [ ] Test memory usage with hour-long batch
- [ ] Test timezone caching with 100+ timezones
- [ ] Test batch patient query with 500 patients
- [ ] Test error logging captures all decisions
- [ ] Test message uniqueness constraint
- [ ] Test timezone validation on patient save
- [ ] Test HTML escaping in messages

---

## Monitoring to Add

```python
# Metrics to track

# Query performance
- Queries per batch
- Time to get active flows
- Time to fetch patients

# Message delivery
- Messages scheduled per hour
- Messages sent per hour
- Message failure rate
- Retry rates by error type

# System health
- Celery task queue depth
- Redis memory usage
- Database connection pool exhaustion
- Timezone conversion cache hit rate

# Flow processing
- Patients processed per hour
- Flows advanced per hour
- Quiz triggers per day
- Flow completion rate
```

---

## Deployment Checklist

Before deploying fixes:

- [ ] All tests passing (unit + integration)
- [ ] Code review completed
- [ ] Performance testing in staging
- [ ] Monitoring alerts configured
- [ ] Rollback plan documented
- [ ] Database migration script tested
- [ ] Communication sent to ops team
- [ ] Change log updated
- [ ] Documentation updated
- [ ] Deployment window scheduled

---

**Document Version**: 1.0
**Last Updated**: 2025-12-22
**Status**: Ready for Implementation
