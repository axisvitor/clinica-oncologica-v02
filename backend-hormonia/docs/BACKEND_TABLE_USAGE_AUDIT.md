# Backend Table Usage Audit Report
**Generated:** 2025-10-10
**Purpose:** Verify all backend code uses correct table names matching production database

---

## Executive Summary

### Critical Findings

**🚨 CRITICAL MISMATCH DETECTED:**

The backend codebase has **TWO CONFLICTING DEFINITIONS** for `webhook_events`:

1. **Production Reality (Migration 019):** `webhook_events` table exists with 17 columns for event tracking
2. **New Migration (20251009_235500):** Attempts to create `webhook_idempotency` table
3. **Model Conflict:** `WebhookEvent` model in `app/models/webhook_event.py` has `__tablename__ = "webhook_events"` BUT was designed for the idempotency table

### Tables Status

| Table Name | Exists in Production | Migration File | Model File | Status |
|------------|---------------------|----------------|------------|---------|
| `webhook_events` | ✅ YES (17 cols) | 019_create_webhook_events.py | ❌ CONFLICT | 🔴 **CRITICAL** |
| `webhook_idempotency` | ❌ NO | 20251009_235500 (not applied) | webhook_event.py (wrong name) | 🔴 **BROKEN** |
| `whatsapp_delivery_failures` | ❌ NO | 20251009_230000 (not applied) | failed_message.py | ⚠️ **PENDING** |
| `evolution_webhook_events` | ❓ UNKNOWN | None | message_events.py | ✅ OK |
| `message_status_events` | ✅ YES | 018_create_message_status_events.py | message_events.py | ✅ OK |

---

## Detailed Analysis

### 1. webhook_events Table - CRITICAL CONFLICT

#### Production Schema (Migration 019)
```sql
-- Table: webhook_events (PRODUCTION - 17 columns)
-- Created by: 019_create_webhook_events.py
-- Purpose: Store webhook events for debugging and audit
```

**Columns (17 total):**
- Core: id, event_type, source, payload
- Processing: processed, processed_at, retry_count, max_retries, next_retry_at
- Error: error_message, error_stack_trace
- Relations: related_message_id, related_patient_id
- Deduplication: event_hash, is_duplicate, original_event_id
- Timestamp: created_at

**Indexes (7 total):**
- `idx_webhook_events_type_processed`
- `idx_webhook_events_retry_schedule`
- `idx_webhook_events_source_time`
- `idx_webhook_events_pending`
- `idx_webhook_events_related_msg`
- `idx_webhook_events_related_patient`

#### Model Definition - WRONG TABLE
**File:** `app/models/webhook_event.py`

```python
class WebhookEvent(Base):
    """Model for idempotency tracking."""
    __tablename__ = "webhook_events"  # ❌ WRONG - Should be "webhook_idempotency"

    # Columns don't match production schema
    event_id = Column(String(255), primary_key=True)  # ❌ Production has 'id' UUID
    provider = Column(String(50))                      # ❌ Not in production
    event_type = Column(String(100))                   # ✅ Matches
    received_at = Column(DateTime(timezone=True))      # ❌ Not in production
    processed_at = Column(DateTime(timezone=True))     # ✅ Matches
    expires_at = Column(DateTime(timezone=True))       # ❌ Not in production
    status = Column(String(20))                        # ❌ Not in production
    retry_count = Column(Integer)                      # ✅ Matches
    payload = Column(JSONB)                            # ✅ Matches
    response_data = Column(JSONB)                      # ❌ Not in production
```

**Problem:** This model was designed for idempotency tracking (migration 20251009_235500) but points to the wrong table name.

#### Code Using WebhookEvent Model

**Files referencing WebhookEvent:**
1. ✅ `app/models/__init__.py` - Exports WebhookEvent
2. ❌ `app/middleware/idempotency.py` - Uses WebhookEvent (expects idempotency schema)
3. ❌ `app/services/idempotency_cleanup.py` - Queries WebhookEvent (expects idempotency schema)
4. ❌ `tests/integration/test_webhook_idempotency.py` - Tests WebhookEvent
5. ❌ `tests/unit/middleware/test_idempotency.py` - Tests WebhookEvent

