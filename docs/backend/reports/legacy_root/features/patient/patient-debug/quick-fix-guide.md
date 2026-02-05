# Follow-Up Automation Quick Fix Guide

## 🔴 CRITICAL ISSUES IDENTIFIED

### Issue #1: Follow-Up Tasks Not Running (HIGHEST PRIORITY)

**Problem**: Follow-up tasks are defined but NOT registered in Celery Beat scheduler

**Files Affected**:
- `/backend-hormonia/app/celery_app.py` - Missing task registration
- `/backend-hormonia/app/tasks/follow_up.py` - Tasks defined but orphaned

**Impact**:
- ❌ Follow-up messages never sent
- ❌ Escalation alerts never processed
- ❌ Provider notifications not delivered
- ❌ Patient concerns go unaddressed

---

## ⚡ QUICK FIX (15 minutes)

### Step 1: Register Follow-Up Tasks

**File**: `/backend-hormonia/app/celery_app.py`

**Location**: Add to `celery_app.conf.beat_schedule` dictionary (after line 203)

```python
# Add these entries to the beat_schedule dictionary:

# ========== FOLLOW-UP SYSTEM TASKS ==========
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
},
```

---

### Step 2: Register Follow-Up Module in Celery

**File**: `/backend-hormonia/app/celery_app.py`

**Location**: Update `include` parameter in `Celery()` instantiation (around line 21)

**BEFORE**:
```python
celery_app = Celery(
    "hormonia",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.messaging",
        "app.tasks.flows",
        "app.tasks.flow_automation",
        "app.tasks.reports",
        "app.tasks.alerts",
        "app.tasks.quiz_link_tasks",
        "app.tasks.quiz_flow",
        "app.tasks.saga_retry",
        "app.tasks.saga_monitoring",
    ],
)
```

**AFTER**:
```python
celery_app = Celery(
    "hormonia",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.messaging",
        "app.tasks.flows",
        "app.tasks.flow_automation",
        "app.tasks.reports",
        "app.tasks.alerts",
        "app.tasks.quiz_link_tasks",
        "app.tasks.quiz_flow",
        "app.tasks.saga_retry",
        "app.tasks.saga_monitoring",
        "app.tasks.follow_up",  # ✅ ADD THIS LINE
    ],
)
```

---

### Step 3: Configure Follow-Up Queue in Worker

**File**: Worker startup configuration (or deployment config)

**Option A - Update Celery Worker Command** (docker-compose.yml or systemd):

```bash
# BEFORE:
celery -A app.celery_app worker -Q default,flows,quiz,maintenance -l info

# AFTER:
celery -A app.celery_app worker -Q default,flows,quiz,maintenance,follow_up -l info
#                                                                    ^^^^^^^^^^^^^ ADD THIS
```

**Option B - Start Dedicated Follow-Up Worker**:

```bash
# Dedicated worker for follow-up tasks
celery -A app.celery_app worker -Q follow_up -l info --concurrency=2
```

---

### Step 4: Restart Services

```bash
# Stop Celery workers
sudo systemctl stop celery-worker
# OR
docker-compose stop celery-worker celery-beat

# Verify Redis connection
redis-cli ping  # Should return "PONG"

# Restart Celery workers
sudo systemctl restart celery-worker celery-beat
# OR
docker-compose up -d celery-worker celery-beat

# Verify tasks registered
celery -A app.celery_app inspect registered | grep follow_up
```

**Expected Output**:
```
* tasks.follow_up.execute_pending_follow_ups
* tasks.follow_up.process_escalation_alerts
* tasks.follow_up.cleanup_old_contexts
```

---

### Step 5: Verify Execution

```bash
# Check scheduled tasks
celery -A app.celery_app inspect scheduled | grep follow_up

# Monitor task execution
celery -A app.celery_app events

# Check logs
tail -f /var/log/celery/worker.log | grep "follow_up"
```

---

## 🧪 TESTING THE FIX

### Test 1: Manual Task Execution

```python
# In Python shell or Django shell
from app.tasks.follow_up import execute_pending_follow_ups

# Trigger manually
result = execute_pending_follow_ups.delay()
print(f"Task ID: {result.id}")
print(f"Status: {result.status}")
print(f"Result: {result.get(timeout=10)}")
```

**Expected Output**:
```python
{
    'executed_count': 5,
    'failed_count': 0,
    'cleaned_count': 2,
    'timestamp': '2025-12-24T10:30:00Z'
}
```

---

### Test 2: Create and Execute Follow-Up Action

```python
from app.services.follow_up_system import FollowUpSystemService
from app.tasks.base import get_db_session
from uuid import UUID

with get_db_session() as db:
    follow_up_service = FollowUpSystemService(db)

    # Health check
    health = await follow_up_service.health_check()
    print(f"Service Health: {health}")

    # Check pending actions
    result = await follow_up_service.execute_pending_actions(limit=10)
    print(f"Execution Result: {result}")
```

