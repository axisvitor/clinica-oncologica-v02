-- P0 Query Performance Testing Script
-- Date: 2025-11-13
-- Purpose: Test query performance before/after index creation

-- Enable timing
\timing on

\echo ''
\echo '=========================================='
\echo 'P0 QUERY PERFORMANCE TESTS'
\echo '=========================================='
\echo ''

-- =============================================================================
-- TEST 1: Doctor Dashboard - Patient List
-- =============================================================================

\echo ''
\echo 'TEST 1: Doctor Dashboard (Patient List)'
\echo 'Query: SELECT * FROM patients WHERE doctor_id = ? ORDER BY created_at DESC LIMIT 20'
\echo 'Expected: Should use idx_patients_doctor_created index'
\echo ''

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT *
FROM patients
WHERE doctor_id = (SELECT id FROM users WHERE role = 'doctor' LIMIT 1)
ORDER BY created_at DESC
LIMIT 20;

-- =============================================================================
-- TEST 2: Patient Chat Interface - Message History
-- =============================================================================

\echo ''
\echo 'TEST 2: Patient Chat (Message History)'
\echo 'Query: SELECT * FROM messages WHERE patient_id = ? ORDER BY created_at DESC LIMIT 10'
\echo 'Expected: Should use idx_messages_patient_created index'
\echo ''

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT *
FROM messages
WHERE patient_id = (SELECT id FROM patients LIMIT 1)
ORDER BY created_at DESC
LIMIT 10;

-- =============================================================================
-- TEST 3: Alert Dashboard - Unread Alerts
-- =============================================================================

\echo ''
\echo 'TEST 3: Alert Dashboard (Unread Alerts)'
\echo 'Query: SELECT * FROM alerts WHERE patient_id = ? AND acknowledged = false'
\echo 'Expected: Should use idx_alerts_patient_acknowledged index'
\echo ''

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT *
FROM alerts
WHERE patient_id = (SELECT id FROM patients LIMIT 1)
  AND acknowledged = false
ORDER BY created_at DESC;

-- =============================================================================
-- TEST 4: Quiz History - Patient Quiz Sessions
-- =============================================================================

\echo ''
\echo 'TEST 4: Quiz History (Patient Sessions)'
\echo 'Query: SELECT * FROM quiz_sessions WHERE patient_id = ? ORDER BY created_at DESC'
\echo 'Expected: Should use idx_quiz_sessions_patient_created index'
\echo ''

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT *
FROM quiz_sessions
WHERE patient_id = (SELECT id FROM patients LIMIT 1)
ORDER BY created_at DESC;

-- =============================================================================
-- TEST 5: Medical Reports - Patient Report History
-- =============================================================================

\echo ''
\echo 'TEST 5: Medical Reports (Patient History)'
\echo 'Query: SELECT * FROM medical_reports WHERE patient_id = ? ORDER BY period_start DESC'
\echo 'Expected: Should use idx_medical_reports_patient_period index'
\echo ''

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT *
FROM medical_reports
WHERE patient_id = (SELECT id FROM patients LIMIT 1)
ORDER BY period_start DESC, period_end DESC;

-- =============================================================================
-- TEST 6: Flow Analytics - Patient Engagement Timeline
-- =============================================================================

\echo ''
\echo 'TEST 6: Flow Analytics (Engagement Timeline)'
\echo 'Query: SELECT * FROM flow_analytics WHERE patient_id = ? ORDER BY created_at DESC'
\echo 'Expected: Should use idx_flow_analytics_patient_created index'
\echo ''

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT *
FROM flow_analytics
WHERE patient_id = (SELECT id FROM patients LIMIT 1)
ORDER BY created_at DESC;

-- =============================================================================
-- TEST 7: Pending Messages - Status Filter
-- =============================================================================

\echo ''
\echo 'TEST 7: Pending Messages (Status Filter)'
\echo 'Query: SELECT * FROM messages WHERE patient_id = ? AND status = pending'
\echo 'Expected: Should use idx_messages_patient_status index'
\echo ''

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT *
FROM messages
WHERE patient_id = (SELECT id FROM patients LIMIT 1)
  AND status = 'pending';

-- =============================================================================
-- TEST 8: Active Sessions - User Session Tracking
-- =============================================================================

\echo ''
\echo 'TEST 8: Active Sessions (User Tracking)'
\echo 'Query: SELECT * FROM sessions WHERE user_id = ? AND is_active = true'
\echo 'Expected: Should use idx_sessions_user_active index'
\echo ''

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT *
FROM sessions
WHERE user_id = (SELECT id FROM users LIMIT 1)
  AND is_active = true
ORDER BY last_activity DESC;

-- =============================================================================
-- TEST 9: Flow State - Patient Flow Tracking
-- =============================================================================

\echo ''
\echo 'TEST 9: Flow State (Patient Flow Tracking)'
\echo 'Query: SELECT * FROM patient_flow_states WHERE patient_id = ?'
\echo 'Expected: Should use idx_patient_flow_states_patient_id index'
\echo ''

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT *
FROM patient_flow_states
WHERE patient_id = (SELECT id FROM patients LIMIT 1);

-- =============================================================================
-- TEST 10: Unread Notifications - User Notification Center
-- =============================================================================

\echo ''
\echo 'TEST 10: Unread Notifications (Notification Center)'
\echo 'Query: SELECT * FROM notifications WHERE user_id = ? AND is_read = false'
\echo 'Expected: Should use idx_notifications_user_unread index'
\echo ''

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT *
FROM notifications
WHERE user_id = (SELECT id FROM users LIMIT 1)
  AND is_read = false
ORDER BY created_at DESC;

-- =============================================================================
-- PERFORMANCE SUMMARY
-- =============================================================================

\echo ''
\echo '=========================================='
\echo 'PERFORMANCE TEST SUMMARY'
\echo '=========================================='
\echo ''
\echo 'Review the execution times above. All queries should:'
\echo '  - Use Index Scan (not Seq Scan)'
\echo '  - Execute in < 10ms'
\echo '  - Show "Index Scan using idx_..." in the plan'
\echo ''
\echo 'If any query shows "Seq Scan", verify:'
\echo '  1. Migration was applied successfully'
\echo '  2. ANALYZE was run on the tables'
\echo '  3. Statistics are up to date'
\echo ''

-- Update statistics to help query planner
ANALYZE patients;
ANALYZE messages;
ANALYZE alerts;
ANALYZE quiz_sessions;
ANALYZE medical_reports;
ANALYZE flow_analytics;
ANALYZE patient_flow_states;
ANALYZE sessions;
ANALYZE notifications;

\echo ''
\echo 'Statistics updated. Re-run tests if needed.'
\echo ''
