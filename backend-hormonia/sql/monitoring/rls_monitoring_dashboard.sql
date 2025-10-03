-- ================================================================
-- RLS MONITORING DASHBOARD QUERIES
-- ================================================================
-- Use these queries to monitor RLS implementation and performance
-- Run regularly during phased rollout
-- ================================================================

-- ================================================================
-- 1. RLS STATUS OVERVIEW
-- ================================================================
-- Check which tables have RLS enabled and policy count
SELECT
    t.schemaname,
    t.tablename,
    t.rowsecurity as rls_enabled,
    COUNT(p.policyname) as policy_count,
    ARRAY_AGG(p.policyname ORDER BY p.policyname) as policies,
    CASE
        WHEN t.rowsecurity = false THEN '❌ RLS Disabled'
        WHEN t.rowsecurity = true AND COUNT(p.policyname) = 0 THEN '⚠️ RLS Enabled but No Policies'
        WHEN t.rowsecurity = true AND COUNT(p.policyname) > 0 THEN '✅ Protected'
        ELSE '❓ Unknown'
    END as status,
    pg_size_pretty(pg_relation_size(quote_ident(t.tablename)::regclass)) as table_size
FROM pg_tables t
LEFT JOIN pg_policies p ON t.tablename = p.tablename AND t.schemaname = p.schemaname
WHERE t.schemaname = 'public'
AND t.tablename NOT IN ('alembic_version', 'schema_migrations')
GROUP BY t.schemaname, t.tablename, t.rowsecurity
ORDER BY
    CASE WHEN t.rowsecurity = true THEN 0 ELSE 1 END,
    t.tablename;

-- ================================================================
-- 2. PERFORMANCE METRICS
-- ================================================================
-- Monitor query performance for RLS-protected tables
WITH query_stats AS (
    SELECT
        queryid,
        query,
        calls,
        total_exec_time,
        mean_exec_time,
        stddev_exec_time,
        rows,
        100.0 * total_exec_time / sum(total_exec_time) OVER () AS percentage
    FROM pg_stat_statements
    WHERE query LIKE '%patients%'
       OR query LIKE '%messages%'
       OR query LIKE '%medical_reports%'
       OR query LIKE '%quiz_sessions%'
    AND query NOT LIKE '%pg_stat_statements%'
)
SELECT
    LEFT(query, 80) as query_preview,
    calls,
    ROUND(mean_exec_time::numeric, 2) as avg_ms,
    ROUND(stddev_exec_time::numeric, 2) as stddev_ms,
    rows as avg_rows,
    ROUND(percentage::numeric, 2) as pct_total_time,
    CASE
        WHEN mean_exec_time > 1000 THEN '🔴 Critical'
        WHEN mean_exec_time > 500 THEN '🟡 Warning'
        ELSE '🟢 Good'
    END as performance
FROM query_stats
ORDER BY mean_exec_time DESC
LIMIT 20;

-- ================================================================
-- 3. USER ACCESS PATTERNS
-- ================================================================
-- Analyze who is accessing what data
WITH access_log AS (
    SELECT
        current_setting('request.jwt.claims', true)::json->>'email' as user_email,
        current_setting('request.jwt.claims', true)::json->>'role' as user_role,
        current_setting('request.jwt.claims', true)::json->>'sub' as user_id,
        NOW() as access_time
)
SELECT
    user_role,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(*) as total_queries
FROM access_log
WHERE user_role IS NOT NULL
GROUP BY user_role
ORDER BY total_queries DESC;

-- ================================================================
-- 4. RLS POLICY VIOLATIONS
-- ================================================================
-- Find queries that are being blocked by RLS
-- (Requires log_error_verbosity = verbose and log_min_messages = error)
SELECT
    log_time,
    user_name,
    database_name,
    error_severity,
    sql_state_code,
    message,
    detail,
    query
FROM postgres_log
WHERE message LIKE '%permission denied%'
   OR message LIKE '%row-level security%'
   OR message LIKE '%RLS%'
ORDER BY log_time DESC
LIMIT 50;

-- ================================================================
-- 5. INDEX USAGE FOR RLS
-- ================================================================
-- Check if indexes are being used for RLS filtering
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
    CASE
        WHEN idx_scan = 0 THEN '❌ Unused'
        WHEN idx_scan < 100 THEN '🟡 Low Usage'
        ELSE '✅ Active'
    END as usage_status
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
AND (indexname LIKE '%doctor_id%'
     OR indexname LIKE '%patient_id%'
     OR indexname LIKE '%user_id%'
     OR indexname LIKE '%session_id%')
