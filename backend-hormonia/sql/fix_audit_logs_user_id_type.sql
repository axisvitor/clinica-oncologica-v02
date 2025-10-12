-- Fix audit_logs.user_id column type from String to UUID
-- This addresses the SQLAlchemy type mismatch error

BEGIN;

-- Step 1: Add a temporary UUID column
ALTER TABLE audit_logs ADD COLUMN user_id_temp UUID;

-- Step 2: Copy data from string column to UUID column, converting the format
UPDATE audit_logs 
SET user_id_temp = user_id::uuid 
WHERE user_id IS NOT NULL AND user_id != '';

-- Step 3: Drop the old string column and its index
DROP INDEX IF EXISTS idx_audit_user_event_time;
ALTER TABLE audit_logs DROP COLUMN user_id;

-- Step 4: Rename the temp column to user_id
ALTER TABLE audit_logs RENAME COLUMN user_id_temp TO user_id;

-- Step 5: Recreate the index
CREATE INDEX idx_audit_user_event_time ON audit_logs (user_id, event_type, created_at);

-- Verify the change
\d audit_logs;

COMMIT;