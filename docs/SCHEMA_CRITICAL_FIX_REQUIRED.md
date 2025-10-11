# 🔴 CRITICAL: Database Schema Fix Required

**Date:** 2025-10-11
**Severity:** HIGH
**Impact:** Webhook processing broken
**Status:** ⚠️ **REQUIRES IMMEDIATE FIX**

---

## Issue Summary

The database schema has **ONE CRITICAL MISMATCH** that will cause webhook event tracking to fail.

### The Problem

**Migration creates table:** `webhook_events`
```python
# File: backend-hormonia/alembic/versions/20251010_010000_baseline_production_schema.py
# Line 317

op.create_table(
    'webhook_events',  # ✅ Migration creates this table name
    sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column('event_type', sa.String(100), nullable=False, index=True),
    ...
)
```

**Model expects table:** `evolution_webhook_events`
```python
# File: backend-hormonia/app/models/message_events.py
# Line 103

class EvolutionWebhookEvent(BaseModel):
    __tablename__ = "evolution_webhook_events"  # ❌ Model expects WRONG table name
```

### Impact

❌ **ORM queries fail** - SQLAlchemy can't find `evolution_webhook_events` table
❌ **Webhook processing broken** - Can't track Evolution API webhook events
❌ **Data loss risk** - If migrations run, table structure may be incorrect

---

## The Fix

### Option 1: Update Model to Match Migration (RECOMMENDED)

**File:** `backend-hormonia/app/models/message_events.py`
**Line:** 103

```python
class EvolutionWebhookEvent(BaseModel):
    """
    Store Evolution API webhook events for debugging and audit purposes.

    Captures all webhook events from Evolution API to enable:
    - Debugging message delivery issues
    - Replay of events for testing
    - Audit trail for compliance
    - Performance monitoring

    Note: Maps to 'webhook_events' table created in baseline migration.
    """
    __tablename__ = "webhook_events"  # ✅ FIX: Changed from "evolution_webhook_events"

    # Event classification
    event_type = Column(String(100), nullable=False, index=True)
    ...
```

### Option 2: Create Migration to Rename Table (NOT RECOMMENDED)

This would require:
1. Create new migration to rename `webhook_events` → `evolution_webhook_events`
2. Update all foreign key references
3. Migrate production database

**Reason not recommended:** Migration creates `webhook_events` as documented, changing it would break production.

---

## Verification Steps

After applying the fix:

### 1. Verify Model Mapping
```bash
cd backend-hormonia
python -c "from app.models.message_events import EvolutionWebhookEvent; print(EvolutionWebhookEvent.__tablename__)"
# Expected output: webhook_events
```

### 2. Test ORM Queries
```python
from app.models.message_events import EvolutionWebhookEvent
from app.database import SessionLocal

db = SessionLocal()
try:
    # This should work after fix
    events = db.query(EvolutionWebhookEvent).limit(5).all()
    print(f"✅ Found {len(events)} webhook events")
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    db.close()
```

### 3. Test Webhook Processing
```bash
# Send test webhook to Evolution API endpoint
curl -X POST http://localhost:8000/api/v1/webhooks/evolution \
  -H "Content-Type: application/json" \
  -d '{
    "event": "messages.upsert",
    "instance": "test",
    "data": {...}
  }'

# Verify event is stored
python -c "
from app.models.message_events import EvolutionWebhookEvent
from app.database import SessionLocal

db = SessionLocal()
event = db.query(EvolutionWebhookEvent).order_by(EvolutionWebhookEvent.created_at.desc()).first()
print(f'Latest event: {event.event_type if event else \"None\"}')
db.close()
"
```

---

## Why This Happened

### Historical Context

1. **Initial design** created `webhook_events` table for Evolution API events
2. **Idempotency feature** needed separate table for 24h deduplication
3. **Naming conflict** occurred when adding idempotency table
4. **Solution attempted:** Rename model to `EvolutionWebhookEvent` and table to `evolution_webhook_events`
5. **Migration baseline** created with ORIGINAL name `webhook_events`
6. **Result:** Model and migration out of sync

### Correct Architecture

Two separate webhook tables with clear purposes:

| Table Name | Model Name | Purpose | Retention |
|------------|------------|---------|-----------|
| **webhook_events** | `EvolutionWebhookEvent` | Full event history | Permanent |
| **webhook_idempotency** | `WebhookEvent` | Deduplication | 24 hours |

---

## Related Files

### Files to Update
- ✅ **REQUIRED:** `backend-hormonia/app/models/message_events.py` (line 103)

### Files to Review After Fix
- `backend-hormonia/app/services/webhook_processor.py` - Webhook event processing
- `backend-hormonia/app/api/v1/webhooks/evolution.py` - Webhook endpoint
- `backend-hormonia/tests/test_webhook_events.py` - Unit tests

### Documentation to Update
- ✅ **COMPLETE:** `docs/DATABASE_SCHEMA_COMPREHENSIVE_ANALYSIS.md`
- ✅ **COMPLETE:** `docs/SCHEMA_ANALYSIS_SUMMARY.md`
- ✅ **COMPLETE:** `docs/SCHEMA_CRITICAL_FIX_REQUIRED.md` (this file)

---

## Testing Checklist

After applying the fix, verify:

- [ ] Model `__tablename__` is `"webhook_events"`
- [ ] ORM queries on `EvolutionWebhookEvent` work
- [ ] Webhook endpoint processes events correctly
- [ ] Events are stored in database
- [ ] Event deduplication works (via `webhook_idempotency`)
- [ ] Retry mechanism processes failed events
- [ ] Related message_id and patient_id are set correctly
- [ ] Event hash calculation works
- [ ] Duplicate detection works

---

## Priority & Timeline

**Priority:** 🔴 **HIGH**
**Timeline:** Fix before next production deployment
**Estimated Time:** 5 minutes to update model + 15 minutes testing

---

## References

- **Migration File:** `backend-hormonia/alembic/versions/20251010_010000_baseline_production_schema.py` (line 317)
- **Model File:** `backend-hormonia/app/models/message_events.py` (line 103)
- **Table Documentation:** `docs/DATABASE_SCHEMA_COMPREHENSIVE_ANALYSIS.md` (Section 6.6)

---

## Approval & Sign-off

- [ ] Code review completed
- [ ] Fix tested in development
- [ ] Fix tested in staging
- [ ] Documentation updated
- [ ] Ready for production deployment

---

**Status:** ⚠️ **AWAITING FIX**
**Next Action:** Update `message_events.py` line 103
