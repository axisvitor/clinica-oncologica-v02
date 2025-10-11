-- Database Constraint and Index Improvements
-- Generated: 2025-10-11
-- Based on: DATABASE_CONSTRAINTS_AUDIT_REPORT.md
--
-- This script contains recommended improvements for the production database.
-- Review and test in staging environment before applying to production.

-- =============================================================================
-- HIGH PRIORITY IMPROVEMENTS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Messages Table - Add Critical Indexes
-- -----------------------------------------------------------------------------
-- Impact: High - Messages table has high query volume
-- Estimated improvement: 40-60% faster patient message history queries

-- Composite index for patient message queries filtered by status
CREATE INDEX IF NOT EXISTS idx_messages_patient_status
    ON messages(patient_id, status);

-- Composite index with created_at for chronological queries
CREATE INDEX IF NOT EXISTS idx_messages_patient_status_created
    ON messages(patient_id, status, created_at DESC);

-- Partial index for pending/scheduled messages (scheduler queries)
CREATE INDEX IF NOT EXISTS idx_messages_scheduled_pending
    ON messages(scheduled_for)
    WHERE status IN ('pending', 'scheduled');

-- Index for retry logic queries
CREATE INDEX IF NOT EXISTS idx_messages_retry
    ON messages(next_retry_at, status)
    WHERE next_retry_at IS NOT NULL;

COMMENT ON INDEX idx_messages_patient_status IS 'Optimizes patient message history queries';
COMMENT ON INDEX idx_messages_patient_status_created IS 'Optimizes chronological message queries';
COMMENT ON INDEX idx_messages_scheduled_pending IS 'Optimizes message scheduler queries (partial)';
COMMENT ON INDEX idx_messages_retry IS 'Optimizes retry logic queries (partial)';

-- -----------------------------------------------------------------------------
-- 2. Messages Table - Add Timing Constraints
-- -----------------------------------------------------------------------------
-- Impact: Medium - Prevents invalid scheduled times

-- Ensure scheduled_for is in the future relative to creation
ALTER TABLE messages
    ADD CONSTRAINT ck_message_schedule_future
    CHECK (scheduled_for IS NULL OR scheduled_for > created_at);

-- Ensure retry count is non-negative
ALTER TABLE messages
    ADD CONSTRAINT ck_message_retry_count_positive
    CHECK (retry_count >= 0);

-- Ensure last_retry_at is after created_at
ALTER TABLE messages
    ADD CONSTRAINT ck_message_retry_timing
    CHECK (last_retry_at IS NULL OR last_retry_at >= created_at);

-- Ensure next_retry_at is after last_retry_at
ALTER TABLE messages
    ADD CONSTRAINT ck_message_next_retry_timing
    CHECK (next_retry_at IS NULL OR last_retry_at IS NULL OR next_retry_at >= last_retry_at);

-- -----------------------------------------------------------------------------
-- 3. Appointments Table - Add Timing Constraint
-- -----------------------------------------------------------------------------
-- Impact: Medium - Prevents invalid appointment times

-- Ensure end time is after start time
ALTER TABLE appointments
    ADD CONSTRAINT ck_appointment_timing_valid
    CHECK (scheduled_start < scheduled_end);

-- Ensure actual times are logical
ALTER TABLE appointments
    ADD CONSTRAINT ck_appointment_actual_timing_valid
    CHECK (actual_start IS NULL OR actual_end IS NULL OR actual_start < actual_end);

-- Ensure actual start is after or equal to scheduled start
ALTER TABLE appointments
    ADD CONSTRAINT ck_appointment_actual_after_scheduled
    CHECK (actual_start IS NULL OR actual_start >= scheduled_start - INTERVAL '1 hour');

-- -----------------------------------------------------------------------------
-- 4. Flow Template Versions - Add Unique Constraint
-- -----------------------------------------------------------------------------
-- Impact: High - Prevents duplicate versions

-- Ensure one version per flow kind
ALTER TABLE flow_template_versions
    ADD CONSTRAINT uq_flow_version UNIQUE (kind_id, version);

COMMENT ON CONSTRAINT uq_flow_version ON flow_template_versions
    IS 'Ensures unique version numbers per flow kind';

-- =============================================================================
-- MEDIUM PRIORITY IMPROVEMENTS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 5. Alerts Table - Add Performance Indexes
-- -----------------------------------------------------------------------------
-- Impact: Medium - Improves dashboard and monitoring queries

