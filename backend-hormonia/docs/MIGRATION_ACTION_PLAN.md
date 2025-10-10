# Migration Action Plan - Quick Reference

**Status:** Production database has 38 tables, alembic_version = NULL
**Goal:** Align production with migration system safely

---

## ⚠️ CRITICAL ISSUES

1. **alembic_version is NULL** - No migrations officially applied
2. **webhook_events schema mismatch** - 47% match with migration 019
3. **13 extra tables** - Created manually, not in any migration
4. **6 tables missing** - Migrations not applied (A/B testing, quiz_questions, etc.)

---

## 🎯 Recommended Approach (Option 2)

### Step 1: Backup First! 🔒

```bash
# Backup production database
pg_dump -h database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com \
        -U neoplasias \
        -d postgres \
        --schema-only \
        > production_schema_backup_$(date +%Y%m%d).sql

pg_dump -h database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com \
        -U neoplasias \
        -d postgres \
        > production_full_backup_$(date +%Y%m%d).sql
```

### Step 2: Create Alignment Migration

```bash
cd backend-hormonia
alembic revision -m "align_webhook_events_with_migration_019"
```

Edit the new migration file:

```python
"""Align webhook_events table with migration 019 schema

Revision ID: align_webhook_events
Revises: 018_message_status_events
Create Date: 2025-10-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'align_webhook_events'
down_revision = '018_message_status_events'
branch_labels = None
depends_on = None

def upgrade():
    """Align existing webhook_events table with migration 019 schema."""

    # 1. Create webhook_event_type ENUM
    op.execute("""
        CREATE TYPE webhook_event_type AS ENUM (
            'message_received',
            'message_status',
            'message_delivered',
            'message_read',
            'message_failed',
            'system_notification',
            'unknown'
        );
    """)

    # 2. Rename payload → raw_payload
    op.execute("ALTER TABLE webhook_events RENAME COLUMN payload TO raw_payload;")

    # 3. Add missing columns
    op.add_column('webhook_events',
        sa.Column('webhook_id', sa.String(255), nullable=True)
    )
    op.add_column('webhook_events',
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True)
    )

    # 4. Drop extra columns (preserve data in archived column first if needed)
    op.execute("""
        -- Optional: Archive extra data before dropping
        UPDATE webhook_events SET
            raw_payload = jsonb_set(
                raw_payload,
                '{_archived_fields}',
                jsonb_build_object(
                    'max_retries', max_retries,
                    'next_retry_at', next_retry_at::text,
                    'error_stack_trace', error_stack_trace,
                    'related_patient_id', related_patient_id::text,
                    'event_hash', event_hash,
                    'is_duplicate', is_duplicate,
                    'original_event_id', original_event_id::text
                )
            )
        WHERE max_retries IS NOT NULL
           OR next_retry_at IS NOT NULL
           OR error_stack_trace IS NOT NULL
           OR related_patient_id IS NOT NULL
           OR event_hash IS NOT NULL
           OR is_duplicate IS NOT NULL
           OR original_event_id IS NOT NULL;
    """)

    op.drop_column('webhook_events', 'max_retries')
    op.drop_column('webhook_events', 'next_retry_at')
    op.drop_column('webhook_events', 'error_stack_trace')
    op.drop_column('webhook_events', 'related_patient_id')
    op.drop_column('webhook_events', 'event_hash')
    op.drop_column('webhook_events', 'is_duplicate')
    op.drop_column('webhook_events', 'original_event_id')

    # 5. Convert event_type to ENUM
    op.execute("""
        ALTER TABLE webhook_events
        ALTER COLUMN event_type TYPE webhook_event_type
        USING event_type::text::webhook_event_type;
    """)

    # 6. Add foreign key constraint
    op.create_foreign_key(
        'fk_webhook_events_message',
        'webhook_events',
        'messages',
        ['related_message_id'],
        ['id'],
        ondelete='SET NULL'
    )

def downgrade():
    """Revert webhook_events alignment."""

    # Reverse the changes
    op.drop_constraint('fk_webhook_events_message', 'webhook_events')

    # Convert ENUM back to VARCHAR
    op.execute("""
        ALTER TABLE webhook_events
        ALTER COLUMN event_type TYPE VARCHAR
        USING event_type::text;
    """)

    # Re-add dropped columns
    op.add_column('webhook_events', sa.Column('max_retries', sa.Integer, nullable=True))
    op.add_column('webhook_events', sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('webhook_events', sa.Column('error_stack_trace', sa.Text, nullable=True))
    op.add_column('webhook_events', sa.Column('related_patient_id', postgresql.UUID, nullable=True))
    op.add_column('webhook_events', sa.Column('event_hash', sa.String, nullable=True))
    op.add_column('webhook_events', sa.Column('is_duplicate', sa.Boolean, nullable=True))
    op.add_column('webhook_events', sa.Column('original_event_id', postgresql.UUID, nullable=True))

    # Remove added columns
    op.drop_column('webhook_events', 'updated_at')
    op.drop_column('webhook_events', 'webhook_id')

    # Rename back
    op.execute("ALTER TABLE webhook_events RENAME COLUMN raw_payload TO payload;")

    # Drop ENUM
    op.execute("DROP TYPE IF EXISTS webhook_event_type CASCADE;")
```

