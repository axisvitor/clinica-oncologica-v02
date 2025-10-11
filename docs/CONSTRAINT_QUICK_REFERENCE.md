# Database Constraints Quick Reference Guide

**Last Updated:** 2025-10-11
**For:** Developers, DBAs, DevOps
**Quick Access:** Critical constraint information at a glance

---

## 🚀 Quick Actions

### Deploy Improvements to Staging
```bash
# 1. Review changes
cat docs/database_improvements.sql

# 2. Test in staging
psql -h staging-db.example.com -U app_user -d clinica_db -f docs/database_improvements.sql

# 3. Verify
psql -h staging-db.example.com -U app_user -d clinica_db -c "
SELECT * FROM pg_stat_user_indexes WHERE tablename IN ('messages', 'alerts');"
```

### Check Index Usage
```sql
SELECT
    tablename,
    indexname,
    idx_scan,
    idx_tup_read
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC
LIMIT 20;
```

### Find Missing Indexes
```sql
SELECT
    schemaname,
    tablename,
    seq_scan,
    seq_tup_read,
    ROUND(100.0 * idx_scan / (seq_scan + idx_scan + 1), 2) AS idx_usage_pct
FROM pg_stat_user_tables
WHERE n_live_tup > 1000
ORDER BY seq_scan DESC;
```

---

## 📋 Constraint Cheat Sheet

### Check Constraints Quick Reference

| Table | Constraint | Purpose | Status |
|-------|-----------|---------|--------|
| `quiz_sessions` | `started_at <= completed_at` | Prevent time travel | ✅ Exists |
| `quiz_sessions` | `status='completed' → timestamp` | State consistency | ✅ Exists |
| `quiz_responses` | `response_type IN (9 types)` | Validate type | ✅ Exists |
| `messages` | `scheduled_for > created_at` | Future scheduling | ⚠️ **MISSING** |
| `appointments` | `start < end` | Valid time range | ⚠️ **MISSING** |

### Unique Constraints Quick Reference

| Table | Columns | Type | Purpose |
|-------|---------|------|---------|
| `users` | `email` | Simple | Unique user |
| `patients` | `phone` | Simple | One patient/phone |
| `quiz_templates` | `(name, version)` | Composite | Versioning |
| `quiz_sessions` | `(patient, template) WHERE started` | Partial | One active session |
| `webhook_events` | `event_hash` | Simple | Idempotency |

### Foreign Key Cascade Rules

| Scenario | Rule | Example |
|----------|------|---------|
| Delete patient | CASCADE | All patient data deleted |
| Delete doctor | SET NULL | Preserve patient records |
| Delete template | RESTRICT | Fail if sessions exist |
| Delete user | CASCADE | Sessions deleted |

---

## 🔍 Common Query Patterns

### Patient Queries
```sql
-- ✅ Well-indexed
SELECT * FROM patients WHERE doctor_id = ?;
SELECT * FROM patients WHERE phone = ?;

-- ⚠️ Could be faster with composite index
SELECT * FROM messages WHERE patient_id = ? AND status = 'pending';
```

### Quiz Queries
```sql
-- ✅ Excellently indexed
SELECT * FROM quiz_sessions
WHERE patient_id = ? AND status = 'started';

SELECT * FROM quiz_responses
WHERE quiz_session_id = ? AND question_id = ?;
```

### Scheduling Queries
```sql
-- ⚠️ Missing index (HIGH PRIORITY)
SELECT * FROM messages
WHERE status = 'pending'
  AND scheduled_for <= NOW()
ORDER BY scheduled_for;

-- Recommended index:
-- CREATE INDEX idx_messages_scheduled_pending
--   ON messages(scheduled_for) WHERE status IN ('pending', 'scheduled');
```

### Alert Queries
```sql
-- ⚠️ Missing index (MEDIUM PRIORITY)
SELECT * FROM alerts
WHERE patient_id = ?
  AND severity = 'critical'
ORDER BY created_at DESC;

-- Recommended index:
-- CREATE INDEX idx_alerts_patient_severity
--   ON alerts(patient_id, severity, created_at);
```

---

## 🎯 Index Coverage Status

### ✅ Excellent Coverage (8/10 or higher)

- `quiz_templates` - 4 indexes
- `quiz_sessions` - 10 indexes (exceptional)
- `quiz_responses` - 9 indexes
- `webhook_events` - 9 indexes
- `audit_logs` - 6 indexes

### ⚠️ Needs Improvement (6/10 or lower)

