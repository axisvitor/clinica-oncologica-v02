# Database Indexes

Index documentation and performance optimization guide for the Hormonia Backend database.

## Table of Contents

- [Index Overview](#index-overview)
- [Index Categories](#index-categories)
- [Performance Indexes](#performance-indexes)
- [Unique Indexes](#unique-indexes)
- [Partial Indexes](#partial-indexes)
- [JSONB Indexes](#jsonb-indexes)
- [Composite Indexes](#composite-indexes)
- [Index Maintenance](#index-maintenance)
- [Query Optimization](#query-optimization)

---

## Index Overview

**Total Indexes:** 150+ across all tables
**Index Types:**
- B-tree (default)
- GIN (JSONB columns)
- Partial (conditional indexes)
- Unique (constraint enforcement)

**Indexing Strategy:**
1. All foreign keys are indexed
2. All unique constraints have indexes
3. Frequently queried columns are indexed
4. JSONB columns use GIN indexes
5. Status/enum columns are indexed
6. Composite indexes for common query patterns

---

## Index Categories

### Primary Key Indexes

All tables use UUID primary keys with automatic B-tree indexes:

```sql
-- Example: users table
CREATE INDEX users_pkey ON users(id);
```

**Performance:** O(log n) lookup time

### Foreign Key Indexes

All foreign keys are indexed for efficient joins:

```sql
-- Patient relationships
CREATE INDEX idx_patients_doctor_id ON patients(doctor_id);
CREATE INDEX idx_messages_patient_id ON messages(patient_id);
CREATE INDEX idx_quiz_sessions_patient_id ON quiz_sessions(patient_id);
CREATE INDEX idx_treatments_patient_id ON treatments(patient_id);
CREATE INDEX idx_appointments_patient_id ON appointments(patient_id);
CREATE INDEX idx_medications_patient_id ON medications(patient_id);

-- User relationships
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);

-- Quiz relationships
CREATE INDEX idx_quiz_responses_quiz_template_id ON quiz_responses(quiz_template_id);
CREATE INDEX idx_quiz_sessions_quiz_template_id ON quiz_sessions(quiz_template_id);
CREATE INDEX idx_quiz_response_session_id ON quiz_responses(quiz_session_id);

-- Flow relationships
CREATE INDEX idx_flow_template_versions_flow_kind ON flow_template_versions(flow_kind_id);
CREATE INDEX idx_patient_flow_states_patient_id ON patient_flow_states(patient_id);
CREATE INDEX idx_patient_flow_states_template_version_id ON patient_flow_states(flow_template_version_id);
```

**Purpose:** Accelerate join operations and foreign key constraint checks

### Status Indexes

Status columns are indexed for filtering:

```sql
-- Message status
CREATE INDEX idx_messages_status ON messages(status);

-- Quiz session status
CREATE INDEX idx_quiz_sessions_status_v2 ON quiz_sessions(status);

-- Treatment status
CREATE INDEX idx_treatments_status ON treatments(status);

-- Appointment status
CREATE INDEX idx_appointments_status ON appointments(status);

-- Session active status
CREATE INDEX idx_sessions_is_active ON sessions(is_active);

-- Notification read status
CREATE INDEX idx_notifications_is_read ON notifications(is_read);
```

**Purpose:** Fast filtering by status in WHERE clauses

---

## Performance Indexes

### P0 Performance Indexes (Migration 010)

Critical indexes added for optimal query performance:

```sql
-- Patient lookups with composite keys
CREATE INDEX idx_patient_phone_doctor ON patients(phone, doctor_id);
CREATE INDEX idx_patient_email_doctor ON patients(email, doctor_id) WHERE email IS NOT NULL;
CREATE INDEX idx_patient_cpf_doctor ON patients(cpf, doctor_id) WHERE cpf IS NOT NULL;

-- Quiz session performance
CREATE INDEX idx_quiz_sessions_patient_id_v2 ON quiz_sessions(patient_id);
CREATE INDEX idx_quiz_sessions_quiz_template_id_v2 ON quiz_sessions(quiz_template_id);
CREATE INDEX idx_quiz_sessions_patient_status_v2 ON quiz_sessions(patient_id, status);
CREATE INDEX idx_quiz_sessions_template_status_v2 ON quiz_sessions(quiz_template_id, status);
CREATE INDEX idx_quiz_sessions_created_at_v2 ON quiz_sessions(created_at);
CREATE INDEX idx_quiz_sessions_completed_at_v2 ON quiz_sessions(completed_at);

-- Flow execution tracking (Migration 008)
CREATE INDEX idx_flow_executions_flow_id ON patient_flow_states(flow_template_version_id);

-- Message idempotency
CREATE INDEX idx_messages_idempotency_key ON messages(idempotency_key);
```

**Impact:** 10-50x query performance improvement for common patterns

### Timestamp Indexes

Temporal queries are accelerated:

```sql
-- Audit logs
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- Quiz responses
CREATE INDEX idx_quiz_responses_responded_at ON quiz_responses(responded_at);

-- Sessions
CREATE INDEX idx_sessions_last_activity ON sessions(last_activity);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);

-- Appointments
CREATE INDEX idx_appointments_scheduled_at ON appointments(scheduled_at);

-- Medications
CREATE INDEX idx_medications_prescription_date ON medications(prescription_date);

-- Notifications
CREATE INDEX idx_notifications_expires_at ON notifications(expires_at);

-- Consents
CREATE INDEX idx_consents_granted_at ON consents(granted_at);
CREATE INDEX idx_consents_expires_at ON consents(expires_at);
```

**Use Cases:**
- Time-range queries
- Expiration checks
- Activity tracking
- Report generation

---

## Unique Indexes

### Simple Unique Indexes

```sql
-- User authentication
CREATE UNIQUE INDEX users_email_key ON users(email);
CREATE UNIQUE INDEX users_firebase_uid_key ON users(firebase_uid);

-- Sessions
CREATE UNIQUE INDEX sessions_session_token_key ON sessions(session_token);
CREATE UNIQUE INDEX sessions_refresh_token_key ON sessions(refresh_token);

-- Flow kinds
CREATE UNIQUE INDEX flow_kinds_kind_key_key ON flow_kinds(kind_key);

-- Quiz templates
CREATE UNIQUE INDEX uq_quiz_template_name_version ON quiz_templates(name, version);

-- Webhook idempotency
CREATE UNIQUE INDEX webhook_idempotency_pkey ON webhook_idempotency(event_id);
```

### Composite Unique Indexes

```sql
-- Patient unique constraints (scoped to doctor)
CREATE UNIQUE INDEX uq_patient_email_doctor ON patients(email, doctor_id);
CREATE UNIQUE INDEX uq_patient_cpf_doctor ON patients(cpf, doctor_id);
CREATE UNIQUE INDEX uq_patient_phone_doctor ON patients(phone, doctor_id);

-- Patient flow states
CREATE UNIQUE INDEX uq_patient_flow_state_unique_version ON patient_flow_states(patient_id, flow_template_version_id);

-- Flow template versions
CREATE UNIQUE INDEX unique_flow_version ON flow_template_versions(flow_kind_id, version_number);

-- Quiz responses (one per question per session)
CREATE UNIQUE INDEX uq_quiz_response_per_question_session ON quiz_responses(quiz_session_id, question_id);
```

---

## Partial Indexes

Partial indexes cover subsets of data for specific query patterns:

### Active Quiz Session Index

```sql
CREATE UNIQUE INDEX idx_quiz_session_unique_active
ON quiz_sessions(patient_id, quiz_template_id)
WHERE status = 'started';
```

**Purpose:** Ensure only one active session per patient per template
**Performance:** Smaller index size, faster lookups for active sessions

### Patient Email Index (Non-NULL only)

```sql
CREATE INDEX idx_patient_email_doctor
ON patients(email, doctor_id)
WHERE email IS NOT NULL;
```

**Purpose:** Exclude NULL emails from index
**Performance:** Smaller index, faster email lookups

### Patient CPF Index (Non-NULL only)

```sql
CREATE INDEX idx_patient_cpf_doctor
ON patients(cpf, doctor_id)
WHERE cpf IS NOT NULL;
```

**Purpose:** Exclude NULL CPFs from index
**Performance:** Efficient CPF lookups for Brazilian patients

### Saga Retry Index

```sql
CREATE INDEX idx_patient_onboarding_saga_retry
ON patient_onboarding_saga(status, next_retry_at)
WHERE status = 'RETRY_SCHEDULED';
```

**Purpose:** Fast lookup of sagas pending retry
**Performance:** Optimized background job processing

---

## JSONB Indexes

GIN (Generalized Inverted Index) for JSONB columns:

### Planned JSONB Indexes (Future Migration)

```sql
-- Patient metadata search
CREATE INDEX idx_patients_metadata_gin ON patients USING GIN(metadata);

-- Quiz response analytics
CREATE INDEX idx_quiz_responses_value_gin ON quiz_responses USING GIN(response_value);

-- Message metadata search
CREATE INDEX idx_messages_metadata_gin ON messages USING GIN(message_metadata);

-- Flow template steps
CREATE INDEX idx_flow_template_versions_steps_gin ON flow_template_versions USING GIN(steps);

-- Session metadata
CREATE INDEX idx_sessions_metadata_gin ON sessions USING GIN(session_metadata);

-- Audit event metadata
CREATE INDEX idx_audit_logs_metadata_gin ON audit_logs USING GIN(event_metadata);
```

**Query Examples:**

```sql
-- Search patient metadata
SELECT * FROM patients WHERE metadata @> '{"diagnosis": "breast_cancer"}';

-- Search quiz responses
SELECT * FROM quiz_responses WHERE response_value @> '{"value": 7}';

-- Search message buttons
SELECT * FROM messages WHERE message_metadata @> '{"buttons": [{"id": "continue"}]}';
```

**Performance:** ~100x faster than sequential scan for JSONB queries

---

## Composite Indexes

Multi-column indexes for common query patterns:

### Covering Indexes

Indexes that include all columns needed for a query:

```sql
-- Quiz response analytics (covering index)
CREATE INDEX idx_quiz_response_analytics_covering_index
ON quiz_responses(quiz_template_id, question_id, response_value, responded_at);

-- Patient-template responses
CREATE INDEX idx_quiz_response_patient_template_index
ON quiz_responses(patient_id, quiz_template_id, responded_at);

-- Flow template version lookup
CREATE INDEX idx_flow_template_versions_version
ON flow_template_versions(flow_kind_id, version_number);

-- Active flow templates
CREATE INDEX idx_flow_template_versions_active
ON flow_template_versions(flow_kind_id, is_active);
```

**Performance:** Index-only scans (no table access required)

### Audit Log Composite Indexes

```sql
-- User activity timeline
CREATE INDEX idx_audit_user_event_time
ON audit_logs(user_id, event_type, created_at);

-- IP-based security monitoring
CREATE INDEX idx_audit_ip_time
ON audit_logs(ip_address, created_at);

-- Event status tracking
CREATE INDEX idx_audit_event_status_time
ON audit_logs(event_type, event_status, created_at);

-- Firebase user tracking
CREATE INDEX idx_audit_firebase_time
ON audit_logs(firebase_uid, created_at);

-- Email-based tracking (failed logins)
CREATE INDEX idx_audit_email_time
ON audit_logs(user_email, created_at);
```

**Use Cases:**
- Security dashboards
- User activity reports
- Failed login tracking
- IP-based blocking

### Webhook Idempotency Indexes

```sql
-- Provider + event type lookups
CREATE INDEX idx_webhook_idempotency_provider_type
ON webhook_idempotency(provider, event_type);

-- Expiration cleanup
CREATE INDEX idx_webhook_idempotency_expires_at
ON webhook_idempotency(expires_at);

-- Reception tracking
CREATE INDEX idx_webhook_idempotency_received_at
ON webhook_idempotency(received_at);

-- Status filtering
CREATE INDEX idx_webhook_idempotency_status
ON webhook_idempotency(status);
```

---

## Index Maintenance

### Index Monitoring

```sql
-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Find unused indexes
SELECT schemaname, tablename, indexname
FROM pg_stat_user_indexes
WHERE idx_scan = 0
AND indexrelname NOT LIKE '%_pkey';

-- Check index size
SELECT schemaname, tablename, indexname, pg_size_pretty(pg_relation_size(indexrelid))
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;
```

### Index Health

```sql
-- Check for index bloat
SELECT schemaname, tablename, indexname,
       pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
       idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;

-- Reindex if needed
REINDEX INDEX CONCURRENTLY idx_name;
```

### Vacuum and Analyze

```sql
-- Update statistics
ANALYZE patients;
ANALYZE quiz_sessions;
ANALYZE messages;

-- Vacuum bloated tables
VACUUM ANALYZE patients;
VACUUM ANALYZE quiz_responses;
```

---

## Query Optimization

### Using Indexes Effectively

**Good Queries (use indexes):**

```sql
-- ✅ Uses idx_patients_doctor_id
SELECT * FROM patients WHERE doctor_id = '...';

-- ✅ Uses idx_quiz_sessions_patient_status_v2
SELECT * FROM quiz_sessions WHERE patient_id = '...' AND status = 'started';

-- ✅ Uses idx_messages_patient_id
SELECT * FROM messages WHERE patient_id = '...' ORDER BY created_at DESC LIMIT 10;

-- ✅ Uses idx_audit_user_event_time
SELECT * FROM audit_logs
WHERE user_id = '...'
AND event_type = 'login_success'
AND created_at > NOW() - INTERVAL '30 days';
```

**Bad Queries (avoid):**

```sql
-- ❌ Function on indexed column (index not used)
SELECT * FROM patients WHERE LOWER(email) = 'test@example.com';
-- Fix: Use functional index or case-insensitive collation

-- ❌ Leading wildcard (index not used)
SELECT * FROM patients WHERE phone LIKE '%1234';
-- Fix: Use full-text search or reverse index

-- ❌ OR with different columns (partial index scan)
SELECT * FROM patients WHERE email = '...' OR cpf = '...';
-- Fix: Use UNION or separate queries

-- ❌ Negation (full table scan)
SELECT * FROM quiz_sessions WHERE status != 'completed';
-- Fix: Use positive logic or partial index
```

### EXPLAIN ANALYZE

Always analyze query plans:

```sql
EXPLAIN ANALYZE
SELECT p.*, COUNT(m.id) as message_count
FROM patients p
LEFT JOIN messages m ON m.patient_id = p.id
WHERE p.doctor_id = '...'
AND p.flow_state = 'active'
GROUP BY p.id
ORDER BY p.created_at DESC
LIMIT 20;
```

**Look for:**
- Sequential scans (bad)
- Index scans (good)
- Nested loops vs hash joins
- Actual vs estimated rows

---

## Index Recommendations

### Missing Indexes (Future)

Based on common query patterns:

```sql
-- Treatment date range queries
CREATE INDEX idx_treatments_start_date ON treatments(start_date);

-- Appointment scheduling
CREATE INDEX idx_appointments_scheduled_at ON appointments(scheduled_at);

-- Patient soft delete queries
CREATE INDEX idx_patients_deleted_at ON patients(deleted_at) WHERE deleted_at IS NULL;

-- Session security flags
CREATE INDEX idx_sessions_is_suspicious ON sessions(is_suspicious) WHERE is_suspicious = true;
```

### Index Consolidation

Some indexes may be redundant:

```sql
-- If you have both:
CREATE INDEX idx_a ON table(col1);
CREATE INDEX idx_b ON table(col1, col2);
-- Consider dropping idx_a (idx_b covers col1 queries)
```

---

## Performance Metrics

### Target Performance

| Query Type | Target Time | Index Strategy |
|------------|-------------|----------------|
| Primary key lookup | < 1ms | B-tree index |
| Foreign key join | < 10ms | Composite index |
| Status filtering | < 50ms | Partial index |
| JSONB search | < 100ms | GIN index |
| Full-text search | < 200ms | GIN index + tsvector |
| Aggregation | < 500ms | Covering index |
| Report generation | < 2s | Materialized view |

### Index Size vs Performance

```
Index Size Impact:
- < 100 MB: Minimal impact, always beneficial
- 100-500 MB: Monitor usage, keep if frequently used
- > 500 MB: Evaluate necessity, consider partial indexes
```

---

## See Also

- [TABLES_REFERENCE.md](./TABLES_REFERENCE.md) - Table column details
- [RELATIONSHIPS.md](./RELATIONSHIPS.md) - Foreign key relationships
- [SCHEMA_OVERVIEW.md](./SCHEMA_OVERVIEW.md) - Schema organization
- [Query Optimization Guide](/docs/operations/performance/QUERY_OPTIMIZATION.md)