ORDER BY idx_scan DESC;

-- ================================================================
-- 6. CONNECTION POOL METRICS
-- ================================================================
-- Monitor database connections for RLS sessions
SELECT
    datname as database,
    usename as username,
    application_name,
    COUNT(*) as connection_count,
    COUNT(*) FILTER (WHERE state = 'active') as active,
    COUNT(*) FILTER (WHERE state = 'idle') as idle,
    COUNT(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction,
    MAX(EXTRACT(EPOCH FROM (NOW() - state_change))) as max_idle_seconds,
    COUNT(*) FILTER (WHERE waiting) as waiting_connections
FROM pg_stat_activity
WHERE datname = current_database()
GROUP BY datname, usename, application_name
ORDER BY connection_count DESC;

-- ================================================================
-- 7. RLS PERFORMANCE COMPARISON
-- ================================================================
-- Compare query times before and after RLS
CREATE OR REPLACE VIEW rls_performance_baseline AS
WITH baseline AS (
    -- Store baseline metrics before RLS
    SELECT
        'patients_list' as operation,
        5.2 as baseline_ms,
        100 as baseline_rows
    UNION ALL
    SELECT 'patients_detail', 2.1, 1
    UNION ALL
    SELECT 'messages_list', 8.3, 50
    UNION ALL
    SELECT 'quiz_sessions_list', 6.7, 25
),
current_metrics AS (
    SELECT
        CASE
            WHEN query LIKE '%/patients-rls%' AND query LIKE '%SELECT%' THEN 'patients_list'
            WHEN query LIKE '%/patients-rls/%' AND query LIKE '%SELECT%' THEN 'patients_detail'
            WHEN query LIKE '%messages%' AND query LIKE '%SELECT%' THEN 'messages_list'
            WHEN query LIKE '%quiz_sessions%' AND query LIKE '%SELECT%' THEN 'quiz_sessions_list'
        END as operation,
        AVG(mean_exec_time) as current_ms,
        AVG(rows) as current_rows
    FROM pg_stat_statements
    WHERE query LIKE '%rls%' OR query LIKE '%auth.uid()%'
    GROUP BY 1
)
SELECT
    b.operation,
    ROUND(b.baseline_ms::numeric, 2) as baseline_ms,
    ROUND(c.current_ms::numeric, 2) as current_ms,
    ROUND(((c.current_ms - b.baseline_ms) / b.baseline_ms * 100)::numeric, 2) as pct_change,
    b.baseline_rows,
    ROUND(c.current_rows::numeric, 0) as current_rows,
    CASE
        WHEN ((c.current_ms - b.baseline_ms) / b.baseline_ms * 100) > 20 THEN '🔴 Degraded'
        WHEN ((c.current_ms - b.baseline_ms) / b.baseline_ms * 100) > 10 THEN '🟡 Warning'
        ELSE '🟢 Acceptable'
    END as performance_status
FROM baseline b
LEFT JOIN current_metrics c ON b.operation = c.operation;

-- View the comparison
SELECT * FROM rls_performance_baseline;

-- ================================================================
-- 8. DATA ACCESS AUDIT
-- ================================================================
-- Track who accessed what data (requires audit table)
SELECT
    DATE_TRUNC('hour', created_at) as hour,
    user_id,
    event_type,
    COUNT(*) as event_count,
    COUNT(DISTINCT entity_id) as unique_entities,
    AVG(CASE WHEN metadata->>'rls_enabled' = 'true' THEN 1 ELSE 0 END) * 100 as pct_rls_enabled
FROM audit_logs
WHERE created_at > NOW() - INTERVAL '24 hours'
AND event_type IN ('patients.list', 'patients.view', 'messages.list', 'quiz.access')
GROUP BY DATE_TRUNC('hour', created_at), user_id, event_type
ORDER BY hour DESC, event_count DESC;

-- ================================================================
-- 9. RLS HEALTH CHECK
-- ================================================================
-- Overall RLS health score
WITH health_metrics AS (
    SELECT
        -- Check tables with RLS
        (SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public' AND rowsecurity = true) as rls_tables,
        -- Check policies
        (SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public') as total_policies,
        -- Check slow queries
        (SELECT COUNT(*) FROM pg_stat_statements WHERE mean_exec_time > 1000) as slow_queries,
        -- Check connection pool
        (SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'idle in transaction' AND NOW() - state_change > INTERVAL '5 minutes') as stuck_connections,
        -- Check index usage
        (SELECT COUNT(*) FROM pg_stat_user_indexes WHERE schemaname = 'public' AND idx_scan = 0) as unused_indexes
)
SELECT
    rls_tables,
    total_policies,
    slow_queries,
    stuck_connections,
    unused_indexes,
    CASE
        WHEN slow_queries > 10 OR stuck_connections > 5 THEN 'CRITICAL'
        WHEN slow_queries > 5 OR stuck_connections > 2 OR unused_indexes > 10 THEN 'WARNING'
        WHEN rls_tables < 5 OR total_policies < 5 THEN 'INCOMPLETE'
        ELSE 'HEALTHY'
    END as overall_status,
    CASE
        WHEN slow_queries > 10 OR stuck_connections > 5 THEN
            'Immediate attention required: Performance issues detected'
        WHEN slow_queries > 5 OR stuck_connections > 2 THEN
            'Monitor closely: Some performance degradation'
        WHEN rls_tables < 5 OR total_policies < 5 THEN
            'RLS rollout incomplete: Continue with next phase'
        ELSE
            'System healthy: RLS operating normally'
    END as recommendation
FROM health_metrics;

-- ================================================================
-- 10. ALERT TRIGGERS
-- ================================================================
-- Create function to check for RLS alerts
CREATE OR REPLACE FUNCTION check_rls_alerts()
RETURNS TABLE(
    alert_level TEXT,
    alert_type TEXT,
    alert_message TEXT,
    metric_value NUMERIC
) AS $$
BEGIN
    -- Check query performance
    IF EXISTS (
        SELECT 1 FROM pg_stat_statements
        WHERE mean_exec_time > 2000
        AND (query LIKE '%patients%' OR query LIKE '%messages%')
        AND calls > 10
    ) THEN
        RETURN QUERY
        SELECT
            'CRITICAL'::TEXT,
            'PERFORMANCE'::TEXT,
            'Queries exceeding 2s threshold'::TEXT,
            MAX(mean_exec_time)::NUMERIC
        FROM pg_stat_statements
        WHERE mean_exec_time > 2000;
    END IF;

    -- Check connection pool
    IF (SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'idle in transaction') > 20 THEN
        RETURN QUERY
        SELECT
            'WARNING'::TEXT,
            'CONNECTIONS'::TEXT,
            'High number of idle transactions'::TEXT,
            COUNT(*)::NUMERIC
        FROM pg_stat_activity
        WHERE state = 'idle in transaction';
    END IF;

    -- Check RLS violations
    IF EXISTS (
        SELECT 1 FROM postgres_log
        WHERE message LIKE '%permission denied%'
        AND log_time > NOW() - INTERVAL '1 hour'
        LIMIT 1
    ) THEN
        RETURN QUERY
        SELECT
            'WARNING'::TEXT,
            'SECURITY'::TEXT,
            'RLS permission denials detected'::TEXT,
            COUNT(*)::NUMERIC
        FROM postgres_log
        WHERE message LIKE '%permission denied%'
        AND log_time > NOW() - INTERVAL '1 hour';
    END IF;

    -- All good
    IF NOT FOUND THEN
        RETURN QUERY
        SELECT
            'OK'::TEXT,
            'SYSTEM'::TEXT,
            'No alerts'::TEXT,
            0::NUMERIC;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Check for alerts
SELECT * FROM check_rls_alerts();

-- ================================================================
-- USAGE INSTRUCTIONS
-- ================================================================
/*
1. Run section 1 daily to check RLS status
2. Run section 2 hourly during rollout to monitor performance
3. Run section 6 every 5 minutes to check connection pool
4. Run section 9 before each phase transition
5. Set up section 10 as automated alerts

To create automated monitoring:
1. Schedule these queries in pg_cron or external monitoring
2. Send alerts when thresholds exceeded
3. Export to Grafana/Datadog for visualization
4. Keep historical data for trend analysis

Performance Thresholds:
- Query time increase: < 20% acceptable
- Connection pool: < 80% utilization
- Index usage: All RLS indexes should be used
- Error rate: < 0.1% permission denials

Phase Progression Criteria:
- Phase 1 → 2: No critical alerts for 48 hours
- Phase 2 → 3: Performance degradation < 15%
- Phase 3 → 4: Full test suite passing
- Phase 4: Security audit complete
*/

-- ================================================================
-- END OF MONITORING DASHBOARD
-- ================================================================