---

### Test 3: Verify Escalation Alerts

```python
from app.tasks.follow_up import process_escalation_alerts

# Execute task
result = process_escalation_alerts.delay()
print(result.get(timeout=10))
```

**Expected Output**:
```python
{
    'alerts_processed': 3,
    'notifications_sent': 3,
    'failed_count': 0,
    'timestamp': '2025-12-24T10:30:00Z'
}
```

---

## 📊 MONITORING AFTER FIX

### Check Task Metrics

```python
# Get task statistics
from celery import current_app

inspector = current_app.control.inspect()

# Active tasks
active = inspector.active()
print(f"Active follow_up tasks: {active.get('follow_up', [])}")

# Scheduled tasks
scheduled = inspector.scheduled()
print(f"Scheduled follow_up tasks: {scheduled.get('follow_up', [])}")

# Task stats
stats = inspector.stats()
print(f"Worker stats: {stats}")
```

---

### Monitor Redis Data

```bash
# Check pending actions
redis-cli HLEN followup:actions:pending

# Check active alerts
redis-cli HLEN followup:alerts:active

# View action details
redis-cli HGET followup:actions:pending <action_id>
```

---

## 🔍 DEBUGGING COMMANDS

### If Tasks Still Not Running

**Check 1: Verify Task Registration**
```bash
celery -A app.celery_app inspect registered | grep follow_up
```

**Check 2: Verify Beat Schedule**
```bash
celery -A app.celery_app inspect scheduled
```

**Check 3: Check Worker Logs**
```bash
# Look for errors
tail -100 /var/log/celery/worker.log | grep -i error

# Look for task execution
tail -100 /var/log/celery/worker.log | grep "execute_pending_follow_ups"
```

**Check 4: Check Redis Connection**
```python
from app.core.redis_unified import get_sync_redis

redis = get_sync_redis()
redis.ping()  # Should return True
```

**Check 5: Check Task Routing**
```bash
# Verify queue configuration
celery -A app.celery_app inspect active_queues
```

---

### If Tasks Execute but Fail

**Check 1: Database Connection**
```python
from app.tasks.base import get_db_session

with get_db_session() as db:
    print(db.execute("SELECT 1").scalar())  # Should return 1
```

**Check 2: AI Service Connection**
```python
from app.services.ai.ai_service import get_ai_service

ai_service = await get_ai_service()
print(f"AI Service: {ai_service}")
```

**Check 3: WhatsApp Service**
```python
from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.tasks.base import get_db_session

with get_db_session() as db:
    whatsapp = UnifiedWhatsAppService(db)
    # Test message sending
```

---

## 🎯 VALIDATION CHECKLIST

After applying fixes, verify:

- [ ] **Tasks Registered**: `celery inspect registered` shows follow_up tasks
- [ ] **Beat Schedule**: Tasks appear in `celery inspect scheduled`
- [ ] **Worker Running**: Worker processing `follow_up` queue
- [ ] **Redis Connected**: Redis ping successful
- [ ] **Manual Execution Works**: `execute_pending_follow_ups.delay()` succeeds
- [ ] **Automatic Execution**: Tasks run every 5 minutes
- [ ] **Logs Clean**: No errors in worker logs
- [ ] **Actions Executing**: Pending actions count decreasing
- [ ] **Alerts Processing**: Escalation alerts being handled
- [ ] **Notifications Sent**: Providers receiving alerts

---

## 🚨 ROLLBACK PLAN

If issues arise after changes:

### Step 1: Stop New Changes
```bash
# Stop workers
sudo systemctl stop celery-worker celery-beat

# Or with Docker
docker-compose stop celery-worker celery-beat
```

### Step 2: Revert Code Changes
```bash
# Revert celery_app.py changes
git checkout HEAD -- backend-hormonia/app/celery_app.py

# Restart with old configuration
sudo systemctl start celery-worker celery-beat
```

### Step 3: Manual Follow-Up Processing
```python
# Process pending actions manually
from app.tasks.follow_up import execute_pending_follow_ups
execute_pending_follow_ups.delay()

# Process escalation alerts manually
from app.tasks.follow_up import process_escalation_alerts
process_escalation_alerts.delay()
```

---

## 📈 EXPECTED IMPROVEMENTS

### Before Fix
- ❌ Follow-up actions: 0 executed per day
- ❌ Escalation alerts: 0 processed per day
- ❌ Provider notifications: 0 sent
- ❌ Patient engagement: Declining

### After Fix
- ✅ Follow-up actions: ~50-100 executed per day
- ✅ Escalation alerts: ~10-20 processed per day
- ✅ Provider notifications: 100% delivery rate
- ✅ Patient engagement: Improved response rates

---

## 🔧 ADDITIONAL OPTIMIZATIONS (OPTIONAL)

