-- Check current unique constraints on patients table
SELECT 
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'patients';
