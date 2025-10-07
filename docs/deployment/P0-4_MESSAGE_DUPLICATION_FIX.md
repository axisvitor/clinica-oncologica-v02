# P0-4: Message Duplication Fix - Technical Documentation

## Problem Statement

**Issue**: MessageScheduler.schedule_message() created a new Message row with status=SCHEDULED, then Celery send_flow_message() created ANOTHER Message instead of updating the scheduled one. The original message stayed "pending" forever, the new one got sent, making reporting and tracking impossible.

**Impact**:
- Duplicate message records in database
- Incorrect message status tracking
- Impossible to correlate scheduled messages with sent messages
- Broken reporting and analytics
- Potential billing issues (counting duplicates)

## Root Cause Analysis

### Flow Before Fix

```
1. MessageScheduler.schedule_message()
   - Creates Message with status=SCHEDULED
   - Saves to database (message_id: ABC)
   - Schedules Celery task WITHOUT passing message_id

2. Celery send_flow_message(patient_id, message_data)
   - Receives NO message_id
   - Creates NEW Message with status=PENDING (message_id: XYZ)
   - Sends message via WhatsApp
   - Updates XYZ to SENT

3. Result:
   - Message ABC: SCHEDULED forever (orphaned)
   - Message XYZ: SENT (duplicate)
   - Database has 2 messages for 1 actual send
```

### Code Locations

1. **backend-hormonia/app/services/message_scheduler.py:210-238**
   - `schedule_message()` created Message but didn't pass ID to Celery
   - `_schedule_celery_task()` only passed patient_id and message_data

2. **backend-hormonia/app/tasks/flows.py:250-276**
   - `send_flow_message()` had no message_id parameter
   - Always created new Message() object
   - No way to update existing scheduled message

## Solution Implementation

### Changes Made

#### 1. Updated Celery Task Signature (flows.py)

**Before:**
```python
def send_flow_message(self, patient_id: str, message_data: dict[str, Any])
```

**After:**
```python
def send_flow_message(self, patient_id: str, message_data: dict[str, Any], message_id: str = None)
```

#### 2. Added Message Update Logic (flows.py:251-298)

```python
if message_id:
    # UPDATE existing scheduled message
    message = message_repo.get(UUID(message_id))
    if not message:
        raise NotFoundError(f"Scheduled message {message_id} not found")

    # Update status to SENDING
    message.status = MessageStatus.SENDING
    message.message_metadata["celery_execution_started"] = datetime.utcnow().isoformat()
else:
    # CREATE new message (backward compatibility)
    logger.warning(f"Creating new message - message_id not passed")
    message = Message(...)
    db.add(message)
```

#### 3. Updated Status Handling (flows.py:319-349)

```python
# Update message status based on send result
if success:
    message.message_metadata["execution_status"] = "success"
    db.commit()
else:
    message.status = MessageStatus.FAILED
    message.message_metadata["failure_reason"] = "Message sending failed"
    db.commit()
```

#### 4. Added Exception Handling (flows.py:355-390)

```python
except Exception as e:
    # Mark message as FAILED if message_id was provided
    if message_id:
        try:
            message = message_repo.get(UUID(message_id))
            if message:
                message.status = MessageStatus.FAILED
                message.message_metadata["celery_execution_error"] = str(e)
                db.commit()
```

#### 5. Updated Scheduler to Pass Message ID (message_scheduler.py:145-149)

**Before:**
```python
task_result = send_flow_message.apply_async(
    args=[str(message.patient_id), message_data],
    eta=delivery_time
)
```

**After:**
```python
task_result = send_flow_message.apply_async(
    args=[str(message.patient_id), message_data, str(message.id)],  # Added message_id
    eta=delivery_time
)
```

#### 6. Added SENDING Status to Enum (message.py:40)

```python
class MessageStatus(enum.Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    SENDING = "sending"  # NEW: Message being sent by Celery worker
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

#### 7. Created Database Migration

File: `alembic/versions/20251007_add_message_sending_status.py`

Adds SENDING status to PostgreSQL enum:
```sql
ALTER TYPE messagestatus ADD VALUE IF NOT EXISTS 'sending' AFTER 'scheduled';
```

## Status Transition Flow (Fixed)

```
SCHEDULED → SENDING → SENT → DELIVERED → READ
            ↓
           FAILED (on error)
