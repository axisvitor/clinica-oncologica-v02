-- P0 Database Indexes Verification Script
-- Date: 2025-11-13
-- Purpose: Verify all 28 indexes from migration 010 are created and being used

-- =============================================================================
-- PART 1: Verify Index Creation (28 indexes)
-- =============================================================================

\echo ''
\echo '=========================================='
\echo 'P0 INDEX VERIFICATION REPORT'
\echo '=========================================='
\echo ''

-- Count total indexes before
\echo 'TOTAL INDEXES IN PUBLIC SCHEMA:'
SELECT COUNT(*) AS total_indexes
FROM pg_indexes
WHERE schemaname = 'public';

\echo ''
\echo '------------------------------------------'
\echo 'FOREIGN KEY INDEXES (16 expected):'
\echo '------------------------------------------'

-- Verify Foreign Key Indexes (16 total)
SELECT
  CASE
    WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_patients_doctor_id') THEN '✓'
    ELSE '✗'
  END AS status,
  'idx_patients_doctor_id' AS index_name,
  'patients.doctor_id' AS column_indexed,
  'Doctor dashboard queries' AS purpose
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_messages_patient_id') THEN '✓' ELSE '✗' END,
  'idx_messages_patient_id',
  'messages.patient_id',
  'Patient chat interface'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_patient_flow_states_patient_id') THEN '✓' ELSE '✗' END,
  'idx_patient_flow_states_patient_id',
  'patient_flow_states.patient_id',
  'Flow state tracking'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_patient_flow_states_template_version_id') THEN '✓' ELSE '✗' END,
  'idx_patient_flow_states_template_version_id',
  'patient_flow_states.flow_template_version_id',
  'Flow template lookups'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_alerts_patient_id') THEN '✓' ELSE '✗' END,
  'idx_alerts_patient_id',
  'alerts.patient_id',
  'Alert dashboard'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_alerts_acknowledged_by') THEN '✓' ELSE '✗' END,
  'idx_alerts_acknowledged_by',
  'alerts.acknowledged_by',
  'Acknowledgment tracking'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_medical_reports_patient_id') THEN '✓' ELSE '✗' END,
  'idx_medical_reports_patient_id',
  'medical_reports.patient_id',
  'Report generation'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_medical_reports_generated_by') THEN '✓' ELSE '✗' END,
  'idx_medical_reports_generated_by',
  'medical_reports.generated_by',
  'User activity tracking'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_flow_analytics_patient_id') THEN '✓' ELSE '✗' END,
  'idx_flow_analytics_patient_id',
  'flow_analytics.patient_id',
  'Analytics queries'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_flow_analytics_template_version_id') THEN '✓' ELSE '✗' END,
  'idx_flow_analytics_template_version_id',
  'flow_analytics.flow_template_version_id',
  'Template analytics'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_flow_messages_template_version_id') THEN '✓' ELSE '✗' END,
  'idx_flow_messages_template_version_id',
  'flow_messages.flow_template_version_id',
  'Message flow lookups'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_flow_messages_patient_id') THEN '✓' ELSE '✗' END,
  'idx_flow_messages_patient_id',
  'flow_messages.patient_id',
  'Legacy message queries'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_flow_messages_message_id') THEN '✓' ELSE '✗' END,
  'idx_flow_messages_message_id',
  'flow_messages.message_id',
  'Message linkage'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_quiz_questions_quiz_template_id') THEN '✓' ELSE '✗' END,
  'idx_quiz_questions_quiz_template_id',
  'quiz_questions.quiz_template_id',
  'Quiz question lookups'
ORDER BY index_name;

\echo ''
\echo '------------------------------------------'
\echo 'COMPOSITE INDEXES (12 expected):'
\echo '------------------------------------------'

-- Verify Composite Indexes (12 total)
SELECT
  CASE
    WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_patients_doctor_created') THEN '✓'
    ELSE '✗'
  END AS status,
  'idx_patients_doctor_created' AS index_name,
  'patients(doctor_id, created_at)' AS columns_indexed,
  'Doctor patient list by date' AS purpose
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_messages_patient_created') THEN '✓' ELSE '✗' END,
  'idx_messages_patient_created',
  'messages(patient_id, created_at)',
  'Patient message history'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_messages_patient_status') THEN '✓' ELSE '✗' END,
  'idx_messages_patient_status',
  'messages(patient_id, status)',
  'Pending messages filter'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_alerts_patient_created') THEN '✓' ELSE '✗' END,
  'idx_alerts_patient_created',
  'alerts(patient_id, created_at)',
  'Recent alerts timeline'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_alerts_patient_acknowledged') THEN '✓' ELSE '✗' END,
  'idx_alerts_patient_acknowledged',
  'alerts(patient_id, acknowledged)',
  'Unread alerts filter'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_quiz_sessions_patient_created') THEN '✓' ELSE '✗' END,
  'idx_quiz_sessions_patient_created',
  'quiz_sessions(patient_id, created_at)',
  'Quiz completion history'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_flow_analytics_patient_created') THEN '✓' ELSE '✗' END,
  'idx_flow_analytics_patient_created',
  'flow_analytics(patient_id, created_at)',
  'Analytics timeline'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_medical_reports_patient_period') THEN '✓' ELSE '✗' END,
  'idx_medical_reports_patient_period',
  'medical_reports(patient_id, period_start, period_end)',
  'Reports by time period'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_patient_flow_states_patient_template') THEN '✓' ELSE '✗' END,
  'idx_patient_flow_states_patient_template',
  'patient_flow_states(patient_id, flow_template_version_id)',
  'Active flows per patient'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_flow_messages_template_step') THEN '✓' ELSE '✗' END,
  'idx_flow_messages_template_step',
  'flow_messages(flow_template_version_id, step_number)',
  'Flow message sequences'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_sessions_user_active') THEN '✓' ELSE '✗' END,
  'idx_sessions_user_active',
  'sessions(user_id, is_active, last_activity)',
  'Active sessions tracking'
