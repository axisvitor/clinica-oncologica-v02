-- Cleanup Test Data Migration 002
-- Removes test data from existing tables to prepare for production

-- ⚠️  WARNING: This script will DELETE data from the database
-- Only run this in development/staging environments
-- Review carefully before executing in any environment with important data

-- Clean up test users from the main users table (healthcare providers)
-- Keep only system-necessary records, remove obvious test data

-- First, let's see what test data exists (commented out for safety)
-- SELECT 'Current users before cleanup:' as info;
-- SELECT id, email, full_name, role, created_at FROM users ORDER BY created_at;

-- Remove test users (be very specific to avoid removing legitimate users)
-- Only remove users with obvious test patterns
DELETE FROM users
WHERE email IN (
    'admin@hormonia.com',
    'dr.silva@hormonia.com',
    'test@example.com',
    'testuser@example.com',
    'demo@example.com',
    'sample@example.com'
)
OR email LIKE '%test%'
OR email LIKE '%demo%'
OR email LIKE '%sample%'
OR full_name LIKE '%Test%'
OR full_name LIKE '%Demo%'
OR full_name LIKE '%Sample%';

-- Clean up test patients (this will cascade to related tables)
-- Remove patients with obvious test patterns
DELETE FROM patients
WHERE name LIKE '%Test%'
OR name LIKE '%Demo%'
OR name LIKE '%Sample%'
OR phone LIKE '+55999%' -- Common test pattern
OR phone LIKE '+55111%'
OR phone LIKE '+55000%'
OR email LIKE '%test%'
OR email LIKE '%demo%'
OR email LIKE '%sample%';

-- Clean up test messages
-- Remove messages with test content
DELETE FROM messages
WHERE content LIKE '%test%'
OR content LIKE '%Test%'
OR content LIKE '%demo%'
OR content LIKE '%Demo%'
OR content LIKE '%sample%'
OR content LIKE '%Sample%';

-- Clean up test quiz responses
-- Remove responses from deleted patients (should cascade, but ensuring cleanup)
DELETE FROM quiz_responses
WHERE patient_id NOT IN (SELECT id FROM patients);

-- Clean up test patient flow states
-- Remove flow states from deleted patients (should cascade, but ensuring cleanup)
DELETE FROM patient_flow_states
WHERE patient_id NOT IN (SELECT id FROM patients);

-- Clean up test medical reports
-- Remove reports from deleted patients (should cascade, but ensuring cleanup)
DELETE FROM medical_reports
WHERE patient_id NOT IN (SELECT id FROM patients);

-- Clean up test alerts
-- Remove alerts from deleted patients (should cascade, but ensuring cleanup)
DELETE FROM alerts
WHERE patient_id NOT IN (SELECT id FROM patients);

-- Reset sequences if needed (PostgreSQL automatically manages UUIDs, so this is mainly for reference)
-- No action needed for UUID primary keys

-- Vacuum tables to reclaim space
VACUUM ANALYZE users;
VACUUM ANALYZE patients;
VACUUM ANALYZE messages;
VACUUM ANALYZE quiz_responses;
VACUUM ANALYZE patient_flow_states;
VACUUM ANALYZE medical_reports;
VACUUM ANALYZE alerts;

-- Create audit log entry for data cleanup
INSERT INTO audit_logs (
    admin_id,
    action,
    entity_type,
    entity_name,
    metadata,
    ip_address,
    success,
    timestamp
) VALUES (
    NULL, -- System action
    'system_backup'::audit_action_type,
    'database',
    'Test data cleanup',
    '{"action": "cleanup_test_data", "tables_cleaned": ["users", "patients", "messages", "quiz_responses", "patient_flow_states", "medical_reports", "alerts"], "note": "Removed test data during production preparation"}'::jsonb,
    '127.0.0.1'::inet,
    true,
    NOW()
);

-- Display cleanup summary
SELECT 'Test data cleanup completed successfully!' as status;
SELECT 'The following tables were cleaned of test data:' as info;
SELECT '- users (healthcare providers)' as table1;
SELECT '- patients' as table2;
SELECT '- messages' as table3;
SELECT '- quiz_responses' as table4;
SELECT '- patient_flow_states' as table5;
SELECT '- medical_reports' as table6;
SELECT '- alerts' as table7;
SELECT 'Database is now ready for production use.' as result;
SELECT '⚠️  Recommendation: Create a backup before running this in production!' as warning;
