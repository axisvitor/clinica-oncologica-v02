# Patient Journey System - Implementation Summary

## Overview

This document summarizes the corrections and improvements implemented to ensure the patient journey system operates smoothly end-to-end, from registration through ongoing monitoring and WhatsApp message delivery.

## Priority 1: Critical Operational Fixes

### ✅ 1. Background Worker Setup

**Status:** COMPLETE

**What Was Done:**
- Created `Dockerfile.worker` for Celery worker deployment
- Created `Dockerfile.beat` for Celery beat scheduler deployment
- Both Dockerfiles include health checks and proper configuration
- Worker processes multiple queues: `celery`, `flows`, `quiz`, `maintenance`, `monitoring`

**Files Created:**
- `backend-hormonia/Dockerfile.worker`
- `backend-hormonia/Dockerfile.beat`

**Existing Infrastructure (Already in Place):**
- `app/celery_app.py` - Celery configuration with beat schedule
- `docker-compose.yml` - Services for celery-worker, celery-beat, celery-flower
- `worker/railway.json` - Railway deployment config for worker
- `beat/railway.json` - Railway deployment config for beat scheduler

**Scheduled Tasks (Already Configured):**
```python
# From celery_app.py beat_schedule:
- process-scheduled-messages: Every 30 seconds
- retry-failed-messages: Every 5 minutes
- cleanup-old-messages: Daily
- generate-message-analytics: Every hour
- process-daily-flows: Every hour (production)
- cleanup-old-flow-data: Daily
- monitor-flow-task-health: Every 5 minutes
- check-expired-quiz-links: Every 30 minutes
- process-quiz-dead-letter-queue: Every 2 hours
```

**How to Deploy:**
```bash
# Local development
docker-compose up -d celery-worker celery-beat

# Production (Railway)
# Worker and beat services will auto-deploy using Dockerfile.worker and Dockerfile.beat
```

**Health Monitoring:**
- Worker health check: `GET /api/v1/worker/health`
- Active tasks: `GET /api/v1/worker/tasks/active`
- Scheduled tasks: `GET /api/v1/worker/tasks/scheduled`
- Worker stats: `GET /api/v1/worker/stats`

---

### ✅ 2. WhatsApp Messaging Consolidation

**Status:** COMPLETE (Documentation)

**What Was Done:**
- Documented the consolidated WhatsApp messaging architecture
- Confirmed all messaging paths converge to single Evolution API client
- Created comprehensive architecture documentation

**Files Created:**
- `docs/WHATSAPP_MESSAGING_ARCHITECTURE.md`

**Architecture Summary:**
```
Entry Points → UnifiedWhatsAppService → (QUEUE/LEGACY) → EvolutionAPIClient → Evolution API
```

**Key Points:**
- **Single API Client:** All WhatsApp messages ultimately go through `EvolutionAPIClient`
- **Unified Routing:** `UnifiedWhatsAppService` determines QUEUE vs LEGACY mode
- **Consistent Tracking:** All messages tracked in `messages` and `message_status_events` tables
- **No Divergent Paths:** Multiple entry points exist but they all converge

**No Code Changes Needed:** The architecture is already consolidated.

---

### ✅ 3. Flow Auto-Enrollment After Registration

**Status:** COMPLETE

**What Was Done:**
- Added configuration flags: `ENABLE_AUTO_FLOW_ENROLLMENT` and `AUTO_FLOW_ENROLLMENT_FALLBACK`
- Updated `PatientService.create_patient()` to respect configuration settings
- Flow enrollment code was already implemented, just needed configuration control

**Files Modified:**
- `backend-hormonia/app/config.py` - Added configuration flags
- `backend-hormonia/app/services/patient.py` - Added configuration checks

**Configuration:**
```python
# In .env or environment variables
ENABLE_AUTO_FLOW_ENROLLMENT=true  # Enable/disable auto-enrollment
AUTO_FLOW_ENROLLMENT_FALLBACK=true  # Use fallback template if specific not found
```

**How It Works:**
1. Patient is created via `POST /api/v1/patients`
2. If `ENABLE_AUTO_FLOW_ENROLLMENT=true`:
   - System determines appropriate flow template based on `cancer_type` or `treatment_type`
   - Calls `flow_engine.start_flow()` with patient ID and template
   - If template not found and `AUTO_FLOW_ENROLLMENT_FALLBACK=true`, uses default template
   - Stores flow metadata in `patient.patient_metadata`
3. If enrollment fails, error is logged but patient creation succeeds
4. Flow state is created in `patient_flow_states` table

**Verification:**
```sql
-- Check if patient has flow enrolled
SELECT p.id, p.name, pfs.flow_type, pfs.started_at, pfs.current_step
FROM patients p
LEFT JOIN patient_flow_states pfs ON p.id = pfs.patient_id
WHERE p.id = '<patient_id>';

-- Check patient metadata for enrollment info
SELECT patient_data->'auto_flow_started', patient_data->'requested_template'
FROM patients
WHERE id = '<patient_id>';
```