### Step 3: Apply Migration Sequence

```bash
# 1. Stamp at migration 018 (last safe point before webhook_events)
alembic stamp 018_message_status_events

# 2. Apply alignment migration
alembic upgrade align_webhook_events

# 3. Skip migration 019 by stamping it (table already exists after alignment)
alembic stamp 019_webhook_events

# 4. Apply remaining migrations
alembic upgrade head
```

### Step 4: Verify

```bash
# Check alembic version
alembic current

# Should show: head (latest migration)

# Verify tables
python scripts/analyze_production_state.py
```

---

## 🚨 Alternative: Conservative Approach (Option 1)

If you want to be EXTRA cautious:

```bash
# 1. Stamp at migration 018 (before webhook_events)
alembic stamp 018_message_status_events

# 2. Create custom migration to DROP and RECREATE webhook_events
alembic revision -m "recreate_webhook_events_from_019"

# In migration:
# - Backup existing webhook_events data to temp table
# - Drop webhook_events
# - Apply migration 019 logic (create table)
# - Migrate data from temp table to new structure
# - Drop temp table

# 3. Apply migrations
alembic upgrade head
```

---

## ⚙️ What Each Migration Will Do

| Migration | Action | Risk | Notes |
|-----------|--------|------|-------|
| align_webhook_events | Fix webhook_events schema | ⚠️ MEDIUM | Data preserved in JSONB |
| 019 (skip) | Create webhook_events | ✅ SAFE | Table already exists (stamped) |
| 020 | Add message_status_events indexes | ✅ SAFE | Indexes only |
| 021 | Add webhook_events indexes | ✅ SAFE | Indexes only |
| 022-028 | Create A/B testing tables | ✅ SAFE | New tables |
| 029 | Create quiz_questions table | ⚠️ CHECK | Verify doesn't exist |
| 030 | Fix audit table naming | ✅ SAFE | Conditional rename |
| 031-039 | Add indexes | ✅ SAFE | Performance only |
| 20251009_230000 | Create whatsapp_delivery_failures | ✅ SAFE | New table |
| 20251009_235500 | Create webhook_idempotency | ✅ SAFE | New table |

---

## 📋 Pre-Flight Checklist

Before running migrations:

- [ ] Full database backup completed
- [ ] Schema-only backup completed
- [ ] Tested alignment migration on local copy
- [ ] Verified no active webhook processing
- [ ] Scheduled maintenance window
- [ ] Team notified
- [ ] Rollback plan documented

---

## 🔄 Rollback Plan

If something goes wrong:

```bash
# 1. Restore from backup
psql -h database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com \
     -U neoplasias \
     -d postgres \
     < production_full_backup_YYYYMMDD.sql

# 2. Reset alembic version
psql -h database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com \
     -U neoplasias \
     -d postgres \
     -c "UPDATE alembic_version SET version_num = NULL;"
```

---

## 📊 Expected End State

After completing all migrations:

### Alembic Status
```bash
alembic current
# Output: 20251009_235500 (head)
```

### New Tables Created
- `ab_experiments`
- `ab_variant_assignments`
- `ab_experiment_metrics`
- `ab_experiment_results`
- `ab_experiment_audit`
- `ab_experiment_monitoring`
- `quiz_questions`
- `whatsapp_delivery_failures`
- `webhook_idempotency`

### Total Tables
- Before: 38 tables
- After: 47 tables (+9 new tables)

### Schema Changes
- `webhook_events`: Aligned with migration 019 schema
- Various tables: New performance indexes added

---

## 🆘 Troubleshooting

### Migration fails: "Table already exists"

```bash
# Check which table
alembic history --verbose

# Skip the problematic migration
alembic stamp <next_migration_id>
```

### ENUM type error

```bash
# Check if ENUM already exists
psql -c "SELECT typname FROM pg_type WHERE typname = 'webhook_event_type';"

# If exists, drop first
psql -c "DROP TYPE IF EXISTS webhook_event_type CASCADE;"
```

### Foreign key constraint fails

```bash
# Check referenced table exists
psql -c "SELECT tablename FROM pg_tables WHERE tablename = 'messages';"

# Check for orphaned records
psql -c "SELECT COUNT(*) FROM webhook_events WHERE related_message_id IS NOT NULL AND related_message_id NOT IN (SELECT id FROM messages);"
```

---

## 📞 Support Contacts

- **DBA:** [Contact info]
- **DevOps:** [Contact info]
- **Tech Lead:** [Contact info]

---

**Document Version:** 1.0
**Last Updated:** 2025-10-09
**Status:** Ready for implementation
