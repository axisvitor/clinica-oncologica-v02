-- Migration: Add expiration support to QuizSession
-- HIGH-004: Add timeout and cleanup for abandoned quiz sessions
-- Date: 2025-11-14
-- Description: Adds 'expired' status and expiration_date field to quiz_sessions table

BEGIN;

-- Step 1: Add expiration_date column
ALTER TABLE quiz_sessions
ADD COLUMN IF NOT EXISTS expiration_date TIMESTAMP WITH TIME ZONE;

-- Step 2: Create index on expiration_date for efficient cleanup queries
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_expiration_date
ON quiz_sessions(expiration_date)
WHERE status = 'started';

-- Step 3: Update check constraint to include 'expired' status
ALTER TABLE quiz_sessions
DROP CONSTRAINT IF EXISTS ck_quiz_session_status_valid;

ALTER TABLE quiz_sessions
ADD CONSTRAINT ck_quiz_session_status_valid
CHECK (status IN ('started', 'completed', 'cancelled', 'expired'));

-- Step 4: Set expiration_date for existing started sessions (started_at + 48 hours)
UPDATE quiz_sessions
SET expiration_date = started_at + INTERVAL '48 hours'
WHERE status = 'started'
  AND expiration_date IS NULL;

-- Step 5: Create function to auto-set expiration_date on insert
CREATE OR REPLACE FUNCTION set_quiz_session_expiration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'started' AND NEW.expiration_date IS NULL THEN
        NEW.expiration_date := NEW.started_at + INTERVAL '48 hours';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Step 6: Create trigger to automatically set expiration_date
DROP TRIGGER IF EXISTS trg_set_quiz_session_expiration ON quiz_sessions;

CREATE TRIGGER trg_set_quiz_session_expiration
BEFORE INSERT OR UPDATE ON quiz_sessions
FOR EACH ROW
WHEN (NEW.status = 'started')
EXECUTE FUNCTION set_quiz_session_expiration();

-- Step 7: Add comment to document the new field
COMMENT ON COLUMN quiz_sessions.expiration_date IS 'Timestamp when the session expires (default: started_at + 48 hours). Sessions are automatically marked as expired by cleanup task.';

-- Step 8: Create composite index for cleanup queries
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_status_expiration
ON quiz_sessions(status, expiration_date)
WHERE status = 'started' AND expiration_date IS NOT NULL;

COMMIT;
