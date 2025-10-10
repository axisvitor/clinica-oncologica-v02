-- ============================================================================
-- GIN Index Verification Script for Text Search Optimization
-- ============================================================================
-- Migration: 20251009_210800_add_gin_indexes_for_search.py
-- Created: 2025-10-09
-- 
-- Purpose: Comprehensive verification of GIN trigram indexes
-- Usage: psql -U postgres -d database_name -f scripts/verify_gin_indexes.sql
-- ============================================================================

\echo ''
\echo '=========================================''
\echo 'GIN INDEX VERIFICATION REPORT''
\echo '=========================================''

-- 1. Check pg_trgm Extension
\echo ''
\echo '1. PostgreSQL pg_trgm Extension Status''
\echo '--------------------------------------''
SELECT extname AS "Extension", extversion AS "Version",
       CASE WHEN extname = '''pg_trgm''' THEN '''✓ Enabled''' ELSE '''✗ Not Found''' END AS "Status"
FROM pg_extension WHERE extname = '''pg_trgm''';

-- 2. List all GIN trigram indexes
\echo ''
\echo '2. GIN Trigram Index Inventory''
\echo '-----------------------------''
SELECT schemaname AS "Schema", tablename AS "Table", indexname AS "Index Name"
FROM pg_indexes
WHERE indexname LIKE ''%gin_trgm%'''
ORDER BY tablename, indexname;

-- 3. Index sizes
\echo ''
\echo '3. Index Storage Statistics''
\echo '---------------------------''
SELECT t.tablename AS "Table", i.indexname AS "Index",
       pg_size_pretty(pg_relation_size(i.indexname::regclass)) AS "Index Size",
       pg_size_pretty(pg_relation_size(t.tablename::regclass)) AS "Table Size"
FROM pg_indexes i
JOIN pg_tables t ON i.tablename = t.tablename
WHERE i.indexname LIKE ''%gin_trgm%'''
ORDER BY pg_relation_size(i.indexname::regclass) DESC;

-- 4. Index usage statistics
\echo ''
\echo '4. Index Usage Statistics''
\echo '------------------------''
SELECT tablename AS "Table", indexname AS "Index",
       idx_scan AS "Scans", idx_tup_read AS "Tuples Read",
       idx_tup_fetch AS "Tuples Fetched"
FROM pg_stat_user_indexes
WHERE indexname LIKE ''%gin_trgm%'''
ORDER BY idx_scan DESC;

-- 5. Test query performance
\echo ''
\echo '5. Query Performance Test (Patient Name Search)''
\echo '-----------------------------------------------''
EXPLAIN ANALYZE
SELECT id, name, email FROM patients WHERE name ILIKE '''%silva%''' LIMIT 10;

\echo ''
\echo '=========================================''
\echo 'Verification Complete''
\echo '=========================================''