- `messages` - 2 indexes (needs 4 more)
- `alerts` - 1 index (needs 3 more)
- `appointments` - 5 indexes (needs 3 more)
- `treatments` - 6 indexes (needs 2 more)

---

## 🛠️ Common Operations

### Adding a Check Constraint
```sql
-- Template
ALTER TABLE table_name
    ADD CONSTRAINT ck_table_column_description
    CHECK (condition);

-- Example
ALTER TABLE messages
    ADD CONSTRAINT ck_message_schedule_future
    CHECK (scheduled_for IS NULL OR scheduled_for > created_at);
```

### Adding a Unique Constraint
```sql
-- Template
ALTER TABLE table_name
    ADD CONSTRAINT uq_table_columns
    UNIQUE (column1, column2);

-- Example
ALTER TABLE flow_template_versions
    ADD CONSTRAINT uq_flow_version
    UNIQUE (kind_id, version);
```

### Adding a Composite Index
```sql
-- Template
CREATE INDEX idx_table_columns
    ON table_name(column1, column2, column3);

-- Example
CREATE INDEX idx_messages_patient_status
    ON messages(patient_id, status);
```

### Adding a Partial Index
```sql
-- Template
CREATE INDEX idx_table_columns
    ON table_name(column1, column2)
    WHERE condition;

-- Example
CREATE INDEX idx_messages_scheduled_pending
    ON messages(scheduled_for)
    WHERE status IN ('pending', 'scheduled');
```

---

## 🚨 Critical Constraints

### Must-Have Constraints (Already Exist)

1. **Quiz Session Active Unique**
   ```sql
   CREATE UNIQUE INDEX ix_quiz_session_active_unique
   ON quiz_sessions (patient_id, quiz_template_id)
   WHERE status = 'started';
   ```
   Prevents duplicate active sessions.

2. **Quiz Timing Validation**
   ```sql
   CHECK (started_at <= COALESCE(completed_at, NOW()))
   ```
   Prevents time travel bugs.

3. **Template Protection**
   ```sql
   FOREIGN KEY (quiz_template_id)
     REFERENCES quiz_templates(id)
     ON DELETE RESTRICT
   ```
   Prevents accidental template deletion.

### Missing Critical Constraints (TODO)

1. **Message Scheduling**
   ```sql
   CHECK (scheduled_for IS NULL OR scheduled_for > created_at)
   ```
   Priority: 🔴 HIGH

2. **Appointment Timing**
   ```sql
   CHECK (scheduled_start < scheduled_end)
   ```
   Priority: 🔴 HIGH

3. **Flow Version Uniqueness**
   ```sql
   UNIQUE (kind_id, version)
   ```
   Priority: 🔴 HIGH

---

## 📊 ENUM Quick Reference

### Authentication
```sql
user_role         → admin, doctor
auth_provider     → local, firebase
```

### Patient Journey
```sql
flow_state        → onboarding, active, paused, completed, inactive
```

### Messaging
```sql
messagestatus     → pending, scheduled, sending, sent, delivered, read, failed, cancelled
messagetype       → text, button, list, media, location, quiz_*, monthly_quiz_*
```

### Clinical
```sql
treatmenttype     → quimioterapia, radioterapia, hormonioterapia,
                    imunoterapia, cirurgia, outros
treatmentstatus   → planned, active, completed, suspended, cancelled
appointmentstatus → scheduled, confirmed, in_progress, completed, cancelled, no_show
```

### Alerts
```sql
alertseverity     → low, medium, high, critical
alertstatus       → pending, active, acknowledged, resolved, dismissed
```

### Security & Audit
```sql
audit_event_type  → 23 security event types (see full list in main report)
```

---

## 🔧 Troubleshooting

### Constraint Violation Errors

#### Check Constraint Failed
```
ERROR: new row for relation "table" violates check constraint "ck_name"
```

**Common Causes:**
- Invalid enum value
- Negative numeric value
- Invalid date/time relationship

**Solution:**
```sql
-- Find violating data
SELECT * FROM table WHERE NOT (constraint_condition);

-- Fix data
UPDATE table SET column = valid_value WHERE condition;
```

#### Unique Constraint Violation
```
ERROR: duplicate key value violates unique constraint "uq_name"
```

**Common Causes:**
- Duplicate insertion attempt
- Missing deduplication logic