-- Composite index for patient alert queries with severity
CREATE INDEX IF NOT EXISTS idx_alerts_patient_severity
    ON alerts(patient_id, severity, created_at DESC);

-- Composite index for status-based monitoring
CREATE INDEX IF NOT EXISTS idx_alerts_status_created
    ON alerts(status, created_at DESC);

-- Partial index for unacknowledged alerts (dashboard queries)
CREATE INDEX IF NOT EXISTS idx_alerts_unacknowledged
    ON alerts(patient_id, status, severity)
    WHERE acknowledged_at IS NULL;

-- Index for quiz session alerts
CREATE INDEX IF NOT EXISTS idx_alerts_quiz_session
    ON alerts(quiz_session_id, severity)
    WHERE quiz_session_id IS NOT NULL;

COMMENT ON INDEX idx_alerts_patient_severity IS 'Optimizes patient alert dashboard queries';
COMMENT ON INDEX idx_alerts_status_created IS 'Optimizes alert monitoring queries';
COMMENT ON INDEX idx_alerts_unacknowledged IS 'Optimizes unacknowledged alert queries (partial)';

-- -----------------------------------------------------------------------------
-- 6. Treatments Table - Add Query Indexes
-- -----------------------------------------------------------------------------
-- Impact: Medium - Improves clinical workflow queries

-- Composite index for patient treatment queries
CREATE INDEX IF NOT EXISTS idx_treatments_patient_status
    ON treatments(patient_id, status, start_date DESC);

-- Composite index for treatment type filtering
CREATE INDEX IF NOT EXISTS idx_treatments_type_active
    ON treatments(treatment_type, is_active)
    WHERE is_active = true;

-- Index for doctor's treatment list
CREATE INDEX IF NOT EXISTS idx_treatments_doctor_status
    ON treatments(doctor_id, status, start_date DESC)
    WHERE doctor_id IS NOT NULL;

COMMENT ON INDEX idx_treatments_patient_status IS 'Optimizes patient treatment history queries';
COMMENT ON INDEX idx_treatments_type_active IS 'Optimizes active treatment by type queries (partial)';

-- -----------------------------------------------------------------------------
-- 7. Appointments Table - Add Performance Indexes
-- -----------------------------------------------------------------------------
-- Impact: Medium - Improves scheduling queries

-- Composite index for patient appointment history
CREATE INDEX IF NOT EXISTS idx_appointments_patient_status
    ON appointments(patient_id, status, scheduled_start DESC);

-- Composite index for practitioner schedule
CREATE INDEX IF NOT EXISTS idx_appointments_practitioner_date
    ON appointments(practitioner_id, scheduled_start)
    WHERE practitioner_id IS NOT NULL;

-- Partial index for upcoming appointments
CREATE INDEX IF NOT EXISTS idx_appointments_upcoming
    ON appointments(scheduled_start, status)
    WHERE status IN ('scheduled', 'confirmed')
    AND scheduled_start >= CURRENT_TIMESTAMP;

-- Index for appointment reminders
CREATE INDEX IF NOT EXISTS idx_appointments_reminders
    ON appointments(scheduled_start, patient_id)
    WHERE reminder_sent = false
    AND status IN ('scheduled', 'confirmed')
    AND scheduled_start > CURRENT_TIMESTAMP;

COMMENT ON INDEX idx_appointments_patient_status IS 'Optimizes patient appointment history';
COMMENT ON INDEX idx_appointments_practitioner_date IS 'Optimizes practitioner schedule queries';
COMMENT ON INDEX idx_appointments_upcoming IS 'Optimizes upcoming appointment queries (partial)';
COMMENT ON INDEX idx_appointments_reminders IS 'Optimizes appointment reminder queries (partial)';

-- -----------------------------------------------------------------------------
-- 8. Medications Table - Add Query Indexes
-- -----------------------------------------------------------------------------
-- Impact: Low-Medium - Improves medication management queries

-- Composite index for patient active medications
CREATE INDEX IF NOT EXISTS idx_medications_patient_active
    ON medications(patient_id, is_active, prescription_date DESC);

-- Index for medication refill queries
CREATE INDEX IF NOT EXISTS idx_medications_refills
    ON medications(patient_id, end_date)
    WHERE is_active = true
    AND refills_remaining > 0;

COMMENT ON INDEX idx_medications_patient_active IS 'Optimizes patient medication list queries';
COMMENT ON INDEX idx_medications_refills IS 'Optimizes refill tracking queries (partial)';