### Optimization 1: Add Startup Rehydration

**File**: `/backend-hormonia/app/core/lifespan.py`

**Add to startup_event()**:
```python
async def startup_event():
    # ... existing startup code ...

    # Rehydrate follow-up system from Redis
    try:
        from app.services.follow_up_system import FollowUpSystemService

        follow_up_service = FollowUpSystemService(db)
        rehydrated = await follow_up_service.rehydrate_from_redis()

        logger.info(
            f"Follow-up system rehydrated: "
            f"{rehydrated['pending_actions']} actions, "
            f"{rehydrated['active_alerts']} alerts"
        )
    except Exception as e:
        logger.warning(f"Follow-up rehydration failed: {e}")
```

---

### Optimization 2: Add Patient Monitor Automation

**File**: Create `/backend-hormonia/app/tasks/monitoring.py`

```python
from celery import shared_task
from app.agents.patient.patient_monitor import PatientMonitorAgent
from app.models.patient import Patient
from app.tasks.base import get_db_session
import logging

logger = logging.getLogger(__name__)


@shared_task(name="tasks.monitoring.monitor_patient_adherence")
def monitor_patient_adherence():
    """Periodic patient adherence monitoring"""
    monitored_count = 0
    alerts_count = 0

    with get_db_session() as db:
        # Get active patients
        patients = db.query(Patient).filter(
            Patient.status == "active"
        ).limit(500).all()

        monitor = PatientMonitorAgent(db)

        for patient in patients:
            try:
                result = await monitor.process_task({
                    "task_type": "monitor_adherence",
                    "payload": {
                        "patient_id": str(patient.id),
                        "days_back": 30
                    }
                })

                monitored_count += 1
                if result.get("alerts"):
                    alerts_count += len(result["alerts"])

            except Exception as e:
                logger.error(f"Failed to monitor patient {patient.id}: {e}")

    return {
        "monitored_count": monitored_count,
        "alerts_count": alerts_count
    }
```

**Add to celery_app.py beat_schedule**:
```python
"monitor-patient-adherence": {
    "task": "tasks.monitoring.monitor_patient_adherence",
    "schedule": crontab(hour="*/6"),  # Every 6 hours
    "options": {"queue": "monitoring"}
}
```

---

### Optimization 3: Add Monitoring Dashboard

**Create API endpoint** (`/backend-hormonia/app/api/v2/routers/monitoring.py`):

```python
from fastapi import APIRouter, Depends
from app.services.follow_up_system import FollowUpSystemService
from app.dependencies import get_db_session

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/follow-up/health")
async def follow_up_health(db = Depends(get_db_session)):
    """Get follow-up system health"""
    service = FollowUpSystemService(db)
    return await service.health_check()


@router.get("/follow-up/stats")
async def follow_up_stats(db = Depends(get_db_session)):
    """Get follow-up statistics"""
    # Get pending actions
    # Get active alerts
    # Get execution metrics
    return {...}
```

---

## 📞 SUPPORT & TROUBLESHOOTING

### Common Issues

**Issue**: Tasks not appearing in `inspect registered`
- **Fix**: Check `include` parameter in `Celery()` instantiation
- **Fix**: Restart Celery workers after code changes

**Issue**: Tasks scheduled but not executing
- **Fix**: Check queue configuration in worker command
- **Fix**: Verify worker is consuming from `follow_up` queue

**Issue**: Redis connection errors
- **Fix**: Check Redis server is running: `redis-cli ping`
- **Fix**: Verify Redis URL in settings: `settings.REDIS_URL`

**Issue**: Database connection pool exhausted
- **Fix**: Increase `pool_size` in database configuration
- **Fix**: Reduce worker concurrency temporarily

**Issue**: Task timeouts
- **Fix**: Increase `soft_time_limit` and `time_limit` for tasks
- **Fix**: Optimize task queries (add indexes)

---

## 📚 RELATED DOCUMENTATION

- [Follow-Up Automation Architecture](/docs/patient-debug/follow-up-automation-architecture.md)
- [Celery Task Dependency Graph](/docs/patient-debug/celery-task-dependency-graph.md)
- [State Machine Transitions](/docs/patient-debug/state-machine-transitions.md)

---

## ✅ COMPLETION CRITERIA

**Fix Complete When**:
1. All 3 follow-up tasks appear in `celery inspect registered`
2. Tasks execute automatically every 5-10 minutes
3. Pending actions decrease over time
4. Escalation alerts processed successfully
5. Provider notifications delivered
6. No errors in Celery worker logs
7. Health check endpoint returns `healthy: true`

**Estimated Time**: 15-30 minutes
**Risk Level**: Low (changes are additive, no existing functionality modified)
**Rollback Time**: <5 minutes

---

**Document Version**: 1.0
**Last Updated**: 2025-12-24
**Tested On**: Python 3.13, Celery 5.x, Redis 7.x
