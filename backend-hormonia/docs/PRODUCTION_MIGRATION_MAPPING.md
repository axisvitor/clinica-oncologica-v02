# Production Database Migration Mapping

**Analysis Date:** 2025-10-09
**Database:** AWS RDS PostgreSQL (database-clinica-neoplasias)
**Current Alembic Version:** `None` (empty alembic_version table)

---

## Executive Summary

The production database has **38 tables** that were manually created, NOT through Alembic migrations. The `alembic_version` table exists but `version_num` is `NULL`, indicating NO migrations have been officially applied via Alembic.

**CRITICAL FINDING:** The database schema DOES NOT match ANY single migration file exactly. Tables have been manually created and modified outside of the migration system.

---

## Production Tables (38 Total)

### Core System Tables
1. ✅ **alembic_version** - Migration tracking (EXISTS but version_num = NULL)
2. ✅ **users** - User accounts
3. ✅ **patients** - Patient records
4. ✅ **messages** - Message history
5. ✅ **alerts** - Patient alerts
6. ✅ **medical_reports** - Medical reports

### Flow Management
7. ✅ **flow_states** - Patient flow states
8. ✅ **patient_flow_states** - Patient-specific flow states
9. ✅ **flow_kinds** - Flow type definitions (migration 015)
10. ✅ **flow_template_versions** - Flow template versioning (migration 015)
11. ✅ **flow_template_categories** - Flow categories (NOT in any migration)
12. ✅ **flow_template_shares** - Template sharing (NOT in any migration)
13. ✅ **flow_template_stats** - Template statistics (NOT in any migration)
14. ✅ **flow_analytics** - Flow analytics (NOT in any migration)
15. ✅ **flow_messages** - Flow messages (NOT in any migration)

### Quiz System
16. ✅ **quiz_templates** - Quiz templates
17. ✅ **quiz_responses** - Quiz responses
18. ✅ **quiz_sessions** - Quiz sessions (migration 002)
19. ✅ **quiz_sessions_v2** - Quiz sessions v2 (NOT in any migration)
20. ✅ **quiz_template_versions_v2** - Quiz template versions v2 (NOT in any migration)

### Webhook & Messaging
21. ✅ **webhook_events** - Webhook event tracking (EXISTS but DIFFERENT from migration 019)
22. ✅ **message_status_events** - Message status tracking (migration 018)
23. ❌ **webhook_idempotency** - MISSING (migration 20251009_235500 NOT applied)
24. ❌ **whatsapp_delivery_failures** - MISSING (migration 20251009_230000 NOT applied)

### Admin System
25. ✅ **admin_users** - Admin users (NOT in any migration)
26. ✅ **admin_roles** - Admin roles (NOT in any migration)
27. ✅ **admin_permissions** - Admin permissions (NOT in any migration)
28. ✅ **admin_role_permissions** - Role-permission mapping (NOT in any migration)
29. ✅ **admin_user_permissions** - User-permission mapping (NOT in any migration)
30. ✅ **admin_sessions** - Admin sessions (NOT in any migration)
31. ✅ **admin_security_events** - Security events (NOT in any migration)
32. ✅ **admin_ip_whitelist** - IP whitelist (NOT in any migration)
33. ✅ **admin_ip_blacklist** - IP blacklist (NOT in any migration)
34. ✅ **admin_audit_log** - Admin audit log (NOT in any migration)

### Audit & Tracking
35. ✅ **audit_log_entries** - Audit log entries (migration 006)
36. ✅ **audit_trail** - Audit trail (NOT in any migration)
37. ✅ **user_sync_log** - User sync log (NOT in any migration)

### Other
38. ✅ **user_profiles** - User profiles (NOT in any migration)
39. ✅ **contacts** - Contacts (NOT in any migration)
40. ✅ **appointments** - Appointments (NOT in any migration)

---

## Key Findings

### 1. webhook_events Table Mismatch