**Solution:**
```sql
-- Find duplicates
SELECT column1, column2, COUNT(*)
FROM table
GROUP BY column1, column2
HAVING COUNT(*) > 1;

-- Use UPSERT
INSERT INTO table (...)
VALUES (...)
ON CONFLICT (column1, column2)
DO UPDATE SET ...;
```

#### Foreign Key Violation
```
ERROR: insert or update on table violates foreign key constraint "fk_name"
```

**Common Causes:**
- Referenced record doesn't exist
- Attempting to delete parent with children (RESTRICT)

**Solution:**
```sql
-- Check if parent exists
SELECT * FROM parent_table WHERE id = ?;

-- Check for dependent children
SELECT * FROM child_table WHERE parent_id = ?;
```

---

## 📈 Performance Monitoring

### Index Usage Report
```sql
CREATE OR REPLACE VIEW v_index_usage AS
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    CASE WHEN idx_scan = 0 THEN 'UNUSED'
         WHEN idx_scan < 100 THEN 'LOW'
         WHEN idx_scan < 1000 THEN 'MEDIUM'
         ELSE 'HIGH'
    END AS usage_level
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- Use it
SELECT * FROM v_index_usage WHERE usage_level = 'UNUSED';
```

### Slow Query Detection
```sql
-- Enable slow query logging
ALTER SYSTEM SET log_min_duration_statement = 1000; -- 1 second

-- View slow queries
SELECT
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
WHERE mean_time > 1000
ORDER BY mean_time DESC
LIMIT 20;
```

### Constraint Check Time
```sql
-- Create test data
EXPLAIN ANALYZE
INSERT INTO messages (patient_id, direction, type, content)
VALUES (...);

-- Check constraint validation time in output
```

---

## 📚 Reference Documents

| Document | Purpose | Size |
|----------|---------|------|
| [DATABASE_CONSTRAINTS_AUDIT_REPORT.md](./DATABASE_CONSTRAINTS_AUDIT_REPORT.md) | Full analysis | 15,000+ words |
| [CONSTRAINT_AUDIT_SUMMARY.md](./CONSTRAINT_AUDIT_SUMMARY.md) | Executive summary | 3,000 words |
| [DATABASE_CONSTRAINT_DIAGRAM.md](./DATABASE_CONSTRAINT_DIAGRAM.md) | Visual reference | Diagrams |
| [database_improvements.sql](./database_improvements.sql) | SQL scripts | 400+ lines |

---

## 🎓 Best Practices

### When to Use Check Constraints
- ✅ Validating enum-like values
- ✅ Ensuring non-negative numbers
- ✅ Enforcing date/time relationships
- ✅ Business rule validation
- ❌ Complex cross-table validation (use triggers)
- ❌ Frequently changing rules (use app logic)

### When to Use Unique Constraints
- ✅ Natural keys (email, phone)
- ✅ Version control (name + version)
- ✅ Idempotency (event_hash)
- ✅ Preventing duplicates
- ❌ Performance-only indexes (use regular index)

### When to Use Partial Indexes
- ✅ Status-based queries (WHERE status='active')
- ✅ Date-based queries (WHERE date > NOW())
- ✅ Boolean filters (WHERE is_deleted=false)
- ✅ Saving disk space
- ❌ When most rows match condition

### When to Use Composite Indexes
- ✅ Multi-column WHERE clauses
- ✅ Covering queries
- ✅ ORDER BY optimization
- ✅ JOIN optimization
- ❌ When columns are independently queried

---

## 🔐 Security Considerations

### HIPAA/LGPD Compliance
- ✅ Audit trail: `audit_logs` with 23 event types
- ✅ Consent tracking: `consents` with full lifecycle
- ✅ Access logging: All authentication events tracked
- ✅ Data retention: Constraints preserve required records

### Constraint-Based Security
- ✅ Foreign keys prevent orphaned PHI
- ✅ Cascades ensure complete data deletion
- ✅ SET NULL preserves audit trails
- ✅ Check constraints enforce data validity

---

## 📞 Support

**For Implementation:**
1. Review full audit report
2. Test in staging environment
3. Monitor application logs
4. Adjust based on actual usage

**For Performance Issues:**
1. Check `pg_stat_user_indexes`
2. Analyze query plans with `EXPLAIN ANALYZE`
3. Consider additional indexes based on patterns

**For Data Issues:**
1. Review constraint violations in logs
2. Validate data before constraint addition
3. Use transactions for bulk changes

---

**Last Updated:** 2025-10-11
**Next Review:** After Phase 1 implementation
**Maintained By:** Database Team
