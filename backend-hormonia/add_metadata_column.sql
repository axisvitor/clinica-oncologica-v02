-- Direct SQL fix for metadata column issue
-- This script adds the metadata column to the patients table if it doesn't exist
-- Run this directly in the database to bypass Alembic migration issues

-- Check if metadata column exists and add it if missing
DO $$
BEGIN
    -- Check if the column exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'patients' 
        AND column_name = 'metadata'
    ) THEN
        -- Add the metadata column
        ALTER TABLE patients ADD COLUMN metadata JSONB DEFAULT '{}'::jsonb;
        RAISE NOTICE '✅ metadata column added to patients table';
    ELSE
        RAISE NOTICE '✅ metadata column already exists in patients table';
    END IF;
END $$;

-- Verify the column was added successfully
SELECT 
    column_name, 
    data_type, 
    is_nullable, 
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public' 
AND table_name = 'patients' 
AND column_name = 'metadata';

-- Test that we can query the column
SELECT 'metadata column is accessible' as status, COUNT(*) as patient_count 
FROM patients;

COMMIT;