**Migration 019 Expected Schema:**
```sql
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY,
    event_type webhook_event_type NOT NULL,  -- ENUM
    source VARCHAR(100) NOT NULL,
    webhook_id VARCHAR(255),
    raw_payload JSONB NOT NULL,
    processed BOOLEAN DEFAULT false,
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    related_message_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**Actual Production Schema:**
```sql
CREATE TABLE webhook_events (
    id UUID NOT NULL,
    event_type VARCHAR NOT NULL,  -- NO ENUM!
    source VARCHAR NOT NULL,
    payload JSONB NOT NULL,  -- Different name: payload vs raw_payload
    processed BOOLEAN NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE NULL,
    retry_count INTEGER NULL,
    max_retries INTEGER NULL,  -- EXTRA COLUMN
    next_retry_at TIMESTAMP WITH TIME ZONE NULL,  -- EXTRA COLUMN
    error_message TEXT NULL,
    error_stack_trace TEXT NULL,  -- EXTRA COLUMN
    related_message_id UUID NULL,
    related_patient_id UUID NULL,  -- EXTRA COLUMN
    event_hash VARCHAR NOT NULL,  -- EXTRA COLUMN
    is_duplicate BOOLEAN NULL,  -- EXTRA COLUMN
    original_event_id UUID NULL,  -- EXTRA COLUMN
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```

**Differences:**
- ❌ Missing `webhook_event_type` ENUM
- ❌ Column renamed: `raw_payload` → `payload`
- ✅ Added 7 extra columns not in migration 019
- ❌ No `updated_at` column

### 2. Missing Migrations

These migrations have NOT been applied to production:

1. **20251009_230000** - `whatsapp_delivery_failures` table
2. **20251009_235500** - `webhook_idempotency` table
3. **029_quiz_questions** - `quiz_questions` table (probably)
4. **022-028** - A/B testing tables (ab_experiments, ab_variant_assignments, etc.)

### 3. Extra Tables (Not in ANY migration)

These tables exist in production but are NOT created by any migration:

- `admin_*` tables (10 tables) - Full admin system
- `flow_template_categories`
- `flow_template_shares`
- `flow_template_stats`
- `flow_analytics`
- `flow_messages`
- `quiz_sessions_v2`
- `quiz_template_versions_v2`
- `audit_trail`
- `user_sync_log`
- `user_profiles`
- `contacts`
- `appointments`

---

## Migration Timeline Reconstruction

Based on table structure analysis, here's the likely migration history:

### Phase 1: Initial Setup (Manual Creation)
- **001_initial_migration** - Core tables (users, patients, messages, alerts, etc.)
- Status: ✅ Tables exist but with modifications

### Phase 2: Quiz System
- **002_add_quiz_sessions_table** - quiz_sessions table
- Status: ✅ Table exists

### Phase 3: Flow Templates
- **002_add_flow_templates** - flow_templates table (later deprecated)
- **015_add_template_versioning_tables** - flow_kinds, flow_template_versions
- Status: ✅ Tables exist

### Phase 4: Audit System
- **006_add_ai_audit_logs_table** - audit_log_entries
- Status: ✅ Table exists

### Phase 5: Webhook System
- **018_create_message_status_events** - message_status_events table
- Status: ✅ Table exists
- **019_create_webhook_events** - webhook_events table
- Status: ⚠️ Table exists but SCHEMA MISMATCH

### Phase 6: A/B Testing (NOT Applied)
- **022-028** - ab_experiments and related tables
- Status: ❌ Not applied

### Phase 7: Recent Migrations (NOT Applied)
- **20251009_230000** - whatsapp_delivery_failures
- **20251009_235500** - webhook_idempotency
- Status: ❌ Not applied

---

## Recommended Action Plan

### Option 1: Stamp at Safe Point (RECOMMENDED)

**Safest approach:** Stamp the database at the last migration where tables match exactly.

```bash
# 1. Find the last "safe" migration (before webhook_events mismatch)
# Based on analysis: migration 018 (message_status_events)

# 2. Stamp the database
alembic stamp 018_message_status_events

# 3. Then apply pending migrations
alembic upgrade head
```

**This will apply:**
- Migration 019 (webhook_events) - Will FAIL due to existing table
- Migrations 020-028 (indexes, A/B testing)
- Migration 029 (quiz_questions)
- Migration 20251009_230000 (whatsapp_delivery_failures)
- Migration 20251009_235500 (webhook_idempotency)

**Problem:** Migration 019 will fail because `webhook_events` table already exists with different schema.

### Option 2: Fix webhook_events, Then Stamp

**Better approach:** Fix the schema mismatch first.

```bash
# 1. Create manual migration to align webhook_events with migration 019 schema
alembic revision -m "fix_webhook_events_schema_alignment"

# 2. In the migration:
#    - Rename columns (payload -> raw_payload)
#    - Drop extra columns
#    - Create webhook_event_type ENUM
#    - Alter event_type column to use ENUM

# 3. Stamp at migration 019
alembic stamp 019_webhook_events

# 4. Apply pending migrations
alembic upgrade head
```

### Option 3: Stamp at Current HEAD (RISKY)

**Dangerous approach:** Pretend all migrations are applied.

```bash
alembic stamp head
```

**Problems:**
- Missing tables (webhook_idempotency, whatsapp_delivery_failures, quiz_questions)
- Schema mismatches won't be fixed
- Future migrations may fail due to missing prerequisites

---

## Detailed Migration Mapping

### Tables Created by Migrations vs Production

| Migration | Tables Created | Status in Production |
|-----------|---------------|---------------------|
| 001_initial | users, patients, messages, flow_states, quiz_templates, quiz_responses, medical_reports, alerts | ✅ All exist |
| 002_quiz_sessions | quiz_sessions | ✅ Exists |
| 002_flow_templates | flow_templates | ❓ Unknown (deprecated) |
| 006_audit_log | audit_log_entries + indexes | ✅ Exists |
| 015_template_versioning | flow_kinds, flow_template_versions | ✅ Both exist |
| 018_message_status | message_status_events | ✅ Exists |
| 019_webhook_events | webhook_events | ⚠️ EXISTS but WRONG SCHEMA |
| 020_message_indexes | N/A (indexes only) | ❓ Unknown |
| 021_webhook_indexes | N/A (indexes only) | ❓ Unknown |
| 022_ab_experiments | ab_experiments | ❌ MISSING |
| 023_ab_variants | ab_variant_assignments | ❌ MISSING |
| 024_ab_metrics | ab_experiment_metrics | ❌ MISSING |
| 025_ab_results | ab_experiment_results | ❌ MISSING |
| 026_ab_audit | ab_experiment_audit | ❌ MISSING |
| 027_ab_monitoring | ab_experiment_monitoring | ❌ MISSING |
| 028_ab_indexes | N/A (indexes only) | ❌ Not applied |
| 029_quiz_questions | quiz_questions | ❌ MISSING |
| 20251009_230000 | whatsapp_delivery_failures | ❌ MISSING |
| 20251009_235500 | webhook_idempotency | ❌ MISSING |

---

## Final Recommendation

**DO NOT stamp at HEAD. Use Option 2:**

1. **Create alignment migration** to fix `webhook_events` schema
2. **Stamp at migration 018** (last known good state)
3. **Apply alignment migration** (fixes webhook_events)
4. **Skip migration 019** (webhook_events already exists)
5. **Apply remaining migrations** (020 → head)

### Implementation Steps

```bash
# Step 1: Create alignment migration
alembic revision -m "align_webhook_events_with_migration_019"

# Step 2: Edit the migration to:
#   - Rename payload → raw_payload
#   - Drop extra columns (max_retries, next_retry_at, etc.)
#   - Create webhook_event_type ENUM
#   - Alter event_type to use ENUM
#   - Add missing columns (webhook_id, updated_at)

# Step 3: Stamp at 018
alembic stamp 018_message_status_events

# Step 4: Apply alignment migration
alembic upgrade +1

# Step 5: Manually mark 019 as applied (since table exists)
alembic stamp 019_webhook_events

# Step 6: Apply remaining migrations
alembic upgrade head
```

---

## Risk Assessment

### Low Risk (Safe to Apply)
- ✅ Migrations 020-021 (indexes only)
- ✅ Migration 20251009_230000 (new table: whatsapp_delivery_failures)
- ✅ Migration 20251009_235500 (new table: webhook_idempotency)

### Medium Risk (Schema Changes)
- ⚠️ Migration 029 (quiz_questions table - check if exists first)
- ⚠️ Migrations 022-028 (A/B testing tables - verify not manually created)

### High Risk (Conflicts)
- ❌ Migration 019 (webhook_events - WILL FAIL due to existing table)

---

## Questions for Team

1. **Who created the admin_* tables?** (10 tables not in any migration)
2. **Why is webhook_events schema different from migration 019?**
3. **Are quiz_sessions_v2 and quiz_template_versions_v2 still used?**
4. **Should we keep or drop the A/B testing migrations (022-028)?**
5. **What's the purpose of flow_template_categories, flow_template_shares, flow_template_stats?**

---

## Appendix: Production vs Migration Schema Comparison

### alembic_version Table
```sql
-- Production:
CREATE TABLE alembic_version (
    version_num VARCHAR(32)  -- Currently NULL
);

-- Expected: Same structure, but should have a version number
```

### webhook_events Table (Detailed Comparison)

| Column Name | Migration 019 | Production | Match |
|-------------|---------------|------------|-------|
| id | UUID PRIMARY KEY | UUID NOT NULL | ✅ |
| event_type | webhook_event_type ENUM | VARCHAR | ❌ |
| source | VARCHAR(100) | VARCHAR | ✅ |
| webhook_id | VARCHAR(255) | - | ❌ MISSING |
| raw_payload | JSONB | - | ❌ MISSING |
| payload | - | JSONB | ❌ EXTRA |
| processed | BOOLEAN DEFAULT false | BOOLEAN NOT NULL | ✅ |
| processed_at | TIMESTAMP | TIMESTAMP | ✅ |
| error_message | TEXT | TEXT | ✅ |
| retry_count | INTEGER DEFAULT 0 | INTEGER | ✅ |
| max_retries | - | INTEGER | ❌ EXTRA |
| next_retry_at | - | TIMESTAMP | ❌ EXTRA |
| error_stack_trace | - | TEXT | ❌ EXTRA |
| related_message_id | UUID | UUID | ✅ |
| related_patient_id | - | UUID | ❌ EXTRA |
| event_hash | - | VARCHAR | ❌ EXTRA |
| is_duplicate | - | BOOLEAN | ❌ EXTRA |
| original_event_id | - | UUID | ❌ EXTRA |
| created_at | TIMESTAMP DEFAULT NOW() | TIMESTAMP NOT NULL | ✅ |
| updated_at | TIMESTAMP | - | ❌ MISSING |

**Match Score:** 8/17 columns match (47%)

---

**Document Version:** 1.0
**Last Updated:** 2025-10-09
**Next Review:** After implementing recommended action plan