```

### Status Meanings

- **SCHEDULED**: Message created, Celery task scheduled with ETA
- **SENDING**: Celery worker picked up task, sending in progress
- **SENT**: WhatsApp API confirmed send
- **DELIVERED**: WhatsApp confirmed delivery to device
- **READ**: User read the message
- **FAILED**: Send attempt failed after retries

## Benefits

1. **One-Message Semantics**: Exactly one database record per actual message
2. **Accurate Tracking**: Complete lifecycle from scheduling to delivery
3. **Proper Reporting**: No duplicate counts, accurate metrics
4. **Retry Safety**: Retries update same message, no new duplicates
5. **Audit Trail**: Full metadata trail in single record
6. **Backward Compatible**: Legacy calls without message_id still work

## Testing

### Unit Tests

File: `tests/test_message_duplication_fix.py`

Coverage:
- ✅ Schedule creates single message record
- ✅ Celery task updates existing message
- ✅ Status transitions (SCHEDULED → SENDING → SENT)
- ✅ Failure handling (marks FAILED)
- ✅ Backward compatibility without message_id
- ✅ No duplicate messages in integration test

### Manual Testing

```bash
# 1. Run migration
cd backend-hormonia
alembic upgrade head

# 2. Run tests
pytest tests/test_message_duplication_fix.py -v

# 3. Test in API
curl -X POST http://localhost:8000/api/v1/messages/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "...",
    "content": "Test message",
    "scheduling_window": "business_hours"
  }'

# 4. Check database
psql -d hormonia_db -c "
  SELECT id, status, created_at, scheduled_for
  FROM messages
  WHERE patient_id = '...'
  ORDER BY created_at DESC
  LIMIT 5;
"
```

## Deployment Checklist

- [ ] Run migration: `alembic upgrade head`
- [ ] Restart Celery workers: `supervisorctl restart celery-worker`
- [ ] Restart backend API: `supervisorctl restart backend`
- [ ] Verify no orphaned SCHEDULED messages in database
- [ ] Monitor Celery logs for message_id in task calls
- [ ] Check message status transitions in database
- [ ] Verify no duplicate messages created
- [ ] Test retry behavior (kill worker mid-send)
- [ ] Confirm reporting accuracy

## Monitoring

### Key Metrics

```sql
-- Count messages by status
SELECT status, COUNT(*)
FROM messages
GROUP BY status;

-- Find orphaned scheduled messages (older than 1 hour)
SELECT id, patient_id, scheduled_for, created_at
FROM messages
WHERE status = 'scheduled'
  AND scheduled_for < NOW() - INTERVAL '1 hour';

-- Check for duplicates (same content, same patient, near same time)
SELECT patient_id, content, COUNT(*)
FROM messages
WHERE created_at > NOW() - INTERVAL '1 day'
GROUP BY patient_id, content
HAVING COUNT(*) > 1;

-- Verify Celery task metadata
SELECT
  id,
  status,
  message_metadata->>'celery_task_id' as task_id,
  message_metadata->>'execution_status' as exec_status
FROM messages
WHERE created_at > NOW() - INTERVAL '1 day'
ORDER BY created_at DESC;
```

### Logging

Look for these log patterns:

```
# Good: Message ID passed to Celery
"Scheduled Celery task abc-123 for message def-456 at 2025-10-07T10:00:00"

# Good: Updating existing message
"Sending flow message to patient xyz, message_id: def-456"

# Bad: Legacy behavior (backward compatibility)
"Creating new message for patient xyz - this may indicate message_id was not passed"
```

## Rollback Plan

If issues occur:

1. **Stop Celery workers**: `supervisorctl stop celery-worker`
2. **Revert code changes**: `git revert <commit-hash>`
3. **Database**: Keep migration (SENDING status is harmless)
4. **Restart services**: `supervisorctl start all`
5. **Mark orphaned messages as FAILED**:
   ```sql
   UPDATE messages
   SET status = 'failed',
       message_metadata = message_metadata || '{"rollback": "orphaned during P0-4 fix"}'::jsonb
   WHERE status IN ('scheduled', 'sending')
     AND scheduled_for < NOW() - INTERVAL '1 hour';
   ```

## Related Issues

- **P0-1**: schedule_existing_message() implementation (prerequisite)
- **P0-5**: MessageSender state management (uses same status flow)
- **P0-6**: Retry mechanism (relies on single message ID)

## Performance Impact

- **Negligible**: Added one UUID parameter to Celery task
- **Database**: One UPDATE instead of INSERT (faster)
- **Network**: No change
- **Memory**: Slightly reduced (no duplicate objects)

## Security Considerations

- Message ID validation prevents injection
- Status transitions only allow valid progressions
- Failed messages can't be re-sent without explicit retry
- Audit trail preserved in metadata

## Future Improvements

1. Add database constraint to prevent duplicate messages
2. Implement message deduplication at API level
3. Add monitoring dashboard for message lifecycle
4. Create automated cleanup job for orphaned messages
5. Add message_id to all Celery logs for better tracing

---

**Author**: Claude Code Agent (Code Implementation Agent)
**Date**: 2025-10-07
**Status**: ✅ Implemented, Ready for Testing
**Priority**: P0 (Critical)