-- -----------------------------------------------------------------------------
-- 9. Notifications Table - Add User Experience Indexes
-- -----------------------------------------------------------------------------
-- Impact: Medium - Improves notification queries

-- Composite index for user notification feed
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
    ON notifications(user_id, is_read, created_at DESC);

-- Partial index for high-priority unread notifications
CREATE INDEX IF NOT EXISTS idx_notifications_priority_unread
    ON notifications(user_id, priority, created_at DESC)
    WHERE is_read = false AND is_archived = false;

-- Index for notification expiration cleanup
CREATE INDEX IF NOT EXISTS idx_notifications_expired
    ON notifications(expires_at)
    WHERE expires_at IS NOT NULL AND is_archived = false;

COMMENT ON INDEX idx_notifications_user_unread IS 'Optimizes notification feed queries';
COMMENT ON INDEX idx_notifications_priority_unread IS 'Optimizes priority notification queries (partial)';

-- -----------------------------------------------------------------------------
-- 10. Consents Table - Add Compliance Indexes
-- -----------------------------------------------------------------------------
-- Impact: Low - Improves consent management and compliance queries

-- Composite index for patient consent queries
CREATE INDEX IF NOT EXISTS idx_consents_patient_type_status
    ON consents(patient_id, consent_type, status);

-- Partial index for active consents
CREATE INDEX IF NOT EXISTS idx_consents_active
    ON consents(patient_id, consent_type)
    WHERE is_active = true AND status = 'granted';

-- Index for consent expiration tracking
CREATE INDEX IF NOT EXISTS idx_consents_expiring
    ON consents(expires_at, patient_id)
    WHERE expires_at IS NOT NULL AND status = 'granted';

COMMENT ON INDEX idx_consents_patient_type_status IS 'Optimizes patient consent queries';
COMMENT ON INDEX idx_consents_active IS 'Optimizes active consent validation (partial)';

-- =============================================================================
-- LOW PRIORITY IMPROVEMENTS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 11. Webhook Idempotency - Add Status Constraint
-- -----------------------------------------------------------------------------
-- Impact: Low - Adds validation for webhook status field

-- Validate status enum values
ALTER TABLE webhook_idempotency
    ADD CONSTRAINT ck_webhook_idempotency_status_valid
    CHECK (status IN ('processing', 'completed', 'failed'));

-- Ensure retry count is non-negative
ALTER TABLE webhook_idempotency
    ADD CONSTRAINT ck_webhook_idempotency_retry_positive
    CHECK (retry_count >= 0);

-- Ensure processed_at is after received_at
ALTER TABLE webhook_idempotency
    ADD CONSTRAINT ck_webhook_idempotency_timing
    CHECK (processed_at IS NULL OR processed_at >= received_at);

-- -----------------------------------------------------------------------------
-- 12. Sessions Table - Add Security Constraints
-- -----------------------------------------------------------------------------
-- Impact: Low - Adds validation for session security

-- Ensure expiration is in the future relative to creation
ALTER TABLE sessions
    ADD CONSTRAINT ck_session_expires_future
    CHECK (expires_at > created_at);

-- Ensure last_activity is valid
ALTER TABLE sessions
    ADD CONSTRAINT ck_session_last_activity_valid
    CHECK (last_activity >= created_at AND last_activity <= expires_at);

-- Ensure revoked sessions have revocation timestamp
ALTER TABLE sessions
    ADD CONSTRAINT ck_session_revocation_timing
    CHECK ((is_active = true) OR (is_active = false AND revoked_at IS NOT NULL));

-- -----------------------------------------------------------------------------
-- 13. Quiz Sessions - Add Additional Constraints
-- -----------------------------------------------------------------------------
-- Impact: Low - Strengthens quiz data integrity

-- Ensure answered questions doesn't exceed total questions
ALTER TABLE quiz_sessions
    ADD CONSTRAINT ck_quiz_session_answered_valid
    CHECK (
        total_questions IS NULL OR
        answered_questions IS NULL OR
        answered_questions <= total_questions
    );

-- Ensure score doesn't exceed max score
ALTER TABLE quiz_sessions
    ADD CONSTRAINT ck_quiz_session_score_max_valid
    CHECK (
        score IS NULL OR
        max_score IS NULL OR
        score <= max_score
    );

-- -----------------------------------------------------------------------------
-- 14. AB Experiments - Add Safety Constraints
-- -----------------------------------------------------------------------------
-- Impact: Low - Strengthens A/B test data integrity