**Impact:** All idempotency code will fail because:
- Model expects `webhook_idempotency` table structure
- Model points to `webhook_events` table name
- Production `webhook_events` has completely different schema
- Migration to create `webhook_idempotency` not applied

---

### 2. whatsapp_delivery_failures Table - NOT IN PRODUCTION

#### Migration Definition
**File:** `alembic/versions/20251009_230000_add_whatsapp_delivery_failures.py`
- **Revision:** 20251009_230000
- **Status:** ❌ NOT APPLIED TO PRODUCTION

**Table Schema (14 columns):**
```sql
CREATE TABLE whatsapp_delivery_failures (
    id UUID PRIMARY KEY,
    patient_id UUID REFERENCES patients(id),
    phone_number VARCHAR(20),
    message_type VARCHAR(50),
    message_content TEXT,
    error_message TEXT NOT NULL,
    error_code VARCHAR(50),
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at TIMESTAMPTZ,
    last_retry_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'pending',
    resolved_at TIMESTAMPTZ,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Model Definition - DIFFERENT STRUCTURE
**File:** `app/models/failed_message.py`

```python
class FailedMessage(BaseModel):
    """DLQ storage for failed messages."""
    __tablename__ = "whatsapp_delivery_failures"  # ✅ Correct name

    # But columns don't match migration!
    original_message_id = Column(UUID)      # ❌ Not in migration
    patient_id = Column(UUID)               # ✅ Matches
    content = Column(Text)                  # ❌ Migration has "message_content"
    whatsapp_phone = Column(String(20))     # ❌ Migration has "phone_number"
    failure_reason = Column(Enum)           # ❌ Not in migration
    failure_details = Column(JSONB)         # ❌ Not in migration (has "metadata")
    retry_count = Column(Integer)           # ✅ Matches
    last_retry_at = Column(DateTime)        # ✅ Matches
    failed_at = Column(DateTime)            # ❌ Not in migration
    dlq_status = Column(Enum)               # ❌ Migration has "status" VARCHAR
    reviewed_by = Column(UUID)              # ❌ Not in migration
    reviewed_at = Column(DateTime)          # ❌ Not in migration
    review_notes = Column(Text)             # ❌ Not in migration
    requeue_count = Column(Integer)         # ❌ Not in migration
    last_requeue_at = Column(DateTime)      # ❌ Not in migration
    dlq_metadata = Column(JSONB)            # ❌ Migration has "metadata"
```

**Problem:** Model schema and migration schema are COMPLETELY DIFFERENT.

#### Code Using FailedMessage Model

**Files referencing FailedMessage:**
1. ✅ `app/integrations/whatsapp/queue/dlq.py` - DLQ handler (extensive usage)
2. ✅ `app/api/v1/admin/dlq.py` - Admin DLQ endpoints
3. ✅ `app/services/message_scheduler.py` - References FailureReason enum
4. ✅ `tests/integration/whatsapp/test_dlq.py` - DLQ integration tests

**Impact:** All DLQ functionality will fail because:
- Table doesn't exist in production
- Even if migration runs, column names don't match model
- Need to reconcile model vs. migration schema

---

### 3. evolution_webhook_events Table - UNKNOWN STATUS

#### Model Definition
**File:** `app/models/message_events.py`

```python
class EvolutionWebhookEvent(BaseModel):
    """Store Evolution API webhook events."""
    __tablename__ = "evolution_webhook_events"

    # Comprehensive schema for webhook storage
    event_type = Column(String(100), index=True)
    source = Column(String(100), index=True)
    payload = Column(JSONB)
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_retry_at = Column(DateTime)
    error_message = Column(Text)
    error_stack_trace = Column(Text)
    related_message_id = Column(UUID)
    related_patient_id = Column(UUID)
    event_hash = Column(String(64), unique=True)
    is_duplicate = Column(Boolean, default=False)
    original_event_id = Column(UUID)
    created_at = Column(DateTime)