UNION ALL
SELECT
  CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_notifications_user_unread') THEN '✓' ELSE '✗' END,
  'idx_notifications_user_unread',
  'notifications(user_id, is_read, created_at)',
  'Unread notifications'
ORDER BY index_name;

-- =============================================================================
-- PART 2: Index Size and Statistics
-- =============================================================================

\echo ''
\echo '------------------------------------------'
\echo 'INDEX SIZE STATISTICS:'
\echo '------------------------------------------'

SELECT
  schemaname,
  tablename,
  indexname,
  pg_size_pretty(pg_relation_size(indexname::regclass)) AS index_size
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname LIKE 'idx_%'
ORDER BY pg_relation_size(indexname::regclass) DESC
LIMIT 20;

-- =============================================================================
-- PART 3: Verify Index Usage (requires some data and queries)
-- =============================================================================

\echo ''
\echo '------------------------------------------'
\echo 'INDEX USAGE STATISTICS:'
\echo '------------------------------------------'

SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan AS scans,
  idx_tup_read AS tuples_read,
  idx_tup_fetch AS tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND indexname LIKE 'idx_%'
ORDER BY idx_scan DESC
LIMIT 20;

-- =============================================================================
-- PART 4: Foreign Key Coverage Check
-- =============================================================================

\echo ''
\echo '------------------------------------------'
\echo 'FOREIGN KEY INDEX COVERAGE:'
\echo '------------------------------------------'

-- Check which foreign keys have indexes
SELECT
  tc.table_name,
  kcu.column_name,
  CASE
    WHEN EXISTS (
      SELECT 1 FROM pg_indexes
      WHERE tablename = tc.table_name
        AND (
          indexdef LIKE '%' || kcu.column_name || '%'
          OR indexdef LIKE '%' || kcu.column_name || ',%'
        )
    ) THEN '✓ INDEXED'
    ELSE '✗ MISSING INDEX'
  END AS index_status
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
  AND tc.table_schema = kcu.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
ORDER BY tc.table_name, kcu.column_name;

-- =============================================================================
-- PART 5: Summary Statistics
-- =============================================================================

\echo ''
\echo '=========================================='
\echo 'SUMMARY STATISTICS'
\echo '=========================================='

-- Count P0 indexes
SELECT
  'P0 Foreign Key Indexes' AS metric,
  COUNT(*) AS count
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname IN (
    'idx_patients_doctor_id',
    'idx_messages_patient_id',
    'idx_patient_flow_states_patient_id',
    'idx_patient_flow_states_template_version_id',
    'idx_alerts_patient_id',
    'idx_alerts_acknowledged_by',
    'idx_medical_reports_patient_id',
    'idx_medical_reports_generated_by',
    'idx_flow_analytics_patient_id',
    'idx_flow_analytics_template_version_id',
    'idx_flow_messages_template_version_id',
    'idx_flow_messages_patient_id',
    'idx_flow_messages_message_id',
    'idx_quiz_questions_quiz_template_id'
  )
UNION ALL
SELECT
  'P0 Composite Indexes',
  COUNT(*)
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname IN (
    'idx_patients_doctor_created',
    'idx_messages_patient_created',
    'idx_messages_patient_status',
    'idx_alerts_patient_created',
    'idx_alerts_patient_acknowledged',
    'idx_quiz_sessions_patient_created',
    'idx_flow_analytics_patient_created',
    'idx_medical_reports_patient_period',
    'idx_patient_flow_states_patient_template',
    'idx_flow_messages_template_step',
    'idx_sessions_user_active',
    'idx_notifications_user_unread'
  )
UNION ALL
SELECT
  'Total Indexes Created',
  COUNT(*)
FROM pg_indexes
WHERE schemaname = 'public'
  AND (
    indexname LIKE 'idx_patients_doctor%'
    OR indexname LIKE 'idx_messages_patient%'
    OR indexname LIKE 'idx_alerts_%'
    OR indexname LIKE 'idx_medical_reports_%'
    OR indexname LIKE 'idx_flow_%'
    OR indexname LIKE 'idx_quiz_%'
    OR indexname LIKE 'idx_sessions_%'
    OR indexname LIKE 'idx_notifications_%'
  );

\echo ''
\echo 'Verification complete!'
\echo ''