-- Ensure traffic split is valid percentage
ALTER TABLE ab_experiments
    ADD CONSTRAINT ck_ab_experiment_traffic_split_valid
    CHECK (traffic_split >= 0.0 AND traffic_split <= 1.0);

-- Ensure duration is positive
ALTER TABLE ab_experiments
    ADD CONSTRAINT ck_ab_experiment_duration_positive
    CHECK (duration_days > 0);

-- Ensure participant counts are non-negative
ALTER TABLE ab_experiments
    ADD CONSTRAINT ck_ab_experiment_participants_valid
    CHECK (
        total_participants >= 0 AND
        control_participants >= 0 AND
        treatment_participants >= 0 AND
        total_participants = control_participants + treatment_participants
    );

-- Ensure start date is before end date
ALTER TABLE ab_experiments
    ADD CONSTRAINT ck_ab_experiment_dates_valid
    CHECK (start_date IS NULL OR end_date IS NULL OR start_date < end_date);

-- =============================================================================
-- PERFORMANCE ANALYSIS QUERIES
-- =============================================================================

-- Use these queries to verify index usage after applying improvements

-- Check index usage on messages table
-- Uncomment to run:
/*
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE tablename = 'messages'
ORDER BY idx_scan DESC;
*/

-- Check table statistics
/*
SELECT
    schemaname,
    tablename,
    seq_scan,
    seq_tup_read,
    idx_scan,
    idx_tup_fetch,
    n_tup_ins,
    n_tup_upd,
    n_tup_del
FROM pg_stat_user_tables
WHERE tablename IN ('messages', 'alerts', 'appointments', 'treatments')
ORDER BY seq_scan DESC;
*/

-- Find missing indexes (tables with high sequential scans)
/*
SELECT
    schemaname,
    tablename,
    seq_scan,
    seq_tup_read,
    idx_scan,
    n_live_tup,
    CASE
        WHEN seq_scan > 0
        THEN ROUND(100.0 * idx_scan / (seq_scan + idx_scan), 2)
        ELSE 100.0
    END AS index_usage_percent
FROM pg_stat_user_tables
WHERE schemaname = 'public'
    AND n_live_tup > 1000
ORDER BY seq_scan DESC
LIMIT 20;
*/

-- =============================================================================
-- ROLLBACK SCRIPT (if needed)
-- =============================================================================

/*
-- To rollback high-priority changes:

-- Drop messages indexes
DROP INDEX IF EXISTS idx_messages_patient_status;
DROP INDEX IF EXISTS idx_messages_patient_status_created;
DROP INDEX IF EXISTS idx_messages_scheduled_pending;
DROP INDEX IF EXISTS idx_messages_retry;

-- Drop messages constraints
ALTER TABLE messages DROP CONSTRAINT IF EXISTS ck_message_schedule_future;
ALTER TABLE messages DROP CONSTRAINT IF EXISTS ck_message_retry_count_positive;
ALTER TABLE messages DROP CONSTRAINT IF EXISTS ck_message_retry_timing;
ALTER TABLE messages DROP CONSTRAINT IF EXISTS ck_message_next_retry_timing;

-- Drop appointments constraints
ALTER TABLE appointments DROP CONSTRAINT IF EXISTS ck_appointment_timing_valid;
ALTER TABLE appointments DROP CONSTRAINT IF EXISTS ck_appointment_actual_timing_valid;
ALTER TABLE appointments DROP CONSTRAINT IF EXISTS ck_appointment_actual_after_scheduled;

-- Drop flow template versions constraint
ALTER TABLE flow_template_versions DROP CONSTRAINT IF EXISTS uq_flow_version;

-- Drop alerts indexes
DROP INDEX IF EXISTS idx_alerts_patient_severity;
DROP INDEX IF EXISTS idx_alerts_status_created;
DROP INDEX IF EXISTS idx_alerts_unacknowledged;
DROP INDEX IF EXISTS idx_alerts_quiz_session;

-- (Continue for other changes as needed)
*/

-- =============================================================================
-- IMPLEMENTATION NOTES
-- =============================================================================

-- 1. Apply changes during low-traffic periods
-- 2. Monitor index build progress for large tables:
--    SELECT * FROM pg_stat_progress_create_index;
-- 3. Use CONCURRENTLY for index creation on production (requires separate transactions):
--    CREATE INDEX CONCURRENTLY idx_name ON table(column);
-- 4. Test constraint additions on staging first
-- 5. Check for existing data violations before adding constraints
-- 6. Monitor query performance before and after changes
-- 7. Update application code if constraints fail with existing data

-- End of script