```

**Status:**
- ❓ No migration file found for this table
- ❓ Not verified in production database
- ✅ Clean model definition (no conflicts)

**Note:** This appears to be the CORRECT model for what production's `webhook_events` should be.

---

## Migration Analysis

### Applied to Production (19 migrations)
```
001 → Initial migration
...
019 → webhook_events table (17 columns)
020 → message_status_events indexes
021 → webhook_events indexes
022 → A/B experiments
```

### NOT Applied to Production (2 migrations)
```
20251009_230000 → whatsapp_delivery_failures (table doesn't exist)
20251009_235500 → webhook_idempotency (table doesn't exist)
```

### Migration Chain Status
```
[PRODUCTION HEAD: 022_ab_experiments]
    ↓
[BROKEN ROOT: 20251009_230000_add_whatsapp_delivery_failures]
    ↓
[BROKEN: 20251009_235500_add_webhook_idempotency]
```

**Problem:** New migrations have no valid `down_revision` chain to production head.

---

## Code Impact Analysis

### Files with Critical Issues

#### 🔴 HIGH SEVERITY - Will Fail in Production

**1. Idempotency Middleware**
- **File:** `app/middleware/idempotency.py`
- **Issue:** Queries `WebhookEvent` expecting idempotency schema
- **Impact:** All webhook requests to `/api/v1/webhooks/*` will fail
- **Error:** `sqlalchemy.exc.OperationalError: column "event_id" does not exist`

**2. Idempotency Cleanup Service**
- **File:** `app/services/idempotency_cleanup.py`
- **Issue:** Queries `WebhookEvent` for cleanup
- **Impact:** Background cleanup job will crash
- **Error:** `sqlalchemy.exc.OperationalError: column "event_id" does not exist`

**3. DLQ Handler**
- **File:** `app/integrations/whatsapp/queue/dlq.py`
- **Issue:** Inserts into `whatsapp_delivery_failures` table
- **Impact:** Failed message handling will crash
- **Error:** `sqlalchemy.exc.ProgrammingError: relation "whatsapp_delivery_failures" does not exist`

**4. Admin DLQ Endpoints**
- **File:** `app/api/v1/admin/dlq.py`
- **Issue:** Queries `whatsapp_delivery_failures` table
- **Impact:** Admin DLQ page will return 500 errors
- **Error:** `sqlalchemy.exc.ProgrammingError: relation "whatsapp_delivery_failures" does not exist`

#### ⚠️ MEDIUM SEVERITY - Tests Will Fail

**5. Webhook Idempotency Tests**
- **File:** `tests/integration/test_webhook_idempotency.py`
- **File:** `tests/unit/middleware/test_idempotency.py`
- **Issue:** Test WebhookEvent model with wrong schema
- **Impact:** All idempotency tests fail

**6. DLQ Integration Tests**
- **File:** `tests/integration/whatsapp/test_dlq.py`
- **Issue:** Test FailedMessage model with non-existent table
- **Impact:** All DLQ tests fail

---

## Recommended Fixes

### Fix #1: Correct WebhookEvent Model (URGENT)

**Option A: Rename Model Table (Recommended)**
```python
# app/models/webhook_event.py
class WebhookEvent(Base):
    """Model for idempotency tracking."""
    __tablename__ = "webhook_idempotency"  # ✅ FIX: Changed from "webhook_events"
    # ... rest of model unchanged
```

**Then apply migration:**
```bash
alembic upgrade 20251009_235500
```

**Option B: Create Separate Models**
- Rename `WebhookEvent` → `WebhookIdempotency`
- Keep `EvolutionWebhookEvent` for production `webhook_events` table
- Update all imports

### Fix #2: Reconcile whatsapp_delivery_failures Schema

**Decision needed:** Which schema is correct?

**Option A: Use Model Schema (Recommended)**
- Model has more features (DLQ workflow, review, requeue)
- Update migration to match model

**Option B: Use Migration Schema**
- Migration is simpler
- Update model to match migration

**Recommended: Use Model Schema**

Update migration `20251009_230000`:
```python
# Change column names to match model
op.create_table(
    'whatsapp_delivery_failures',
    sa.Column('id', UUID, primary_key=True),
    sa.Column('original_message_id', UUID, ForeignKey('messages.id')),  # Add
    sa.Column('patient_id', UUID, ForeignKey('patients.id')),
    sa.Column('content', Text),  # Rename from message_content
    sa.Column('whatsapp_phone', String(20)),  # Rename from phone_number
    sa.Column('failure_reason', sa.Enum(FailureReason)),  # Add enum
    sa.Column('failure_details', JSONB),  # Add
    sa.Column('retry_count', Integer),
    sa.Column('last_retry_at', DateTime),
    sa.Column('failed_at', DateTime),  # Add
    sa.Column('dlq_status', sa.Enum(DLQStatus)),  # Change from status
    sa.Column('reviewed_by', UUID, ForeignKey('users.id')),  # Add
    sa.Column('reviewed_at', DateTime),  # Add
    sa.Column('review_notes', Text),  # Add
    sa.Column('requeue_count', Integer),  # Add
    sa.Column('last_requeue_at', DateTime),  # Add
    sa.Column('metadata', JSONB),  # Keep
    sa.Column('created_at', DateTime),
    sa.Column('updated_at', DateTime)
)
```

### Fix #3: Fix Migration Chain

Current migrations have no valid chain to production head (022_ab_experiments).

**Fix migration down_revision:**
```python
# 20251009_230000_add_whatsapp_delivery_failures.py
down_revision = '022_ab_experiments'  # Fix from '20251009_210800'

# 20251009_235500_add_webhook_idempotency.py
down_revision = '20251009_230000'  # Keep (already correct)
```

### Fix #4: Apply Migrations to Production

After fixing schemas:
```bash
# 1. Fix model __tablename__
# 2. Fix migration schemas
# 3. Fix migration chain
# 4. Test locally
alembic upgrade head

# 5. Verify tables
psql $DATABASE_URL -c "\dt whatsapp_delivery_failures"
psql $DATABASE_URL -c "\dt webhook_idempotency"

# 6. Deploy to production
```

---

## Implementation Priority

### P0 - Immediate (Deploy Blocking)
1. ✅ Fix `WebhookEvent.__tablename__` → `"webhook_idempotency"`
2. ✅ Fix migration chain `down_revision`
3. ✅ Reconcile `whatsapp_delivery_failures` schema (model vs migration)
4. ✅ Test migrations locally
5. ✅ Apply migrations to production

### P1 - High Priority (Within 24h)
6. ✅ Update all imports after model rename
7. ✅ Run test suite to verify fixes
8. ✅ Update documentation

### P2 - Medium Priority (Within 1 week)
9. ⚠️ Investigate `evolution_webhook_events` table status
10. ⚠️ Audit other model `__tablename__` attributes
11. ⚠️ Create database schema validation tests

---

## Testing Checklist

### Before Deploy
- [ ] `WebhookEvent` model points to `webhook_idempotency` table
- [ ] `FailedMessage` model schema matches migration
- [ ] Migration chain is valid (022 → 230000 → 235500)
- [ ] Local `alembic upgrade head` succeeds
- [ ] All tests pass locally

### After Deploy
- [ ] Verify `webhook_idempotency` table exists in production
- [ ] Verify `whatsapp_delivery_failures` table exists in production
- [ ] Test webhook idempotency middleware
- [ ] Test DLQ handler
- [ ] Monitor for errors in production logs

---

## Summary Statistics

**Tables Audited:** 5
- ✅ **Correct:** 1 (message_status_events)
- ⚠️ **Pending:** 2 (webhook_idempotency, whatsapp_delivery_failures)
- 🔴 **Critical Issues:** 1 (webhook_events conflict)
- ❓ **Unknown:** 1 (evolution_webhook_events)

**Files Affected:** 12+
- Models: 3
- Services: 2
- Middleware: 1
- APIs: 1
- Tests: 5+

**Migrations to Apply:** 2
- 20251009_230000 (whatsapp_delivery_failures)
- 20251009_235500 (webhook_idempotency)

---

## Conclusion

**Critical Issue:** The `WebhookEvent` model has a severe table name conflict that will cause all idempotency and DLQ functionality to fail in production.

**Root Cause:** Migration 20251009_235500 creates `webhook_idempotency` table, but the model points to `webhook_events` (which already exists with a different schema).

**Immediate Action Required:**
1. Change `WebhookEvent.__tablename__` to `"webhook_idempotency"`
2. Reconcile `whatsapp_delivery_failures` schemas
3. Fix migration chain
4. Apply migrations to production

**Risk Level:** 🔴 **CRITICAL** - Deploy blocking issue
