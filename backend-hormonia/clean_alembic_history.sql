-- Clean Alembic Migration History
-- This script removes all migration records from the alembic_version table
-- so Alembic stops looking for removed migration files

-- Check current migration records
SELECT 'Current migration records:' as info;
SELECT version_num FROM alembic_version ORDER BY version_num;

-- Remove all migration records
DELETE FROM alembic_version;

-- Verify cleanup
SELECT 'Records after cleanup:' as info;
SELECT COUNT(*) as remaining_records FROM alembic_version;

-- Add metadata column if missing (safe to run multiple times)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'patients' 
        AND column_name = 'metadata'
    ) THEN
        ALTER TABLE patients ADD COLUMN metadata JSONB DEFAULT '{}'::jsonb;
        RAISE NOTICE 'metadata column added to patients table';
    ELSE
        RAISE NOTICE 'metadata column already exists in patients table';
    END IF;
END $$;

-- Test that metadata column is accessible
SELECT 'Testing metadata column access:' as info;
SELECT COUNT(*) as patient_count FROM patients;

COMMIT;