---

## Priority 2: Scheduler and Queue Guarantees

### ✅ 4. Daily Flow Advancement Scheduler

**Status:** ALREADY IMPLEMENTED

**What Exists:**
- Celery beat task: `process-daily-flows` runs every hour
- Task: `app.tasks.flows.process_daily_flows`
- Processes up to 100 active flows per run
- Calls `FlowOrchestrator.advance_patient_flow()` for each active flow

**How It Works:**
1. Beat scheduler triggers `process_daily_flows` every hour
2. Task queries `patient_flow_states` for active flows
3. For each flow:
   - Calculates current treatment day
   - Advances flow to appropriate step
   - Schedules messages via Celery tasks
   - Updates `next_scheduled_at` timestamp
4. Results tracked in Redis and logs

**Monitoring:**
```bash
# Check if task is running
celery -A app.celery_app inspect active

# Check scheduled tasks
celery -A app.celery_app inspect scheduled

# View task results
GET /api/v1/worker/tasks/active
```

**No Changes Needed:** System is already configured correctly.

---

### ✅ 5. Monthly Quiz Scheduling

**Status:** ALREADY IMPLEMENTED

**What Exists:**
- Celery beat task: `check-expired-quiz-links` runs every 30 minutes
- Task: `app.tasks.quiz_link_tasks.check_expired_links`
- Generates quiz links and sends via WhatsApp automatically

**How It Works:**
1. Beat scheduler triggers quiz link check every 30 minutes
2. Task queries for patients eligible for monthly quiz
3. For each eligible patient:
   - Generates tokenized quiz link with expiry
   - Creates WhatsApp message with link
   - Schedules message for delivery
4. Quiz sessions tracked in `quiz_sessions` table

**Monitoring:**
```sql
-- Check recent quiz sessions
SELECT qs.id, qs.patient_id, qs.quiz_template_id, qs.status, qs.created_at
FROM quiz_sessions qs
WHERE qs.created_at >= NOW() - INTERVAL '7 days'
ORDER BY qs.created_at DESC;

-- Check quiz link messages
SELECT m.id, m.patient_id, m.content, m.status, m.created_at
FROM messages m
WHERE m.message_metadata->>'quiz_link' IS NOT NULL
ORDER BY m.created_at DESC;
```

**No Changes Needed:** System is already configured correctly.

---

## Priority 3: Frontend Enhancements

### 🔄 6. Message Delivery Status Visibility

**Status:** NEEDS IMPLEMENTATION

**What's Needed:**
- Update `MessagesPage.tsx` to display message status timeline
- Update `WhatsAppPage.tsx` to show delivery status progression
- Create timeline component showing: pending → sent → delivered/read/failed
- Add retry indicators for failed messages

**Recommended Implementation:**
```typescript
// Component: MessageStatusTimeline.tsx
interface MessageStatusEvent {
  status: 'pending' | 'scheduled' | 'sending' | 'sent' | 'delivered' | 'read' | 'failed';
  timestamp: string;
  metadata?: Record<string, any>;
}

// Fetch from: GET /api/v1/messages/{message_id}/status-events
// Display as vertical timeline with icons and timestamps
```

**API Endpoints Available:**
- `GET /api/v1/messages/{message_id}` - Get message with current status
- `GET /api/v1/messages/{message_id}/events` - Get status event history (needs to be created)

---

### 🔄 7. Patient Flow Status Display

**Status:** NEEDS IMPLEMENTATION

**What's Needed:**
- Update `PatientDetailPage.tsx` to show current flow information
- Display: current step, next scheduled message, last interaction
- Add flow progress indicator (e.g., "Day 5 of 15")
- Show recent quiz sessions and completion status

**Recommended Implementation:**
```typescript
// Component: PatientFlowStatus.tsx
interface FlowStatus {
  flowType: string;
  currentStep: string;
  currentDay: number;
  totalDays: number;
  nextScheduledAt: string;
  lastInteractionAt: string;
  status: 'active' | 'paused' | 'completed';
}

// Fetch from: GET /api/v1/patients/{patient_id}/flow-status
// Display as progress bar with step indicators
```

**API Endpoints Available:**
- `GET /api/v1/patients/{patient_id}` - Get patient with flow_state
- `GET /api/v1/flows/patient/{patient_id}` - Get patient flow states

---

## Deployment Checklist

### Environment Variables Required

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:port/db

# Redis (use rediss:// with SSL for production)
REDIS_URL=rediss://default:password@host:port/0
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required

# Celery
CELERY_BROKER_URL=rediss://default:password@host:port/0
CELERY_RESULT_BACKEND=rediss://default:password@host:port/1
CELERY_WORKER_CONCURRENCY=4
CELERY_QUEUES=celery,flows,quiz,maintenance,monitoring

# WhatsApp
EVOLUTION_API_URL=https://your-evolution-api.com
EVOLUTION_API_KEY=your-api-key
EVOLUTION_INSTANCE_NAME=your-instance
ENABLE_WHATSAPP_ON_REGISTRATION=true
WHATSAPP_WELCOME_MESSAGE_ENABLED=true

# Flow Auto-Enrollment
ENABLE_AUTO_FLOW_ENROLLMENT=true
AUTO_FLOW_ENROLLMENT_FALLBACK=true

# Monitoring
LOG_LEVEL=info
```

### Services to Deploy

1. **Web API** - Main FastAPI application
   - Dockerfile: `Dockerfile`
   - Port: 8000
   - Health: `GET /health`

2. **Celery Worker** - Background task processor
   - Dockerfile: `Dockerfile.worker`
   - Health: `GET /api/v1/worker/health`

3. **Celery Beat** - Task scheduler
   - Dockerfile: `Dockerfile.beat`
   - Health: Check celerybeat-schedule file exists

4. **Redis** - Message broker and cache
   - Use managed Redis service (Railway, AWS ElastiCache, etc.)
   - Enable SSL/TLS in production

5. **PostgreSQL** - Database
   - Use managed PostgreSQL service
   - Version: 17.4+

### Verification Steps

1. **Check Workers Are Running:**
```bash
curl http://your-api/api/v1/worker/health
# Should return: {"overall_healthy": true, "worker_status": {"status": "healthy"}}
```

2. **Check Scheduled Tasks:**
```bash
curl http://your-api/api/v1/worker/tasks/scheduled
# Should show beat schedule tasks
```

3. **Test Patient Registration with Auto-Enrollment:**
```bash
curl -X POST http://your-api/api/v1/patients \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Patient", "phone": "+5511999999999", "treatment_type": "quimioterapia"}'

# Check patient flow was created
curl http://your-api/api/v1/patients/{patient_id}
# Should show flow_state and patient_data.auto_flow_started = true
```

4. **Check Message Queue Processing:**
```bash
# Send a test message
curl -X POST http://your-api/api/v1/messages \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "...", "content": "Test", "scheduled_for": "2025-10-15T10:00:00Z"}'

# Check message status updates
curl http://your-api/api/v1/messages/{message_id}
# Status should progress: pending → scheduled → sending → sent → delivered
```

---

## Summary of Changes

### Files Created (4)
1. `backend-hormonia/Dockerfile.worker` - Celery worker container
2. `backend-hormonia/Dockerfile.beat` - Celery beat scheduler container
3. `backend-hormonia/app/api/v1/worker_health.py` - Worker health monitoring API
4. `docs/WHATSAPP_MESSAGING_ARCHITECTURE.md` - WhatsApp architecture documentation

### Files Modified (3)
1. `backend-hormonia/app/config.py` - Added auto-enrollment configuration flags
2. `backend-hormonia/app/services/patient.py` - Added configuration checks for auto-enrollment
3. `backend-hormonia/app/core/router_registry.py` - Registered worker health endpoints

### Documentation Created (2)
1. `docs/WHATSAPP_MESSAGING_ARCHITECTURE.md` - Complete WhatsApp messaging architecture
2. `docs/PATIENT_JOURNEY_FIXES_IMPLEMENTATION.md` - This document

---

## Next Steps (Frontend)

The backend is now fully operational. Frontend enhancements are recommended but not critical:

1. **Message Status Timeline** - Visual timeline showing message delivery progression
2. **Patient Flow Progress** - Display current flow step and progress indicators
3. **Quiz Status Dashboard** - Show quiz completion rates and pending quizzes

These can be implemented incrementally without affecting backend functionality.

---

## Support and Troubleshooting

### Common Issues

**Workers Not Starting:**
- Check Redis connection (must use `rediss://` with SSL in production)
- Verify `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` are set
- Check logs: `docker logs <worker-container>`

**Messages Not Sending:**
- Verify Evolution API is accessible
- Check `EVOLUTION_API_URL` and `EVOLUTION_API_KEY`
- Review message status: `SELECT * FROM messages WHERE status = 'FAILED'`

**Flows Not Advancing:**
- Check beat scheduler is running: `GET /api/v1/worker/tasks/scheduled`
- Verify `process-daily-flows` task is scheduled
- Check flow states: `SELECT * FROM patient_flow_states WHERE completed_at IS NULL`

### Monitoring Endpoints

- **Worker Health:** `GET /api/v1/worker/health`
- **Active Tasks:** `GET /api/v1/worker/tasks/active`
- **Scheduled Tasks:** `GET /api/v1/worker/tasks/scheduled`
- **Worker Stats:** `GET /api/v1/worker/stats`
- **System Health:** `GET /health`
- **Database Health:** `GET /api/v1/health/database`

---

**Implementation Date:** 2025-10-15  
**Status:** Backend Complete, Frontend Enhancements Pending  
**Production Ready:** Yes (with environment variables configured)

